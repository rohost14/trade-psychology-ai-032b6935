"""
The temporal contract of `ctx.session_trades`.

THE DEFECT, found by the Pattern 20 review (2026-08-30)

`load_session_trades` filtered on `exit_time >= session_start` with NO upper
bound. On the LIVE postback path that was harmless — the engine runs when a
trade closes, and a trade that has not closed has no `CompletedTrade` row, so
the bound was implicit in the data. On the BULK path
(`run_behavior_engine_full_session`, used when trades arrive by REST sync
because the trader was not in the app) every row of the day already exists, so
analysing trade 3 of 10 handed the detectors trades 4 through 10.

Measured on the 175-session reference book:

    entries handed to detectors, unbounded   3,616
    ...that had actually closed yet          1,808
    FUTURE entries visible                   1,808   = 50%
    trades affected                          565 of 740  (worst: 13 futures)

And the two paths disagreed on output, not just input:

    overtrading_burst    248 firings (bulk)  vs   13 (live)
    same_symbol_obsession 111               vs   49
    martingale_behaviour   85               vs   32
    fomo_entry             44               vs   32

THE FIX: `as_of`, bounding the load at the analysed trade's exit — the moment
being reconstructed. The live path is unchanged by construction, because that
is already all it could see; the bulk path now agrees with it.

WHY THE BOUND IS ON EXIT AND NOT ON ENTRY
An entry bound was measured and REJECTED. A trade entered after this one but
closed before it HAS happened by the time the engine fires, and for a counting
detector it is plainly one of today's trades. Bounding on entry changed live
firing for four detectors — `overtrading_burst` 13 -> 2 — which is a product
change, not a correctness fix.

Detectors that use a prior's OUTCOME to describe a DECISION must compare
against `ct.entry_time` themselves. Three do, and §3 pins them.
"""
import inspect
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

IST_OPEN = datetime(2026, 4, 15, 9, 15, tzinfo=timezone.utc)


# ── 1. the boundary exists and is applied ──────────────────────────────────

def test_load_session_trades_accepts_an_as_of_bound():
    from app.core.session_facts import load_session_trades

    params = inspect.signature(load_session_trades).parameters
    assert "as_of" in params, "the temporal boundary must be a real parameter"
    assert params["as_of"].default is None, (
        "callers that legitimately want the whole day must be unaffected")


def test_the_bound_is_applied_to_the_query_when_given():
    src = (APP / "core" / "session_facts.py").read_text(encoding="utf-8")
    body = src[src.index("async def load_session_trades"):]
    body = body[:body.index("async def load_facts")]
    code = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))

    assert "if as_of is not None:" in code
    assert "CompletedTrade.exit_time <= as_of" in code


def test_the_bound_is_on_exit_not_entry():
    """
    Pinned because the entry bound is the plausible-looking wrong answer, and
    it was measured: it changes live firing for four detectors.
    """
    src = (APP / "core" / "session_facts.py").read_text(encoding="utf-8")
    body = src[src.index("async def load_session_trades"):]
    body = body[:body.index("async def load_facts")]
    code = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))

    assert "CompletedTrade.entry_time" not in code, (
        "an entry bound here would silently change what 'today's trades' means "
        "for every counting detector")


def test_the_engine_passes_the_analysed_trades_exit_time():
    """The whole point: the engine reconstructs a MOMENT, not a day."""
    src = (APP / "services" / "behavior_engine.py").read_text(encoding="utf-8")
    call = src[src.index("session_trades = await session_facts.load_session_trades("):]
    call = call[:call.index(")") + 1]

    assert "exclude_id=completed_trade.id" in call
    assert 'as_of=getattr(completed_trade, "exit_time", None)' in call


# ── 2. no future trade can be handed to a detector ─────────────────────────

class _FakeResult:
    def __init__(self, rows): self._rows = rows
    def scalars(self): return self
    def all(self): return self._rows


class _RecordingSession:
    """Captures the compiled WHERE clause so the bound can be asserted."""
    def __init__(self): self.sql = None

    async def execute(self, stmt):
        self.sql = str(stmt)
        return _FakeResult([])


async def _run(as_of):
    from uuid import uuid4
    from app.core.session_facts import load_session_trades

    db = _RecordingSession()
    await load_session_trades(db, uuid4(), IST_OPEN.date(), as_of=as_of)
    return db.sql


def test_an_as_of_produces_an_upper_bound_in_the_sql():
    import asyncio

    sql = asyncio.run(_run(IST_OPEN + timedelta(hours=2)))
    ge = sql.count("completed_trades.exit_time >=")
    le = sql.count("completed_trades.exit_time <=")
    assert ge == 1, f"the session-start bound must survive: {sql}"
    assert le == 1, f"the as_of bound must be present: {sql}"


def test_no_as_of_leaves_the_query_open_ended():
    """`load_facts`, the coach and the constitution screen want the whole day."""
    import asyncio

    sql = asyncio.run(_run(None))
    assert sql.count("completed_trades.exit_time <=") == 0


# ── 3. THE DETECTORS THAT READ AN OUTCOME TO DESCRIBE A DECISION ───────────
#
# The exit bound alone does not make these correct — a trade can close before
# this one closed yet still have been open when this one was ENTERED. Any
# detector claiming "you did X AFTER losing" must say so against entry_time.
# These three do. Pattern 20's retired detector did not, and 5 of its 44
# firings cited a loss that had not happened at the moment it described.

def test_revenge_trade_compares_the_prior_close_to_this_entry():
    """
    UPDATED 2026-08-30: it used to spell `t.exit_time < ct.entry_time` inline,
    and this test asserted that literal. The predicate has not changed - it moved
    to `EngineContext.concluded_before_entry`, so the two detectors that had the
    guard and the two that lacked it now share one definition. The guarantee is
    stronger, not weaker; its edges are pinned in test_temporal_contract.py and
    its firing set is unchanged at 182 on the reference book.
    """
    from app.services.behavior_engine import BehaviorEngine, EngineContext

    src = inspect.getsource(BehaviorEngine._detect_revenge_trade)
    assert "ctx.concluded_before_entry" in src, (
        "a revenge trade is a reaction to a loss that had already happened")

    relation = inspect.getsource(EngineContext.concluded_before_entry.fget)
    assert "t.exit_time < entry" in relation, (
        "and the shared relation must still be the strict one")


def test_the_constitution_cooldown_rule_compares_against_this_entry():
    from app.services.behavior_engine import BehaviorEngine

    src = inspect.getsource(BehaviorEngine._detect_constitution_violation)
    assert re.search(r"t\.exit_time\s*<=\s*ct\.entry_time", src), (
        "the cooldown measures the gap from a loss that had already closed")


def test_fomo_entry_bounds_its_window_at_this_entry():
    from app.services.behavior_engine import BehaviorEngine

    src = inspect.getsource(BehaviorEngine._detect_fomo_entry)
    assert re.search(r"window_start\s*<=\s*t\.entry_time\s*<=\s*ct\.entry_time", src), (
        "the FOMO window ends at the entry it is describing")


# ── 4. the callers that legitimately want the whole day ────────────────────

def test_the_whole_day_callers_do_not_pass_as_of():
    """
    `load_facts`, the coach, the constitution screen and early warning answer
    "where is this trader right now", which is a question about the day, not
    about a moment inside it. A bound would be wrong for them.
    """
    for rel in ("core/session_facts.py", "api/coach.py", "api/constitution.py",
                "services/early_warning_service.py"):
        path = APP / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        # calls only — the definition in session_facts.py names the parameter
        for m in re.finditer(r"(?<!def )load_session_trades\((.{0,240}?)\)", text, re.S):
            call = m.group(1)
            assert "as_of" not in call, (
                f"{rel} bounded a whole-day question to a moment: {call[:120]}")
