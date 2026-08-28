# Hand-over — Patterns 9 and 10, 27 Aug 2026

Written mid-flight because the machine may power off. Everything below is either
committed or reproducible from this file. **Read this first, then
`docs/patterns/README.md`.**

---

## TL;DR — state of play

| | status |
|---|---|
| **Pattern 9 `expiry_day_overtrading`** | **RETIRED, code complete, tests green, confirmation replay green — ONE open item: the `death_spiral 20 → 16` reconciliation** |
| **Pattern 10 `size_escalation`** | **RETIRED, code complete, regression tests written but NOT YET EXECUTED, replay NOT YET RUN** |
| **Pattern 11 `direction_instability`** | not started. **Do not start until 9 and 10 are closed** (explicit user instruction) |

**Counts now: 24 detectors, 30 pattern types.** `all_pattern_types()` is the
authority. Retirements to date: 4 `consecutive_loss_streak`, 6 `profit_giveaway`,
9 `expiry_day_overtrading`, 10 `size_escalation`.

---

## THE ONE OPEN BLOCKER — Pattern 9's `death_spiral` −4

### What happened

The Pattern 9 confirmation replay ran clean, 203/203, zero errors:

```
TOTAL                          330 -> 298   (-32)
expiry_day_overtrading          28 ->   0   (-28)   <- intended
death_spiral                    20 ->  16   ( -4)   <- NOT YET EXPLAINED
every other detector          identical
```

`adding_to_adverse_position` 99, `martingale_behaviour` 39,
`options_premium_avg_down` 30, `size_escalation` 30, `same_symbol_obsession` 22,
`fomo_entry` 19 — all unchanged.

### Why −4 is not yet accepted

`death_spiral` counts **distinct nature-domains with a danger+ event**, needs ≥2
(`behavior_scores_service.py:evaluate_death_spiral`,
`spiral_domain_min_severity = "danger"`). `expiry_day_overtrading` was
`nature="emotional"`, so removing it can only reduce spirals — the *direction* is
structurally correct.

**But the magnitude does not reconcile against evidence in hand.** An independent
in-process run found only **2 danger-severity expiry firings** in the whole book,
which can cost at most 2 days their emotional domain — not 4.

Ruled out already:
- **Not wall-clock noise.** `evaluate_death_spiral`'s `now` parameter is assigned
  and never used; the function is deterministic.
- **Not `continued_escalation`.** That gates only the *critical* tier, not
  whether it fires.

**Leading hypothesis (unproven):** `death_spiral` reads **BehaviorEvents**, not
alerts. Expiry's dedup (24 h, one caution→danger escalation) hides extra danger
*events* behind a single danger *alert*, and the replay's own CompletedTrade
construction differs from the CSV reconstruction used in-process — so the replay
plausibly produced more than 2 danger expiry events.

### How to settle it — the run that was in flight

A **pre-change baseline replay** was running in a git worktree when this was
written. It had reached ~127/203.

```bash
# the worktree (detached at 567cd6c = the Pattern 8 commit, pre-Pattern-9)
C:/Users/being/.claude/jobs/33a73186/tmp/baseline_p8

# if it is gone, recreate:
git worktree add C:/Users/being/.claude/jobs/33a73186/tmp/baseline_p8 567cd6c --detach
cp backend/.env  C:/Users/being/.claude/jobs/33a73186/tmp/baseline_p8/backend/.env
cp .env          C:/Users/being/.claude/jobs/33a73186/tmp/baseline_p8/.env

# run it (CSV is gitignored, so point at the main checkout's copy)
cd C:/Users/being/.claude/jobs/33a73186/tmp/baseline_p8
python -u tradedesk/scripts/replay_tradebook.py \
  "D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26.csv" \
  --capital 200000 --no-rules > /path/to/replay_baseline.log 2>&1
```

It writes `docs/tradebook-CY6001-FO2025-26-replay.json` **inside the worktree**.
Then diff it against the post-change result, which is saved at:

```
C:/Users/being/.claude/jobs/33a73186/tmp/after_p9.json
```

(The repo copy is **gitignored** — `.gitignore:110 *-replay.json` — which is why
the original baseline was lost when the Pattern 9 run overwrote it. Always copy
the artifact aside before re-running.)

Reconciliation script: for each of the 4 days that had `death_spiral` before and
not after, print both days' full alert lists and the domains present. Each lost
day must show an **emotional-domain danger+ event supplied only by
`expiry_day_overtrading`**. If any lost day cannot be explained that way, the
retirement is not clean — **stop and report, do not commit the closure**.

### ATTEMPT 1 FAILED — 27 Aug ~23:15

The baseline run reached **145 of 203** and died on
`socket.gaierror: [Errno 11001] getaddrinfo failed` — the machine's network
dropped and Supabase became unreachable. **No `*-replay.json` artifact was
written**, so there is still no baseline to diff against. Nothing about the code
is implicated; DNS resolved normally again afterwards.

**HAZARD — read before the next replay of any kind.** That killed run left
**partial synthetic rows in the shared database**. Any replay started without
clearing them will produce wrong counts that look like a code regression:

```bash
# ALWAYS do this first after a killed replay
rm -f tradedesk/.replay.lock
python tradedesk/scripts/replay_tradebook.py   docs/tradebook-CY6001-FO2025-26.csv --capital 200000 --wipe
```

`--wipe` prints what it removed (behavior_events / risk_alerts /
completed_trades / ledger_entries / trades / sessions / strategy_groups). Only
then start the real run.

### ATTEMPT 2 FAILED — 28 Aug ~10:53

Died at session **10/203**: the background task was killed (machine slept). No
artifact. Partial rows wiped afterwards.

Note on process checking: `Where CommandLine -like '*replay_tradebook*'` **matches
the probe command itself** and will report a phantom process. Filter on the full
path — `'*tradedesk/scripts/replay_tradebook.py*'` — or you will conclude a run
is alive when nothing is.

### A CHEAPER ROUTE WAS TRIED AND DOES NOT WORK

`evaluate_death_spiral(events)` is a pure function over a day's BehaviorEvents,
so the mechanism looked reproducible in-process: run every detector over the book
with the pre-change worktree engine, then evaluate death_spiral with and without
expiry's events. Script: `tmp/ds_reconcile.py`.

**It returned delta 0, and that number is worthless.** The harness produced only
**8** spiral days against the replay's **20**. Cause:
**`adding_to_adverse_position` yields 0 in any CSV-based harness** — it reads a
fill sequence the reconstruction does not carry — and it is a **`risk`**-domain
detector with 99 alerts in the replay. `death_spiral` needs >=2 danger+ domains
and its danger tier requires `capital_at_risk` ("risk" present), so losing that
detector guts the very interaction under test.

**Conclusion: only a real replay can settle the -4.** Do not accept an
in-process death_spiral number.

### ATTEMPT 3 FAILED — 28 Aug ~11:00. STOPPING.

Died at session **1/203**, no errors in the log, process simply gone. The three
attempts reached **145 → 10 → 1**: each one is killed sooner than the last, and
none failed on anything in the code. **This machine cannot currently hold a
2-hour replay.** Partial rows wiped; the database is clean.

**Do not simply retry.** Three runs cost ~3 hours and produced nothing. Before
attempt 4, change something about the environment:

- disable sleep / hibernation and screen-lock for the duration
  (`powercfg /change standby-timeout-ac 0`), and keep the machine on mains
- confirm the network stays up (attempt 1 died on a DNS failure)
- run it in a plain terminal outside the agent harness, so no task lifecycle can
  reap the child — this is the likeliest cause of attempts 2 and 3
- then follow the wipe-first procedure in the HAZARD box above

### If it reconciles

1. `cd backend && python -m pytest -q --ignore=tests/production` (expect
   **1,479+** passing, 0 failed — `tests/production` needs a live server and its
   ~35 `ConnectError` failures are pre-existing and unrelated)
2. `npm run typecheck && npm run lint && npm run test` (expect clean, 0 errors,
   102 tests)
3. Fill in the replay table in
   `docs/patterns/09-expiry_day_overtrading/STATUS.md` (section *"Replay — 203
   sessions"*, currently a placeholder)
4. Update `docs/patterns/README.md` row 09 to **RETIRED / COMPLETE**
5. Commit and mark CLOSED

---

## Pattern 10 — what still has to happen

The code is done and committed. **Nothing has been executed against it.**

1. **Run the tests** — `backend/tests/test_size_escalation_retired.py` (25 tests,
   never run). Expect failures only from my own mistakes in the test file, not
   from the deletion; fix the tests, never the code.
2. **Run the 203-session replay.** Expected: `size_escalation` **30 → 0**, plus a
   `death_spiral` fall as arithmetic (it co-fired on 9 of its 30 days). Anything
   else moving means the run failed.
3. Fill in the *"Replay — 203 sessions"* placeholder in
   `docs/patterns/10-size_escalation/STATUS.md`
4. Update `docs/patterns/README.md` row 10 to **RETIRED / COMPLETE**, commit

**Note:** the two earlier retirement tests (`test_profit_giveaway_retired.py`,
`test_expiry_day_overtrading_retired.py`) pin absolute detector counts and were
updated to **24 / 30**. Every future retirement must update them again — this is
a known brittleness, not a bug.

---

## Replay operating rules — every one learned the hard way tonight

- **`Start-Service Memurai`** (Redis) first and verify with a `ping`. A stopped
  Redis once made a replay take 72 minutes to reach session 5.
- **Run `python -u`.** Without it, redirected stdout block-buffers and the log
  sits at 0 bytes — a healthy run looks identical to a hung one.
- **Never pipe through `tail`** — it buffers until exit.
- **Never run pytest against the same database concurrently.**
- **Never run two replays at once.** They serialise, deadlock, and the symptom
  looks exactly like a code regression.
- **`tradedesk/.replay.lock` exists to prevent that — do NOT delete it to clear
  the way.** Tonight a `nohup … &` child outlived the task that reported
  "completed"; the lock was deleted on the assumption the process was dead, and
  two replays ran against one database. Check first:
  `Get-CimInstance Win32_Process | Where CommandLine -like '*replay_tradebook*'`.
  If a run was killed, `--wipe` the partial synthetic rows before restarting.
- **Do not use `nohup … &`** for the replay. Use the harness's own background
  mode so the process is actually tracked.
- **Budget 40 min – 2 h**, depending on DB latency and what else is on the CPU.
  The docstring's 15 min is wrong.
- **Copy the artifact aside before re-running** — it is gitignored and will be
  overwritten.

---

## Method notes worth keeping

### The shuffle null is the standing first test

For any detector whose claim is about **ordering** or a **running total**:
preserve each session's trades, sizes and P&L, permute only the order, and run
**the real detector** inside the loop. It has now retired three patterns:

| pattern | observed | shuffled | verdict |
|---|---|---|---|
| 4 `consecutive_loss_streak` | 63 sessions | 63.0 expected | chance |
| 6 `profit_giveaway` | 49 | 56.3 | chance (fired *less*) |
| **10 `size_escalation`** | **42** | **49.7, p = 0.880** | **chance (fired less)** |

### Validate any in-process harness before trusting it

`martingale` v2.0.0 returns a `DetectorResult`, which wraps **positive** findings
as well as negative ones. A coverage check that treated every `DetectorResult` as
non-firing silently reported martingale covering **0 of 42** — completely wrong.

**The correct predicate is `DetectorResult.fired`** (`evidence.verdict is
Verdict.POSITIVE`). Always sanity-check raw in-process counts against the
replay's alert counts before drawing conclusions:

```
martingale_behaviour        raw 48   replay 39   OK
post_loss_recovery_bet      raw  9   replay  5   OK
options_premium_avg_down    raw 60   replay 30   OK
adding_to_adverse_position  raw  0   replay 99   HARNESS LIMIT — needs position_fills
```

`adding_to_adverse_position` **cannot** be measured from the CSV reconstruction
at all; it reads a fill sequence that harness does not carry.

### Measurement scripts

Kept in `C:/Users/being/.claude/jobs/33a73186/tmp/` (job-scoped, **not durable**):
`p9_expiry.py`, `p9b.py`, `p9c.py`, `p10_size.py`, `p10b.py`. Re-derivable from
the review documents, which contain every number and the method.

---

## Recorded, NOT fixed — for later reviews

1. **`opening_5min_trap` carries the same defect class Pattern 9 was retired
   for** — *"NSE data: 78% of retail opening-5-min derivative trades are
   unprofitable"*, sourced to the same archived document
   (`docs/archive/PATTERN_REFERENCE.md`) that gave the retracted 85% expiry
   claim. **Check this claim when that pattern is reviewed.**
2. **The copy contract does not cover detector messages.**
   `test_copy_carries_no_invented_statistics` checks `PatternCopy.observes` and
   `.explanation` only — which is exactly why Pattern 9's registry copy was clean
   while its shipped `message` carried two fabricated statistics.
3. **`AlertDetailSheet.tsx:208` pastes raw `alert.message` into the AI coach
   prompt.** Whatever the engine writes becomes model context. Deserves a policy
   decision.
4. **Family consolidation is per-trade, not per-session.** Two members of one
   family firing on different trades in a day both reach the trader — the family
   ordering was written to prevent exactly that. Affects all remaining families.
5. **`demoData.ts` gives `size_escalation` `critical`/`danger` severities** it
   could never emit (always `caution`). The vocabulary contract checks fixture
   severities are *in* the vocabulary, not that a detector can produce them.
6. **`martingale_behaviour`'s displayed sequence includes the current trade while
   its deciding `max_ratio` does not** — already on the tracker, still open.
7. **`sl_percent_futures`** is still read by no detector.
8. **Pattern 12 `no_stoploss` stays exit-only** — live stop-loss state needs the
   `TRIGGER PENDING` order events `order_stream_service` discards.
9. **`ENGINE_BACKLOG` M0** — `pattern_prediction_service` writes five prediction
   keys naming patterns the engine cannot emit.

---

## Review queue after 9 and 10

11 `direction_instability` → 12 `no_stoploss` (blocked, see above) →
`session_meltdown` (ON HOLD).

**Standing review protocol** (user's, unchanged): review first → measure against
the corrected 189-session / 912-position book → no code until the behavioural
decision is justified → explicit approval before implementing. Deliverable
sections: *Current behaviour · What is correct · Problems found · Evidence ·
Recommended behavioural contract · Exact changes required · Verdict*.
