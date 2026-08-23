# `confidence_alert_gate` — audit closed

24 Aug 2026. **No code changed.** Status: **absent, and staying absent.**
Global confidence suppression: **DEFERRED.**

---

## What it was

Introduced 14 Jul 2026 in *"Engine v2 Phase 4: detector migration — merges,
splits, confidence, dedup v2"*, in the same commit and the same block as
`signal_points_*`:

```python
'confidence_alert_gate': 50,   # below this: recorded as info, no alert
```

Intent: a detection the engine is not sure about is recorded as evidence but not
shown to the trader.

## It was never engine-wide

Checked across 40 commits of `behavior_engine.py`: **exactly one reader in every
commit of its entire lifetime.** It belonged to `revenge_trade`'s
signal-stacking score, was introduced with that score, and only ever gated that
detector.

The other 26 detectors never referenced it. Its removal changed nothing for them,
because nothing was ever there.

**It was engine-wide only in two pieces of prose:** the constant's own comment,
and my frozen `revenge_trade` contract, which stated *"the gate's
rewrite-to-`info` behaviour applies afterwards as it does today."* That claim was
false when written.

## What actually happened when `revenge_trade` was rewritten

The gate was severity being rewritten by confidence — precisely the conflation
the contract set out to remove. Deleting it there was intended and correct.

What was unintended was the *claim* that it survived elsewhere. It did not exist
elsewhere.

**The demotion it performed is largely reproduced structurally.** The cases it
silenced — few signals, unrelated instrument — are the B1 cells the A×B matrix
already scores `info`, reached by the shape of the evidence rather than by a
number.

## Deliberate separation, not accidental loss

Severity and confidence are now separate by design: severity is a claim about
harm, confidence is a claim about how well we could see it, and neither derives
from the other. The gate was the old coupling.

**A different confidence floor exists and is untouched:**
`ENTRY_CONFIDENCE_FLOOR = 60.0` in `entry_detectors.py`, used to judge which
entry-time detections count as findings for promotion decisions. It never gated
alerts and is unaffected by any of this.

## Verified: no production dependency

```
grep confidence_alert_gate  backend/ src/  (py, ts, tsx, sql)  →  1 hit
```

That single hit is the constant's own definition. No detector, task, API, test or
frontend file reads it. No alert path gates on confidence anywhere.

## One thing left, and it is not fixed here

`backend/app/core/trading_defaults.py:251` still carries the comment
*"below this: recorded as info, no alert"*. **That comment now describes
behaviour that does not exist** and would mislead the next reader.

Not corrected in this pass because the instruction was explicitly no code
changes, and a comment lives in a source file. It should be corrected — or the
constant removed with it — in the next threshold pass. Recorded here so it is not
rediscovered as a surprise.

## Decision

**KEEP ABSENT.** Nothing to restore: it protected one detector that no longer
computes a stackable confidence score, and restoring it literally would mean
reintroducing the points arithmetic that was deleted for good reasons.

**Global confidence suppression: DEFERRED.** The open question — *should a
low-confidence detection be shown at all?* — is real and belongs to the engine,
not to one detector. It should be decided after two or three detectors have been
reviewed and there is evidence about what confidence values actually look like in
practice, rather than from one detector's example.

No global confidence threshold has been created. No new rule has been added.
