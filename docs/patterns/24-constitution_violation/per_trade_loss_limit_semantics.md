# Per-trade loss limit — semantics that must be settled before coding

**1 Sep 2026. SPECIFICATION ONLY. NO CODE WRITTEN. NOT APPROVED.**

Confirmed already:

* `per_trade_loss_limit` — a new **optional** `RULE_FIELD`, denominated in **₹**
* **no suggested or default value**
* `suggested_max_position_size` **removed** (done, see §7)
* ladder stays **0.80 / 1.00 / 1.20** — not changed to 0.60

What follows is the set of questions that must be answered before the rule can
be written, because each has a defensible answer that differs from the others
and the code cannot express two of them at once.

---

## Q1. Realised or unrealised? — **realised, and that is not a free choice**

`constitution_violation` is `trigger="exit"`. It runs from
`BehaviorEngine.analyze()`, once per `CompletedTrade`, after a position has
closed. At that moment the only loss that exists is realised.

**Consequence the trader will notice, and which must be said in the copy:** the
alert cannot arrive while the trade is open. A ₹4,500 loss against a ₹4,000
limit is reported **after** the position is closed, not while it is running.

There *is* a live path — `live_risk_state.py` on the tick stream — which already
raises the trader's declared `sl_percent_options` as a `constitution_violation`
while a position is open. **Putting the per-trade loss limit there as well is a
separate piece of work** with its own failure modes (it needs a live price, it
fires repeatedly as price moves, it needs its own dedup) and is **not proposed
here**.

> **DECISION 1.** Exit-time only for now, with copy that does not imply
> real-time protection. Live-path enforcement recorded as a follow-up.

---

## Q2. Which number is "the loss on a single trade"?

`CompletedTrade.realized_pnl` is the candidate, and for a simple one-in-one-out
position it is unambiguous. The complications are below.

**Sign convention.** The rule is a *loss* limit, so it must compare
`abs(realized_pnl)` **only when `realized_pnl < 0`**. A winning trade can never
breach it. This is the same shape `daily_loss` already uses for the session.

> **DECISION 2.** `realized_pnl < 0`, compared as `abs(realized_pnl) / limit`.

---

## Q3. Partial exits — **the hard one**

A `CompletedTrade` is a **full position lifecycle**: it is written when the
position reaches zero, and `realized_pnl` is the total across every exit fill.
`num_exits` records how many there were.

So a position exited in three tranches produces **one** row with the **summed**
loss. Two readings, both defensible:

| reading | behaviour | argument |
|---|---|---|
| **A — position-level** (proposed) | the limit applies to the whole position's realised loss | The trader's mental unit is "this trade". Scaling out of one losing position is one decision, and three tranche-losses of ₹1,600 against a ₹4,000 limit *is* a ₹4,800 loss on that trade. |
| B — fill-level | each exit tranche compared separately | Would never fire on the example above, letting a position lose any amount provided it is closed in small enough pieces. |

**A is proposed.** B has a defeat that is not merely theoretical: it makes the
rule evadable by exit style rather than by risk taken.

> **DECISION 3.** Position-level. One `CompletedTrade`, one comparison.

**But note what A cannot do:** it cannot warn *during* the scale-out, because the
row does not exist until the position is flat. See Q1.

---

## Q4. Multi-leg and strategy trades — **the ambiguity that needs your call**

`CompletedTrade` is **per `tradingsymbol`**. A four-leg iron condor closes as
**four rows**, each with its own `realized_pnl`.

The engine already knows they belong together: `ctx.strategy_group` carries the
structure and `strategy_group.net_pnl` the combined figure. `session_meltdown`
already consults it — a losing leg inside a net-profitable structure is
deliberately not a meltdown.

Three candidate behaviours:

| | behaviour | consequence |
|---|---|---|
| **i** | compare **each leg** against the limit | A hedged structure fires on its losing leg while the structure as a whole may be profitable. On a ₹4,000 limit, an iron condor whose short leg loses ₹6,000 while the long legs gain ₹5,500 reports a breach on a position that lost ₹500. |
| **ii** | compare the **structure's net** when `strategy_group` exists, the leg otherwise | Matches how a trader thinks about a spread, and matches `session_meltdown`'s existing precedent. Requires deciding which leg *carries* the alert. |
| **iii** | **abstain** on any trade that is part of a strategy group | Honest but silent exactly where sizing mistakes are most expensive. |

**(ii) is proposed**, because the product already made this call once for
`session_meltdown` and consistency is worth more than a fresh judgement here.
But it is genuinely a product decision, not a derivation, and **it needs your
explicit answer** — under (ii) a four-leg structure produces at most one
per-trade-loss alert, and something must decide which leg carries it (proposed:
the leg the engine is analysing when the structure's net first breaches, which
is deterministic but arbitrary).

> **DECISION 4 — OPEN. I will not choose this alone.**

---

## Q5. Futures vs options — no difference, and that is the point

The rule compares rupees to rupees. `realized_pnl` is
`(exit − entry) × qty × multiplier` for every instrument type, so a ₹4,000 limit
means ₹4,000 whether the loss came from a NIFTY future or a bought call.

**No instrument branch is proposed.** This is deliberately unlike
`max_position_size`, which needs the risk layer and abstains where capital is not
determinable — a loss in rupees needs no such machinery and never abstains.

> **DECISION 5.** One rule, all instruments, no branch.

---

## Q6. Charges — **excluded, per the charter, and this one is already settled**

P&L in this system is **RAW only**: `(exit − entry) × qty × multiplier`. No
brokerage, no STT, no taxes, anywhere — a standing project rule.

So a ₹4,000 limit is breached by ₹4,000 of **raw** loss. A trader whose
all-in cost is ₹4,300 will see the alert at the raw figure.

> **DECISION 6.** Raw, consistent with every other number in the product. The
> copy should not imply the figure is net of costs.

---

## Q7. Interaction with the existing rules

Nothing is shared and nothing is changed:

| rule | measures | unchanged? |
|---|---|---|
| `daily_loss_limit` | session realised loss ÷ limit | yes |
| **`per_trade_loss_limit`** | **this trade's realised loss ÷ limit** | new |
| `max_position_size` | capital requirement ÷ capital | yes |

The worked example from the brief behaves correctly with no combination logic,
because `constitution_violation` already returns a **list** and dedups **per
rule**:

```
daily limit ₹10,000, per-trade limit ₹4,000

  a single trade loses ₹4,500   -> per-trade rule, ratio 1.13 -> danger
  several trades total ₹9,000   -> daily rule,     ratio 0.90 -> caution ("approaching")
  total reaches ₹10,000         -> daily rule,     ratio 1.00 -> danger  ("reached")
  total exceeds ₹12,000         -> daily rule,     ratio 1.20 -> critical ("exceeded")
```

A single trade that breaches both produces **two events**, one per rule, which is
the existing behaviour and needs no grouping architecture.

**Note on the ladder's words.** With 0.80/1.00/1.20 retained, "approaching"
begins at 80% rather than the 60% the brief sketched. The three stages exist;
only the first threshold differs. Copy should say what the number is rather than
implying a fixed percentage.

---

## Q8. Where it must NOT double-count

`session_meltdown` also watches session loss against `daily_loss_limit`. It is
already the case that both can speak about the same session; that is existing
behaviour and this rule does not touch it.

**A single trade large enough to breach the daily limit on its own will fire
both the per-trade rule and the daily rule.** That is correct — two different
promises were broken — and per-rule dedup keeps them as two rows rather than a
storm.

---

## What must be decided before any code

| # | question | status |
|---|---|---|
| 1 | exit-time only, no live-path enforcement yet | **proposed** |
| 2 | `abs(realized_pnl)` when negative | **proposed** |
| 3 | position-level, not fill-level | **proposed** |
| 4 | **multi-leg: net vs per-leg vs abstain** | **OPEN — needs your call** |
| 5 | no futures/options branch | **proposed** |
| 6 | raw P&L, charges excluded | **settled by the charter** |

**Q4 is the blocker.** Everything else follows from existing structures or
existing project rules; Q4 is a genuine product choice about what "a trade"
means for a spread trader, and choosing it silently would be exactly the kind of
invented definition the brief forbids.

---

## §7 — what WAS done in this pass

**`suggested_max_position_size` removed** from
`constitution_service.generate_defaults`. It returned `m["risk_pct"]` —
1.0/2.0/2.5/3.0 — a generic risk-per-trade percentage with no standing for F&O.

The onboarding control it fed was rewired rather than deleted: the capital
exposure rule is still offered, still explained, and now takes a number the
trader types, with copy stating plainly that we do not suggest one and why.
Removing the suggestion without that would have left a permanently disabled
checkbox — the same dead-control failure this work exists to remove.

`suggested_daily_loss_limit` is untouched: it is satisfiable at any account size
and is not a per-trade risk percentage.

**`api/cooldown.py:373` was NOT fixed, by the stated condition.** It compares
`data.order_value` — a raw rupee figure supplied by the caller — against
`max_position_size`, a percentage of capital measured on the *capital
requirement*. Correcting it means converting an order into a capital requirement
through the risk layer, including an abstain path when that is not determinable.
That is an implementation, not a semantic tidy, so it is recorded rather than
done. `POST /cooldown/pre-trade-check` has **no callers**, so nothing live is
affected either way.
