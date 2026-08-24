"""
False negatives and overlap for martingale_behaviour.

FN definition used here is the detector's OWN stated intent, taken from its
docstring and message: "I lost, so I'll go bigger" - a position materially
larger than the one before it, entered after consecutive losses. No new
threshold is invented: the same 1.5x/2.0x multipliers the detector already
uses are applied to the step the trader actually took (previous -> current)
instead of to a step between two earlier trades.
"""
import json
import sys
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

sys.path.insert(0, "backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.services.behavior_engine import BehaviorEngine, EngineContext  # noqa: E402
from app.services.instrument_parser import parse_symbol  # noqa: E402

engine = BehaviorEngine()
REPLAY = r"C:\Users\being\.claude\jobs\33a73186/tmp/replay_g4_baseline.json"


def und(sym):
    try:
        return parse_symbol(sym or "").underlying or sym or ""
    except Exception:
        return sym or ""


def build(rows):
    out = []
    for r in rows:
        if not r.get("exit_time"):
            continue
        try:
            itype = parse_symbol(r["symbol"] or "").instrument_type or "EQ"
        except Exception:
            itype = "EQ"
        out.append(SimpleNamespace(
            id=uuid4(), broker_account_id=None, tradingsymbol=r["symbol"],
            exchange="NFO", product="MIS", instrument_type=itype, direction="LONG",
            total_quantity=int(r["qty"] or 0),
            avg_entry_price=Decimal(str(r["entry"] or 0)),
            avg_exit_price=Decimal(str(r["exit"] or 0)),
            realized_pnl=Decimal(str(r["pnl"] or 0)),
            pnl_pct=None, duration_minutes=None,
            entry_time=datetime.fromisoformat(r["entry_time"]) if r.get("entry_time") else None,
            exit_time=datetime.fromisoformat(r["exit_time"]),
            num_entries=1, num_exits=1, closed_by_flip=False,
            status="closed", quality_score=None,
        ))
    out.sort(key=lambda t: t.exit_time)
    return out


def notional(t):
    return float(abs(t.total_quantity or 0)) * float(t.avg_entry_price or 0)


d = json.load(open(REPLAY))
fired_keys, fn, overlap = set(), [], {"post_loss_recovery_bet": 0,
                                      "size_escalation": 0,
                                      "same_symbol_obsession": 0}
n_fired = 0

for day, v in sorted(d["days"].items()):
    trades = build(v.get("trades") or [])
    if not trades:
        continue
    for i, ct in enumerate(trades):
        ctx = EngineContext(
            broker_account_id=uuid4(),
            session=SimpleNamespace(session_pnl=Decimal("0"), session_date=day,
                                    market_open=None),
            completed_trade=ct, session_trades=trades[:i],
            active_cooldowns=[], thresholds={},
        )
        mart = engine._detect_martingale_behaviour(ctx)
        if mart:
            n_fired += 1
            fired_keys.add((day, i))
            for name in overlap:
                other = getattr(engine, f"_detect_{name}")(ctx)
                if other:
                    overlap[name] += 1

        # --- would the detector's own stated intent have fired here? ---
        if i < 2:
            continue
        prev = trades[i - 1]
        prior2 = trades[i - 2]
        both_lost = (float(prev.realized_pnl) < 0 and float(prior2.realized_pnl) < 0)
        if not both_lost:
            continue
        same_und = und(ct.tradingsymbol) == und(prev.tradingsymbol)
        a = (prev.total_quantity or 1) if same_und else max(notional(prev), 1.0)
        b = (ct.total_quantity or 1) if same_und else max(notional(ct), 1.0)
        step = b / a
        if step >= 1.5 and not mart:
            fn.append({
                "day": day, "idx": i, "underlying": und(ct.tradingsymbol),
                "units": "lots" if same_und else "rupees",
                "prev": round(a), "current": round(b), "step": round(step, 2),
                "prior_pnls": [round(float(prior2.realized_pnl)),
                               round(float(prev.realized_pnl))],
                "current_pnl": round(float(ct.realized_pnl)),
            })

print(f"martingale firings: {n_fired}")
print(f"\nMISSED by the current implementation but matching its own stated intent")
print(f"(two consecutive losses, then a step-up of >=1.5x on the trade itself): {len(fn)}")
big = [f for f in fn if f["step"] >= 2.0]
print(f"  of which >=2.0x (the danger multiple): {len(big)}")
print(f"  distinct days: {len({f['day'] for f in fn})}")
for f in sorted(fn, key=lambda x: -x["step"])[:10]:
    print(f"   {f['day']} {f['underlying']:<11} {f['units']:<6} "
          f"{f['prev']}->{f['current']} = {f['step']}x  "
          f"after {f['prior_pnls']}  this trade {f['current_pnl']:+}")

print("\nOVERLAP — other detectors firing on the SAME trade as martingale:")
for k, n in overlap.items():
    print(f"  {k:<26} {n:>3} of {n_fired}  ({100*n/max(n_fired,1):.0f}%)")

json.dump(fn, open(r"C:\Users\being\.claude\jobs\33a73186/tmp/martingale_fn.json", "w"), indent=1)
