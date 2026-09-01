"""
`winning_streak_overconfidence` is retired. These tests hold the retirement in
place AND preserve the two things worth keeping from it.

WHY IT WAS RETIRED (2026-08-30, Pattern 19)

THE CONCEPT IS REAL. THE CONDITIONING VARIABLE HAD THE WRONG SIGN.

It fired when the last N session exits all won AND the position was >= M x the
average size of prior trades. Neither half is a behaviour alone - traders have
winning runs, traders vary size - so the entire claim was that the RUN is why
the SIZE went up. Measured directly on 175 sessions / 740 rounds:

    P(size >= 1.3x baseline)
        after a 3+ win run       21.4%   (n=28)
        every other comparable   30.4%   (n=263)

Sizing up is LESS likely after a winning run, and monotonically so across run
lengths 0-4: 32.1%, 27.9%, 27.0%, 28.6%, 0.0%. Spearman rho(run length, size
ratio) = -0.076, p = 0.902. The detector's theory predicts a POSITIVE
correlation.

The sizing response to a run DOES exist in this book, inverted. After LOSING
runs of 0-4 the same probability rises: 26.0%, 28.4%, 30.6%, 40.0%, 53.8%.
THIS TRADER SIZES UP AFTER LOSSES AND DOWN AFTER WINS - `martingale_behaviour`'s
subject, which it already covers. Asserted below.

Shuffle null: 6 real firings against a shuffled mean of 6.2, p = 0.582.

The danger tier never fired in 175 sessions and was NOT correctly silent: only
1 trade of 740 ever had a 5-win run behind it, and it was under 2.0x. The SIZE
half of that tier was satisfied twice (ratios 2.22, 2.65), both emitting caution
because the streak was 3. The tier was gated by the half with no evidence.

NOT RETIRED PERMANENTLY. Overconfidence after wins is established literature
(Barber & Odean; Statman, Thorley & Vorkink). n=28 cannot exclude a modest real
effect in another trader; what it excludes is this implementation.

Evidence: docs/patterns/19-winning_streak_overconfidence/.
"""
import inspect
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

APP = Path(__file__).resolve().parents[1] / "app"

RETIRED = "winning_streak_overconfidence"


# ── 1. it cannot generate new events ───────────────────────────────────────

def test_the_detector_method_is_gone():
    from app.services.behavior_engine import BehaviorEngine

    assert not hasattr(BehaviorEngine(), "_detect_winning_streak_overconfidence")


def test_it_is_not_in_the_registry_or_the_vocabulary():
    from app.services.detector_registry import (
        ALIASES, BY_NAME, PATTERN_COPY, REGISTRY, all_pattern_types,
    )

    assert RETIRED not in BY_NAME
    assert RETIRED not in ALIASES
    assert RETIRED not in all_pattern_types()
    assert RETIRED not in PATTERN_COPY
    assert all(d.name != RETIRED for d in REGISTRY)


def test_no_registry_spec_points_at_the_deleted_method():
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import REGISTRY

    engine = BehaviorEngine()
    for spec in REGISTRY:
        assert spec.method != "_detect_winning_streak_overconfidence"
        assert hasattr(engine, spec.method), f"{spec.name} points at a missing method"


def test_the_engine_counts_are_what_the_retirement_left():
    from app.services.detector_registry import ALIASES, REGISTRY, all_pattern_types

    assert len(REGISTRY) == 15
    assert len(ALIASES) == 5
    assert len(all_pattern_types()) == 20


def test_it_is_recorded_as_retired():
    from tests.test_pattern_contract import RETIRED_PATTERN_NAMES

    assert RETIRED in RETIRED_PATTERN_NAMES


# ── 2. its four thresholds went with it, and none was replaced ─────────────

def test_the_thresholds_are_gone():
    from app.core.threshold_registry import THRESHOLD_SPECS
    from app.core.trading_defaults import COLD_START_DEFAULTS

    for key in ("overconfidence_win_streak_caution", "overconfidence_win_streak_danger",
                "overconfidence_size_mul_caution", "overconfidence_size_mul_danger"):
        assert key not in COLD_START_DEFAULTS, key
        assert key not in THRESHOLD_SPECS, key


def test_no_live_module_reads_the_deleted_thresholds():
    offenders = []
    for path in APP.rglob("*.py"):
        if "__pycache__" in path.parts or "_archive" in path.parts:
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
        ):
            if line.lstrip().startswith("#"):
                continue
            if "overconfidence_" in line:
                offenders.append(f"{path.relative_to(APP)}:{lineno}")
    assert offenders == [], f"deleted thresholds still read: {offenders}"


def test_no_multiplier_was_substituted():
    """
    The measurement said the gate was aimed the wrong way, not that 1.3 was the
    wrong number. Re-tuning would have been fixing the wrong thing.
    """
    from app.core.trading_defaults import COLD_START_DEFAULTS

    assert not any(k.startswith("overconfidence") for k in COLD_START_DEFAULTS)


def test_the_unsourced_hot_hand_statistic_is_gone():
    """
    "after 3 wins, retail traders increase size 40-80%" had no source anywhere
    in the repository, and the multipliers it justified were 1.3 (+30%) and 2.0
    (+100%) - neither endpoint of the range it cited.
    """
    src = (APP / "core" / "trading_defaults.py").read_text(encoding="utf-8")
    assert '"Hot hand fallacy": after 3 wins' not in src, (
        "it must not be stated as fact")
    # The retirement note quotes the claim in order to record WHY it was
    # removed, so the bare string still appears. What must not survive is
    # any live threshold resting on it.
    assert not any(k.startswith("overconfidence")
                   for k in __import__("app.core.trading_defaults",
                                       fromlist=["x"]).COLD_START_DEFAULTS)


# ── 3. THE BEHAVIOUR IS COVERED, INVERTED, BY martingale_behaviour ─────────
#
# The half of this retirement that matters. This trader's real response to a
# run is to size up after LOSSES, and that detector owns it.

def test_martingale_behaviour_still_owns_sizing_up_after_losses():
    from app.core.trading_defaults import COLD_START_DEFAULTS
    from app.services.behavior_engine import BehaviorEngine, EngineContext

    engine = BehaviorEngine()
    now = datetime(2026, 4, 15, 11, 0, tzinfo=timezone.utc)
    acct = uuid4()

    def _ct(qty, pnl, mins_ago):
        return SimpleNamespace(
            id=uuid4(), broker_account_id=acct, tradingsymbol="NIFTY25APR24000CE",
            exchange="NFO", product="MIS", instrument_type="CE", direction="LONG",
            total_quantity=qty, avg_entry_price=Decimal("100"),
            avg_exit_price=Decimal("90"), realized_pnl=Decimal(str(pnl)),
            pnl_pct=None, duration_minutes=10,
            entry_time=now - timedelta(minutes=mins_ago + 10),
            exit_time=now - timedelta(minutes=mins_ago),
            num_entries=1, num_exits=1, status="closed", quality_score=None)

    losses = [_ct(75, -3000, 60), _ct(75, -2500, 40), _ct(75, -2800, 20)]
    escalated = _ct(300, -1000, 0)          # 4x the prior size, after 3 losses

    ctx = EngineContext(
        broker_account_id=acct,
        session=SimpleNamespace(session_pnl=Decimal("-9300"),
                                session_date=now.date(), market_open=None),
        completed_trade=escalated,
        session_trades=losses + [escalated],
        thresholds=dict(COLD_START_DEFAULTS))

    result = engine._detect_martingale_behaviour(ctx)
    assert getattr(result, "fired", bool(result)), (
        "the inverted behaviour must still be caught - it is the one this "
        "trader actually exhibits")


def test_the_other_sizing_detectors_are_untouched():
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import BY_NAME

    engine = BehaviorEngine()
    for name in ("martingale_behaviour", "post_loss_recovery_bet"):
        assert name in BY_NAME, name
        assert hasattr(engine, BY_NAME[name].method), name


# ── 4. what the deleted tests used to pin ──────────────────────────────────
#
# Two tests in test_f_cleanup_regressions.py had this detector as their
# subject. Their REASONING is preserved here; their assertions could not be.

def test_f22_reasoning_survives_the_detector_it_protected():
    """
    F22 removed an unreachable cross-underlying branch from
    `post_loss_recovery_bet`. A companion test existed only to prove the fix was
    NOT swept into this detector, whose `_cross` branch was reachable. It did
    its job - F22 left that branch alone - and its subject is now gone.

    F22's own fix must still be pinned.
    """
    from app.services.behavior_engine import BehaviorEngine

    src = inspect.getsource(BehaviorEngine._detect_post_loss_recovery_bet)
    assert "== ct_underlying" in src
    assert "if _cross:" not in src


def test_f23_bug_class_is_recorded_not_closed():
    """
    F23 was `avg_baseline is not None` passing for 0.0, turning a danger gate
    into `current_qty >= 0`. The fix was correct and lived in this detector to
    the end.

    DELETING THE DETECTOR DOES NOT CLOSE THE BUG CLASS - any `is not None` guard
    on a numeric baseline has the same defect. This test records that rather
    than pretending to sweep for it.
    """
    from app.services.behavior_engine import BehaviorEngine

    assert not hasattr(BehaviorEngine(), "_detect_winning_streak_overconfidence")


# ── 5. the danger-zone caution set is now unreachable, ON PURPOSE ──────────

def test_the_caution_pattern_set_is_left_in_place_though_unreachable():
    """
    `patterns_active` is built from RiskAlert rows, and `rapid_reentry` emits
    `info`, which by the closed INFO/evidence rule never becomes an alert. The
    only member that could reach this set was the retired detector.

    The set is DELIBERATELY LEFT. Pattern 13 classified the dead `rapid_reentry`
    branch as a consumer/design inconsistency and NOT a bug, so that it would
    not later be "fixed" into changing the alerting philosophy. Deleting the
    pattern-driven CAUTION path is that same change by another route, and
    belongs to a danger-zone review.
    """
    src = (APP / "services" / "danger_zone_service.py").read_text(encoding="utf-8")

    # The retirement note names it; the SET must not.
    body = src[src.index("caution_patterns = {"):]
    body = body[:body.index("}")]
    assert RETIRED not in body, "the retired detector must not gate anything"
    assert '"rapid_reentry"' in body, "the set itself stays"


# ── 6. entry-time wiring ───────────────────────────────────────────────────

def test_it_is_no_longer_entry_decidable():
    from app.services.entry_detectors import ENTRY_DECIDABLE

    assert RETIRED not in ENTRY_DECIDABLE


# ── 7. historical rows stay readable ───────────────────────────────────────

def test_the_report_label_survives_for_stored_rows():
    src = (APP / "tasks" / "report_tasks.py").read_text(encoding="utf-8")
    assert '"winning_streak_overconfidence": "Overconfidence"' in src, (
        "monthly reports over stored rows must not print a raw key")


def test_the_frontend_can_still_name_a_stored_row():
    ctx = Path(__file__).resolve().parents[2] / "src" / "contexts" / "AlertContext.tsx"
    if not ctx.exists():
        return
    text = ctx.read_text(encoding="utf-8")

    routing = text[text.index("const BACKEND_TO_FRONTEND_TYPE"):]
    routing = routing[:routing.index("\n};")]
    assert "'winning_streak_overconfidence':" not in routing, (
        "the engine cannot emit it, so the routing map must not name it")

    assert "'winning_streak_overconfidence': 'Overconfidence (Win Streak)'" in text, (
        "stored rows must still render a human name")
