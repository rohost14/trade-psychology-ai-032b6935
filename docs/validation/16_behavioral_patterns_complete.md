# Behavioral Patterns — Complete Reference
*AUTO-GENERATED from `detector_registry.py` — do not edit by hand.*
*Engine version 1.1.0 · 27 registered detectors + 5 emitted aliases*

Single source of truth: `backend/app/services/detector_registry.py`.
The legacy 3-layer description (frontend patternDetector, RiskDetector,
BehavioralEvaluator) is obsolete — those layers were removed in Sessions 21
and Engine v2 Phase 0. BehaviorEngine is the only detection source.

Dispositions: `alerting` may notify per the severity x confidence routing
matrix; `analytics` records evidence (BehaviorEvents) only - feeds scores,
journal, EOD reports, never interrupts.

| Detector | Ver | Nature | Disposition | Trigger | Max channel | Guardian | Baseline | Constitution | Risk delta |
|---|---|---|---|---|---|---|---|---|---|
| consecutive_loss_streak | 1.1.0 | emotional | alerting | exit | push |  | yes | yes | 20 |
| revenge_trade | 2.0.0 | emotional | alerting | exit | push |  |  | yes | 25 |
| overtrading_burst | 2.0.0 | emotional | alerting | exit | push |  | yes | yes | 10 |
| size_escalation | 1.1.0 | emotional | alerting | exit | in-app |  |  |  | 15 |
| rapid_reentry | 2.0.0 | emotional | analytics | exit | analytics |  |  |  | 15 |
| panic_exit | 2.0.0 | emotional | analytics | exit | analytics |  |  |  | 10 |
| martingale_behaviour | 1.1.0 | risk | alerting | exit | push |  |  |  | 20 |
| direction_instability | 2.0.0 | emotional | alerting | exit | in-app |  |  |  | 15 |
| excess_exposure | 1.0.0 | risk | alerting | exit | push |  |  | yes | 15 |
| session_meltdown | 1.0.0 | risk | alerting | exit | guardian | yes |  | yes | 30 |
| fomo_entry | 1.0.0 | emotional | alerting | exit | in-app |  |  |  | 15 |
| no_stoploss | 1.0.0 | risk | alerting | exit | push |  |  |  | 20 |
| early_exit | 2.0.0 | performance | analytics | session | analytics |  |  |  | 10 |
| winning_streak_overconfidence | 1.1.0 | emotional | alerting | exit | in-app |  | yes |  | 15 |
| options_premium_avg_down | 1.0.0 | emotional | alerting | exit | in-app |  |  |  | 15 |
| premium_loss_event | 2.0.0 | risk | alerting | exit | critical push |  |  |  | 15 |
| expiry_day_overtrading | 1.0.0 | emotional | alerting | exit | push |  | yes |  | 20 |
| opening_5min_trap | 2.0.0 | emotional | analytics | exit | analytics |  |  |  | 10 |
| end_of_session_mis_panic | 2.0.0 | emotional | alerting | exit | in-app |  |  |  | 15 |
| post_loss_recovery_bet | 1.1.0 | risk | alerting | exit | push |  |  |  | 20 |
| profit_giveaway | 1.0.0 | emotional | alerting | exit | push |  |  |  | 20 |
| cooldown_violation | 1.0.0 | discipline | analytics | exit | analytics |  |  | yes | 25 |
| constitution_violation | 1.0.0 | discipline | alerting | exit | guardian | yes |  | yes | 25 |
| same_symbol_obsession | 1.0.0 | emotional | alerting | exit | push |  |  |  | 20 |
| time_of_day_bias | 1.0.0 | performance | alerting | exit | in-app |  | yes |  | 5 |
| win_rate_collapse | 1.0.0 | performance | analytics | session | analytics |  | yes |  | 10 |
| strategy_breakdown | 1.0.0 | performance | analytics | session | analytics |  | yes |  | 15 |

## Emitted aliases (patterns produced under a different name)

| Pattern | Ver | Emitted by | Notes |
|---|---|---|---|
| daily_overtrading | 2.0.0 | _detect_overtrading_burst | Phase 4 split: daily total vs 30-min burst |
| death_spiral | 1.0.0 | behavior_scores_service (meta, L2) | consumes BehaviorEvents; warning/danger/critical; guardian at critical |
| overexposure | 2.0.0 | position_monitor (entry-time) | All-In ladder + emotional multiplier, live LTP |
| portfolio_concentration | 1.0.0 | position_monitor (entry-time) | largest underlying / total open exposure, 40/60/80 |
| holding_loser | 1.0.0 | position_monitor (scheduled) | open losing position checks |

## Cross-layer rules

- Suppression is NOTIFICATION-layer only: every detection persists as a
  BehaviorEvent and feeds driver scores (master 1C.8).
- Constitution breach (danger+) suppresses the paired behavioral pattern's
  notification: cooldown->revenge, max_consecutive_losses->streak,
  daily_trades->overtrading/daily, max_trade_risk->excess_exposure,
  daily_loss->session_meltdown.
- Dedup: per pattern (constitution: per rule), severity escalation always
  passes, stateful re-arm when the driving metric worsens >=20%.
- Guardian: eligible patterns only, danger+, hard budget 3/month.
