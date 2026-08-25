# 1 — `martingale_behaviour` · **COMPLETE**

v2.0.0 · exit-triggered · `risk`/`alerting` · notification level 2

## What it reports
A **closed** loss, then a subsequent attempt at materially more risk. The losing
position is gone by the time this fires — adding to one that is still open is
Pattern 2, and the two may both be true.

## Current logic
1. Last N prior closed trades must be **trailing consecutive losses**
   (`martingale_min_losses` = 2).
2. Step measured = **previous closed position → current**, in **capital at
   risk** via `instrument_risk.risk_basis` — not quantity, not notional.
3. `>= 2.0×` **danger** · `>= 1.5×` **caution** · below → not detected.
4. Abstains when risk is not comparable (spread / hedged leg).

## Constants
| key | value | why |
|---|---|---|
| `martingale_min_losses` | 2 | definitional — no progression from one loss |
| `martingale_caution_multiplier` | 1.5 | unchanged; validated on the corrected measure |
| `martingale_danger_multiplier` | 2.0 | unchanged; both tiers populated |

## Replay (corrected 203-session baseline)
**39 alerts / 36 days** · danger 27 · caution 12
31 firings verified: **5/5 definition checks PASS**. Ratio min 1.53× · p50 2.45×
· max 11.63×. 12 firings in the caution band, 19 at danger.
**21 of 31 escalations rotate to a different underlying** — why capital-at-risk
was the necessary correction.

## Limitations
- Instrument coverage outside long options is **synthetic** (book is 727 LONG /
  15 SHORT).
- 9 firings are on winning trades — deliberate; reports the decision, not the
  outcome.
- Post-win control is negative: escalating after two losses is no more likely
  than after two wins. No predictive claim is made.

Detail: `martingale_behaviour_review.md` · `../00-shared/two_behaviours_not_one.md`
