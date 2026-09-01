# Do the behavioural detectors work without money rules?

**1 Sep 2026. INVESTIGATION ONLY. NO CODE CHANGED.**

The principle under test: **user-configured money rules are optional guardrails,
not prerequisites for the rest of the engine.**

Method: five configurations × every active detector × the real 175-session /
740-round book, running the real detectors in process.
`docs/patterns/_measurement/p25_money_rule_independence.py`.

`trading_capital` was held **constant** across the five, because it is not one
of the three money rules — it is a separate onboarding field. It is then varied
on its own in §5, and that is where the one finding worth acting on appears.

---

## 1. The answer: yes

| | |
|---|---|
| active detectors in the registry | **17** |
| detectors that fire on this book | 14 |
| **detectors identical across all five configurations** | **12** |
| detectors that move | **2 — both by design** |
| **leaks (one money rule changing another rule)** | **0** |

```
  detector                             A none B daily only  C per-trade   D exposure  E all three
  adding_to_adverse_position               64           64           64           64           64
  end_of_session_mis_panic                  1            1            1            1            1
  excess_exposure                         231          231          231          231          231
  fomo_entry                               32           32           32           32           32
  martingale_behaviour                     26           26           26           26           26
  no_stoploss                              52           52           52           52           52
  overtrading_burst                        26           26           26           26           26
  post_loss_recovery_bet                    7            7            7            7            7
  premium_loss_event                       17           17           17           17           17
  rapid_reentry                            14           14           14           14           14
  revenge_trade                           182          182          182          182          182
  same_symbol_obsession                    49           49           49           49           49
  constitution_violation                  431          461          442          431          472   <-- MOVES
  session_meltdown                          0           99            0            0           99   <-- MOVES
```

`time_of_day_bias`, `win_rate_collapse` and `strategy_breakdown` fire **0 times
in every configuration** — they have never fired on this book at all, which is
their own open question (reviews 25–27) and not a money-rule dependency. A
static scan confirms none of the three reads a money rule or capital.

**Every detector named in the brief is independent:** `premium_loss_event` (17),
consecutive losses via `constitution_violation`'s count rule (194, unchanged),
`revenge_trade` (182), `adding_to_adverse_position` (64), `overtrading_burst`
(26), `fomo_entry` (32), `no_stoploss` (52).

---

## 2. What correctly abstains

### `session_meltdown` — 0 without a declared limit, 99 with

Exactly the Pattern 17 decision, still holding: the detector judges the session
against **the trader's own daily loss limit** and abstains when there is none,
rather than deriving one from capital. The `trading_capital × 0.05` fallback was
removed then and has not crept back.

### `constitution_violation` — evaluates only what was configured

```
  rule                             A none B daily only  C per-trade   D exposure  E all three
  cooldown                            181          181          181          181          181
  daily_trades                         56           56           56           56           56
  max_consecutive_losses              194          194          194          194          194
  daily_loss                            0           30            0            0           30
  per_trade_loss                        0            0           11            0           11
```

The three **count/time** rules fire identically in all five. Each **money** rule
fires **only** in the configuration that sets it. This is requirement 5,
verified.

### The leak check

| configuration | expected to change | result |
|---|---|---|
| B — daily only | `daily_loss` | **NO LEAK** |
| C — per-trade only | `per_trade_loss` | **NO LEAK** |
| D — exposure only | `max_trade_risk` | **NO LEAK** |

**Config D was re-run because the first attempt proved nothing.** At 25% of
₹200,000 the rule allows ₹50,000 a trade and the book's largest margin is far
below that, so it fired 0 and demonstrated only that a non-binding rule does
nothing. Re-run at **3% (₹6,000, against a ₹7,580 median margin)** it fires
**532** times — and **still nothing else moves**:

```
  constitution_violation   431 -> 963      (all of it max_trade_risk: 0 -> 532)
  excess_exposure          231 -> 231      unchanged
  every other detector     unchanged
```

---

## 3. The important one: `excess_exposure` does NOT need the exposure rule

This is the case most likely to have been a dependency, and it is not.

`excess_exposure` fires **231 times with no money rules set at all**, using the
**universal safety band** `max_position_pct_caution` 5% / `max_position_pct_danger`
10%. Those are `UNIVERSAL_SAFETY` thresholds, not user rules.

And declaring `max_position_size = 25%` — a *looser* number — **does not move
it**: still 231. The 2026-08-28 safety bound holds a universal-safety threshold
at its own value as a floor, so a trader can tighten it but never loosen it.
Its docstring predicted exactly the failure that bound prevents:

> *"declaring 40 moved the caution line from 5.0 to 40.0 and danger from 10.0 to
> 80.0, so the detector that exists to say 'this position is dangerously large'
> went quiet for exactly the traders taking the largest positions."*

**Over-exposure protection is therefore universal and unconditional**, and the
trader's own rule is an *additional*, tighter promise enforced separately by
`constitution_violation`. That is the architecture working as designed.

---

## 4. Two findings that looked like bugs and are not

### `overtrading_burst` 13 → 26 — the `daily_overtrading` alias, working correctly

Isolated by varying one threshold at a time:

```
  bare defaults                : 13
  + trading_capital=200000     : 13
  + user_daily_trade_limit=10  : 26   <-- the cause
  + max_consecutive_losses=3   : 13
  + user_cooldown_min=15       : 13
```

`overtrading_burst` emits a second `pattern_type`, `daily_overtrading`, which
fires against the trader's **declared daily trade limit**. That is a **count**
rule, not a money rule, and Pattern 5 deliberately made it fire on the declared
limit only. It was held constant across all five configurations, so it does not
affect the question — but it is recorded because the number looks alarming out
of context.

### `revenge_trade` reads `ctx.account_risk` — with zero effect

A static scan flagged it, and it is real: the detector calls
`loss_vs_account(prior_loss, ctx.account_risk)`.

Measured with and without a usable ₹200,000 denominator:

| | firings | severities |
|---|---|---|
| `account_risk = None` | **182** | 166 info, 16 caution |
| `account_risk = ₹200,000` | **182** | 166 info, 16 caution |

**Identical.** The account frame can only record `a_level = 1`, which the
**trade** frame already reaches without any capital figure, and the threshold
that would let it bite — `revenge_account_loss_pct` (S1) — **is not present in
the threshold set at all**. The detector's own comment says so: *"S1 is
unresolved, so it abstains twice over today."*

**This is a documentation defect, not a behaviour one** — see §6.

---

## 5. The one real dependency, and it is NOT a money rule

`excess_exposure` needs **`trading_capital`**, which is a separate onboarding
field, not one of the three rules:

| | firings |
|---|---|
| capital unset, no money rules | **0** |
| capital ₹200,000, no money rules | **231** |

**Every other detector is identical.**

This is **correct abstention** — a percentage of capital cannot be computed
without capital, and the risk layer's rule is that a wrong confident answer is
worse than no answer. But the consequence is worth stating plainly:

> **A trader who skips the capital field gets no over-exposure protection at
> all** — not the universal band, not their own rule. Silently, with no alert
> and nothing on screen saying why.

That is a **product** question about whether capital should be required or
prompted, not a bug in any detector. Recorded, not fixed.

---

## 6. Bugs found

**None affecting behaviour.** One documentation defect:

`EngineContext.account_risk`'s docstring says:

> *"Detectors do NOT read this yet - no detector has been migrated."*

`revenge_trade` reads it. The statement was true when written and is now false.
Its *effect* is nil (§4), so nothing has silently changed — but the comment is
the kind that stops someone checking, and this investigation only found the read
because a static scan contradicted the prose.

**Recommended fix (not implemented):** correct the docstring to say that
`revenge_trade` consumes it for the account frame, that the frame records a
measurement and an abstention rather than gating, and that it cannot influence
severity until `revenge_account_loss_pct` is decided. One comment, no behaviour.

---

## 7. Verdict — the architecture is safe to keep

The principle holds, measured rather than asserted:

* **12 of 14 firing detectors are byte-identical across all five configurations.**
* The 2 that move do so **only** in the configuration that sets their rule.
* **No money rule changes any other rule or any other detector** — verified with
  a binding exposure limit that fires 532 times and moves nothing else.
* **Over-exposure protection is unconditional**, delivered by the universal
  safety band whether or not the trader declares anything, and a declared value
  can tighten it but never loosen it.
* `session_meltdown` and the three money rules abstain cleanly when unset — no
  invented defaults, no derived limits.

**Two things to decide, neither urgent and neither a code fault:**

1. **`trading_capital` is a single point of failure for `excess_exposure`.**
   Skipping it removes the only unconditional over-exposure protection, silently.
   Worth deciding whether onboarding should require it or the UI should say what
   is lost.
2. **The stale `account_risk` docstring** should be corrected before someone
   relies on it.
