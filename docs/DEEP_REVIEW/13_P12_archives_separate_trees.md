# P12 — Archived & Separate Trees (findings)

> Scope: `_archive/` (root + `backend/app/**/_archive` + `src/**/_archive`), `design_v2/`, `prototype_design/`,
> `scroll-loss-experience/` (separate Next.js app), `docsreview*` (docs → P13). Per your "everything" call I
> verified reachability/build-inclusion/secrets rather than line-auditing dead code. **Findings-only.**

## Verdict
The archive discipline **works** — archives are properly isolated and unreachable. The three separate/dead trees are confirmed dead and are **removal candidates** (repo bloat, esp. the committed Next.js build cache).

## Findings

### 🟡 P2 · Dead/separate trees confirmed removable (repo bloat) · dead-code
- `design_v2/`, `prototype_design/`, `scroll-loss-experience/`: **zero references** from `vite.config`, `tsconfig*`, `package.json`, or `src/` (grep clean). Not part of the app build.
- `scroll-loss-experience/` is a **separate Next.js app** with its **own `node_modules/` AND committed `.next/` build cache** (`.next/cache/webpack/*.pack.gz`, server manifests) in git → **repo bloat + build artifacts tracked** that should never be committed. → remove from the repo (or move to its own repo) and add `.next/`+`node_modules/` to ignore if kept.
- **No secrets** in any dead tree (grep clean).
- Root stray docs `AUDIT_FINDINGS.md`, `DESIGN.md` → handled in **P13**.

## ✅ Solid (credit) — the archive discipline is clean
- `_archive/` is **excluded from typecheck** (`tsconfig.app.json: "exclude": ["src/**/_archive/**"]`) **and eslint** (`eslint.config.js: "**/_archive/**"`).
- **No live file imports from any `_archive`** (grep across `src` + `backend/app` clean) → archived code is genuinely unreachable, not lurking in the build. The "move to `_archive`, don't delete" rule is implemented correctly.
- Archived backend routers/services confirmed unmounted (P0/P6).

## Ledger (feeds DEAD_CODE_LEDGER + P15)
Removal candidates: `scroll-loss-experience/` (separate app + committed `.next`), `design_v2/`, `prototype_design/`, `AUDIT_FINDINGS.md`, `DESIGN.md`. Archives (`_archive/*`): keep as-is (correctly isolated) or prune later — no risk either way.
