"""
`time_of_day_bias` is retired. These tests hold the retirement in place.

WHY IT WAS RETIRED (2026-09-01, Reviews 25-27)

THE SIGNAL IT ALERTED ON DOES NOT SURVIVE INTO A SECOND TIME PERIOD.

It fired when a trade was entered in an hour the nightly learner had marked
"dangerous" - win rate under 35% with at least 5 trades in that hour, over a
90-day window - gated on 30+ sessions of history.

Measured on 175 sessions / 740 rounds of the reference book:

    danger hours, full book     [12, 15]
    first half                  [11, 12, 15]
    SECOND HALF                 []             <- none at all
    flagged in BOTH halves      NONE
    by quarter                  [9,11]  [11,12,15]  [12,13]  []

Five different hours across four quarters and not one persists. Shuffling the
hour labels and re-applying the learner's own filter flags 2+ hours 31% of the
time; the real book flags 2, the single most likely outcome under pure noise -
and that is a LOWER bound, because trades within a session are not independent.

The descriptive fallback ("drop the label, just show the numbers") fails too:
hourly win rates between the two halves rank-correlate at Spearman rho = +0.071.
Hour 11 goes 28.3% -> 52.9%; hour 15 goes 18.2% -> 50.0%.

Sample arithmetic, not a chosen threshold: separating a 30% hour from a 40%
baseline at 95% confidence needs n ~ 100 trades IN THAT HOUR. The learner's gate
is n >= 5, where the interval is +/-43 points - wider than the whole plausible
range of win rates. Even hour 12's 68 trades cannot make the separation.

ALL FOUR SIGNALS WERE MEASURED SEPARATELY, and they do not license the same
statement:

  danger_hours  MEASURED AND CONTRADICTED - flagged, chance-reproducible, no
                persistence, ranks uncorrelated.
  best_hours    MEASURED, UNSTABLE - one hour (14:00), present in the second
                half only.
  danger_days   MEASURED, FLAT - zero on the full book; the day-of-week win
                rates span 36.0%-42.6% around a 39.5% book rate. The first half
                alone flagged Friday and Wednesday and neither survived, so the
                methodology does fire on subsets and its output does not hold.
  best_days     UNVALIDATED, NOT INVALIDATED - it fires zero times at every
                slice, which is no evidence either way.

INSUFFICIENT EVIDENCE IS NOT PROOF THAT TIME-OF-DAY EFFECTS DO NOT EXIST.
Intraday seasonality is real in markets and plausible in traders. What is retired
is this METHOD of finding it on this book, and every trader-facing claim built on
it. The learning and the storage are DELIBERATELY KEPT so a future evidence pass
has the data.

A CORRECTION BELONGS IN THIS RECORD. The first review called the detector
mis-wired and dead on arrival, claiming `detected_patterns["time_patterns"]` had
no writer. THAT WAS WRONG - it is written at ai_personalization_service.py:142 on
a nightly 18:15 IST beat. The detector was LIVE and firing for any trader with
30+ sessions. Its zero in replay was only that a CSV tradebook carries no
profile. The correction made the finding more serious, not less.

Evidence: docs/patterns/25-27-performance-trio/.
"""
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
SRC = Path(__file__).resolve().parents[2] / "src"

RETIRED = "time_of_day_bias"

#: The four classified lists. Retired as trader-facing claims, kept as storage.
SIGNALS = ("danger_hours", "danger_days", "best_hours", "best_days")


def _live_py():
    for path in APP.rglob("*.py"):
        if "__pycache__" in path.parts or "_archive" in path.parts:
            continue
        yield path


def _code_lines(path):
    """Source lines with whole-line comments stripped.

    The retirement notes quote the predicates they replaced, so a naive scan
    matches its own explanation.
    """
    for lineno, line in enumerate(
        path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
    ):
        if line.lstrip().startswith("#"):
            continue
        yield lineno, line


# ── 1. it cannot generate new events ───────────────────────────────────────

def test_the_detector_method_is_gone():
    from app.services.behavior_engine import BehaviorEngine

    assert not hasattr(BehaviorEngine(), "_detect_time_of_day_bias")


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
        assert spec.method != "_detect_time_of_day_bias"
        assert hasattr(engine, spec.method), f"{spec.name} points at a missing method"


def test_the_engine_counts_are_what_the_retirement_left():
    from app.services.detector_registry import ALIASES, REGISTRY, all_pattern_types

    assert len(REGISTRY) == 14
    # 2026-09-02: 5 -> 4 aliases and 20 -> 19 pattern types. `death_spiral`
    # was retired - a summary of alerts already delivered, not a state.
    assert len(ALIASES) == 2
    assert len(all_pattern_types()) == 16


def test_it_is_recorded_as_retired():
    from tests.test_pattern_contract import RETIRED_PATTERN_NAMES

    assert RETIRED in RETIRED_PATTERN_NAMES


# ── 2. its threshold went with it, unreplaced ──────────────────────────────

def test_the_threshold_is_gone():
    from app.core.threshold_registry import THRESHOLD_SPECS
    from app.core.trading_defaults import COLD_START_DEFAULTS

    assert "tod_bias_min_sessions" not in COLD_START_DEFAULTS
    assert "tod_bias_min_sessions" not in THRESHOLD_SPECS


def test_danger_hours_is_no_longer_resolved_as_a_threshold():
    """
    Both resolvers put it into the threshold set. Neither does now - and this is
    the check that would catch one of them being restored alone, which is how
    the two resolvers drifted before.
    """
    from app.core.threshold_resolution import resolve_thresholds
    from app.core.trading_defaults import get_thresholds

    class _Profile:
        trading_capital = 50000
        detected_patterns = {"time_patterns": {"danger_hours": [{"hour": 13}]}}

        def __getattr__(self, name):
            return None

    ts = resolve_thresholds(_Profile())
    assert "danger_hours" not in ts.values
    assert ts.explain("danger_hours") is None

    assert "danger_hours" not in get_thresholds(_Profile())
    assert "danger_hours" not in get_thresholds(None)


def test_no_live_module_reads_the_deleted_threshold():
    offenders = []
    for path in _live_py():
        for lineno, line in _code_lines(path):
            if "tod_bias_min_sessions" in line:
                offenders.append(f"{path.relative_to(APP)}:{lineno}")
    assert offenders == [], f"deleted threshold still read: {offenders}"


def test_no_replacement_sample_gate_was_invented():
    """
    The evidence identifies n >= 5 as far too small and does NOT identify a
    number that would be enough - a larger sample tightens each estimate but
    does not make an unstable phenomenon stable (rho = 0.071 between halves).
    Any credible gate would need a persistence test across periods, and nothing
    in this book decides its parameters.
    """
    from app.core.trading_defaults import COLD_START_DEFAULTS

    assert not any("tod_" in k for k in COLD_START_DEFAULTS)
    assert not any("danger_hour" in k for k in COLD_START_DEFAULTS)


# ── 3. THE LEARNING AND STORAGE ARE DELIBERATELY KEPT ──────────────────────

def test_the_learner_still_computes_all_four_signals():
    """
    The point of the retirement: the interpretation goes, the measurement stays.
    If this ever fails, the data a future evidence pass needs has been thrown
    away.
    """
    import inspect

    from app.services.ai_personalization_service import AIPersonalizationService

    src = inspect.getsource(AIPersonalizationService._learn_time_patterns)
    for signal in SIGNALS:
        assert f'"{signal}"' in src, f"{signal} is no longer computed"
    assert '"hourly_breakdown"' in src
    assert '"daily_breakdown"' in src


def test_the_learner_still_persists_them():
    import inspect

    from app.services.ai_personalization_service import AIPersonalizationService

    learn = inspect.getsource(AIPersonalizationService.learn_patterns)
    assert '"time_patterns": time_patterns' in learn
    assert "_store_learned_patterns" in learn

    store = inspect.getsource(AIPersonalizationService._store_learned_patterns)
    assert "profile.detected_patterns = patterns" in store


def test_the_nightly_refresh_beat_is_untouched():
    """
    The chain the first review wrongly called dead. It stays live - it is the
    research path now, not an alerting path.
    """
    beat = (APP / "core" / "celery_app.py").read_text(encoding="utf-8")
    assert "refresh_personalization_patterns" in beat

    task = (APP / "tasks" / "intent_tasks.py").read_text(encoding="utf-8")
    assert "def refresh_personalization_patterns" in task or \
           "refresh_personalization_patterns" in task


def test_the_raw_breakdowns_are_still_served():
    """
    Hour-by-hour and day-by-day counts with no classification attached. They
    carry no claim, so they are not a trader-facing interpretation - and no
    surface renders them today.
    """
    api = (APP / "api" / "personalization.py").read_text(encoding="utf-8")
    assert '"hourly_breakdown"' in api
    assert '"daily_breakdown"' in api


# ── 4. no trader-facing surface makes the retired claims ───────────────────

def test_the_api_no_longer_serves_the_four_classified_lists():
    from app.api import personalization

    src = Path(personalization.__file__).read_text(encoding="utf-8")
    body = "\n".join(l for _, l in _code_lines(Path(personalization.__file__)))
    for signal in SIGNALS:
        assert f'time_patterns.get("{signal}"' not in body, signal
    assert src  # the module is still there; only the four keys went


def test_insights_no_longer_flattens_danger_hours_or_days():
    """
    These two flat arrays existed for one consumer - PredictiveContextStrip -
    which compared the IST-derived values against browser-local time. Both the
    claim and the timezone defect went together.
    """
    import inspect

    from app.services.ai_personalization_service import AIPersonalizationService

    src = inspect.getsource(AIPersonalizationService.get_personalized_insights)
    body = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert '"danger_hours"' not in body
    assert '"danger_days"' not in body
    assert '"revenge_window_minutes"' in body, "the surviving flat field must stay"


def test_no_predictive_window_or_alert_is_built_from_time_patterns():
    import inspect

    from app.services.ai_personalization_service import AIPersonalizationService

    for fn in (AIPersonalizationService._calculate_predictive_windows,
               AIPersonalizationService.get_predictive_alert):
        body = "\n".join(
            l for l in inspect.getsource(fn).splitlines()
            if not l.lstrip().startswith("#")
        )
        assert '"time_warning"' not in body, fn.__name__
        assert '"day_warning"' not in body, fn.__name__
        for signal in SIGNALS:
            assert f'get("{signal}"' not in body, f"{fn.__name__} still reads {signal}"


def test_the_daily_report_makes_no_hour_or_day_claim_anywhere():
    """
    NO allowance. `_calculate_readiness_score`'s danger-day factor was the one
    site left open when the rest of this retirement shipped, and it was closed
    on 2026-09-01 by decision: a readiness score is a trader-facing decision
    signal, so the rule that retired the alert applies to it too.
    """
    from app.services import daily_reports_service

    path = Path(daily_reports_service.__file__)
    offenders = []
    for lineno, line in _code_lines(path):
        for signal in SIGNALS:
            if f'"{signal}"' in line:
                offenders.append(f"{lineno}: {line.strip()}")
    assert offenders == [], f"daily report still reads the retired lists: {offenders}"


def test_the_readiness_score_has_no_day_or_time_factor():
    """
    The penalty is GONE, not hidden. Keeping the arithmetic while dropping only
    the visible detail string was the rejected option: an unsupported signal
    moving a decision number invisibly is harder to audit than one that at least
    states itself. So this asserts on the SCORE, not on the copy.
    """
    from datetime import datetime, timedelta
    from types import SimpleNamespace

    from app.services.daily_reports_service import DailyReportsService

    svc = DailyReportsService()
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
            "Saturday", "Sunday"]

    for day in days:
        flagged = SimpleNamespace(detected_patterns={"time_patterns": {
            "danger_days": [{"day": day, "win_rate": 31.2}],
            "best_days": [{"day": day, "win_rate": 61.0}],
            "danger_hours": [{"hour": 12, "win_rate": 29.9, "trades": 68}],
            "best_hours": [{"hour": 14, "win_rate": 60.0, "trades": 30}],
        }})
        clean = SimpleNamespace(detected_patterns={})

        with_signal = svc._calculate_readiness_score(flagged, [], day)
        without = svc._calculate_readiness_score(clean, [], day)

        assert with_signal == without, (
            f"{day}: a learned danger_day still changes the readiness score")
        assert not any(f["factor"] == "danger_day"
                       for f in with_signal["factors"]), day


def test_no_replacement_day_or_time_factor_was_substituted():
    """
    The instruction was explicit: do not replace it with another time/day factor
    or a new threshold. The three surviving factors are recent P&L, losing streak
    and expiry day - and `expiry_day` is a MARKET fact (weekly expiry), not a
    learned property of the trader, so it is not a substitute.
    """
    import inspect

    from app.services.daily_reports_service import DailyReportsService

    body = "\n".join(
        l for l in inspect.getsource(
            DailyReportsService._calculate_readiness_score).splitlines()
        if not l.lstrip().startswith("#")
    )
    for signal in SIGNALS:
        assert signal not in body, signal
    assert "time_patterns" not in body
    assert "detected_patterns" not in body

    emitted = {
        "large_recent_loss", "moderate_recent_loss", "losing_streak",
        "expiry_day",
    }
    found = set()
    for line in body.splitlines():
        if '"factor":' in line:
            found.add(line.split('"factor":')[1].split('"')[1])
    assert found == emitted, f"the factor set changed: {found}"


def test_the_surviving_factors_are_untouched():
    """
    Measured over all 489,951 reachable inputs: 435,512 cases (88.9%) are
    identical and the other 54,439 move by exactly +20. Nothing else shifted.
    These are the boundary cases from that sweep.
    """
    from datetime import datetime, timedelta
    from types import SimpleNamespace

    from app.services.daily_reports_service import DailyReportsService

    svc = DailyReportsService()
    base = datetime(2026, 9, 1, 15, 0, 0)

    def pos(pnls):
        return [SimpleNamespace(last_exit_time=base - timedelta(minutes=i),
                                realized_pnl=p, pnl=None)
                for i, p in enumerate(pnls)]

    # large_recent_loss: sum < -3000
    r = svc._calculate_readiness_score(None, pos([-900.0] * 5), "Monday")
    assert ("large_recent_loss", -20) in [(f["factor"], f["impact"]) for f in r["factors"]]
    assert ("losing_streak", -15) in [(f["factor"], f["impact"]) for f in r["factors"]]
    assert r["score"] == 65

    # moderate_recent_loss: -3000 <= sum < -1500
    r = svc._calculate_readiness_score(None, pos([-400.0] * 5), "Monday")
    assert ("moderate_recent_loss", -10) in [(f["factor"], f["impact"]) for f in r["factors"]]
    assert r["score"] == 75

    # no loss at all, and the expiry-day branch is a MARKET fact, not learned
    r = svc._calculate_readiness_score(None, pos([2000.0] * 5), "Monday")
    assert r["score"] == 100 and r["status"] == "ready"
    r = svc._calculate_readiness_score(None, pos([2000.0] * 5), "Thursday")
    assert r["score"] == 95
    assert [(f["factor"], f["impact"]) for f in r["factors"]] == [("expiry_day", -5)]


def test_the_warning_band_is_now_unreachable_and_that_is_recorded():
    """
    A consequence of the removal, not a defect introduced by it, and NOT a reason
    to substitute a replacement factor - that would be inventing a threshold,
    which is the thing this retirement exists to stop.

    The remaining penalties total at most 40 (large_recent_loss 20 + streak 15 +
    expiry 5), so the floor is exactly 60 - the `caution` cut. All 4,564 cases
    that reached `warning` in the pre-change sweep required the removed -20.

    Pinned so the dead band is a known, recorded product question rather than
    something discovered later as a surprise. See PENDING_AND_TODO.md.
    """
    from datetime import datetime, timedelta
    from types import SimpleNamespace

    from app.services.daily_reports_service import DailyReportsService

    svc = DailyReportsService()
    base = datetime(2026, 9, 1, 15, 0, 0)
    worst = [SimpleNamespace(last_exit_time=base - timedelta(minutes=i),
                             realized_pnl=-100000.0, pnl=None)
             for i in range(5)]

    r = svc._calculate_readiness_score(None, worst, "Thursday")
    assert r["score"] == 60, "the worst reachable score is no longer 40"
    assert r["status"] == "caution"
    assert sum(f["impact"] for f in r["factors"]) == -40


def test_the_day_warning_banner_is_gone_from_the_briefing():
    from app.services.daily_reports_service import DailyReportsService

    assert not hasattr(DailyReportsService, "_generate_day_warning")


def test_avoid_times_is_still_in_the_contract_but_never_filled():
    """
    The key stays - it is part of the report shape - and nothing writes an hour
    into it. A key that silently disappears is a different kind of break from a
    key that is empty.
    """
    import inspect

    from app.services.daily_reports_service import DailyReportsService

    src = inspect.getsource(DailyReportsService._generate_focus_area) \
        if hasattr(DailyReportsService, "_generate_focus_area") else None
    if src is None:
        # the method was renamed; fall back to the module
        src = Path(
            __import__("app.services.daily_reports_service", fromlist=["x"]).__file__
        ).read_text(encoding="utf-8")
    assert '"avoid_times": []' in src
    body = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert 'focus["avoid_times"] =' not in body


def test_the_morning_push_makes_no_danger_day_claim():
    body = "\n".join(
        l for _, l in _code_lines(APP / "tasks" / "intent_tasks.py")
    )
    assert "danger_days" not in body
    assert "worst trading day" not in body


# ── 5. the frontend ────────────────────────────────────────────────────────

def _fe(rel):
    p = SRC / rel
    return p.read_text(encoding="utf-8") if p.exists() else None


def test_the_strip_no_longer_renders_a_danger_hour_or_day():
    text = _fe("components/dashboard/PredictiveContextStrip.tsx")
    if text is None:
        return
    body = "\n".join(
        l for l in text.splitlines()
        if not l.lstrip().startswith("//") and not l.lstrip().startswith("*")
    )
    assert "ins.danger_hours" not in body
    assert "ins.danger_days" not in body
    assert "'danger-hour'" not in body
    assert "'danger-day'" not in body


def test_the_strip_no_longer_compares_ist_signals_to_browser_local_time():
    """
    The one file in the codebase that did. `new Date().getHours()` and
    `new Date().getDay()` were matched against IST-derived hours and weekdays,
    so for a trader outside IST the hour compared was simply the wrong one.
    Every other component converts first.
    """
    text = _fe("components/dashboard/PredictiveContextStrip.tsx")
    if text is None:
        return
    # The header comment names both calls to record what was removed, so the
    # scan has to look at code rather than at its own explanation.
    body = "\n".join(
        l for l in text.splitlines()
        if not l.lstrip().startswith("//") and not l.lstrip().startswith("*")
    )
    assert "new Date().getHours()" not in body
    assert "new Date().getDay()" not in body


def test_the_report_page_no_longer_renders_the_day_warning_banner():
    text = _fe("pages/Reports.tsx")
    if text is None:
        return
    body = "\n".join(
        l for l in text.splitlines()
        if not l.lstrip().startswith("//") and not l.lstrip().startswith("*")
    )
    assert "data.day_warning" not in body
    assert "dayWarning" not in body


def test_the_guest_fixture_mirrors_the_real_endpoint():
    """
    Guest fixtures double as smoke fixtures. A fixture that still serves the
    retired cards would be the only place in the product where they appear.
    """
    text = _fe("lib/guestMode.ts")
    if text is None:
        return
    body = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("//"))
    assert "'danger_time'" not in body
    assert "'best_time'" not in body
    assert "'time_warning'" not in body


def test_the_frontend_can_still_name_a_stored_row():
    text = _fe("contexts/AlertContext.tsx")
    if text is None:
        return

    routing = text[text.index("const BACKEND_TO_FRONTEND_TYPE"):]
    routing = routing[:routing.index("\n};")]
    assert "'time_of_day_bias':" not in routing, (
        "the engine cannot emit it, so the routing map must not name it")

    assert "'time_of_day_bias': 'Time-of-day pattern'" in text, (
        "stored rows must still render a human name")


# ── 6. the two detectors reviewed alongside it are UNTOUCHED ───────────────

def test_win_rate_collapse_and_strategy_breakdown_were_not_modified():
    """
    Reviewed in the same investigation: `win_rate_collapse` KEEP AS-IS,
    `strategy_breakdown` DEFER. Neither reads `time_patterns` - both depend on
    `detected_patterns["baseline"]`, written by a different service on a
    different path - so nothing in this retirement touches either.
    """
    import inspect

    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import BY_NAME, PATTERN_COPY

    # `strategy_breakdown` was checked here too until it was retired
    # 2026-09-02 for a reason unrelated to this one: its profit-factor half
    # never bound. This assertion is about THIS retirement not touching the
    # performance detectors, and `win_rate_collapse` is the one that survives.
    for name, method in (("win_rate_collapse", "_detect_win_rate_collapse"),):
        assert name in BY_NAME
        assert name in PATTERN_COPY
        assert hasattr(BehaviorEngine(), method)
        src = inspect.getsource(getattr(BehaviorEngine, method))
        assert "time_patterns" not in src
        for signal in SIGNALS:
            assert signal not in src


def test_my_record_is_out_of_scope_and_untouched():
    """
    `api/my_record.py` is a SECOND, INDEPENDENT hourly implementation. It does
    not read `time_patterns` - it computes from trades directly, uses `now_ist`
    rather than browser-local time, states its own sample in the sentence, and
    is a PULL surface the trader opens deliberately.

    It carries the same instability risk, because "weakest window" is a ranking
    and rankings are what rho = 0.071 says do not hold. It was explicitly
    excluded from this pass and recorded as a separate product review. This test
    pins that it was left alone rather than forgotten.
    """
    src = (APP / "api" / "my_record.py").read_text(encoding="utf-8")
    assert "time_patterns" not in src
    assert "MIN_SAMPLE" in src
    assert "now_ist" in src
    assert re.search(r'"best_hour"', src)
    assert re.search(r'"worst_hour"', src)
