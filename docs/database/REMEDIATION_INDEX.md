# Database Remediation — Master Index

**Source of truth for findings:** `DATABASE_ARCHITECTURE_AUDIT.md` — **FROZEN**.
That document is a point-in-time record and is never edited as work proceeds.
Progress is tracked here and in the phase folders.

**Rule:** every finding in the audit appears in exactly one phase below. The
accounting is checked in §4 of this file. Findings that require no action are
still listed, in `phase-9-no-action-register.md`, so that "nothing was left out"
is verifiable rather than asserted.

---

## 1. Finding registry — complete

45 actionable findings. IDs H1–H2, M1–M27, L1–L17.

**IDs M22–M27, L16 and L17 are additions.** M22–M25 and L16 came from the
§3.5/§3.6 resolution pass; **M26, M27 and L17 were found by a completeness
sweep** that cross-checked every audit subsection against the ID registry —
they carried a Classification line in the body but were never picked up into the
§21 severity tables. The §3.5/§3.6 resolution pass was written after
the severity tables in §21, so its findings never received IDs. They are
assigned here so nothing is untracked:

| new ID | finding | audit § |
|---|---|---|
| M22 | `trading_sessions.trade_count` is 0 on every row while `session_pnl` is correct | §3.6a |
| M23 | 13 of 23 trading days have no `trading_sessions` row | §3.6b |
| M24 | 3.5-month behavioural coverage gap, 2026-04-15 → 07-29 | §3.6d |
| M25 | `trades` vs `position_ledger` — two records of the same fill, nothing reconciles them | §20.1 |
| L16 | 22 trades with NULL `fill_timestamp` | §3.6c |
| M26 | Alert lineage is optional (nullable + SET NULL) — cannot tell "never had a trigger" from "trigger deleted" | §4.3 |
| M27 | Partial-commit risk in the ingestion pipeline | §14.8 |
| L17 | Endpoint-usage analysis incomplete — gates any further endpoint retirement | §9.5 |

---

## 2. Phase map

| phase | folder | theme | findings | risk of the work |
|---|---|---|---|---|
| **0** | `phase-0-decisions/` | Decisions only — no code | M1, M4, M5, M16, M24, L6, L12, L15 | none |
| **1** | `phase-1-safety-net/` | Build the checks that would have caught all of this | M9 | none — test-only |
| **2** | `phase-2-data-integrity/` | The two HIGH findings | H1, H2, M18 | **schema change** |
| **3** | `phase-3-correctness/` | Defects inside the live Feb–Jul window | M6, M12, M13, M22, M23, M25, M26, M27, L16 | logic change |
| **4** | `phase-4-security/` | Security + hardening | M17, L9, L10, L11, (M1 impl) | moderate |
| **5** | `phase-5-performance-scale/` | Indexes, N+1, growth protection | M2, M7, M8, M19, L5, L13 | moderate |
| **6** | `phase-6-schema-hygiene/` | Model↔DB drift and missing constraints | M11, L1, L2, L3, L4, L7 | low, high volume |
| **7** | `phase-7-observability/` | Make silent failure visible | M3, M20, M21, (M10 superseded) | low |
| **8** | `phase-8-legacy-retirement/` | Execute Phase 0's retirement decisions | L8, L14, L17, + M5/L6/L12/L15 execution | **destructive** |
| **9** | `phase-9-no-action-register.md` | GOOD, resolved, and do-not-change | M14, M15 + all GOOD findings | none |
| **—** | `_shared-reference/` | Baseline + verification queries used by every phase | audit §2, §25 | none |

**Sequencing rationale:** Phase 0 first because ~8 findings are decisions, and
fixing before deciding wastes work. Phase 1 second because it is the only
zero-risk phase and it produces the means to *prove* every later phase. Phase 8
last because it is destructive and depends on Phase 0's answers.


---

## 2b. Owning phase — where the work actually happens

Several findings appear in more than one phase folder. That is deliberate: a
decision in Phase 0 links forward to the phase that executes it. **The owning
phase below is the single place the work is done**; other mentions are
cross-references.

| ID | owning phase | also referenced in | note |
|---|---|---|---|
| H1 | 2 | 1, 6, 7 | 6 lists it in the drift census; 1 and 7 as what would catch it |
| H2 | 2 | 1, 7 | |
| M1 | 4 | 0 | decision D2 gates the implementation |
| M2 | 5 | 1 | Phase 1 baselines it at 21 groups |
| M3 | 7 | — | |
| M4 | **8** | 0 | D3 = RETIRE, so no model sync needed |
| M5 | 8 | 0 | D1 = retire; **unblocked** (M16 withdrawn) |
| M6 | 3 | — | |
| M7 | 5 | — | |
| M8 | 5 | — | |
| M9 | 1 | — | |
| M10 | superseded by M20 | 7, 9 | first-pass figure, do not use |
| M11 | 6 | — | settle L7 first |
| M12 | 3 | — | |
| M13 | 3 | 5 | investigation in 3; M19 in 5 depends on the answer |
| M14 | 9 | — | resolved; re-verify when reconnected |
| M15 | 9 | — | resolved |
| M16 | **WITHDRAWN** | — | audit error: matched a variable name and comments, not table access |
| M17 | 4 | 7 | |
| M18 | 2 | — | part of the H1 fix |
| M19 | 5 | — | depends on M13's answer |
| M20 | 7 | 9 | supersedes M10 |
| M21 | 7 | — | |
| M22 | **1** | 0, 3 | D8 = already fixed; verification only |
| M23 | 3 | — | |
| M24 | **3** | — | D4 = backfill Feb-Jul |
| M25 | 3 | 5 | |
| M26 | 3 | — | same family as H2, M13/M25 |
| M27 | 3 | — | investigate alongside M6 |
| L17 | 8 | — | gates R7; no further endpoint retirement without it |
| L1, L2, L3, L7 | 6 | — | |
| L4 | 6 | 8 | disappears if M5 retires |
| L5 | 5 | 8 | 6 of 8 moot if M5 retires |
| L6 | 8 | 0 | decision D5/D7 |
| L8, L14 | 8 | — | |
| L9, L10, L11 | 4 | — | |
| L12 | 8 | 0 | decision D6 |
| L13 | 5 | — | |
| L15 | 8 | 0 | decision D7 |
| L16 | 3 | — | |

**Completeness verified programmatically:** 43 IDs expected, 43 placed, 0
missing.

---

## 2c. Where the non-finding audit sections went

Six audit sections carry no findings. They are **not** unused — each has an
operational role, and two of them were initially left unabsorbed, which would
have made "re-run the audit query" unexecutable:

| audit § | role | now lives in |
|---|---|---|
| §2 Exact Database Inventory | frozen baseline to diff against | `_shared-reference/BASELINE.md` |
| §25 Evidence / Methodology | the queries that found each defect | `_shared-reference/VERIFICATION_QUERIES.md` |
| §21 Findings by Severity | prioritisation input | consumed into §2 phase map above |
| §22 Findings by Classification | grouping input | consumed into phase assignment |
| §23 Recommended Follow-up Order | sequencing rationale | consumed into §2 and §5 |
| §1 Executive Summary | onboarding context | read directly; deliberately not duplicated |

§21/§22/§23 are intentionally **not** copied — duplicating them would create a
second source of truth that could drift from this index.

---

## 3. Validation strategy — how each phase is proved

Verified available before writing this plan:

- **`alertlab/runner/harness.py` → `lab_environment()`** — patches Redis with a
  fake and runs Celery eager, so `.delay()` executes the **real task body
  inline**. Full ingestion → ledger → engine → alert with no worker and no Redis.
- **`frozen_clock()`** — deterministic time for date-dependent behaviour.
- **`ensure_lab_account()` / `teardown_lab()`** — fixed synthetic identities
  `LAB000001` / `DESK00001`, cleaned between runs.
- **`alertlab/runner/inject.py`** — drives `process_webhook_trade` /
  `persist_order_event` directly.
- **`tradedesk/scripts/replay_tradebook.py`** — replays the 203-session
  reference book (`docs/tradebook-CY6001-FO2025-26.csv`, 2,175 fills) through
  the whole engine.
- **`backend/tests/test_adverse_add_integration.py`** — existing proof that the
  real pipeline can be driven synthetically end to end: *"Nothing is
  monkeypatched. Fills go in; a RiskAlert row is asserted."*

**Standard proof for every phase:**

1. Re-run the exact audit query that found the defect — it must now return zero.
2. Synthetic replay through `lab_environment()` before and after the change;
   compare alerts, events and row counts.
3. Full backend suite (2,492 tests at the time of the audit) plus Phase 1's new
   drift checks.
4. The 203-session tradebook replay as the regression backstop — six months of
   real trading shapes, no live account required.

**What synthetic testing cannot cover** — these need a live Zerodha connection
and must be validated separately, whenever the account is next connected:

- OAuth login and the token-exchange round trip
- Real postback delivery and Zerodha's own checksum
- Live KiteTicker WebSocket ticks
- Real margin API responses
- Token expiry/refresh against the broker

---

## 4. Completeness check

```
Findings in the audit with an assigned ID .......... 38  (H1-H2, M1-M21, L1-L15)
Findings added by the §3.5/§3.6 resolution pass ....  5  (M22-M25, L16)
                                                    ----
Total ID space ..................................... 48  (H1-H2, M1-M27, L1-L17, N1-N2)
  N1/N2 found during Phase 0 investigation, not in the audit
  placed in a phase folder ......................... 46
  missing .......................................... 0   <- verified by script
  in phase 9 (resolved / no action) ................. 3  (M10 superseded, M14, M15)

Second check, independent of IDs: all 103 audit subsections were scanned and
cross-referenced against the phase folders. Every subsection carrying an
actionable Classification is claimed. The only unclaimed match is the parent
header S3.6, whose four children (3.6a-d) are claimed as M22, M23, L16, M24.
```

Verified by walking every phase README for every ID rather than by assertion.

Every GOOD / GOOD WITH NOTE finding and the entire §24 "Do Not Change Yet" list
is carried in `phase-9-no-action-register.md`.

---

## 5. Status

| phase | state |
|---|---|
| 0 | **COMPLETE** — all 8 decided and approved 2026-09-04 |
| 1 | **COMPLETE 2026-09-06** — 45 tests, test-only. See `phase-1-safety-net/README.md` under BUILT |
| 2 | NOT STARTED |
| 3 | NOT STARTED — **carries one live defect found by Phase 1**: `persist_order_event` raises `NameError` on every call, so `orders` has never received a row. One line |
| 4 | NOT STARTED |
| 5 | NOT STARTED |
| 6 | NOT STARTED |
| 7 | NOT STARTED |
| 8 | READY — all retirement decisions recorded |

Phase 1 is implemented; it changed no production code, no schema and no data.
Everything else is unimplemented and the audit remains frozen.

**Three audit figures were corrected by re-measurement during Phase 1**, and the
measured value is what later phases should use:

| figure | audit | measured 2026-09-06 |
|---|---|---|
| model/DB drift items | 127 | **88** — 41 of the audit's "type mismatches" were rendered-string artefacts, not differences |
| FKs into `broker_accounts` | 37 | **37**, confirmed — but only excluding partition children; 80 with them |
| duplicate index groups | 21 | **14** — a partial index is not a duplicate of a full one on the same column |

The 88 live in `backend/tests/_schema_baseline.json`, each tagged with the phase
that owns it: **1 to Phase 2, 61 to Phase 6, 26 to Phase 8.**
