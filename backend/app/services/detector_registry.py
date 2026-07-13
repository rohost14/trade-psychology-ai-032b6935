"""
Detector Registry — Engine v2 Appendix A.1 / A.10.

One declarative record per detector. The engine iterates THIS list, not a
hardcoded method list. Adding a detector = one DetectorSpec + one method.

Fields
------
name                pattern_type written to BehaviorEvent.detector / RiskAlert.pattern_type
version             per-detector semver; bump on ANY logic change (A.2).
                    Alerts/events store max(detector version, ENGINE_VERSION).
nature              emotional | risk | discipline | performance   (master §1.1 Axis A)
disposition         alerting | analytics                          (master §1.1 Axis C)
                    NOTE: dispositions describe the CURRENT engine. The Phase 4
                    strangler migration flips panic_exit/early_exit/opening_trap/
                    rapid_reentry to analytics — do not flip here before then.
trigger             exit | session   — when the detector can fire. All detectors
                    are exit-triggered today (engine runs per CompletedTrade);
                    'session' marks session-level patterns that will move to
                    EOD evaluation in Phase 4+. 'entry' arrives with Phase 6.
notification_level  0 analytics · 1 in-app · 2 push · 3 critical push · 4 guardian
                    (maximum level this detector may reach; routing still applies
                    severity × confidence — master §1B.7b)
guardian_eligible   may ever reach the guardian channel
consumes            state the detector reads (A.10 — primary state only, never
                    another detector, never derived scores)
uses_baseline / uses_constitution / uses_position_state
                    threshold-source dependencies (master §1.1 Axis B)

Dependency rule (A.10): no detector may consume another detector's output.
Detectors consume primary state + the trade event; meta-detectors (Phase 5
death spiral) consume BehaviorEvents.
"""
from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class DetectorSpec:
    name: str
    method: str                     # BehaviorEngine method name
    version: str
    nature: str                     # emotional | risk | discipline | performance
    disposition: str                # alerting | analytics
    trigger: str                    # exit | session (entry arrives Phase 6)
    notification_level: int         # 0-4, max channel
    guardian_eligible: bool = False
    uses_baseline: bool = False
    uses_constitution: bool = False
    uses_position_state: bool = False
    consumes: Tuple[str, ...] = ("session_trades", "completed_trade", "thresholds")


REGISTRY: Tuple[DetectorSpec, ...] = (
    DetectorSpec("consecutive_loss_streak", "_detect_consecutive_loss_streak",
                 "1.1.0", "emotional", "alerting", "exit", 2,
                 uses_baseline=True, uses_constitution=True),
    DetectorSpec("revenge_trade", "_detect_revenge_trade",
                 "1.0.0", "emotional", "alerting", "exit", 2,
                 uses_constitution=True),
    DetectorSpec("overtrading_burst", "_detect_overtrading_burst",
                 "1.1.0", "emotional", "alerting", "exit", 2,
                 uses_baseline=True, uses_constitution=True),
    DetectorSpec("size_escalation", "_detect_size_escalation",
                 "1.1.0", "emotional", "alerting", "exit", 1),
    DetectorSpec("rapid_reentry", "_detect_rapid_reentry",
                 "1.1.0", "emotional", "alerting", "exit", 1),
    DetectorSpec("panic_exit", "_detect_panic_exit",
                 "1.0.0", "emotional", "alerting", "exit", 1,
                 consumes=("completed_trade", "exit_order_types", "thresholds")),
    DetectorSpec("martingale_behaviour", "_detect_martingale_behaviour",
                 "1.1.0", "risk", "alerting", "exit", 2),
    DetectorSpec("rapid_flip", "_detect_rapid_flip",
                 "1.0.0", "emotional", "alerting", "exit", 1),
    DetectorSpec("excess_exposure", "_detect_excess_exposure",
                 "1.0.0", "risk", "alerting", "exit", 2,
                 uses_constitution=True),
    DetectorSpec("session_meltdown", "_detect_session_meltdown",
                 "1.0.0", "risk", "alerting", "exit", 4, guardian_eligible=True,
                 uses_constitution=True,
                 consumes=("session", "completed_trade", "thresholds")),
    DetectorSpec("fomo_entry", "_detect_fomo_entry",
                 "1.0.0", "emotional", "alerting", "exit", 1),
    DetectorSpec("no_stoploss", "_detect_no_stoploss",
                 "1.0.0", "risk", "alerting", "exit", 2,
                 consumes=("completed_trade", "exit_order_types", "thresholds")),
    DetectorSpec("early_exit", "_detect_early_exit",
                 "1.0.0", "performance", "alerting", "session", 1),
    DetectorSpec("winning_streak_overconfidence", "_detect_winning_streak_overconfidence",
                 "1.1.0", "emotional", "alerting", "exit", 1,
                 uses_baseline=True),
    DetectorSpec("options_direction_confusion", "_detect_options_direction_confusion",
                 "1.0.0", "emotional", "alerting", "exit", 1),
    DetectorSpec("options_premium_avg_down", "_detect_options_premium_avg_down",
                 "1.0.0", "emotional", "alerting", "exit", 1),
    DetectorSpec("iv_crush_behavior", "_detect_iv_crush_behavior",
                 "1.0.0", "risk", "alerting", "exit", 1),
    DetectorSpec("premium_destruction", "_detect_premium_destruction",
                 "1.0.0", "risk", "alerting", "exit", 2),
    DetectorSpec("expiry_day_overtrading", "_detect_expiry_day_overtrading",
                 "1.0.0", "emotional", "alerting", "exit", 2,
                 uses_baseline=True),
    DetectorSpec("opening_5min_trap", "_detect_opening_5min_trap",
                 "1.0.0", "emotional", "alerting", "exit", 1),
    DetectorSpec("end_of_session_mis_panic", "_detect_end_of_session_mis_panic",
                 "1.0.0", "emotional", "alerting", "exit", 1),
    DetectorSpec("post_loss_recovery_bet", "_detect_post_loss_recovery_bet",
                 "1.1.0", "risk", "alerting", "exit", 2),
    DetectorSpec("profit_giveaway", "_detect_profit_giveaway",
                 "1.0.0", "emotional", "alerting", "exit", 2,
                 consumes=("session", "session_trades", "completed_trade", "thresholds")),
    # cooldown_violation: system-suggested cooldowns (Cooldown DB records),
    # analytics-only. Distinct from the constitution cooldown rule below.
    DetectorSpec("cooldown_violation", "_detect_cooldown_violation",
                 "1.0.0", "discipline", "analytics", "exit", 0,
                 uses_constitution=True,
                 consumes=("active_cooldowns", "completed_trade")),
    # Constitution violation (Phase 2, Q15): one pattern for every user-declared
    # rule — daily_loss, daily_trades, max_consecutive_losses, cooldown,
    # restricted_window, max_trade_risk. Ladder: 80% caution / 100% danger /
    # 120% critical (guardian-eligible). Returns a LIST (multi-rule breaches).
    DetectorSpec("constitution_violation", "_detect_constitution_violation",
                 "1.0.0", "discipline", "alerting", "exit", 4,
                 guardian_eligible=True, uses_constitution=True,
                 consumes=("session", "session_trades", "completed_trade", "thresholds")),
)

# Fast lookups
BY_NAME = {spec.name: spec for spec in REGISTRY}


def spec_for(pattern_type: str) -> DetectorSpec | None:
    return BY_NAME.get(pattern_type)
