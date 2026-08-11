# Next session — start here

State at end of 11 Aug 2026. Everything committed and pushed (`5433f67`).

## Do these three first

**1. A readable replay report.** The current one is 2,300 lines and the user
correctly called it unusable — nobody reads a year of trades day by day. It
should be one page: alerts per month, alerts per pattern, and the ten worst
days with their trades. Per-day detail becomes an appendix or is dropped.
`tradedesk/scripts/replay_tradebook.py` writes it.

**2. Retire `post_loss_recovery_bet`.** 2 alerts against 26 days of the
behaviour — 8% recall. Not worth fixing, because the user's judgement is right:
it is revenge trading with extra steps, and the concept is already covered.
Retire rather than repair a duplicate.

**3. Move `time_of_day_bias` to analytics.** It is dispositioned `alerting` in
`detector_registry.py` and should not be. "You lose most between 2 and 3pm" is a
pattern over months, not something to say mid-trade. `panic_exit`, `early_exit`,
`win_rate_collapse` and `strategy_breakdown` are ALREADY `analytics` and are
correctly silent — do not touch those. I misread their silence as failure once;
do not repeat it.

## Then

**4. Extend `recall_check.py`.** It models six behaviours, so only six detectors
have a measured recall. Seventeen fired across the year with nothing checking
whether they fired on everything they should have. That unmeasured majority is
exactly where martingale hid for a year.

## What the year of data established

355 alerts across 203 sessions — 1.7 per session. Seventeen patterns fired.

Recall, engine against independent count:

| Pattern | Engine | Behaviour present | Recall |
|---|---|---|---|
| `martingale_behaviour` | 31 | 40 days | ~78% |
| `profit_giveaway` | 21 | 30 days | ~70% |
| `same_symbol_obsession` | 24 | 37 days | ~65% |
| `revenge_trade` | 34 | 58 days | ~59% |
| `size_escalation` | 8 | 16 days | ~50% |
| `post_loss_recovery_bet` | 2 | 26 days | ~8% |

`revenge_trade` at 59% is worth reading a few of the 24 missed days before
assuming it is wrong — the engine is stricter than the checker by design and
some gap is correct.

## What cannot be claimed

That the detectors which have never been recall-measured are working. They fire.
Nothing has checked what they miss. `martingale_behaviour` had correct code, 32
passing tests and a wrong idea of the behaviour, and only real trades found it.

## Tools

- `tradedesk/scripts/replay_tradebook.py` — engine over a real tradebook
- `tradedesk/scripts/recall_check.py` — counts behaviours from the CSV with no
  engine involved. Deliberately a second implementation; sharing code would
  share the assumptions under test. It found most of today's real defects.
- `alertlab/scripts/audit.py` — alert-quality across the 108 scenarios
- `docs/DETECTOR_ASSUMPTIONS.md` — what each detector assumes, checked against
  real trading
- `docs/THRESHOLD_REWORK_PLAN.md` — why capital-relative thresholds fail for F&O

## Open, with evidence attached

- The 5 remaining `flood` findings from the alert audit — 3-4 genuinely
  different facts on one bad trade. Left deliberately; the user's call.
- `no_stoploss` and `end_of_session_mis_panic` cannot be judged from a tradebook
  at all — no order type, no product column. Need live postbacks.
