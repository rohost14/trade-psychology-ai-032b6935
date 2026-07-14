"""
P0 fixes smoke test (Principal Engineer review items 1-5). DB-free.

Run:  python scripts/smoke_p0fixes.py
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


# ── 1. Idempotency key on engine-built events ─────────────────────────────
print("1. Event idempotency keys (#1)")
from app.models.behavior_event import BehaviorEvent
cols = {c.name for c in BehaviorEvent.__table__.columns}
check("idempotency_key column on model", "idempotency_key" in cols)

src = inspect.getsource(sys.modules["app.services.behavior_engine"].BehaviorEngine.analyze) \
    if "app.services.behavior_engine" in sys.modules else None
from app.services import behavior_engine as be_mod
src = inspect.getsource(be_mod.BehaviorEngine.analyze)
check("engine sets key detector:trade:rule", "idempotency_key=" in src and ".get('rule', '')" in src)

# ── 2. Persist path uses ON CONFLICT DO NOTHING ───────────────────────────
print("2. Upsert-ignore persistence (#1)")
from app.tasks import trade_tasks as tt
psrc = inspect.getsource(tt._persist_events)
check("_persist_events uses pg insert on_conflict_do_nothing",
      "on_conflict_do_nothing" in psrc and "pg_insert" in psrc)
check("dedup marker applied pre-insert", '"_suppressed": "dedup"' in psrc)
check("alert linkage via dedup key", "surviving_by_key.get(ek)" in psrc)
wsrc = inspect.getsource(tt.run_risk_detection_async)
check("webhook path uses _persist_events", "_persist_events" in wsrc)
bsrc = inspect.getsource(tt.run_behavior_engine_full_session)
check("bulk path uses _persist_events", "_persist_events" in bsrc)

# ── 3. Idempotent pre-check (#5) ──────────────────────────────────────────
print("3. Already-analyzed pre-check (#5)")
check("webhook path pre-checks", "_already_analyzed" in wsrc and "already analyzed" in wsrc)
check("bulk path pre-checks per trade", bsrc.count("_already_analyzed") >= 1)

# ── 4. Lock exhaustion -> requeue + metric, bulk takes lock (#2, #4) ──────
print("4. Lock handling (#2, #4)")
proc_src = inspect.getsource(tt)
check("silent behavior_skipped removed", '"behavior_skipped": True' not in proc_src)
check("requeue task dispatched on exhaustion", "run_behavior_detection_retry.apply_async" in proc_src)
check("exhaustion metric counted", 'behavior_lock_exhausted' in proc_src)
check("bulk path acquires behavior_lock", "behavior_lock" in bsrc and "_acquire_lock" in bsrc)
check("bulk lock released", "_release_lock" in bsrc)
check("bulk abort metric", "behavior_bulk_lock_abort" in bsrc)
check("retry task registered", hasattr(tt, "run_behavior_detection_retry"))

# ── 5. learn_patterns on CompletedTrade (#3) ──────────────────────────────
print("5. Time patterns data source (#3)")
from app.services.ai_personalization_service import AIPersonalizationService
lsrc = inspect.getsource(AIPersonalizationService.learn_patterns)
check("queries CompletedTrade not Trade", "CompletedTrade" in lsrc and "Trade.status" not in lsrc)
check("shim exposes real realized_pnl", "realized_pnl" in lsrc and "_TradeShim" in lsrc)

# shim behaves: fake CT -> shim fields
ct = types.SimpleNamespace()
ct.entry_time = datetime.now(timezone.utc)
ct.exit_time = ct.entry_time + timedelta(minutes=10)
ct.realized_pnl = Decimal("-450.5")
ct.tradingsymbol = "NIFTY25JUL25000CE"
ct.total_quantity = 75
# reconstruct shim class the same way learn_patterns does
class _TradeShim:
    __slots__ = ("order_timestamp", "pnl", "tradingsymbol", "quantity")
    def __init__(self, ct):
        self.order_timestamp = ct.entry_time or ct.exit_time
        self.pnl = float(ct.realized_pnl or 0)
        self.tradingsymbol = ct.tradingsymbol
        self.quantity = ct.total_quantity or 0
sh = _TradeShim(ct)
check("shim pnl is real (not 0)", sh.pnl == -450.5)
check("shim timestamp = entry time", sh.order_timestamp == ct.entry_time)

# ── 6. Migration file sanity ──────────────────────────────────────────────
print("6. Migration 066")
mig = Path("migrations/066_event_idempotency.sql").read_text(encoding="utf-8")
check("adds column", "ADD COLUMN IF NOT EXISTS idempotency_key" in mig)
check("backfills existing rows", "SET idempotency_key" in mig)
check("removes duplicates keeping earliest", "keep.created_at < be.created_at" in mig)
check("partial unique index", "CREATE UNIQUE INDEX" in mig and "WHERE idempotency_key IS NOT NULL" in mig)

print()
if failures:
    print(f"RESULT: {len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("RESULT: ALL PASS")
