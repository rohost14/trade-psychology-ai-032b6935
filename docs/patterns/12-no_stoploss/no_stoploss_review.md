# Pattern 12 — `no_stoploss`

**Review, 29 Aug 2026. CLOSED — MODIFIED.**

Points 1 and 2 below were approved and implemented the same day (`8d3c632`);
the firing set is unchanged at 52 alerts / 42 sessions. Points 3 and 4 remain on
[`PENDING_AND_TODO.md`](../../DEEP_REVIEW/PENDING_AND_TODO.md).

Review-order 12. Source-list #13 in
[`BEHAVIOURAL_PATTERNS.md`](../00-shared/BEHAVIOURAL_PATTERNS.md), where it is
recorded as *"IMPLEMENTED, NOT VERIFIABLE from tradebook — needs live order
data"* and **skipped from the replay as UNJUDGEABLE**. So it has no firing
history at all; every number below is new.

Measured by [`p12_stoploss.py`](../_measurement/p12_stoploss.py) and
[`p12b.py`](../_measurement/p12b.py) against the real book — **175 sessions,
740 completed rounds** — running the real detector in process.

---

## What it claims

> `NIFTY2570325500PE: manual exit after 37min with 36% loss of premium
> (₹2,212). **No stop-loss order detected on this trade.**`

Registry: `nature=risk`, `disposition=alerting`, `trigger=exit`, v1.0.0.

---

## 1. It is not a Pattern 9. The gates work.

Pattern 9 was retired for never withholding — it fired on 55 of the 55
positions it could judge. This one withholds heavily, and each gate does real
work:

| gate | remaining | excluded |
|---|---|---|
| all completed rounds | 740 | |
| CE/PE/FUT | 740 | 0 — the book is entirely derivatives |
| a loss | 434 | 306 |
| survived the SL gate | 434 | **0 — see §3** |
| held ≥ 5 min | 326 | 108 (**25%**) |
| loss ≥ 25% of entry value | **52** | 274 |

**Firing rate: 52 of 434 judgeable losses = 12.0%.** Across **42 sessions**,
**14 danger / 38 caution**.

The 25% gate is genuinely selective — only **13.4%** of losses clear it:

```
loss as % of entry value, n=434
  p10  2.0   p25  4.2   median  8.9   p75 17.3   p90 30.2
  >=10%  45.4%     >=20%  20.7%     >=25%  13.4%     >=50%  4.1%
```

The 5-minute hold excludes a quarter of candidates; median hold is 15 min.

**Neither gate is a rubber stamp.** That is the substantive difference from
Patterns 9 and 10, and it is why this review does not end where those did.

---

## 2. It catches trades nothing else catches

The coverage test that retired Patterns 9 and 10 gives the opposite answer here.

| | |
|---|---|
| co-fired with at least one other detector | **37 / 52 (71%)** |
| **fired alone** | **15 / 52 (29%)** |

What else fires on them: `revenge_trade` 37% · `premium_loss_event` 25% ·
`options_premium_avg_down` 25% · `same_symbol_obsession` 25% ·
`martingale_behaviour` 10%.

The 15 nobody else sees are ordinary, real losses:

```
TITAN25APR3360CE        21min   -1,452   36.4%
SENSEX2552081500CE      28min   -4,362   53.6%
DIXON25MAY17500CE      248min   -1,120   27.3%
NIFTY2570325500PE       37min   -2,212   36.2%
NIFTY25D1625850PE       26min   -1,080   44.7%
```

**A trade held 4 hours into a 27% loss with no other detector firing is a real
gap in the book, and this is the only thing that sees it.**

---

## 3. But its headline sentence cannot be checked

The alert ends *"No stop-loss order detected on this trade."*

That is derived from **the exit fill's order type**, via `exit_order_types` →
`exit_trade_ids`. In this book, order type is absent for every fill, so the
claim was **checkable on 0 of 52 alerts**. The SL gate withheld **0 of 434**
judgeable losses — not because the gate is broken, but because it had nothing
to read.

On the live path it was worse than unread. **F1** (fixed 29 Aug) means
`exit_trade_ids` held Kite order ids while the consumer matched `Trade.id`
UUIDs, so the lookup matched nothing and the list was **structurally empty for
every live trade**. Every `no_stoploss` alert ever raised in production asserted
"no stop-loss detected" from a list that could not have contained one.

**And even now that F1 has landed, the exit fill answers a different question:**

| question | answerable |
|---|---|
| *"was this exit executed by a stop order?"* | **yes**, post-F1 — a fact about the fill |
| *"did the trader have a resting stop-loss?"* | **no** — needs the order book |
| *"did the trader ignore their stop-loss?"* | **no** |

A trader holding a resting SL who exits manually first shows `MKT` and is told
they had no stop — the inverse of the truth. The detector's own comment calls
that edge case *"benign"*. It is not benign; it is the alert being confidently
wrong at exactly the moment the trader was being disciplined.

The order book **is** available from Kite and our `Order` model can hold it.
`sync_orders_to_db` syncs all statuses correctly — but runs only from two manual
endpoints, the real-time path filters to `COMPLETE`, and **no detector reads the
`orders` table.**

---

## 4. The weekly-expiry branch is a no-op

```
normal  : loss >= 25%   hold >= 5 min
expiry  : loss >= 25%   hold >= 5 min      <-- identical
monthly : loss >= 20%   hold >= 5 min
```

`no_stoploss_expiry_loss_pct` and `no_stoploss_expiry_hold_min` equal their
normal counterparts exactly. The entire `elif is_expiry:` arm selects the same
trades the `else` would have.

It is not cosmetic-only: **23 of the 52 firings route through it** and are
labelled `"(expiry day)"`, which tells the trader a different standard was
applied when none was. 27 normal, **23 expiry**, 2 monthly.

---

## 5. Consequence runs backwards, and it is significant

Rest-of-session P&L after a flagged trade, against an unflagged loss that
cleared every gate but the loss percentage:

| test | flagged | comparison | difference | p |
|---|---|---|---|---|
| raw | **+₹296** | −₹518 | **+₹815** | **0.024** |
| only where session remained | **+₹467** | −₹673 | **+₹1,140** | **0.025** |
| matched on loss size (15–25% vs ≥25%) | **+₹296** | −₹594 | **+₹890** | **0.020** |

**The trader does better after a flagged trade, not worse**, and it survives
both confounds — position-in-session (flagged trades sit slightly later, 0.554
vs 0.472, and 37% are the day's last against 23%) and loss magnitude.

**This ranks the detector; it does not condemn it.**
`docs/BEHAVIOUR_SYSTEM_DESIGN.md` is explicit that an alert's job is to convert
an automatic action into a deliberate one, **not to predict**, so rest-of-session
P&L cannot judge the product — only `heeded` can, and only live. Three
independent framings agreeing is still worth recording: whatever this detector
selects, it is not a run of trades that go on to get worse.

---

## 6. Two filed defects, checked

**F13 — REFUTED. My own filing was wrong.** It was recorded as *"`opening_5min_trap`
admits futures then computes `loss_pct` only for CE/PE, so the large-loss branch
is unreachable"*, and the same claim was carried against `no_stoploss`. Reading
the code: the `else` branch computes `capital_at_risk` for futures via
`estimate_capital_at_risk`, and `loss_pct` is computed **after** the branch, for
both. Futures can reach the loss branch. The item was marked *reported* rather
than verified in the consolidated report — it should not have been carried
forward as a defect.

**F4 — confirmed, inert on this book.** The CE/PE denominator is
`entry_price × qty`, which is premium **paid** for a buyer and premium
**received** for a writer, with `direction` referenced zero times. Exactly
**1 of 52** firings is a short option, because the book is 911 LONG against
1 SHORT. It is a real defect that this book cannot exercise.

---

## 7. Verdict — recommend **MODIFY**, not retire

The three previous retirements each rested on the detector having nothing of its
own: Pattern 9 never withheld, Pattern 10's claim was ordering and lost to a
shuffle null, Pattern 11 could not separate a reversal from a change of view.

**None of that applies here.** The gates withhold, the selection is 12% not
100%, and 29% of firings are trades no other detector sees. What is wrong is one
sentence.

| | |
|---|---|
| **selection** | sound — keep it |
| **assertion** | unsupported — must change |
| **expiry branch** | dead — remove or give it a real threshold |
| **denominator** | F4, direction-blind — pending a decision |

**Proposed** (nothing implemented, awaiting approval):

1. **Say what is true.** Post-F1 the honest claim is about the *exit*: *"exited
   manually at a 36% loss after 37 minutes"* — measurable, and it drops the
   unverifiable stop-loss assertion. The behavioural claim is not lost, it is
   **deferred** to the order book.
2. **Resolve the expiry branch** — either give weekly expiry a threshold that
   differs from normal, or delete the arm and the `(expiry day)` label with it.
3. **F4 stays pending.** The direction-aware denominator is a decision, not a
   fix, and it is already on the register.
4. **Order-book route stays RESEARCH FURTHER.** Making `orders` available to
   detectors would restore the full claim — *"you had a stop at X and exited at
   Y instead"* — and is the only thing that would.

**Not recommended:** retiring it. That would give up the 15 trades nothing else
catches in order to remove one sentence.

**Open question for you:** point 1 changes what the alert says, which is a
product decision about what the trader is told. Point 2 is a defect with a
choice in it. Neither should be implemented on my judgement alone.
