"""
same_symbol_obsession, measured against the real book.

Positions are rebuilt from raw fills (open -> flat), so a position carried
overnight keeps its real entry - the replay JSON on disk predates that fix and
misreads 9.2% of fills. The REAL detector method decides; nothing is
reimplemented.
"""
import json
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tradedesk.scripts.replay_tradebook import read_fills  # noqa: E402
from app.services.behavior_engine import BehaviorEngine, EngineContext  # noqa: E402
from app.services.instrument_parser import parse_symbol  # noqa: E402

engine = BehaviorEngine()


def meta(sym):
    try:
        p = parse_symbol(sym or "")
        return (p.instrument_type or "EQ"), (p.underlying or sym or "")
    except Exception:
        return "EQ", sym or ""


def build_positions(fills):
    """Raw fills -> completed positions, one per open->flat cycle."""
    pos = defaultdict(lambda: {"qty": 0, "avg": 0.0, "opened": None,
                               "realized": 0.0, "legs": 0})
    out = []
    for f in fills:
        key = (f["date"], f["symbol"])
        p = pos[key]
        signed = f["qty"] if f["side"] == "BUY" else -f["qty"]
        price = float(f["price"])
        if p["qty"] == 0:
            p.update(qty=signed, avg=price, opened=f["at"], realized=0.0, legs=1)
            continue
        if (p["qty"] > 0) == (signed > 0):
            nq = p["qty"] + signed
            p["avg"] = (p["avg"] * abs(p["qty"]) + price * abs(signed)) / abs(nq)
            p["qty"] = nq
            p["legs"] += 1
            continue
        closing = min(abs(signed), abs(p["qty"]))
        d = 1 if p["qty"] > 0 else -1
        p["realized"] += (price - p["avg"]) * closing * d
        p["qty"] += signed
        if p["qty"] == 0:
            it, und = meta(f["symbol"])
            out.append(SimpleNamespace(
                id=uuid4(), broker_account_id=None, tradingsymbol=f["symbol"],
                exchange="NFO", product="MIS", instrument_type=it,
                direction="LONG" if d > 0 else "SHORT",
                total_quantity=abs(int(p["avg"] and closing or closing)),
                avg_entry_price=Decimal(str(round(p["avg"], 4))),
                avg_exit_price=Decimal(str(price)),
                realized_pnl=Decimal(str(round(p["realized"], 2))),
                pnl_pct=None, duration_minutes=None,
                entry_time=p["opened"], exit_time=f["at"],
                num_entries=p["legs"], num_exits=1, closed_by_flip=False,
                status="closed", quality_score=None, _und=und,
                _peak_qty=abs(closing),
            ))
            p.update(qty=0, avg=0.0, opened=None, realized=0.0, legs=0)
    return out


def main():
    fills = read_fills("D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26.csv")
    fills.sort(key=lambda f: f["at"])
    byday = defaultdict(list)
    for f in fills:
        byday[f["date"]].append(f)

    fired, overlaps = [], Counter()
    sessions = trades = 0
    for day in sorted(byday):
        ts = build_positions(byday[day])
        if not ts:
            continue
        ts.sort(key=lambda t: t.exit_time)
        sessions += 1
        trades += len(ts)
        for i, ct in enumerate(ts):
            ctx = EngineContext(
                broker_account_id=uuid4(),
                session=SimpleNamespace(session_pnl=Decimal("0"),
                                        session_date=day, market_open=None),
                completed_trade=ct, session_trades=ts[:i],
                active_cooldowns=[], thresholds={},
            )
            ev = engine._detect_same_symbol_obsession(ctx)
            if not ev:
                continue
            c = ev.context
            same = [t for t in ts[:i] if t._und == ct._und] + [ct]
            qtys = [t.total_quantity for t in same]
            # do the attempts actually follow one another, or overlap?
            concurrent = sum(1 for a, b in zip(same, same[1:])
                             if a.exit_time and b.entry_time and b.entry_time < a.exit_time)
            fired.append({
                "day": str(day), "underlying": c["underlying"],
                "severity": ev.severity, "attempts": c["attempts"],
                "losses": c["losses"], "total_loss": c["total_loss"],
                "size_rising": c["size_rising"],
                "qtys": qtys,
                "max_qty": max(qtys), "first": qtys[0], "last": qtys[-1],
                "current_pnl": float(ct.realized_pnl),
                "concurrent_pairs": concurrent,
                "distinct_symbols": len({t.tradingsymbol for t in same}),
            })
            for name in ("martingale_behaviour", "adding_to_adverse_position",
                         "revenge_trade", "rapid_reentry", "size_escalation"):
                try:
                    r = getattr(engine, f"_detect_{name}")(ctx)
                except Exception:
                    r = None
                if r is not None and (getattr(r, "fired", None) is True
                                      or getattr(r, "severity", None) not in (None,)):
                    if getattr(r, "fired", True):
                        overlaps[name] += 1

    print(f"sessions {sessions}  positions {trades}")
    print(f"same_symbol_obsession firings: {len(fired)} across "
          f"{len({f['day'] for f in fired})} days")
    print("severity:", dict(Counter(f["severity"] for f in fired)))
    print()
    print("=== the severity switch: last qty > first qty ===")
    print("  size_rising True :", sum(1 for f in fired if f["size_rising"]))
    print("  size_rising False:", sum(1 for f in fired if not f["size_rising"]))
    mid = [f for f in fired if not f["size_rising"] and f["max_qty"] > f["first"]]
    print(f"  size PEAKED in the middle but ended <= the first, so scored caution: {len(mid)}")
    for f in mid[:5]:
        print(f"     {f['day']} {f['underlying']:<11} qtys={f['qtys']} -> {f['severity']}")
    print()
    print("=== is min_reentries reachable? ===")
    print("  firings where reentries < 3:", sum(1 for f in fired if f["attempts"] - 1 < 3))
    print("  minimum attempts seen:", min(f["attempts"] for f in fired))
    print()
    print("=== are the attempts sequential, or concurrent positions? ===")
    print("  firings containing at least one OVERLAPPING pair:",
          sum(1 for f in fired if f["concurrent_pairs"]))
    print("  total overlapping pairs:", sum(f["concurrent_pairs"] for f in fired))
    print()
    print("=== does the CURRENT trade have to be a loss? ===")
    print("  fired on a winning current trade:",
          sum(1 for f in fired if f["current_pnl"] > 0))
    print()
    print("=== same underlying, but how many distinct STRIKES? ===")
    print(" ", dict(Counter(f["distinct_symbols"] for f in fired)))
    print()
    print("=== overlap with other detectors on the same trade ===")
    for k, v in overlaps.most_common():
        print(f"  {k:<28} {v:>3} of {len(fired)}  ({100*v/max(len(fired),1):.0f}%)")
    print()
    print("=== biggest by loss ===")
    for f in sorted(fired, key=lambda x: -x["total_loss"])[:8]:
        print(f"  {f['day']} {f['underlying']:<11} [{f['severity']:<7}] "
              f"{f['losses']}/{f['attempts']} attempts  Rs {f['total_loss']:>8,.0f}  qtys={f['qtys']}")

    json.dump(fired, open(r"C:\Users\being\.claude\jobs\33a73186/tmp/obsession_fired.json", "w"), indent=1)


main()
