"""
P1 smoke test — observability instrumentation + parity suite wiring. DB-free.

Run:  python scripts/smoke_p1.py
"""
import sys
import inspect
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

failures = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


# ── 1. Metrics module ─────────────────────────────────────────────────────
print("1. Metrics module")
from app.core import metrics
check("SLO metric registered", "alert_e2e_lag_ms" in metrics.TIMINGS)
check("all review counters registered", all(
    c in metrics.COUNTERS for c in
    ("behavior_lock_exhausted", "events_written", "events_conflict_skipped",
     "alerts_deduped", "trades_skipped_idempotent")))
# never-break-pipeline: metrics calls swallow Redis failures
src = inspect.getsource(metrics.incr)
check("incr swallows failures", "except Exception" in src)
# health flags fire correctly on synthetic snapshot
from datetime import datetime, timezone
day = datetime.now(timezone.utc).strftime("%Y%m%d")
flags = metrics.health_flags({day: {"counters": {"behavior_lock_exhausted": 2},
                                    "timings": {"alert_e2e_lag_ms": {"avg_ms": 4500}}}})
check("skip flag raised", "detection_skips" in flags)
check("SLO breach flag raised", "slo_breach" in flags, str(flags))
check("quiet snapshot -> no flags", metrics.health_flags({day: {"counters": {}, "timings": {}}}) == {})

# ── 2. Pipeline instrumentation ───────────────────────────────────────────
print("2. Pipeline instrumentation")
from app.tasks import trade_tasks as tt
src = inspect.getsource(tt.run_risk_detection_async)
check("analyze timed", '_mtimer("analyze_ms")' in src)
check("persist timed", '_mtimer("persist_ms")' in src)
check("death spiral timed", '_mtimer("death_spiral_ms")' in src)
check("e2e SLO observed from trade exit time", 'alert_e2e_lag_ms' in src and "exit_time" in src)
check("dedup counted", '_mincr("alerts_deduped")' in src)
check("stale suppressions counted", 'notifications_stale_suppressed' in src)
psrc = inspect.getsource(tt._persist_events)
check("event writes vs conflicts counted", 'events_written' in psrc and 'events_conflict_skipped' in psrc)

# ── 3. Admin endpoint ─────────────────────────────────────────────────────
print("3. Admin endpoint")
from app.api.admin import system as admin_system
check("engine-metrics route exists",
      any(getattr(r, "path", "") == "/engine-metrics" for r in admin_system.router.routes))

# ── 4. Parity suite ───────────────────────────────────────────────────────
print("4. Replay parity suite (the P2 gate)")
parity_src = Path("scripts/replay_parity.py").read_text(encoding="utf-8")
check("two builders: rescan + state", '"rescan"' in parity_src and '"state"' in parity_src)
check("fingerprint includes rule + suppression", '"rule"' in parity_src and "suppressed_reason" in parity_src)
check("nonzero exit on diff (CI-gateable)", "sys.exit" in parity_src and "return 1" in parity_src)
check("state builder uses SessionState.rebuild", "SessionState.rebuild" in parity_src)

print()
if failures:
    print(f"RESULT: {len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("RESULT: ALL PASS")
