# Exposure hierarchy — user rule vs universal safety

**1 Sep 2026. INVESTIGATION ONLY. NO CODE. NO NUMBER CHOSEN.**

---

## 0. Two corrections to my own earlier passes, first

**(a) The 5% / 10% thresholds were NOT calibrated to notional.** My design pass
said *"they were calibrated against notional; against capital requirement they
describe a different distribution"*. **Wrong for these two.** Their source
comment says `capital-at-risk`, and `excess_exposure` **already uses
`capital_requirement`** — `behavior_engine.py:2031` calls
`quantities_for_trade()` and reads `rq.capital_requirement.amount`, with the
`usable_for_capital_rules` abstention.

**So `excess_exposure`'s quantity is already correct.** The quantity defect is
`overexposure`'s alone, and the numbers at risk of being invalidated are its
10/15/30/50 — not the 5/10.

**(b) That means answer 4 below is "nothing changes"**, which reframes the whole
question you asked.

---

## 1. Provenance of 5% / 10% — the four commits

| commit | what it did |
|---|---|
| `008e6af` | introduced with the source comment below |
| `e91ec58` | gave every threshold a provenance |
| `08e7596` | F1 — classified them `Kind.UNIVERSAL_SAFETY` |
| `de863d9` | added the safety **bound**, because a declared 40 loosened the line to 40/80 |

The source comment, verbatim:

```python
# Kelly criterion for 45% win rate, 1.5:1 R:R -> ~13% optimal, half-Kelly = 6%.
# SEBI: profitable traders averaged 4-6% per trade; loss-makers averaged 20-50%.
'max_position_pct_caution':  5.0,   # 5% capital-at-risk = caution
'max_position_pct_danger':  10.0,   # 10% capital-at-risk = danger
```

**One of those two references is real; the other is not verifiable.** Kelly is a
formula and the arithmetic checks. **The SEBI claim has no source anywhere in the
repository** — and it is the *fourth* instance of that exact shape, after
`expiry_day_overtrading` (which **shipped** unsourced statistics to traders),
`winning_streak_overconfidence`'s hot-hand claim, and the averaging-down "3×"
claim removed at Pattern 20. `PENDING_AND_TODO.md` already records *"three
instances is a pattern, not three accidents"*. **This is the fourth.**

**What they protect against:** one position consuming a large share of the
account, for a trader who has declared no rule of their own.

---

## 2. THE CONFLICT YOU DESCRIBED EXISTS IN PRODUCTION TODAY

Reproduced against live `resolve_thresholds`, capital ₹1L:

**Trader declares `max_position_size = 40`:**

```
resolved caution 5.0  danger 10.0
  [Source.FLOOR] held at the safety bound 5 - this would otherwise have
  resolved to 40. a universal-safety threshold is its own bound: it may be
  tightened for you, never loosened

  position 35.0% of capital -> excess_exposure DANGER  | user rule: within rule
  position 40.0% of capital -> excess_exposure DANGER  | user rule: BREACH
  position 45.0% of capital -> excess_exposure DANGER  | user rule: BREACH
```

**At 35% the trader is inside their own declared rule and is told DANGER.** That
is exactly your example, and the alert cannot distinguish 35% from 45% — both are
simply "past 10%".

**Trader declares `max_position_size = 3` (tighter):**

```
resolved caution 3.0  danger 6.0   [Source.CAPITAL] your declared max position size

  position 2.6% -> silent   | within rule    OK
  position 3.0% -> silent   | BREACH         <- the rule is breached, this is silent
  position 3.4% -> CAUTION  | BREACH         OK
```

**The tightening direction works.** The 3.0% gap is not a defect —
`constitution_violation.max_trade_risk` catches exactly that breach with its
0.80 / 1.00 / 1.20 ladder.

**Diagnosis: the bound is doing its job, and the job is wrong.** `de863d9`
prevented a declared value from *loosening a safety line*, which is correct as a
safety rule. What it did not do is decide **what happens to the safety line's
alert when the trader has a looser rule of their own** — and today the answer is
"both speak, and the safety line drowns the rule".

---

## 3. Concept 2 already exists, and it is not `overexposure`

`constitution_violation.max_trade_risk` (`behavior_engine.py:3256-3289`):

| | |
|---|---|
| trigger | the declared `max_position_size` — **no rule, no evaluation** |
| quantity | `quantities_for_trade(...).capital_requirement` — **already correct** |
| abstention | `usable_for_capital_rules`, never substitutes notional |
| ladder | 0.80 approaching / 1.00 breached / 1.20 severe |
| dedup | `_pattern_dedup_key` = `constitution_violation:max_trade_risk`, 24h, severity-escalating |
| copy | *"Your per-trade risk rule breached: X risked 26% of capital (your limit: 15%)"* |

**That is decision 2's "user rule takes precedence" and decision 4's "factual
user-rule violation", already shipped and already correct.**

If `overexposure` also alerts on the declared limit, the two fire on the same
rule, same quantity, same position:

| declared limit | entry-time firings | judged again at exit |
|---|---|---|
| 5% | 820 | same rounds |
| 10% | 453 | same rounds |
| 15% | 215 | same rounds |

**Recommendation: `overexposure` should not be a second detector for the user's
rule.** The gap it can legitimately fill is **timing** — `max_trade_risk` runs on
a `CompletedTrade`, i.e. after the position closed, so **the declared rule is
never enforced while the position is open**, which is the only moment it can be
acted on.

---

## 4. Answers to your six traces

**1. Why introduced?** Initial build, with a Kelly + SEBI comment; classified
UNIVERSAL_SAFETY at F1; bounded at `de863d9` after a declared 40 was measured
loosening the line to 40/80.

**2. What do they protect against?** One position taking a large share of the
account, for a trader with no rule of their own.

**3. Calibrated to the old notional quantity?** **No.** The comment says
capital-at-risk and `excess_exposure` computes `capital_requirement` today. Only
`overexposure`'s 10/15/30/50 are notional-calibrated.

**4. What happens if the quantity becomes `capital_requirement / capital`?**
**For `excess_exposure`, nothing — that is already the quantity.** For
`overexposure` it is a real change, and its own rungs die with the notional.

**5. Should a universal layer remain?** **Genuinely open, and the argument is
finely balanced:**

*For removing it:* it is the thing producing the false DANGER at 35% in §2; its
outcome value is unestablished (my measurement: no trend across 0–25%, n = 10
above 25% with 81% of the effect from one position); half its stated source is
unverifiable.

*For keeping it:* money rules are **opt-in and `None` by default** since
Pattern 24, and `generate_defaults` deliberately returns `None`. So **most
traders will have declared no exposure rule at all**, and removing the universal
layer leaves them with **no single-position signal whatsoever**. That is a real
protection loss, not a theoretical one.

**I am not choosing.** But note the asymmetry: keeping it costs a wrong alert to
traders who *did* declare a rule (§2, fixable by hierarchy); removing it costs
all coverage for traders who declared nothing (not fixable by hierarchy).

**6. Are the old thresholds still semantically valid?** **The quantity change
does not invalidate them** — that was my error in (0a). What is true is weaker
and separate: **they were never validated against outcome**, and one of their two
sources cannot be produced. They are *not invalidated*; they are *unvalidated*.

**7. Would a new number need research/policy?** **Yes.** §Core of the product
design showed the outcome evidence is insufficient at exactly the sizes a
threshold would sit at. A number from this book would be invented.

---

## 5. F&O safety cases

| position | capital requirement | severe-risk safety net today |
|---|---|---|
| **Bought option** | premium — definitional, works on MCX | `premium_loss_event` (40/60/80% of premium), plus the loss is bounded |
| **Long cash equity** | notional delivery value | none, but loss is bounded |
| **Future** | margin — **UNAVAILABLE today** | **none** |
| **Naked short option** | margin — **UNAVAILABLE today** | **NONE — and this is the gap that matters** |
| **MTF / short equity / unresolved** | abstains | none |
| **Multi-leg** | per-leg only, **no grouping invented** | per-leg, overstating |

### The naked-short gap, stated precisely

**`premium_loss_event` is LONG-only** — `behavior_engine.py` gates on
`ct.direction != "LONG"` and returns. So a naked short option has **no
loss-magnitude detector at all**, and:

* its `capital_requirement` is **unavailable** (`position_margin_observations` is
  empty, 0 rows), so it abstains from every capital rule too;
* its `denominator_kind` is `MARGIN_POSTED` — *loss NOT bounded by what was
  committed* — so even a perfect margin figure would not describe its risk;
* it is therefore the **one instrument the system currently says nothing about,
  and the one where the loss is unbounded.**

**Your "exceptional severe-risk condition" belongs exactly here**, and it must be
a **separate safety concept**, never worded as a breach of the trader's own rule —
because it isn't one. **It also cannot be built today**: it needs either live
margin, live mark-to-market on an open short, or both. **Recorded as future work,
not proposed.**

**Coverage lost for futures / naked shorts if `overexposure` stops using
notional:** on the reference book, 4 futures entries and 1 short option — 5 of
1,071 (0.5%). **But that is this trader's mix, not a general rate.** A
futures-heavy trader would lose the signal entirely. The honest framing: the
signal being lost was **wrong** (575% of capital), so this is removing a false
alert rather than losing a true one — but the *silence* that replaces it is real,
and only broker-margin capture fixes it.

---

## 6. What I recommend — and it needs your decision

### Proposed hierarchy

```
1. USER RULE declared?
     YES -> constitution_violation.max_trade_risk owns it. ONE evaluation,
             one ladder, one dedup key. The universal line MUST NOT alert
             below the user's own rule.
     NO  -> universal safety layer, IF one is kept (open question 5)

2. SEVERE RISK, regardless of rule -> a SEPARATE safety concept, worded as a
     safety caution and never as a rule breach. NOT BUILDABLE TODAY.

3. UTILIZATION -> information only, always, no ladder, no alert.
```

### How the duplicate should be resolved

**Preferred: `overexposure` stops being a second detector of the user's rule, and
becomes the entry-time arm of the existing one.**

The cleanest mechanism already exists and needs **no change to
`constitution_violation`**: if the entry-time check emits
`pattern_type="constitution_violation"` with `rule="max_trade_risk"`, then
`_pattern_dedup_key` (`constitution_violation:max_trade_risk`, 24h,
severity-escalating) **suppresses the exit-time repeat automatically** unless it
escalates.

**The cost, stated plainly: `overexposure` stops existing as a pattern type.**
That is close to the merge you rejected — so I am **not** treating your "keep two
concepts" as overridden. **If you want `overexposure` to survive as its own
pattern type, the duplicate cannot be resolved without touching
`constitution_violation`, and I will stop rather than do that.**

### What happens with no user rule

Open question 5. Either abstain entirely (no signal for most traders), or keep a
universal layer whose number is **decided, not inherited**. The 5/10 may end up
being that number — but by a decision, not by default.

### Other conflicts found

* **The SEBI statistic is the fourth unsourced claim.** Worth the sweep
  `PENDING_AND_TODO.md` already calls for.
* **`safety_bounds.py`'s rationale becomes partly stale** under any hierarchy
  where the user's rule wins. Its *bound* is still right (a declared value must
  not loosen a safety line); its *implication* — that the safety line should then
  alert — is what is being revisited.
* **`overexposure`'s emotional bump has no equivalent** in
  `max_trade_risk`. Routing entry-time checks through the constitution rule would
  **lose it** unless carried across, and it is the best-motivated part of the
  current detector. **Flagged, not solved.**

---

## 7. Decisions I need before any code

1. **Universal safety layer: keep or remove?** (§4.5 — asymmetric costs.)
2. **If kept, does its number stay 5/10 by decision, or go to research?**
3. **Duplicate resolution: may `overexposure` become the entry-time arm of
   `constitution_violation:max_trade_risk`** — which resolves it with no change
   to the reviewed detector — **or must it keep its own pattern type**, in which
   case I stop?
4. **The emotional bump** — carry it across, or drop it?
5. **Naked-short severe-risk safety: confirm it is future work**, blocked on
   margin capture.

**No code written. Nothing committed to behaviour.**
