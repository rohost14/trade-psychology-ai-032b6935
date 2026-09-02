"""
The contract that stops the vocabulary drifting again.

Every defect in docs/VOCABULARY_AUDIT.md came from one mechanism: a name or a
severity value changed, and the places comparing against a string literal kept
compiling and kept running, silently meaning something narrower than intended.
No exception, no failing test, no empty screen — a lookup miss renders nothing
and a filter that matches nothing looks like a quiet day.

  * Engine v2 renamed `overtrading` → `overtrading_burst`. Seven files kept
    comparing to the old name. The frontend's explanation and facts tables were
    three of them, so our most common alert opened a detail panel with nothing
    in it.
  * Severity grew from two values to four. `!= "danger"` silently excluded
    every `critical` alert from WhatsApp; `any(== "danger")` reported a critical
    session as caution.

Individually those were bugs. Together they were a missing test. This is it:
the vocabulary has one definition, and anything that names a pattern or a
severity has to agree with it.
"""
import re
from pathlib import Path

import pytest

from app.core.severity import NOTIFIABLE, SEVERITY_ORDER, is_notifiable, rank
from app.services.detector_registry import (
    ALIAS_COPY, ALIASES, BY_NAME, PATTERN_COPY, REGISTRY, all_pattern_types,
    pattern_copy,
)

APP_DIR = Path(__file__).resolve().parent.parent / "app"

#: Files that legitimately contain the old vocabulary: the audit that documents
#: it, and the severity module whose docstring quotes the broken comparisons.
_VOCAB_EXEMPT = {"severity.py"}


def _live_python_files():
    """Every shipping module — archived code is not part of the contract."""
    for path in APP_DIR.rglob("*.py"):
        if "_archive" in path.parts or path.name in _VOCAB_EXEMPT:
            continue
        yield path


# ── Every pattern has copy, and all copy has a pattern ───────────────────────

def test_every_emitted_pattern_has_copy():
    """
    A detector added without copy is a detail panel that renders nothing. That
    is not hypothetical: 15 of 32 pattern types had no frontend copy at all.
    """
    missing = [name for name in all_pattern_types() if pattern_copy(name) is None]
    assert missing == [], f"pattern types with no copy: {missing}"


def test_no_copy_is_orphaned():
    """
    The other direction, which is what a rename breaks. Copy keyed on a name
    nothing emits is copy the user will never see.
    """
    known = set(all_pattern_types())
    orphans = sorted((set(PATTERN_COPY) | set(ALIAS_COPY)) - known)
    assert orphans == [], f"copy for pattern types that are never emitted: {orphans}"


def test_registry_copy_and_alias_copy_do_not_overlap():
    """One home per pattern, so `pattern_copy` can never be ambiguous."""
    both = sorted(set(PATTERN_COPY) & set(ALIAS_COPY))
    assert both == [], f"pattern types defined in both copy maps: {both}"


def test_copy_is_substantive():
    """Empty strings satisfy a key check and still render nothing."""
    for name in all_pattern_types():
        copy = pattern_copy(name)
        assert copy.label.strip(), f"{name}: no label"
        assert len(copy.observes.strip()) > 20, f"{name}: observes is not a sentence"
        assert len(copy.explanation.strip()) > 20, f"{name}: explanation is not a sentence"


def test_copy_carries_no_invented_statistics():
    """
    The frontend shipped precise unsourced claims presented as measurement —
    "win rate on the 4th trade after 3 losses is typically below 30%". Where a
    number belongs it is the trader's own, from their record. Not ours.
    """
    stat_shaped = re.compile(r"\b\d+(\.\d+)?\s*%|\b\d+×|\b\d+x\b", re.IGNORECASE)
    for name in all_pattern_types():
        copy = pattern_copy(name)
        for field in (copy.observes, copy.explanation):
            assert not stat_shaped.search(field), \
                f"{name}: copy contains a statistic — use the trader's own record instead"


# ── Registry integrity ───────────────────────────────────────────────────────

def test_registry_names_are_unique():
    names = [spec.name for spec in REGISTRY]
    assert len(names) == len(set(names))


def test_aliases_are_not_also_registry_specs():
    """
    An alias is a pattern type emitted under a name that is NOT a spec. If it
    were both, BY_NAME lookups and version lookups would disagree.
    """
    collisions = sorted(set(ALIASES) & set(BY_NAME))
    assert collisions == [], f"names that are both a spec and an alias: {collisions}"


def test_every_spec_declares_a_known_disposition_and_trigger():
    for spec in REGISTRY:
        assert spec.disposition in ("alerting", "analytics"), spec.name
        assert spec.trigger in ("exit", "session", "entry"), spec.name
        assert spec.default_mode in ("off", "shadow", "canary", "on"), spec.name


def test_guardian_eligibility_stays_rare():
    """
    Guardian is emergency accountability, not coaching. If this count starts
    climbing, someone is turning a third party's phone into a feed.
    """
    eligible = [s.name for s in REGISTRY if s.guardian_eligible]
    assert len(eligible) <= 4, f"too many guardian-eligible detectors: {eligible}"


# ── Severity vocabulary ──────────────────────────────────────────────────────

def test_severity_order_is_the_whole_vocabulary():
    assert SEVERITY_ORDER == ("info", "caution", "danger", "critical")


def test_notifiable_is_the_top_two():
    assert NOTIFIABLE == frozenset({"danger", "critical"})
    assert is_notifiable("critical") and is_notifiable("danger")
    assert not is_notifiable("caution") and not is_notifiable("info")


def test_ranking_is_ascending_by_seriousness():
    assert rank("info") < rank("caution") < rank("danger") < rank("critical")


def test_no_shipping_module_defines_its_own_severity_rank():
    """
    Five separate _SEV_RANK tables existed, and one of them was INVERTED — it
    put `critical` at 0 and a phantom `positive` at 3, so used with the same
    comparison the others use it would have ranked the least severe alert as
    the worst. Rank comes from app.core.severity now.
    """
    offenders = []
    for path in _live_python_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"_SEV_RANK\s*=\s*\{|_RANK\s*=\s*\{\s*[\"']info", text):
            offenders.append(str(path.relative_to(APP_DIR)))
    assert offenders == [], (
        "local severity rank tables found — import from app.core.severity: "
        f"{offenders}"
    )


def test_no_shipping_module_uses_a_severity_value_outside_the_vocabulary():
    """`positive` and `medium` were both compared against and never emitted."""
    phantom = re.compile(r'severity\s*==\s*[\"\'](positive|medium|low|high)[\"\']')
    offenders = []
    for path in _live_python_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if phantom.search(text):
            offenders.append(str(path.relative_to(APP_DIR)))
    assert offenders == [], f"severity compared against a value we never emit: {offenders}"


# ── Pattern-name literals ────────────────────────────────────────────────────

#: Names that engine v1 emitted and v2 renamed. Anything still comparing
#: against these is dead code that looks alive.
RETIRED_PATTERN_NAMES = (
    "revenge_sizing",
    # Retired 2026-09-02: a snapshot plus a stopwatch. Its predicate never
    # observed the loss CHANGING, and the winner/loser hold substitute failed
    # the persistence test - ratio 0.62 in the first half of the book against
    # 2.54 in the second, intraday 1.04 at shuffle p = 0.343, median 0.98. Not
    # replaced: no MTM capture, and the hold comparison was not promoted to
    # analytics because it fails the same test.
    "holding_loser",
    # Retired 2026-09-02, and NOT on evidence about the behaviour - the alias
    # was already dead. `_overexposure_task` emits constitution_violation with
    # rule max_trade_risk, gates on the DECLARED limit and abstains without a
    # capital requirement. The entry-time check is untouched; only the name is
    # retired.
    "overexposure",
    # Retired 2026-09-02 (Reviews 25-27 follow-up): it required a win-rate
    # collapse AND a profit-factor collapse together, and the profit-factor
    # half never bound - 4 firings, the IDENTICAL set to `win_rate_collapse`,
    # ZERO unique. A session winning 11% of its trades almost always has a
    # wrecked profit factor, so the two conditions were not independent and it
    # was a second name for one finding. `win_rate_collapse` keeps the subject.
    "strategy_breakdown",
    # Retired 2026-09-01 (Pattern 28): there is no universal exposure threshold
    # any more and none replaced its 5/10. A trader who DECLARED 40% was told
    # DANGER at 35% - inside their own rule - because safety_bounds clamps a
    # declared value so it may only tighten. Single-position exposure is now a
    # breach of the trader's OWN limit, which constitution_violation's
    # max_trade_risk rule already owned with the same quantity.
    "excess_exposure",
    # Retired 2026-09-01 (Pattern 28): it measured how FEW positions were open.
    # With n positions the top underlying's share is at least 1/n, so a
    # two-position book had a 50% floor against a 40% cut and could never
    # withhold - 206 of 206 fired, 69% of all firings.
    "portfolio_concentration",
    # Retired 2026-09-01 (Reviews 25-27): the learned "danger hours" it alerted
    # on do not survive into a second time period - full book [12, 15], first
    # half [11, 12, 15], SECOND HALF none at all, and not one hour flagged in
    # both. Chance reproduces 2+ flagged hours 31% of the time. The descriptive
    # fallback fails too: the two halves' hourly ranks correlate at rho =
    # +0.071. Insufficient evidence, NOT proof that time-of-day effects do not
    # exist; the nightly learning and storage are kept for future research.
    "time_of_day_bias",
    # Retired 2026-09-02 (Review A1): a summary of alerts the trader had
    # already been sent, not a state. At `danger` it was set-identical to "a
    # danger emotional alert and a danger risk alert happened today"; with one
    # declared rule it fired on 38.9% of sessions, `constitution_violation`
    # appeared in 100% of them, and in 61% BOTH domains were carried by two
    # detectors reading the SAME declared daily_loss_limit. Order-independent
    # at every tier that ever fired, and its 180-minute compression window
    # never bound. Historical rows are KEPT and still render.
    "death_spiral",
    # Retired 2026-08-30 (Pattern 21): the opening window was not a worse place
    # to trade - 39.4% win inside 09:15-09:25 against 39.5% for the rest of the
    # day, and BETTER on money (p = 0.274). It reached its finding by discarding
    # 42% of window entries for having made money: selection on outcome, the
    # shape that retired panic_exit.
    "opening_5min_trap",
    # Retired 2026-08-30 (Pattern 20): it was never an average-down. 0 of 44
    # firings involved an open position - its "prior losers" were CLOSED rounds
    # on the same UNDERLYING. Its copy described adding_to_adverse_position,
    # which already covers option premium averaging on 100% of its 64 firings.
    "options_premium_avg_down",
    # Retired 2026-08-30 (Pattern 19): the concept is real literature but the
    # conditioning variable had the wrong sign. Sizing up was LESS likely after
    # a 3+ win run (21.4% vs 30.4%), monotone across run lengths, rho = -0.076.
    # This trader sizes up after LOSSES instead - martingale_behaviour's
    # subject. Shuffle null p = 0.582; danger never fired in 175 sessions.
    "winning_streak_overconfidence",
    # Retired 2026-08-30 (Pattern 18): the disposition-effect measure was right,
    # computing it over ONE SESSION was not. The effect is absent in the book
    # (winners 41.0min vs losers 36.7min) and at 3-5 samples a side the ratio is
    # chance - shuffle null p = 0.610. baseline_service still computes it over
    # the full history.
    "early_exit",
    # Retired 2026-08-29 (Pattern 15): its precondition never occurred on the
    # live path - no Celery task creates a Cooldown - and the behaviour is fully
    # covered by constitution_violation's `cooldown` rule, which uses the
    # trader's OWN declared value at danger. 181 events against this one's 0.
    "cooldown_violation",
    # Retired 2026-08-29 (Pattern 14): its subject did not exist. Sub-5-minute
    # holds won at 38.3% against 39.8% for longer holds, so a fast exit is not a
    # worse decision - and it fired only on the losing 60%, ignoring 69
    # identical-behaviour trades because they made money. Selection on OUTCOME,
    # not behaviour. It also fired on the trader's cheapest losses (median
    # Rs 308) and its message made three unsupported claims in one sentence.
    "panic_exit",
    # Retired 2026-08-26: the trigger was chance (63 sessions with a 3+ loss run
    # against 63.0 expected from the win rate alone). The trader's own
    # max_consecutive_losses rule under constitution_violation replaces it.
    "consecutive_loss_streak",
    # Retired 2026-08-27: a drawdown from the session peak is arithmetic. 181 of
    # 189 sessions have one, and shuffling each session's trade order produced
    # MORE firings than the real order (49 vs 56.3) with identical money given
    # back (ratio 1.01).
    "profit_giveaway",
    # Retired 2026-08-27: it never withheld. Of the 55 positions it could judge
    # it fired on 55, because `today_lots` summed CONTRACTS against a threshold
    # of 10 and a NIFTY lot is 75. Both trader-facing statistics were unsourced
    # and measured false (claimed >85% loss rate, actual 53.8%; "each additional
    # trade reduces your edge" measured r = +0.260, the opposite sign).
    "expiry_day_overtrading",
    # Retired 2026-08-27: its claim was ordering, and against 200 permutations of
    # each session's trade order the real order fired LESS than chance (42 vs
    # 49.7, p = 0.880). Its gate selected at the rate three random numbers are
    # increasing. martingale_behaviour and post_loss_recovery_bet keep the claim.
    "size_escalation",
    # Retired 2026-08-28: it could not separate an emotional reversal from a
    # change of view. Its only discriminator was a 10-minute clock, and trades
    # inside the window did BETTER (56.2% win, +Rs 276) than the same transition
    # outside it (41.7%, -Rs 73). Rest-of-session after a flip improved.
    "direction_instability",
    "tilt_loss_spiral",
    "iv_crush_behavior",
    "options_direction_confusion",
    "premium_destruction",
)


def test_no_shipping_module_compares_against_a_retired_pattern_name():
    """
    The exact defect: `if alert.pattern_type == "revenge_sizing"` compiled fine
    and never matched, so three hand-written WhatsApp messages were dead for
    months without a single error.
    """
    offenders = {}
    for path in _live_python_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for retired in RETIRED_PATTERN_NAMES:
            if re.search(rf'\w+\.pattern_type\s*==\s*[\"\']{retired}[\"\']', text):
                offenders.setdefault(str(path.relative_to(APP_DIR)), []).append(retired)
    assert offenders == {}, f"comparisons against retired pattern names: {offenders}"


def test_pattern_type_equality_checks_name_a_real_pattern():
    """
    Any `pattern_type == "x"` in shipping code must name something we emit.
    Catches both retirements and typos, which fail identically and silently.
    """
    known = set(all_pattern_types())
    # Attribute access only. pattern_prediction_service has a local parameter
    # of the same name carrying its own short vocabulary ("revenge", "tilt") —
    # that is a different thing from RiskAlert.pattern_type and not part of
    # this contract.
    literal = re.compile(r'\w+\.pattern_type\s*==\s*[\"\']([a-z_0-9]+)[\"\']')
    offenders = {}
    for path in _live_python_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name in literal.findall(text):
            if name not in known:
                offenders.setdefault(str(path.relative_to(APP_DIR)), []).append(name)
    assert offenders == {}, f"pattern_type compared to unknown names: {offenders}"
