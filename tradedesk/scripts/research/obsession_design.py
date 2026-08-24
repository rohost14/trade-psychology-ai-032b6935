"""
Pattern #3 design questions, answered from the real book.

The criterion for the severity rule is NOT which one alerts more. It is
STABILITY: an episode only ever grows, so a severity that can fall as trades are
added is telling the trader their situation improved when it did not. That is
measurable, it is not a matter of taste, and it is what the current rule fails.
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
from app.core.position_fills import PositionFill  # noqa: E402
from app.services.behavior_engine import BehaviorEngine, EngineContext  # noqa: E402
from app.services.instrument_parser import parse_symbol  # noqa: E402

engine = BehaviorEngine()


def meta(sym):
    try:
        p = parse_symbol(sym or "")
        return (p.instrument_type or "EQ"), (p.underlying or sym or "")
    except Exception:
        return "EQ", sym or ""


def build(fills):
    """Raw fills -> completed positions, each carrying its own fill sequence."""
    pos = defaultdict(lambda: {"qty": 0, "avg": 0.0, "opened": None,
                               "realized": 0.0, "rows": []})
    out = []
    for f in fills:
        key = (f["date"], f["symbol"])
        p = pos[key]
        signed = f["qty"] if f["side"] == "BUY" else -f["qty"]
        price = float(f["price"])
        if p["qty"] == 0:
            p.update(qty=signed, avg=price, opened=f["at"], realized=0.0, rows=[])
            p["rows"].append(PositionFill("OPEN", signed, price, signed, price, f["at"]))
            continue
        if (p["qty"] > 0) == (signed > 0):
            nq = p["qty"] + signed
            p["avg"] = (p["avg"] * abs(p["qty"]) + price * abs(signed)) / abs(nq)
            p["qty"] = nq
            p["rows"].append(PositionFill("INCREASE", signed, price, nq, p["avg"], f["at"]))
            continue
        closing = min(abs(signed), abs(p["qty"]))
        d = 1 if p["qty"] > 0 else -1
        p["realized"] += (price - p["avg"]) * closing * d
        p["qty"] += signed
        p["rows"].append(PositionFill(
            "CLOSE" if p["qty"] == 0 else "DECREASE",
            signed, price, p["qty"], p["avg"] if p["qty"] else None, f["at"]))
        if p["qty"] == 0:
            it, und = meta(f["symbol"])
            out.append(SimpleNamespace(
                id=uuid4(), broker_account_id=None, tradingsymbol=f["symbol"],
                exchange="NFO", product="MIS", instrument_type=it,
                direction="LONG" if d > 0 else "SHORT",
                total_quantity=abs(closing),
                avg_entry_price=Decimal(str(round(p["avg"], 4))),
                avg_exit_price=Decimal(str(price)),
                realized_pnl=Decimal(str(round(p["realized"], 2))),
                pnl_pct=None, duration_minutes=None,
                entry_time=p["opened"], exit_time=f["at"],
                num_entries=sum(1 for r in p["rows"] if r.entry_type in ("OPEN", "INCREASE")),
                num_exits=1, closed_by_flip=False, status="closed",
                quality_score=None, _und=und, _fills=list(p["rows"]),
            ))
            p.update(qty=0, avg=0.0, opened=None, realized=0.0, rows=[])
    return out


# ── severity candidates, each a function of the quantity sequence ────────

CANDIDATES = {
    "A last>first  (current)": lambda q: q[-1] > q[0],
    "B peak>first":            lambda q: max(q) > q[0],
    "C any step-up":           lambda q: any(b > a for a, b in zip(q, q[1:])),
    "D peak>=2x first":        lambda q: max(q) >= 2 * q[0],
}


def main():
    fills = read_fills("D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26.csv")
    fills.sort(key=lambda f: f["at"])
    byday = defaultdict(list)
    for f in fills:
        byday[f["date"]].append(f)

    episodes = defaultdict(list)   # (day, und) -> list of severity snapshots
    firings = []
    other = Counter()
    covered = defaultdict(set)

    for day in sorted(byday):
        ts = build(byday[day])
        if not ts:
            continue
        ts.sort(key=lambda t: t.exit_time)
        for i, ct in enumerate(ts):
            ctx = EngineContext(
                broker_account_id=uuid4(),
                session=SimpleNamespace(session_pnl=Decimal("0"),
                                        session_date=day, market_open=None),
                completed_trade=ct, session_trades=ts[:i],
                active_cooldowns=[], thresholds={},
                position_fills=ct._fills,
            )
            ev = engine._detect_same_symbol_obsession(ctx)
            if not ev:
                continue
            same = [t for t in ts[:i] if t._und == ct._und] + [ct]
            q = [t.total_quantity for t in same]
            key = (str(day), ct._und)
            episodes[key].append({c: f(q) for c, f in CANDIDATES.items()})
            firings.append({"key": key, "qtys": q, "losses": ev.context["losses"],
                            "attempts": ev.context["attempts"]})
            for name in ("martingale_behaviour", "adding_to_adverse_position",
                         "revenge_trade", "rapid_reentry"):
                r = getattr(engine, f"_detect_{name}")(ctx)
                fired = getattr(r, "fired", None)
                if fired is True or (fired is None and r is not None):
                    other[name] += 1
                    covered[name].add(key)

    print(f"firings {len(firings)}   episodes {len(episodes)}\n")

    print("=== 1. SEVERITY: does the rule ever FALL as the episode grows? ===")
    print("    An episode only grows. A severity that can fall tells the trader")
    print("    their situation improved when it did not.\n")
    print(f"{'candidate':<26}{'danger%':>9}{'episodes':>10}{'UNSTABLE':>10}  examples")
    for name, fn in CANDIDATES.items():
        unstable, ex = 0, []
        for key, snaps in episodes.items():
            seq = [s[name] for s in snaps]
            if any(not b and a for a, b in zip(seq, seq[1:])):
                unstable += 1
                if len(ex) < 2:
                    ex.append(f"{key[1]}")
        total = sum(len(v) for v in episodes.values())
        hits = sum(1 for v in episodes.values() for s in v if s[name])
        print(f"{name:<26}{100*hits/total:>8.0f}%{len(episodes):>10}{unstable:>10}  {', '.join(ex)}")

    print("\n=== 2. min_reentries ===")
    print("  minimum attempts across every firing:", min(f["attempts"] for f in firings))
    print("  firings where reentries < 2:", sum(1 for f in firings if f["attempts"] - 1 < 2))

    print("\n=== 3. episode shape ===")
    sizes = Counter(len(v) for v in episodes.values())
    print("  firings per (session, underlying) episode:", dict(sorted(sizes.items())))
    print(f"  total firings {len(firings)} for {len(episodes)} episodes "
          f"= {len(firings)/len(episodes):.1f}x repetition")

    print("\n=== 5. OVERLAP: what does Pattern 3 uniquely contribute? ===")
    for k, v in other.most_common():
        print(f"  {k:<28} co-fires on {v:>3} of {len(firings)} firings, "
              f"{len(covered[k]):>2} of {len(episodes)} episodes")
    union = set().union(*covered.values()) if covered else set()
    print(f"\n  episodes where NO other detector fires at all: "
          f"{len(set(episodes) - union)} of {len(episodes)}")
    for key in sorted(set(episodes) - union):
        f = next(x for x in firings if x["key"] == key)
        print(f"     {key[0]} {key[1]:<11} qtys={f['qtys']} losses={f['losses']}")

    json.dump({"episodes": {f"{k[0]}|{k[1]}": v for k, v in episodes.items()},
               "firings": firings},
              open(r"C:\Users\being\.claude\jobs\33a73186/tmp/obsession_design.json", "w"),
              indent=1, default=str)


main()
