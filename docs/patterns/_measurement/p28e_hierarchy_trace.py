# -*- coding: utf-8 -*-
"""A-L: what fires TODAY, from live code. No changes made."""
import sys
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.core.threshold_resolution import resolve_thresholds
from app.services.behavior_engine import BehaviorEngine
from app.services.live_risk_state import build_watches
from app.core.risk_quantities import quantities_for_trade

E = BehaviorEngine()
CAP = 100_000.0


class Prof:
    trading_capital = CAP
    detected_patterns = None
    def __init__(self, mps=None):
        self.max_position_size = mps
    def __getattr__(self, n):
        return None


def ct_for(symbol, qty, entry, exit_px=None, direction="LONG", itype="CE"):
    e = Decimal(str(entry))
    x = Decimal(str(exit_px if exit_px is not None else entry))
    pnl = (x - e) * qty * (1 if direction == "LONG" else -1)
    pnl_pct = float((x - e) / e * 100) * (1 if direction == "LONG" else -1)
    return SimpleNamespace(
        id=uuid4(), broker_account_id=None, tradingsymbol=symbol,
        exchange="NFO", product="MIS", instrument_type=itype,
        direction=direction, total_quantity=abs(qty),
        avg_entry_price=e, avg_exit_price=x,
        realized_pnl=pnl, pnl_pct=pnl_pct, duration_minutes=30,
        entry_time=datetime(2026, 2, 2, 4, 0, tzinfo=timezone.utc),
        exit_time=datetime(2026, 2, 2, 5, 0, tzinfo=timezone.utc),
        num_entries=1, num_exits=1, status="closed", underlying=symbol[:5],
    )


def ctx_for(ct, th):
    return SimpleNamespace(completed_trade=ct, thresholds=th, broker_margin=None,
                           session=SimpleNamespace(session_pnl=0), strategy_group=None)


def exposure_of(ct):
    rq = quantities_for_trade(ct, margin=None)
    if not rq.usable_for_capital_rules:
        return None, rq.capital_requirement.note
    return float(rq.capital_requirement.amount), None


def run(label, declared, symbol, qty, entry, exit_px=None,
        direction="LONG", itype="CE"):
    th = resolve_thresholds(Prof(declared))
    ct = ct_for(symbol, qty, entry, exit_px, direction, itype)
    cap_req, why = exposure_of(ct)
    pct = (cap_req / CAP * 100) if cap_req else None

    print(f"\n{'='*74}\n{label}\n{'='*74}")
    print(f"  declared max_position_size : {declared}")
    print(f"  position                   : {symbol} qty {qty} @ {entry}"
          + (f" -> {exit_px}" if exit_px is not None else ""))
    if cap_req is None:
        print(f"  capital_requirement        : UNAVAILABLE - {why[:70]}")
    else:
        print(f"  capital_requirement        : Rs {cap_req:,.0f}  = {pct:.1f}% of capital")
    print(f"  resolved caution/danger    : {th.get('max_position_pct_caution')}"
          f" / {th.get('max_position_pct_danger')}")

    fired = []
    ev = E._detect_excess_exposure(ctx_for(ct, th))
    if ev:
        fired.append(("excess_exposure", ev.severity, ev.message[:78]))

    # constitution max_trade_risk, isolated arithmetic from the live rule
    lim = th.get("max_position_size")
    if lim and cap_req is not None:
        ratio = (cap_req / CAP * 100) / float(lim)
        from app.services.behavior_engine import BehaviorEngine as _B
        sev = None
        if ratio >= 1.20: sev = "critical"
        elif ratio >= 1.00: sev = "danger"
        elif ratio >= 0.80: sev = "caution"
        if sev:
            fired.append(("constitution_violation:max_trade_risk", sev,
                          f"ratio {ratio:.2f} of your {lim}% limit"))

    # overexposure, as it is TODAY (notional, max_size or 10.0)
    from app.tasks.position_monitor_tasks import _exposure_value
    notional, ok = _exposure_value(symbol, "NFO", float(entry), qty)
    if ok:
        ms = float(lim) if lim else 10.0
        npct = notional / CAP * 100
        if npct > ms * 1.5:
            s = ("critical" if npct >= 30 else
                 "danger" if npct > ms * 2 else "caution")
            fired.append(("overexposure (TODAY, notional)", s,
                          f"Rs {notional:,.0f} = {npct:.1f}% vs limit {ms:.0f}%"))

    # live severe-loss ladder
    if exit_px is not None:
        watches = build_watches(
            positions=[SimpleNamespace(tradingsymbol=symbol, total_quantity=qty,
                                       average_entry_price=Decimal(str(entry)),
                                       instrument_token=1, exchange="NFO")],
            thresholds=th, broker_account_id="x")
        if not watches:
            fired.append(("live severe-loss", "-", "NO WATCH BUILT (not a long option)"))
        for w in watches:
            for c in w.evaluate(float(exit_px)):
                fired.append((f"live severe-loss [{c.kind}]", c.severity,
                              f"{c.loss_pct}% of premium, boundary {c.boundary_pct}"))

    if not fired:
        print("  -> NOTHING FIRES")
    for name, sev, msg in fired:
        print(f"  -> {name:<38} {sev:<9} {msg}")


print("#" * 74)
print("# A-L : CURRENT BEHAVIOUR, FROM LIVE CODE. NOTHING CHANGED.")
print("#" * 74)

run("A. no user rule + position uses 30% capital", None, "NIFTY26FEB24000CE", 400, 75.0)
run("B. no user rule + position uses 90% capital", None, "NIFTY26FEB24000CE", 1200, 75.0)
run("C. user rule 40% + position uses 35%", 40.0, "NIFTY26FEB24000CE", 466, 75.0)
run("D. user rule 40% + position uses 45%", 40.0, "NIFTY26FEB24000CE", 600, 75.0)
run("E. user rule 80% + position uses 75%", 80.0, "NIFTY26FEB24000CE", 1000, 75.0)
run("F. user rule 80% + position uses 85%", 80.0, "NIFTY26FEB24000CE", 1133, 75.0)
run("G. no user rule + severe loss >60% of premium", None, "NIFTY26FEB24000CE",
    100, 75.0, exit_px=22.5)
run("H. user rule 80% + severe loss >60% of premium", 80.0, "NIFTY26FEB24000CE",
    1000, 75.0, exit_px=22.5)
run("K. FUTURES, margin unavailable", None, "CIPLA26JANFUT", 375, 1533.2,
    itype="FUT")
run("L. NAKED SHORT option, margin unavailable", None, "NIFTY26FEB24000CE",
    -400, 75.0, direction="SHORT")
