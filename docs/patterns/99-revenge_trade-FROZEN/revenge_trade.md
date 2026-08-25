# Detector contract — `revenge_trade`

Status: **draft for argument, not a production specification.** Every number
below is illustrative and marked as such. The point of this document is to test
whether the contract *format* from `Redesign_Alerts_BehaviouralEngineV3.md`
survives contact with a real detector. If it does, the other 26 follow.

Measured facts about the current implementation, from the 203-session replay on
the repaired harness: **26 alerts, 47% day-recall, +7 lift** against a
loss-matched null (65% of sessions ended negative after it fired, against a 58%
base rate for "after any loss"). It is the highest-volume alerting detector and
the only one with signal stacking.

---

## 1. What the behaviour actually is

**Re-entering the market so soon after a losing trade that the new position is a
reaction to the loss rather than an independent decision.**

Three things must be true for the word "revenge" to be honest:

1. a loss occurred that was **meaningful to this trader**,
2. the next entry was **fast relative to how they normally re-enter**,
3. the new position shows **recovery intent** — bigger, or the same instrument,
   or into a session already down.

Timing alone is not revenge. A trader who re-enters every 4 minutes all day is
not taking revenge forty times; that is their tempo.

**What it is not:** a rule about a rupee amount, and not a prediction. "You
re-entered 90 seconds after a loss 3× your usual" is true regardless of what
happens next.

---

## 2. Measurement dimensions

Per the taxonomy — these are *dimensions*, not engine layers.

| dimension | used for | denominator | available at |
|---|---|---|---|
| **Trader-relative** | is this loss / gap / size unusual **for them** | own distribution (percentile) | ~20 losses, ~20 gaps |
| **Trade-relative** | how much of *this position* was lost | capital at risk (`estimate_capital_at_risk`) | trade 1 |
| **Account-relative** | how much of the *account* this damaged | equity / capital | trade 1, needs capital |
| **Sequence** | did the reaction follow the trigger | gap, ordering, instrument identity | trade 2 |
| **Instrument** | is the risk figure meaningful | long option = premium; futures/short = SPAN | trade 1 |
| **Constitution** | trader's own declared cooldown | `cooldown_after_loss` | day 1 if set |
| **Policy** | may it interrupt | cap, mute, staleness | always |

---

## 3. The two layers

### 3a. Safety floor — never learns, fires for anyone

> **Normal ≠ safe.** A trader who has re-entered inside 60 seconds of a heavy
> loss two hundred times has not made it safe. The floor must not be reachable
> by the personal layer.

Fires when **both**:

- the prior loss was **≥ 5% of account equity** *(illustrative)*, **and**
- re-entry occurred within **2 minutes** *(illustrative)*

No history required. No personalisation may suppress it. If capital is unknown,
this layer **abstains** rather than substituting a guess — it does not fall back
to a rupee figure.

Rationale for account-relative here specifically: the harm this layer exists to
prevent is *account destruction*, and that is the one thing capital genuinely
denominates. The user's own example — ₹20k account, ₹10k loss — must alert with
zero history.

### 3b. Behavioural layer — learns, needs maturity

Signals, each independently observable:

| signal | measure | illustrative trigger |
|---|---|---|
| meaningful loss | percentile of own losing trades | ≥ p60 |
| fast re-entry | percentile of own loss→re-entry gaps | ≤ p25 |
| size escalation | capital-at-risk ÷ own median | ≥ 1.5× |
| same underlying | parsed symbol identity | exact / same underlying |
| session already red | session P&L | < 0 |

Deliberately **no fixed rupee or minute value anywhere in this layer.**

---

## 4. Severity and confidence are different axes

**Severity = potential harm if the behaviour is real.**
Driven by account impact and size escalation, not by how sure we are.

| severity | condition *(illustrative)* |
|---|---|
| `critical` | safety floor breached **and** new position ≥ 25% of equity |
| `danger` | safety floor breached, **or** ≥ 3 behavioural signals with size escalation |
| `caution` | ≥ 3 behavioural signals without size escalation |
| `info` | 2 signals — recorded as evidence, never notified |

**Confidence = certainty the detector identified it correctly.**
Driven by signal count, sample size behind each percentile, and data quality.

The existing implementation already separates these — it computes a stacked
confidence and gates alerting at 50 — but currently derives severity partly from
the same signals. **The contract requires them fully separated:** a 95%-confident
low-harm re-entry is `caution`; a 60%-confident potentially account-ending one is
`danger` and escalates.

---

## 5. Maturity and abstention

Per-metric, not one global flag.

| state | condition | behaviour |
|---|---|---|
| **Objective-only** | < 10 losses **or** < 10 gaps observed | safety floor **only**. Behavioural layer abstains — it does not guess a baseline from three points. |
| **Learning** | 10–30 observations | safety floor + behavioural signals shrunk toward the prior by `confidence = n/30`. Copy says "our starting estimate". |
| **Mature** | > 30 observations | full behavioural layer, percentiles trusted. |
| **Insufficient** | required input missing/stale | abstain. Emit nothing, not a low-confidence guess. |

**Abstention is a first-class outcome.** The detector returning `None` because it
does not know is correct behaviour, not a failure to be papered over.

Today's implementation violates this: `_typical_loss` needs 3 losses and falls
back to a flat ₹500 floor, which is exactly the invented threshold this contract
forbids. Under the contract it would abstain instead.

---

## 6. Baseline contamination

The re-entry-gap baseline is the vulnerable one: revenge sequences are *fast*, so
learning from them drags "normal" downward until nothing looks fast any more.

Rules:
- trades belonging to a **confirmed** revenge sequence do not train the gap
  baseline;
- percentiles over **median/MAD**, never mean — one 40-second gap must not move
  the estimate;
- **two windows** — long-term (~60 sessions) and recent (~15 trades). Divergence
  between them is itself a finding: *"your re-entry pace has halved this month"*
  is a different and better alert than any single trade.
- baseline movement is **capped per period**, so a bad week cannot redefine
  normal.

---

## 7. Data required, and what happens when it is missing

| input | source | if missing |
|---|---|---|
| prior trade `realized_pnl`, `exit_time` | `CompletedTrade` | abstain |
| current `entry_time` | `CompletedTrade` | abstain |
| `avg_entry_price`, `total_quantity`, `instrument_type`, `direction` | `CompletedTrade` | size-escalation signal unavailable; others still evaluate |
| account equity | broker margin | **safety floor abstains**; behavioural layer unaffected |
| own loss / gap distributions | baseline | objective-only mode |
| `cooldown_after_loss` | profile | ignored — it is an override, not a requirement |

All trade fields above exist on `CompletedTrade` today. **Equity does not** —
it is the one genuinely new dependency, and it gates only the safety floor.

---

## 8. False positives this must not produce

| scenario | why it looks like revenge | required defence |
|---|---|---|
| Multi-leg entry (iron condor) | 4 entries seconds apart after a losing leg | strategy-group suppression (**exists**) |
| Scalper's normal tempo | 90-second gaps all day | percentile of *their own* gaps — 90s is their p50, not p25 |
| Hedging a loser | fast, same underlying, larger | opposite direction, and net exposure falls |
| Re-entry after a *scratch* | fast and same instrument | loss below their p60 → not meaningful |
| Systematic re-entry at a level | fast, same instrument, bigger | **no defence available.** Intent is unobservable — accept as a known false positive rather than pretend otherwise |
| Market-wide event | everyone re-enters fast | out of scope; noted, not handled |

---

## 9. What the trader sees

Evidence first, never a bare score.

**Critical (safety floor + heavy size):**
> **You re-entered 40 seconds after losing ₹10,000 — half your account.**
> This position risks a further ₹5,000.

**Danger (behavioural, mature):**
> **You re-entered 90 seconds after a ₹3,000 loss, at 3.2× your usual size.**
> Your typical gap after a loss is 11 minutes.

**Caution (behavioural, learning):**
> **You re-entered 2 minutes after a loss, faster than usual.**
> Based on 14 trades so far — our estimate of your normal pace will sharpen.

Every clause is a fact about this trader. Nothing forecasts.

---

## 10. Test personas — must be evaluated against all

| persona | expected |
|---|---|
| ₹5k scalper, 40 trades/day, 90s gaps | behavioural layer near-silent; safety floor only on genuine account damage |
| ₹20k options buyer, 3 trades/day | both layers active; the ₹10k-loss case is `critical` on day one |
| ₹50k intraday, our reference book | approximately current behaviour: ~26 alerts/year |
| ₹5L active F&O | safety floor rarely fires; behavioural layer does the work |
| ₹50L trader | account-relative floor almost never fires — correct |
| Swing trader, 2 trades/week | gap distribution is in hours; a 2-hour re-entry may be their p25 |
| Consistently losing trader | **the key test.** Behavioural layer may go quiet as losses become "normal"; the safety floor must keep firing. If it does not, this contract has failed. |

---

## 11. Open questions

1. **Equity source.** Kite margins are per-account and move intraday. Which
   figure denominates the safety floor — opening equity, available margin, or
   declared capital? Affects every account-relative rule, not just this one.
2. **Do the floor's two numbers (5% / 2 min) need deriving, or are they
   genuinely universal?** The contract's own logic says a safety floor should not
   be personalised — but that does not make the numbers self-evident.
3. **Should the floor be able to reach the accountability partner** when the
   limit it references was never declared? Carried over from the
   `session_meltdown` decision.
4. **Cost of the change.** Current `revenge_trade` fires 26 times a year at +7
   lift. This contract will change that number. We should decide in advance what
   would count as an improvement — more recall, fewer false positives, or
   earlier warning — because otherwise any outcome can be rationalised.
