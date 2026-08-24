# Adding to a loser is not martingale

24 Aug 2026. **Semantic correction. No detector logic changed by this document.**

Four review documents used "martingale" and "averaging down" as if they named
one behaviour. They do not, and the conflation was mine.

---

## The two definitions

**`adding_to_adverse_position`** — the trader has an **open** position, it is
moving **against** them, and they **increase exposure in it** before closing it.

- The previous position is **still open**. That is the whole premise.
- The size of the add is **irrelevant to whether it happened**. Same-size,
  smaller and larger adverse adds are all the behaviour. In a year of real
  trades 95 of 96 adverse adds were *smaller* than the position held.
- Larger or repeated additions indicate greater intensity, not a different
  event.

**`martingale_behaviour`** — the trader takes a loss, then **escalates risk or
stake on a subsequent attempt**, potentially repeatedly.

- The losing position is **closed**. An open loser is **not required** and is
  not what this measures.
- Escalation is the whole point. Without an increase there is no martingale.
- The unit is the **attempt**, not the fill.

## Why they cannot be merged

They read different objects, and no amount of shared vocabulary changes that:

| | `adding_to_adverse_position` | `martingale_behaviour` |
|---|---|---|
| unit | a **fill** inside one open position | a **completed position** among several |
| requires the position to be | **open** | **closed** |
| size must increase | **no** | **yes** — it is the definition |
| reads | `ctx.position_fills` (PositionLedger) | `ctx.session_trades` (CompletedTrades) |
| fires | on the `INCREASE` fill | at exit |
| trigger | `entry` | `exit` |

A `CompletedTrade` folds every entry into one `avg_entry_price`, so
`martingale_behaviour` **structurally cannot see** an add inside a position.
And the fill sequence of one open position says nothing about what the trader
did after closing a different one. Neither detector can observe the other's
subject.

## The four cases, as tests

`tests/test_adverse_add_lifecycle.py::TestTheTwoBehavioursAreDistinct`

| # | case | adding | martingale |
|---|---|---|---|
| 1 | 75 @50 → +75 @40 → +75 @30, all one position | **fires** | silent — nothing grew, and it is one CompletedTrade |
| 2 | four separate closed positions, 75 → 150 → 300 → 600, each a loss | silent — no position was added to | **fires** |
| 3 | 75 @50 → +150 @40 → +300 @30, one position, adds growing | **fires** | **fires** — both are true |
| 4 | 75 @50 → +75 @60 (in profit); and sizes rising while winning | silent | silent |

**Case 3 is the important one.** Both firing is correct, not duplication: the
trader added to an open loser *and* escalated across attempts. Two true
statements about one session.

## What this changes

Nothing in the code. `adding_to_adverse_position` was built to this definition
already — it never used the 1.5×/2.0× multipliers, and its two axes are
repetition and whether an add was at least as large as the position it was added
to.

What changes is the **documentation**, which in three earlier places said
averaging down and martingale were "the same behaviour at different
intensities". They are not. That sentence is withdrawn.

`martingale_behaviour` is untouched and still carries every defect recorded in
`martingale_behaviour_review.md`: 46 of 58 firings contain a statement the trades
do not show, it misses 22 real escalations, and it needs four completed positions
to fire rather than the three its docstring implies. **Its own review corrects
those against its own definition — escalation across attempts — and not against
this one.**

## Numbering

The reviews were originally ordered with martingale first. Both names now mean
something specific, so:

- **Pattern 1 — `martingale_behaviour`.** Escalation across attempts after
  losses. Semantics to be corrected, then implemented and replay-tested.
- **Pattern 2 — `adding_to_adverse_position`.** Shipped 24 Aug 2026.

They may fire together. They are not merged and neither is deleted.
