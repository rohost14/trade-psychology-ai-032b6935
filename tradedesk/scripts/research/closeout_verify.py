"""
Close-out verification for Patterns 1 and 2 against the corrected replay.

Two sources, deliberately:

  * the replay SIDECAR is the real alert stream - post consolidation, post
    dedup, post alert cap. It answers "what would the trader actually receive".
  * the OFFLINE HARNESS runs the real detector methods over positions rebuilt
    from raw fills, and carries full context. It answers "does every firing
    satisfy the definition", which the sidecar cannot because it stores no
    details.

Nothing here changes any detector.
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
SIDECAR = "D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26-replay.json"


def meta(sym):
    try:
        p = parse_symbol(sym or "")
        return (p.instrument_type or "EQ"), (p.underlying or sym or "")
    except Exception:
        return "EQ", sym or ""


def build(fills):
    st = defaultdict(lambda: {"qty": 0, "avg": 0.0, "opened": None,
                              "pnl": 0.0, "rows": []})
    out = []
    for f in fills:
        k = (f["date"], f["symbol"])
        p = st[k]
        s = f["qty"] if f["side"] == "BUY" else -f["qty"]
        px = float(f["price"])
        if p["qty"] == 0:
            p.update(qty=s, avg=px, opened=f["at"], pnl=0.0, rows=[])
            p["rows"].append(PositionFill("OPEN", s, px, s, px, f["at"]))
            continue
        if (p["qty"] > 0) == (s > 0):
            nq = p["qty"] + s
            p["avg"] = (p["avg"] * abs(p["qty"]) + px * abs(s)) / abs(nq)
            p["qty"] = nq
            p["rows"].append(PositionFill("INCREASE", s, px, nq, p["avg"], f["at"]))
            continue
        c = min(abs(s), abs(p["qty"]))
        d = 1 if p["qty"] > 0 else -1
        p["pnl"] += (px - p["avg"]) * c * d
        p["qty"] += s
        p["rows"].append(PositionFill("CLOSE" if p["qty"] == 0 else "DECREASE",
                                      s, px, p["qty"],
                                      p["avg"] if p["qty"] else None, f["at"]))
        if p["qty"] == 0:
            it, und = meta(f["symbol"])
            out.append(SimpleNamespace(
                id=uuid4(), broker_account_id=None, tradingsymbol=f["symbol"],
                exchange="NFO", product="MIS", instrument_type=it,
                direction="LONG" if d > 0 else "SHORT", total_quantity=abs(c),
                avg_entry_price=Decimal(str(round(p["avg"], 4))),
                avg_exit_price=Decimal(str(px)),
                realized_pnl=Decimal(str(round(p["pnl"], 2))),
                pnl_pct=None, duration_minutes=None,
                entry_time=p["opened"], exit_time=f["at"],
                num_entries=sum(1 for r in p["rows"]
                                if r.entry_type in ("OPEN", "INCREASE")),
                num_exits=1, closed_by_flip=False, status="closed",
                quality_score=None, _und=und, _fills=list(p["rows"])))
            p.update(qty=0, avg=0.0, opened=None, pnl=0.0, rows=[])
    return out


def main():
    # ── the real alert stream ─────────────────────────────────────────────
    print("=" * 74)
    print("THE REPLAY — what the trader would actually receive")
    print("=" * 74)
    try:
        side = json.load(open(SIDECAR))
    except Exception as e:
        print(f"  sidecar unreadable: {e}")
        side = None

    if side:
        c, days, sev = Counter(), defaultdict(set), Counter()
        per_symbol = defaultdict(list)
        for day, v in side["days"].items():
            for a in v.get("alerts", []):
                p = a["pattern_type"]
                c[p] += 1
                days[p].add(day)
                sev[(p, a["severity"])] += 1
        print(f"  sessions {side['sessions']}   skipped patterns "
              f"{side.get('skipped_patterns')}")
        print(f"\n{'pattern':<32}{'alerts':>8}{'days':>7}   severities")
        for p, n in c.most_common():
            s = {k[1]: v for k, v in sev.items() if k[0] == p}
            print(f"  {p:<30}{n:>8}{len(days[p]):>7}   {s}")

    # ── per-firing verification ───────────────────────────────────────────
    fills = read_fills("D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26.csv")
    fills.sort(key=lambda f: f["at"])
    byday = defaultdict(list)
    for f in fills:
        byday[f["date"]].append(f)

    mart, aap = [], []
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
                completed_trade=ct, session_trades=ts[:i], active_cooldowns=[],
                thresholds={}, position_fills=ct._fills)
            m = engine._detect_martingale_behaviour(ctx)
            if m is not None and getattr(m, "fired", False):
                mart.append({"day": str(day), **m.context, "sev": m.severity,
                             "pnl": float(ct.realized_pnl)})
            a = engine._detect_adding_to_adverse_position(ctx)
            if a is not None and getattr(a, "fired", False):
                aap.append({"day": str(day), "sym": ct.tradingsymbol,
                            **a.context, "sev": a.severity})

    print("\n" + "=" * 74)
    print("PATTERN 1 — does every firing satisfy the definition?")
    print("=" * 74)
    print(f"  firings {len(mart)} across {len({m['day'] for m in mart})} days")
    checks = {
        "risk actually increased":
            all(m["risk_after"] > m["risk_before"] for m in mart),
        "at least 2 trailing consecutive losses":
            all(m["consecutive_losses"] >= 2 for m in mart),
        "ratio at or above the caution multiple":
            all(m["risk_ratio"] >= 1.5 for m in mart),
        "danger only at or above 2.0x":
            all(m["risk_ratio"] >= 2.0 for m in mart if m["sev"] == "danger"),
        "caution strictly below 2.0x":
            all(m["risk_ratio"] < 2.0 for m in mart if m["sev"] == "caution"),
    }
    for k, v in checks.items():
        print(f"    {'PASS' if v else 'FAIL'}  {k}")
    print(f"  severity: {dict(Counter(m['sev'] for m in mart))}")
    r = sorted(m["risk_ratio"] for m in mart)
    if r:
        print(f"  ratio: min {r[0]:.2f}x  p50 {r[len(r)//2]:.2f}x  max {r[-1]:.2f}x")
        print(f"  in the caution band 1.5-2.0x: {sum(1 for x in r if x < 2)}")
    print(f"  fired on a winning current trade: "
          f"{sum(1 for m in mart if m['pnl'] > 0)} (reports the escalation, not the outcome)")
    print(f"  rotated to another underlying: "
          f"{sum(1 for m in mart if m.get('rotated_instrument'))} of {len(mart)}")

    print("\n" + "=" * 74)
    print("PATTERN 2 — does every firing satisfy the definition?")
    print("=" * 74)
    print(f"  firings {len(aap)} across {len({a['day'] for a in aap})} days")
    ok = {
        "every firing has at least one adverse add":
            all(a["adverse_add_count"] >= 1 for a in aap),
        "every adverse move is strictly positive":
            all(a["deepest_adverse_pct"] > 0 for a in aap),
        "critical only with 3+ adverse adds":
            all(a["adverse_add_count"] >= 3 for a in aap if a["sev"] == "critical"),
        "info only with a single add that did not double down":
            all(a["adverse_add_count"] == 1 and not a["at_least_doubled_down"]
                for a in aap if a["sev"] == "info"),
    }
    for k, v in ok.items():
        print(f"    {'PASS' if v else 'FAIL'}  {k}")
    print(f"  severity: {dict(Counter(a['sev'] for a in aap))}")
    ep = defaultdict(list)
    for a in aap:
        ep[(a["day"], a["sym"])].append(a)
    print(f"  distinct (day, symbol) episodes: {len(ep)}")
    print(f"  firings per episode: "
          f"{dict(sorted(Counter(len(v) for v in ep.values()).items()))}")
    esc = sum(1 for v in ep.values()
              if len({x['sev'] for x in v}) == len(v))
    print(f"  episodes whose repeats are all DISTINCT severities "
          f"(what dedup keeps): {esc} of {len(ep)}")

    json.dump({"martingale": mart, "adding": aap},
              open(r"C:\Users\being\.claude\jobs\33a73186/tmp/closeout.json", "w"),
              indent=1, default=str)


main()
