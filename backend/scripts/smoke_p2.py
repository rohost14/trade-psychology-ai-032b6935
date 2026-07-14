"""
P2 increment smoke test — shadow state, write gating, coalescing. DB-free.

Run:  python scripts/smoke_p2.py
"""
import sys
import types
import uuid
import inspect
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

failures = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


# ── 1. Shadow state wiring ────────────────────────────────────────────────
print("1. SessionState shadow (migration weeks 1-2)")
from app.services import behavior_engine as be
src = inspect.getsource(be.BehaviorEngine._load_context)
check("shadow computed in _load_context", "SessionState.rebuild" in src)
check("mismatch counted, never raised", "state_shadow_mismatch" in src and "state_shadow_checked" in src)
check("shadow attached to ctx", "session_state=shadow_state" in src)
from app.services.behavior_engine import EngineContext
import dataclasses
fields = {f.name for f in dataclasses.fields(EngineContext)}
check("EngineContext.session_state field", "session_state" in fields)

# detectors must NOT read session_state yet (cutover not started)
all_src = inspect.getsource(be)
detector_srcs = [inspect.getsource(getattr(be.BehaviorEngine, s.method))
                 for s in __import__("app.services.detector_registry", fromlist=["REGISTRY"]).REGISTRY
                 if hasattr(be.BehaviorEngine, s.method)]
check("no detector consumes ctx.session_state yet",
      all("ctx.session_state" not in d for d in detector_srcs))

# ── 2. Snapshot severity-gating (addendum #3) ─────────────────────────────
print("2. input_snapshot gating")
asrc = inspect.getsource(be.BehaviorEngine.analyze)
check("snapshot only for danger/critical",
      'if e.severity in ("danger", "critical") else None' in asrc)

# ── 3. Info-noise write gating ────────────────────────────────────────────
print("3. Info-noise event gating")
from app.tasks import trade_tasks as tt
psrc = inspect.getsource(tt._persist_events)
check("alerting-detector info noise gated", "events_info_gated" in psrc)
check("analytics-disposition info kept", 'disposition == "alerting"' in psrc)
check("suppressed evidence never gated (1C.8)", "_suppressed" in psrc and "not suppressed" in psrc)

# behavioral check via row construction logic: simulate gate conditions
from app.services.detector_registry import BY_NAME
check("panic_exit is analytics (info kept)", BY_NAME["panic_exit"].disposition == "analytics")
check("revenge is alerting (info gated)", BY_NAME["revenge_trade"].disposition == "alerting")

# ── 4. Coalescing ─────────────────────────────────────────────────────────
print("4. Task coalescing (review S6.2)")
tsrc = inspect.getsource(tt)
check("no .delay fan-out for overexposure", "check_position_overexposure.delay" not in tsrc)
check("no .delay fan-out for concentration", "check_portfolio_concentration.delay" not in tsrc)
check("no .delay fan-out for entry rules", "check_entry_rules.delay" not in tsrc)
check("inline awaits present", "_overexposure_task(" in tsrc and "_concentration_task(" in tsrc
      and "_entry_rules_task(" in tsrc)
check("holding_loser chain still scheduled (time-based)", "check_holding_loser_scheduled" in tsrc)
check("each inline check individually non-fatal", tsrc.count("inline check failed") == 3)

# ── 5. Metrics + flags ────────────────────────────────────────────────────
print("5. Metrics registry + drift flag")
from app.core import metrics
check("shadow counters registered", "state_shadow_mismatch" in metrics.COUNTERS
      and "events_info_gated" in metrics.COUNTERS)
day = datetime.now(timezone.utc).strftime("%Y%m%d")
flags = metrics.health_flags({day: {"counters": {"state_shadow_mismatch": 1}, "timings": {}}})
check("drift flag blocks migration", "state_drift" in flags and "BLOCKED" in flags["state_drift"])

# ── 6. Migration 067 sanity ───────────────────────────────────────────────
print("6. Migration 067 (partitioning)")
mig = Path("migrations/067_partition_behavior_events.sql").read_text(encoding="utf-8")
check("range partitioned on detected_at", "PARTITION BY RANGE (detected_at)" in mig)
check("12 monthly partitions + default", mig.count("PARTITION OF behavior_events FOR VALUES") == 12
      and "PARTITION OF behavior_events DEFAULT" in mig)
check("unique idem index includes partition key",
      "uq_behavior_events_idem" in mig and "idempotency_key, detected_at)" in mig)
check("legacy copied then dropped", "INSERT INTO behavior_events" in mig
      and "DROP TABLE behavior_events_legacy" in mig)
check("retention documented", "DROP TABLE behavior_events_y" in mig)

print()
if failures:
    print(f"RESULT: {len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("RESULT: ALL PASS")
