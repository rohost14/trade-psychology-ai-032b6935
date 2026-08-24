"""
Two challenges to the proposed contract, answered from the book.

1. Is `peak > first` MEANINGFUL, or only stable? Stability is necessary and not
   sufficient: a rule that is stable but almost always true carries no
   information. The test is whether the two groups it creates are materially
   different episodes.

2. Is the 3/4 loss boundary justified, or is 4 just "one more than 3"? The test
   is whether the loss distribution has anything at 4 - a gap, a mode, a change
   in what the episodes look like. If it does not, the boundary is a choice
   dressed up as a fact and should go.
"""
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tradedesk.scripts.replay_tradebook import read_fills  # noqa: E402
from app.core.instrument_risk import risk_basis  # noqa: E402
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
    pos = defaultdict(lambda: {"qty": 0, "avg": 0.0, "opened": None, "realized": 0.0})
    out = []
    for f in fills:
        key = (f["date"], f["symbol"])
        p = pos[key]
        signed = f["qty"] if f["side"] == "BUY" else -f["qty"]
        price = float(f["price"])
        if p["qty"] == 0:
            p.update(qty=signed, avg=price, opened=f["at"], realized=0.0)
            continue
        if (p["qty"] > 0) == (signed > 0):
            nq = p["qty"] + signed
            p["avg"] = (p["avg"] * abs(p["qty"]) + price * abs(signed)) / abs(nq)
            p["qty"] = nq
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
                total_quantity=abs(closing),
                avg_entry_price=Decimal(str(round(p["avg"], 4))),
                avg_exit_price=Decimal(str(price)),
                realized_pnl=Decimal(str(round(p["realized"], 2))),
                pnl_pct=None, duration_minutes=None,
                entry_time=p["opened"], exit_time=f["at"],
                num_entries=1, num_exits=1, closed_by_flip=False,
                status="closed", quality_score=None, _und=und))
            p.update(qty=0, avg=0.0, opened=None, realized=0.0)
    return out


def risk_of(t):
    return risk_basis(t.instrument_type, t.tradingsymbol, t.direction,
                      float(t.avg_entry_price), int(t.total_quantity)).amount


def main():
    fills = read_fills("D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26.csv")
    fills.sort(key=lambda f: f["at"])
    byday = defaultdict(list)
    for f in fills:
        byday[f["date"]].append(f)

    episodes = {}
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
                active_cooldowns=[], thresholds={})
            ev = engine._detect_same_symbol_obsession(ctx)
            if not ev:
                continue
            same = [t for t in ts[:i] if t._und == ct._und] + [ct]
            key = (str(day), ct._und)
            episodes[key] = {          # last write wins = the episode's final state
                "qtys": [t.total_quantity for t in same],
                "risks": [risk_of(t) for t in same],
                "losses": ev.context["losses"],
                "attempts": ev.context["attempts"],
                "total_loss": ev.context["total_loss"],
            }

    eps = list(episodes.values())
    print(f"{len(eps)} episodes\n")

    # ── Q1 ────────────────────────────────────────────────────────────────
    print("=" * 72)
    print("Q1  Is `peak > first` meaningful, or only stable?")
    print("=" * 72)
    rose = [e for e in eps if max(e["qtys"]) > e["qtys"][0]]
    flat = [e for e in eps if max(e["qtys"]) <= e["qtys"][0]]
    print(f"  rose {len(rose)}   flat {len(flat)}")
    print("\n  HOW MUCH bigger did it get? peak / first, for the 'rose' group:")
    ratios = sorted(max(e["qtys"]) / e["qtys"][0] for e in rose)
    for r in ratios:
        print(f"     {r:.2f}x")
    print(f"\n  A rule is noise if the rises are marginal. Here: "
          f"min {ratios[0]:.2f}x  median {ratios[len(ratios)//2]:.2f}x  max {ratios[-1]:.2f}x")
    print(f"  rises of at least 2x: {sum(1 for r in ratios if r >= 2)} of {len(ratios)}")
    print(f"  rises under 1.5x    : {sum(1 for r in ratios if r < 1.5)} of {len(ratios)}")

    def med(xs):
        xs = sorted(xs)
        return xs[len(xs) // 2] if xs else 0

    print("\n  Do the two groups differ in anything a trader would feel?")
    print(f"{'':<22}{'rose':>12}{'flat':>12}")
    for label, fn in (
        ("attempts", lambda e: e["attempts"]),
        ("losses", lambda e: e["losses"]),
        ("total loss (Rs)", lambda e: e["total_loss"]),
        ("peak capital at risk", lambda e: max(e["risks"])),
        ("capital at risk, first", lambda e: e["risks"][0]),
    ):
        print(f"  {label:<20}{med([fn(e) for e in rose]):>12,.0f}"
              f"{med([fn(e) for e in flat]):>12,.0f}")

    print("\n  peak RISK / first RISK (exposure, not lots):")
    rr = sorted(max(e["risks"]) / e["risks"][0] for e in rose if e["risks"][0])
    fr = sorted(max(e["risks"]) / e["risks"][0] for e in flat if e["risks"][0])
    print(f"     rose: median {med(rr):.2f}x   flat: median {med(fr):.2f}x")

    # ── Q2 ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("Q2  Is the 3/4 loss boundary justified by anything?")
    print("=" * 72)
    dist = Counter(e["losses"] for e in eps)
    print("  loss count per episode:", dict(sorted(dist.items())))
    print("\n  Is there a gap, a mode, or a change in what the episodes look like at 4?")
    print(f"{'losses':>8}{'episodes':>10}{'median loss':>14}{'median peak risk':>18}")
    for n in sorted(dist):
        g = [e for e in eps if e["losses"] == n]
        print(f"{n:>8}{len(g):>10}{med([e['total_loss'] for e in g]):>14,.0f}"
              f"{med([max(e['risks']) for e in g]):>18,.0f}")
    print("\n  Where would each candidate boundary split the 20 episodes?")
    for b in (4, 5):
        hi = sum(1 for e in eps if e["losses"] >= b)
        print(f"     >= {b} losses: {hi} danger / {len(eps)-hi} caution")


main()
