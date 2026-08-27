# Measurement scripts

The scripts behind the Pattern 9 and 10 reviews. Kept so every number in those
reviews is reproducible rather than merely asserted.

| script | what it measures |
|---|---|
| `p9_expiry.py` | Pattern 9 — firing counts by branch, the contracts-vs-lots units bug, the 13:00 gate, and the two trader-facing claims |
| `p9b.py` | Pattern 9 — message mislabelling, permutation significance, the 85% claim, trade-number correlation |
| `p9c.py` | Pattern 9 — whether a units fix would rescue it, day-level tests, expiry vs non-expiry days |
| `p10_size.py` | Pattern 10 — firings, the window question, "while losing" base rate, **the shuffle null**, outcome test, threshold sensitivity |
| `p10b.py` | Pattern 10 — headline mislabelling, replay overlap, the strictly-increasing gate vs chance |

## Running them

```bash
cd D:/trade-psychology-ai
python docs/patterns/_measurement/p10_size.py
```

They read the real tradebook CSV (gitignored) directly and run the **real
detectors** in-process. No database, so they are safe to run while a replay is in
flight.

`p10b.py` imports the helpers from `p10_size.py` with
`exec(src.rsplit("\nmain()", 1)[0])` — everything is defined, nothing runs.

## Two traps these scripts exist to document

1. **Validate the harness before trusting it.** `martingale` v2.0.0 returns a
   `DetectorResult`, which wraps *positive* findings as well as negative ones.
   Treating every `DetectorResult` as non-firing silently reported it covering
   0 of 42. The correct predicate is **`DetectorResult.fired`**. Always check raw
   in-process counts against the replay's alert counts first.
2. **`adding_to_adverse_position` cannot be measured here at all** — it reads a
   fill sequence the CSV reconstruction does not carry. A zero from it is a tool
   limit, not a finding.
