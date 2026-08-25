"""
Pattern #4 consecutive_loss_streak — evidence.

Positions rebuilt from raw fills with carry-forward handled, so this uses the
corrected 912-position trade set rather than the contaminated 742. The REAL
detector method decides every case.

The central question is not "does it fire" - it fires more than anything else in
the engine. It is whether a run of losses carries any information beyond what a
41.4% win rate produces on its own.
"""
import json
import random
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tradedesk.scripts.replay_tradebook import read_fills, carry_fills  # noqa: E402
from app.services.behavior_engine import BehaviorEngine, EngineContext  # noqa: E402
from app.services.instrument_parser import parse_symbol  # noqa: E402

engine = BehaviorEngine()
random.seed(11)


def meta(sym):
    try:
        p = parse_symbol(sym or "")
        return (p.instrument_type or "EQ"), (p.underlying or sym or "")
    except Exception:
        return "EQ", sym or ""


def build(day_fills, carry):
    """Positions for one session, with any carried position opened first."""
    st = defaultdict(lambda: {"qty": 0, "avg": 0.0, "opened": None, "pnl": 0.0})
    out = []
    for f in list(carry) + list(day_fills):
        sym = f["symbol"]
        p = st[sym]
        s = f["qty"] if f["side"] == "BUY" else -f["qty"]
        px = float(f["price"])
        if p["qty"] == 0:
            p.update(qty=s, avg=px, opened=f["at"], pnl=0.0)
            continue
        if (p["qty"] > 0) == (s > 0):
            nq = p["qty"] + s
            p["avg"] = (p["avg"] * abs(p["qty"]) + px * abs(s)) / abs(nq)
            p["qty"] = nq
            continue
        c = min(abs(s), abs(p["qty"]))
        d = 1 if p["qty"] > 0 else -1
        p["pnl"] += (px - p["avg"]) * c * d
        p["qty"] += s
        if p["qty"] == 0:
            it, und = meta(sym)
            out.append(SimpleNamespace(
                id=uuid4(), broker_account_id=None, tradingsymbol=sym,
                exchange="NFO", product="MIS", instrument_type=it,
                direction="LONG" if d > 0 else "SHORT", total_quantity=abs(c),
                avg_entry_price=Decimal(str(round(p["avg"], 4))),
                avg_exit_price=Decimal(str(px)),
                realized_pnl=Decimal(str(round(p["pnl"], 2))),
                pnl_pct=None, duration_minutes=None,
                entry_time=p["opened"], exit_time=f["at"],
                num_entries=1, num_exits=1, closed_by_flip=False,
                status="closed", quality_score=None, _und=und))
            p.update(qty=0, avg=0.0, opened=None, pnl=0.0)
    return [t for t in out if t.exit_time and t.exit_time.date() == day_fills[0]["date"]]


def runs_of(seq):
    out, c = [], 0
    for won in seq:
        if not won:
            c += 1
        else:
            if c:
                out.append(c)
            c = 0
    if c:
        out.append(c)
    return out


def main():
    fills = read_fills("D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26.csv")
    fills.sort(key=lambda f: f["at"])
    byday = defaultdict(list)
    for f in fills:
        byday[f["date"]].append(f)

    sessions = []
    fired, overlaps = [], Counter()
    for day in sorted(byday):
        ts = build(byday[day], carry_fills(fills, day))
        if not ts:
            continue
        ts.sort(key=lambda t: t.exit_time)
        sessions.append([float(t.realized_pnl) > 0 for t in ts])
        for i, ct in enumerate(ts):
            ctx = EngineContext(
                broker_account_id=uuid4(),
                session=SimpleNamespace(session_pnl=Decimal("0"),
                                        session_date=day, market_open=None),
                completed_trade=ct, session_trades=ts[:i],
                active_cooldowns=[], thresholds={})
            ev = engine._detect_consecutive_loss_streak(ctx)
            if not ev:
                continue
            fired.append({"day": str(day), "sev": ev.severity, **ev.context,
                          "n_trades": len(ts)})
            for name in ("martingale_behaviour", "same_symbol_obsession",
                         "revenge_trade", "profit_giveaway"):
                r = getattr(engine, f"_detect_{name}")(ctx)
                if r is not None and getattr(r, "fired", True):
                    overlaps[name] += 1

    trades = sum(len(s) for s in sessions)
    wins = sum(sum(s) for s in sessions)
    wr = wins / trades
    print(f"sessions {len(sessions)}   positions {trades}   win rate {wr:.3f}")
    print(f"\nfirings {len(fired)} across {len({f['day'] for f in fired})} days")
    print("severity:", dict(Counter(f["sev"] for f in fired)))
    print("streak at firing:", dict(sorted(Counter(f["streak"] for f in fired).items())))
    print("escalated by loss size:",
          sum(1 for f in fired if f.get("escalated_by") == "loss_size"),
          "(needs a declared daily_loss_limit; absent under --no-rules)")

    # ── the question that matters ────────────────────────────────────────
    print("\n" + "=" * 70)
    print("Do loss runs carry information beyond a coin at this win rate?")
    print("=" * 70)
    obs = Counter()
    for s in sessions:
        for r in runs_of(s):
            obs[r] += 1
    sim = Counter()
    T = 2000
    for _ in range(T):
        for s in sessions:
            seq = [random.random() < wr for _ in s]
            for r in runs_of(seq):
                sim[r] += 1
    print(f"{'run':>5}{'observed':>10}{'chance':>10}{'diff':>9}")
    for k in sorted(set(obs) | set(sim)):
        e = sim[k] / T
        if obs[k] == 0 and e < 0.4:
            continue
        print(f"{k:>5}{obs[k]:>10}{e:>10.1f}{obs[k]-e:>+9.1f}")

    # how many sessions contain a 3+ run, observed vs chance
    o3 = sum(1 for s in sessions if any(r >= 3 for r in runs_of(s)))
    s3 = 0
    for _ in range(T):
        for s in sessions:
            if any(r >= 3 for r in runs_of([random.random() < wr for _ in s])):
                s3 += 1
    print(f"\nsessions containing a 3+ loss run: observed {o3}, "
          f"chance {s3/T:.1f} of {len(sessions)}")

    # ── would the loss-size escalation add anything? ─────────────────────
    print("\n" + "=" * 70)
    print("The loss-size escalation branch (total_loss >= 50% of daily limit)")
    print("=" * 70)
    losses = sorted(f["total_loss"] for f in fired)
    print(f"  total loss at firing: p25 {losses[len(losses)//4]:,.0f}  "
          f"p50 {losses[len(losses)//2]:,.0f}  "
          f"p75 {losses[3*len(losses)//4]:,.0f}  max {losses[-1]:,.0f}")
    for cap in (25_000, 10_000, 5_000, 2_500):
        n = sum(1 for f in fired
                if f["streak"] < 5 and f["total_loss"] >= cap * 0.5)
        print(f"  if the trader declared a Rs {cap:,} daily limit: "
              f"{n} of {len(fired)} firings would escalate to danger on loss size")

    print("\n" + "=" * 70)
    print("Overlap on the same trade")
    print("=" * 70)
    for k, v in overlaps.most_common():
        print(f"  {k:<28} {v:>3} of {len(fired)}  ({100*v/len(fired):.0f}%)")

    json.dump(fired, open(r"C:\Users\being\.claude\jobs\33a73186/tmp/streak_fired.json", "w"),
              indent=1, default=str)


main()
