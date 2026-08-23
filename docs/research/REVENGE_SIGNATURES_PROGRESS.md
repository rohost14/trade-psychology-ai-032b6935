# Revenge research — live progress and restart instructions

24 Aug 2026. **Research only. No engine code has been changed in this pass.**
The frozen `revenge_trade` detector is untouched.

This file exists so the work survives a closed session or a shutdown. If you are
picking this up cold, read this file, then `REVENGE_TRADING_REVIEW_BRIEF.md`.

---

## Where this stands

| step | state |
|---|---|
| 1. Confidence-gate audit | **DONE** — `docs/contracts/confidence_alert_gate_CLOSED.md` |
| 2. 15 signatures, full book | **collecting** — see restart below |
| 3. The 14-episode problem | **DONE** — root cause found, below |
| 4. Personal ground-truth list | blocked on step 2 |
| 5. Final conclusion | blocked on step 2 |

## If the collection was interrupted, restart it like this

```bash
# from the repo root, ~75 min for 203 sessions. NEVER on a foreground timeout.
rm -f tradedesk/.replay.lock
.venv/Scripts/python.exe tradedesk/scripts/research/signatures.py
```

Writes `docs/research/data/signatures.json`. Then:

```bash
.venv/Scripts/python.exe tradedesk/scripts/research/analyse.py
```

**Two replays at once deadlock** and the symptom looks like a code regression.
Check nothing else is running first:

```bash
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*signatures.py*' }"
```

A parent/child pair for one script is normal — that is the launcher, not two runs.

## What the collector records, and one correction already made

One row per **round-trip**, winners included. The winners are not padding: every
signature is measured after a loss *and after a win*, and **the post-win rate is
the control**. That is what makes the analysis threshold-free — "unusually fast"
means "faster than this same trader after a win", which the data answers by
itself, with no constant invented anywhere.

The first version of the collector recorded losses only. It was killed and
restarted ~12 minutes in, because without the post-win baseline the word
"unusual" could only have been answered by inventing a number.

## Step 3 result — why H2 finds only 14 episodes

**H2's own evidence had a measurement defect.** `exposure_grew` was computed on
quantity:

```python
"exposure_grew": any(b > a for a, b in zip(qtys, qtys[1:]))
```

For options **quantity is not exposure.** 20 lots of a ₹5 far-OTM contract is not
20 lots of a ₹300 one. Clearest case it hid:

> **2025-07-28 SENSEX — 5 attempts, quantity flat at 20 the whole way, capital at
> risk 593 → 5600 (9.45×), −₹3,605.** Recorded as `exposure_grew: False`.

Recomputed on capital at risk:

| exposure measure | episodes flagged | H2 (≥3 attempts) |
|---|---|---|
| quantity growth (as measured) | 32 / 92 | **14** |
| any risk step-up | 54 / 92 | 17 |
| risk higher at end than start | 47 / 92 | 10 |

**Risk-growth is not the fix, and no binary is.** "Any step-up" fires on
9845 → 9940, which is a different strike, not an escalation. The magnitude
distribution shows why:

| max single-step risk multiple, across 92 episodes |
|---|
| p50 **1.03×** · p75 1.43× · p90 2.97× · p95 4.09× · max 9.45× |

One continuous tail, not two populations. There is no gap in it to put a
threshold in, which is the same shape that killed S2a.

**Attempts is the larger filter, not exposure.** 71 of 92 candidates have exactly
2 attempts, so `≥3` alone discards 77% before exposure is consulted.

**Outcome evidence keeps pointing the same way:** 6 of the 10 largest escalations
ended in a win; 8 of the 14 H2 firings ended in a win. Escalation after a loss is
not reliably followed by more loss in this book.

## Signature #13 is unobservable — settled, do not re-attempt

"Loss → abandoning normal rules/stops" cannot be measured from this dataset at
all. The Zerodha tradebook has no order-type column:

```
symbol,isin,trade_date,exchange,segment,series,trade_type,auction,
quantity,price,trade_id,order_id,order_execution_time,expiry_date
```

and the replay never sets one, so `exit_order_types` is empty for all 203
sessions. `_detect_no_stoploss` reads exactly that field. No analysis recovers
it; it would need live order data.

## Standing constraints for this work

- No code. No thresholds. No scores. No detector redesign. No Pattern #2.
- Do not turn a promising observation into a rule.
- **"Observable loss-chasing behaviour" is not "proven revenge trading."** Every
  finding here is about observable behaviour only.
- H2 is one hypothesis among fifteen, not the frontrunner.

## Files

- `tradedesk/scripts/research/signatures.py` — the collector (203 sessions)
- `tradedesk/scripts/research/analyse.py` — the 15 signatures, loss vs win control
- `tradedesk/scripts/research/episodes_full.py` — earlier episode collector
- `docs/research/data/*.json` — collected evidence, kept so claims stay checkable
