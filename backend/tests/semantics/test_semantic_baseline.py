"""
Semantic baseline — characterization test.

Runs every scenario in `scenarios.py` through the real engine and compares the
result against a committed snapshot (`baseline.json`).

A DIFF HERE IS NOT AUTOMATICALLY A FAILURE.

This suite records what the engine DOES, not what it SHOULD do. The Trading
Semantics audit found several of these behaviours to be wrong, and Phase 1 will
change them on purpose. When a fix lands:

    1. read the diff and confirm every changed line is a change you intended
    2. regenerate:  python -m tests.semantics.test_semantic_baseline --update
    3. commit the new baseline WITH the fix, so the diff is reviewable

What this suite is for is the other case: a change you did NOT intend, in a
scenario you were not thinking about. That is what a foundational refactor gets
wrong, and it is invisible without a baseline.

Run:  pytest tests/semantics/ -q
"""
from __future__ import annotations

import json
import sys
from enum import Enum
from datetime import timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.semantics import scenarios as SC

BASELINE = Path(__file__).parent / "baseline.json"


# ---------------------------------------------------------------------------
# Rendering — every value must be JSON-stable and human-readable in a diff
# ---------------------------------------------------------------------------

def _r(v):
    # Enum FIRST. DenominatorKind and InstrumentClass are `str` subclasses, so an
    # isinstance(str) check catches them and returns the live member, which reads
    # as "DenominatorKind.MARGIN_POSTED" in a diff while the stored JSON holds
    # "margin_posted". They compare equal, so nothing was wrong — but the diff
    # was unreadable, which defeats the point of a reviewable snapshot.
    if isinstance(v, Enum):
        return str(v.value)
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, Decimal):
        return round(float(v), 4)
    if isinstance(v, (list, tuple)):
        return [_r(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _r(v[k]) for k in sorted(v, key=str)}
    return str(v)


# ---------------------------------------------------------------------------
# L1 — semantic primitives
# ---------------------------------------------------------------------------

def _l1_structures():
    from app.services.strategy_detector import classify_legs

    out = {}
    for name, legs in SC.STRUCTURE_SCENARIOS:
        views = [SC.leg(sym, d) for sym, d in legs]
        try:
            out[name] = {"legs": len(legs), "classified": _r(classify_legs(views))}
        except Exception as e:
            out[name] = {"legs": len(legs), "error": f"{type(e).__name__}: {e}"}
    return out


def _l1_parsing():
    from app.services.instrument_parser import parse_symbol, is_expiry_day

    symbols = sorted({s for _, legs in SC.STRUCTURE_SCENARIOS for s, _ in legs})
    out = {}
    for sym in symbols:
        try:
            p = parse_symbol(sym)
            out[sym] = {
                "underlying": _r(p.underlying),
                "instrument_type": _r(p.instrument_type),
                "expiry_key": _r(getattr(p, "expiry_key", None)),
                "strike": _r(getattr(p, "strike", None)),
                "is_expiry_day_on_2026_03_12": _r(is_expiry_day(sym, SC.DAY)),
            }
        except Exception as e:
            out[sym] = {"error": f"{type(e).__name__}: {e}"}
    return out


def _l1_capital_at_risk():
    from app.core.trading_defaults import estimate_capital_at_risk

    out = {}
    for name, itype, sym, direction, price, qty, exch in SC.RISK_SCENARIOS:
        try:
            risk = estimate_capital_at_risk(
                instrument_type=itype, tradingsymbol=sym, direction=direction,
                avg_entry_price=price, total_quantity=qty, exchange=exch,
            )
            out[name] = {
                "exchange": _r(exch),
                "notional_price_x_qty": _r(price * qty),
                "capital_at_risk": _r(risk),
                "ratio_to_notional": _r(risk / (price * qty)) if price * qty else None,
            }
        except Exception as e:
            out[name] = {"error": f"{type(e).__name__}: {e}"}
    return out


def _l1_instrument_risk():
    from app.core.instrument_risk import classify, risk_basis

    out = {}
    for name, itype, sym, direction, price, qty, exch in SC.RISK_SCENARIOS:
        try:
            cls = classify(itype, direction, is_spread=False)
            basis = risk_basis(itype, sym, direction, price, qty,
                               is_spread=False, exchange=exch)
            out[name] = {
                "class": _r(cls),
                "kind": _r(getattr(basis, "kind", None)),
                "amount": _r(getattr(basis, "amount", None)),
                "is_comparable": _r(getattr(basis, "is_comparable", None)),
            }
        except Exception as e:
            out[name] = {"error": f"{type(e).__name__}: {e}"}
    return out


def _l1_structure_counting():
    from app.services.strategy_detector import count_structures

    out = {}
    for name, legs in SC.STRUCTURE_SCENARIOS:
        trades = [SC.trade(sym, direction=d) for sym, d in legs]
        try:
            out[name] = {"legs": len(legs), "structures": count_structures(trades)}
        except Exception as e:
            out[name] = {"error": f"{type(e).__name__}: {e}"}
    return out


# ---------------------------------------------------------------------------
# L2 — fill lifecycle, via the ledger's pure decision function
# ---------------------------------------------------------------------------

def _l2_lifecycle():
    from app.services.position_ledger_service import _compute_fill_effect

    out = {}
    for name, fills in SC.LIFECYCLE_SCENARIOS:
        qty, avg = 0, Decimal("0")
        steps = []
        for fq, fp in fills:
            try:
                eff = _compute_fill_effect(
                    current_qty=qty, current_avg_price=avg,
                    fill_qty=fq, fill_price=Decimal(str(fp)),
                )
                if isinstance(eff, tuple):
                    entry_type, new_qty, new_avg, realized = (list(eff) + [None] * 4)[:4]
                else:
                    entry_type = getattr(eff, "entry_type", None)
                    new_qty = getattr(eff, "position_qty_after", None)
                    new_avg = getattr(eff, "avg_entry_price_after", None)
                    realized = getattr(eff, "realized_pnl", None)
                steps.append({
                    "fill": [fq, fp], "entry_type": _r(entry_type),
                    "qty_after": _r(new_qty), "avg_after": _r(new_avg),
                    "realized": _r(realized),
                })
                qty = new_qty if new_qty is not None else qty
                avg = new_avg if new_avg is not None else avg
            except Exception as e:
                steps.append({"fill": [fq, fp],
                              "error": f"{type(e).__name__}: {e}"})
                break
        out[name] = steps
    return out


# ---------------------------------------------------------------------------
# L3 — the real detectors
# ---------------------------------------------------------------------------

def _l3_detectors():
    from app.services.behavior_engine import BehaviorEngine, EngineContext
    from app.services.detector_registry import REGISTRY
    from app.core.detector_result import DetectorResult
    from app.core.trading_defaults import COLD_START_DEFAULTS

    engine = BehaviorEngine()
    out = {}

    for sc in SC.detector_scenarios():
        subject, priors = sc["subject"], sc["priors"]
        th = dict(COLD_START_DEFAULTS)
        th.update(sc["thresholds"])

        session = SimpleNamespace(
            session_pnl=Decimal(str(sum(float(p.realized_pnl) for p in priors))),
            session_date=SC.DAY, market_open=None,
        )
        ctx = EngineContext(
            broker_account_id=subject.broker_account_id,
            session=session, completed_trade=subject,
            session_trades=list(priors), active_cooldowns=[], thresholds=th,
        )

        fired = {}
        for spec in REGISTRY:
            method = getattr(engine, spec.method, None)
            if method is None:
                continue
            try:
                res = method(ctx)
            except Exception as e:
                fired[spec.name] = {"error": f"{type(e).__name__}: {e}"}
                continue
            if res is None:
                continue
            events = res if isinstance(res, list) else [res]
            for ev in events:
                if isinstance(ev, DetectorResult):
                    if not ev.fired:
                        continue
                    fired[spec.name] = {"severity": _r(ev.severity),
                                        "via": "DetectorResult"}
                    continue
                if getattr(ev, "event_type", None) is None:
                    continue
                fired[spec.name] = {
                    "severity": _r(ev.severity),
                    "message": _r(getattr(ev, "message", None)),
                }
        out[sc["name"]] = {"note": sc["note"], "fired": _r(fired)}
    return out


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

def build_snapshot() -> dict:
    return {
        "_README": (
            "CHARACTERIZATION SNAPSHOT — what the engine DOES today, not what "
            "it SHOULD do. Phase 1 fixes will change these values on purpose. "
            "See docs/DEEP_REVIEW/SEMANTIC_CONTRACT.md."
        ),
        "L1_parsing": _l1_parsing(),
        "L1_structures": _l1_structures(),
        "L1_structure_counting": _l1_structure_counting(),
        "L1_capital_at_risk": _l1_capital_at_risk(),
        "L1_instrument_risk": _l1_instrument_risk(),
        "L2_lifecycle": _l2_lifecycle(),
        "L3_detectors": _l3_detectors(),
        "_coverage_limits": SC.COVERAGE_LIMITS,
    }


def test_semantic_baseline_is_unchanged():
    """
    The whole point of the harness. Any diff must be explained before it is
    accepted; see the module docstring for the update procedure.
    """
    if not BASELINE.exists():
        pytest.skip("no baseline yet — run with --update to create it")

    current = build_snapshot()
    stored = json.loads(BASELINE.read_text(encoding="utf-8"))

    drift = []
    for layer in sorted(set(current) | set(stored)):
        if layer.startswith("_"):
            continue
        cur, old = current.get(layer, {}), stored.get(layer, {})
        for key in sorted(set(cur) | set(old)):
            if cur.get(key) != old.get(key):
                drift.append(f"{layer}.{key}")

    assert drift == [], (
        f"{len(drift)} scenario(s) changed behaviour:\n  "
        + "\n  ".join(drift)
        + "\n\nIf this change was intended, regenerate the baseline and commit "
          "it alongside the fix so the diff is reviewable."
    )


def test_the_harness_actually_exercises_the_engine():
    """
    A characterization suite that silently stops running is worse than none:
    it would report 'no drift' forever. Pin the shape.
    """
    snap = build_snapshot()
    assert len(snap["L1_structures"]) >= 25
    assert len(snap["L2_lifecycle"]) >= 10
    assert len(snap["L3_detectors"]) >= 18

    fired_total = sum(len(v["fired"]) for v in snap["L3_detectors"].values())
    assert fired_total > 0, "no detector fired on any scenario — harness is inert"

    errors = [
        f"{layer}.{k}"
        for layer, body in snap.items()
        if isinstance(body, dict) and not layer.startswith("_")
        for k, v in body.items()
        if isinstance(v, dict) and "error" in v
    ]
    assert errors == [], f"scenarios raised instead of returning: {errors}"


if __name__ == "__main__":
    if "--update" in sys.argv:
        BASELINE.write_text(
            json.dumps(build_snapshot(), indent=2, sort_keys=True,
                       ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"baseline written: {BASELINE}")
    else:
        print(json.dumps(build_snapshot(), indent=2, sort_keys=True,
                         ensure_ascii=False))
