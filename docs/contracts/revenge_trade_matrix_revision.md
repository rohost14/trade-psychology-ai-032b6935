# `revenge_trade` — revised decision logic

23 Aug 2026. **Proposal. No code.** Implementation is parked in a stash, not
committed. Revises the frozen matrix in response to two flaws implementation
surfaced.

---

## 1. What went wrong, precisely

**Flaw 1 — B0 emitted `info`.** A re-entry ninety minutes after a loss is
"unrelated" by the contract's own wording, and recording an event to say two
trades were unrelated is noise, not evidence. **Settled: B0 → `NOT_DETECTED`.**

**Flaw 2 — a ₹120 scratch loss reached `caution` at B3.** This has *two* causes
and separating them matters, because one is mine and one is the contract's.

### 2a. My implementation error

The contract already defines A1 as *"at least one frame measured the loss and
none reached A2"*. **Measuring a loss does not require S2** — `risk_basis` returns
a comparable denominator for a long option on trade one, so `loss / premium` is
computable today. S2 is only needed to decide whether that ratio is *large*.

My implementation set `a_level` only when a threshold was crossed and left it at
0 otherwise, collapsing "measured, not significant" into "not measured". **A1 was
unreachable by construction.** That is a bug against the contract, not a contract
flaw.

### 2b. The genuine contract gap

Fixing 2a is not sufficient, because the frozen matrix makes the **A0 and A1 rows
identical**. That decision was justified as *"'measured and ordinary' and 'could
not measure' should lead to the same action"* — and it is wrong for exactly the
case you identified: a measured small loss and an unknown loss are different
claims and must not act the same.

---

## 2. The constraint that makes this hard

Without a decided S2, **A1 cannot separate trivial from large.** A ₹120 loss on a
₹10,000 premium (1.2%) and a ₹8,000 loss on the same premium (80%) are both
"measured, and we have no sanctioned rule for calling either one large".

So any rule that lets A1 produce a user-visible alert would have to decide
significance at the moment of use — which is inventing S2 under another name.

That constraint drives the whole proposal.

---

## 3. Proposed change — two cells, no new numbers

### A-axis, restated (definitions unchanged, A1 now reachable)

| level | established when |
|---|---|
| **A0** `unmeasurable` | every magnitude frame abstained — no comparable denominator, no equity, no mature baseline |
| **A1** `measured, unjudged` | at least one frame produced a **measurable value**, and no decided threshold declared it significant |
| **A2** `large` | a decided threshold was crossed — `S2[class]` or `P1` |
| **A3** `account-threatening` | `S1` crossed |

A1 is reached by *measurability*, not by threshold-crossing. That is the
contract's original wording, restored.

### The matrix

| | ~~B0~~ | B1 prompt | B2 targeted | B3 escalated |
|---|---|---|---|---|
| **A3** account-threatening | — | `danger` | `danger` | `critical` |
| **A2** large | — | `caution` | `danger` | `danger` |
| **A1** measured, unjudged | — | `info` | `info` | **`info`** ← changed |
| **A0** unmeasurable | — | `info` | `info` | `caution` |

**Two changes only:**

1. **The B0 column is gone** — it returns `NOT_DETECTED`, so those cells do not exist.
2. **(A1, B3): `caution` → `info`.**

Nothing else moves. No threshold, weight or multiplier is introduced.

---

## 4. Why A1 is quieter than A0, which looks backwards

This is the one counter-intuitive consequence and it deserves the argument in
full, because "we alert more when we know less" is a claim that should be
uncomfortable.

- **A0 means the loss *might* have been large.** Every frame abstained, so we
  hold no number at all. The structural claim — *you came straight back to the
  same underlying with a bigger position after losing* — is all the evidence
  there is, and it is genuinely unambiguous. One `caution` is proportionate.

- **A1 means we hold a number and have no sanctioned rule for judging it.**
  Claiming harm would be deciding significance at the moment of use. The engine's
  standing rule everywhere else is: when the decision has not been made, abstain
  rather than guess. Emitting `info` *is* that abstention — recorded, countable,
  not shouted.

So the asymmetry is not "less knowledge, louder alert". It is: **structure alone
can carry a claim; a number we are not licensed to interpret cannot.**

## 5. What this costs, stated plainly

**A genuinely large measured loss will produce `info`, not `caution`, until S2a
is decided.** An 80%-of-premium loss followed by an escalated re-entry is exactly
the case this detector exists for, and it will be recorded and not shown.

That is a real reduction in coverage and I am not going to dress it up. Its
merit is that it makes S2a's absence **visible as lost coverage** rather than
hidden behind a threshold nobody chose. The detector says "I measured this and
have no rule" instead of quietly inventing one.

**Replay consequence.** The tradebook is overwhelmingly long options, which are
measurable, so almost every alert will land at A1 → `info`. **I expect
`revenge_trade` to produce close to zero visible alerts on the 40-session replay.**

That is the outcome I flagged as "a finding about the matrix, not a success", and
under this proposal it is the *expected* outcome rather than a surprise. It is
also the strongest possible argument for deciding S2a.

---

## 6. The alternative, and why I do not recommend it

**Make (A0, B3) `info` as well**, so the detector is uniformly silent until a
threshold exists. Fully consistent, and removes the asymmetry in §4 entirely.

I do not recommend it because it deletes the cold-start guarantee: a brand-new
trader on a spread or an unclassifiable instrument would get nothing at all from
this detector, and (A0,B3) is the cell that was validated specifically as the one
that fires on day one. Keeping it preserves a floor of protection for the case
where we truly cannot measure.

If you prefer uniform silence, it is one cell and I will change it.

---

## 7. Not changed

- The lattice join on both axes — an abstaining frame still cannot lower a level,
  personal history still cannot lower one.
- B0–B3 membership rules, including B3 as a plain inequality with no multiplier.
- Declared-rule breach as a `caution` floor, never `danger` on its own.
- Severity and confidence remain separate.
- S1, S2a–d, P1, M1, B1 remain unresolved and each frame still abstains alone.

## 8. Shared legacy recorded

**`_typical_loss` stays.** `revenge_trade` no longer calls it, but
`profit_giveaway` does (`behavior_engine.py:2805`). It is session-scoped and
presented as personal — a real defect — but removing it now would change a
detector outside this review.

Recorded as **shared legacy logic, to be addressed in `profit_giveaway`'s own
pattern review.** Whichever review touches it last should delete it.
