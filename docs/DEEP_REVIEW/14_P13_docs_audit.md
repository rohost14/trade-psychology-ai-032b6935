# P13 — Docs Audit (findings)

> Scope: 132 markdown docs (`docs/**`, `docsreview*`, root `*.md`). **Honest depth:** I verified the
> **always-loaded authoritative doc (`CLAUDE.md`)** against code line-by-line for its factual claims, and
> **categorized** the rest of the corpus (most is quarantined history). I did **not** line-audit all 132 —
> `docs/architecture/*` deep-verify is deferrable. **Findings-only** (per the rule, no doc edits without approval).

## Verdict
Doc hygiene is reasonable — history is correctly quarantined under `docs/archive/`. The one **material** problem: **`CLAUDE.md` (loaded as authoritative project instructions every session) is stale in its architecture sections**, so it actively misleads.

---

## 🟡 P2

### DOC1 · `CLAUDE.md` architecture sections describe the PRE-v2 system · doc-stale (high-impact)
> ✅ **FIXED 2026-07-26** — rewrote the "Behavioral Pattern Detection" section (single backend engine, 28 detectors, per-CompletedTrade, `AlertContext` fetches-not-detects) + "Key endpoints" (`money-saved`→`behaviour-cost` factual, `/behavioral/` = live-engine summary, added `/my-record/`). No more "detection client-side" / "estimated costs" / old-8-patterns.
`CLAUDE.md` is the project instruction file loaded every session — its staleness propagates. Verified-wrong claims:
- **Line 92:** *"Detection runs client-side in `AlertContext` using trades from API… estimated costs."* — **false on two counts:** detection is **backend-only** (BehaviorEngine; `AlertContext` is backend-driven, per its own line 53 which contradicts line 92), and costs are **realized P&L, not "estimated"** (violates the raw-P&L/no-counterfactual rule the same file states elsewhere). *(= FE4.)*
- **"Behavioral Pattern Detection" section (lines ~84-92):** lists the **old 8 patterns** from the removed frontend `patterns.ts` (`overtrading`, `revenge_trading`, `loss_aversion`, `fomo`, `no_stoploss`, `early_exit`, `winning_streak_overconfidence`, `position_sizing`) — **not** the **28-detector** registry (`detector_registry.py`) of engine v2. Describes a deleted architecture.
- **"Key endpoints":** references renamed/removed routes — `/api/analytics/money-saved` (P5's endpoint inventory has **no** such route; superseded by `behaviour-cost`), and blowup-shield paths (replaced by `my-record` per the project's own history).
**Fix (highest-priority doc change):** rewrite the "Behavioral Pattern Detection" + "Key endpoints" + line-92 sections to match engine v2 (28 detectors, backend-only, realized-P&L framing). The auto-`MEMORY.md` is already current — `CLAUDE.md` lags it.

## ⚪ P3
- **DOC2** Empty cruft dirs `docsreviewscreens/` + `docsreviewsessions/` (0 files) → remove. Root stray `AUDIT_FINDINGS.md` + `DESIGN.md` → archive (D12). `docs/CODEBASE_AUDIT.md` is **superseded** by `docs/DEEP_REVIEW/` — mark it historical.
- **DOC3** Already-logged stale docs (fix with their code): `pnl_calculator` docstring (M4/D17), `SCALABILITY_REVIEW_10K.md` B2 (already patched, C2), `behavior_engine.py` "single source of truth" claim (E1).

## Corpus categorization (for the record)
- **`docs/archive/` (~100 files):** historical audits/plans/session logs — **correctly quarantined**; keep as history, do not trust as current, no action.
- **`docs/architecture/` (9):** SYSTEM_ARCHITECTURE (2200 lines) + ARCHITECTURE/CELERY_SCALE/KITETICKER/etc. — describe the live system; **partially stale by the project's own admission** ("repo docs can be stale — verify against code"). Verify before relying; not line-audited here.
- **`docsreview/` (14):** implementation plans + behavioural-engine design docs + page reviews — reference material.
- **3 planning docs** (`PLATFORM_ROADMAP_AUTH_PAYMENTS`, `PRODUCTION_READINESS_CHECKLIST`, `SCALABILITY_REVIEW_10K`): forward-looking plans, not code-describing (so "stale" applies less); SCALABILITY already corrected (C2). These + this DEEP_REVIEW feed P15.

## ✅ Solid (credit)
`README.md` is **correct** — "Backend: FastAPI (Python)" (definitively answers the earlier "is the backend JS?" question: it is Python). History is quarantined under `docs/archive/` rather than deleted or left mixed with current docs. The auto-`MEMORY.md` tracker is kept current.

## For P15
Top doc action: **refresh CLAUDE.md's architecture sections** (DOC1) — it's the highest-leverage doc because it's loaded every session. Then the cruft cleanup (DOC2) rolls into the dead-code pass.
