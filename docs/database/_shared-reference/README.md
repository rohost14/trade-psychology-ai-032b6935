# Shared Reference — used by every phase

**Not a work phase.** This folder holds the parts of the audit that are
*operationally* needed while fixing, as opposed to being findings themselves.

It exists because six audit sections carry no findings but are not therefore
useless — they are what makes the remediation executable and verifiable:

| audit § | role in the remediation | where it lives now |
|---|---|---|
| **§2** Exact Database Inventory | the **frozen baseline** to diff against | `BASELINE.md` (this folder) |
| **§25** Evidence / Methodology | the **queries that found each defect** | `VERIFICATION_QUERIES.md` (this folder) |
| **§21** Findings by Severity | prioritisation input | consumed → `../REMEDIATION_INDEX.md` §2 phase map |
| **§22** Findings by Classification | grouping input | consumed → phase assignment |
| **§23** Recommended Follow-up Order | sequencing rationale | consumed → `../REMEDIATION_INDEX.md` §2 |
| **§1** Executive Summary | onboarding context for anyone picking up a phase cold | read it first; not duplicated here |

§21, §22 and §23 are genuinely absorbed — they became the phase structure, and
duplicating them would create a second source of truth that could drift from the
index. §2 and §25 were **not** absorbed, and that was a gap: without them,
"re-run the audit query and confirm zero" is not an executable instruction.

---

## How to use this folder

**Before starting any phase:** read `BASELINE.md` and confirm the current
database still matches it. If it does not, something changed outside this plan
and that needs explaining before you fix anything on top of it.

**When closing any finding:** run its query from `VERIFICATION_QUERIES.md`. The
expected result is stated per query. That is the proof, not a green test suite —
the test suite could not see most of these findings, which is why they existed.

**After any phase:** re-run the baseline check. Everything not deliberately
changed by that phase must be unchanged.

---

## Files

- **`BASELINE.md`** — the frozen state at audit time, plus a re-runnable script
  to compare current reality against it.
- **`VERIFICATION_QUERIES.md`** — the exact query behind each finding, with its
  audit-time result and its expected post-fix result.

---

## A caution carried from the audit

Two techniques in `VERIFICATION_QUERIES.md` produced **wrong answers** during the
audit before being corrected. Both are recorded there so the mistake is not
repeated:

1. **`relkind` and `contype` come back as Python bytes reprs** (`b'r'`, `b'f'`)
   through this driver. Comparing them to `'r'` or `'f'` silently matches
   nothing. Decode in SQL, not in Python.
2. **Searching for a table by name alone will wrongly condemn it** — several
   tables are reached only through their ORM class. Always search the table name
   **and** the model class name.
