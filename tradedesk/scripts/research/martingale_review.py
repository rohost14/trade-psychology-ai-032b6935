"""
Pattern #1 martingale_behaviour — evidence.

Runs the REAL detector method against the replay's own per-trade data, offline.
No reimplementation of the logic: the engine's own code decides, so what comes
out is what production would produce. Session state is rebuilt the way
_load_context does it — for trade i in exit order, session_trades = trades[:i].
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

REPLAY = r"C:\Users\being\.claude\jobs\33a73186/tmp/replay_g4_baseline.json"
engine = BehaviorEngine()


class T(SimpleNamespace):
    pass


def build(day, rows):
    out = []
    for r in rows:
        try:
            p = parse_symbol(r["symbol"] or "")
            itype, und = p.instrument_type or "EQ", p.underlying or r["symbol"]
        except Exception:
            itype, und = "EQ", r["symbol"]
        t = T(
            id=uuid4(),
            broker_account_id=None,
            tradingsymbol=r["symbol"],
            exchange="NFO",
            product="MIS",
            instrument_type=itype,
            direction="LONG",
            total_quantity=int(r["qty"] or 0),
            avg_entry_price=Decimal(str(r["entry"] or 0)),
            avg_exit_price=Decimal(str(r["exit"] or 0)),
            realized_pnl=Decimal(str(r["pnl"] or 0)),
            pnl_pct=None,
            duration_minutes=None,
            entry_time=datetime.fromisoformat(r["entry_time"]) if r.get("entry_time") else None,
            exit_time=datetime.fromisoformat(r["exit_time"]) if r.get("exit_time") else None,
            num_entries=1, num_exits=1, closed_by_flip=False,
            status="closed", quality_score=None,
            _und=und,
        )
        out.append(t)
    return out


def main():
    d = json.load(open(REPLAY))
    fired, sessions_with_trades = [], 0
    total_trades = 0

    for day, v in sorted(d["days"].items()):
        rows = v.get("trades") or []
        if not rows:
            continue
        sessions_with_trades += 1
        trades = build(day, rows)
        trades = [t for t in trades if t.exit_time]
        trades.sort(key=lambda t: t.exit_time)
        total_trades += len(trades)

        for i, ct in enumerate(trades):
            ctx = EngineContext(
                broker_account_id=uuid4(),
                session=SimpleNamespace(session_pnl=Decimal("0"), session_date=day,
                                        market_open=None),
                completed_trade=ct,
                session_trades=trades[:i],
                active_cooldowns=[],
                thresholds={},          # inline defaults: 2 losses, 1.5x, 2.0x
            )
            ev = engine._detect_martingale_behaviour(ctx)
            if ev is None or not getattr(ev, "fired", False):
                continue
            c = ev.context
            fired.append({
                "day": day, "idx": i, "severity": ev.severity,
                "ratio": c["risk_ratio"],
                "risk_before": c["risk_before"], "risk_after": c["risk_after"],
                "losses": c["consecutive_losses"],
                "rotated": c["rotated_instrument"],
                "instrument": c["instrument_class"],
                "current_pnl": float(ct.realized_pnl),
                "message": ev.message,
            })

    print(f"sessions with trades: {sessions_with_trades}   round-trips: {total_trades}")
    print(f"martingale firings: {len(fired)}   "
          f"days: {len({f['day'] for f in fired})}")
    from collections import Counter
    print("severity:", dict(Counter(f["severity"] for f in fired)))
    json.dump(fired, open(r"C:\Users\being\.claude\jobs\33a73186/tmp/martingale_fired.json", "w"),
              indent=1)
    print("written martingale_fired.json")


main()
