# Handoff notes

Written 2026-08-04 by the agent, for the agent. Everything here is stuff that is **not** already captured in `MEMORY.md`, the other `docs/`, or git history — mostly hard-won working method, environment quirks, and observed user preferences. Read this before starting UI work on this repo.

---

## 1. How this user works (observed, not stated)

- **Rejects a card-per-row layout instantly, every time.** It has been called "vibe coded" three separate times. Default to rows on one shared surface, separated by hairlines. But see the next point.
- **Equally rejects flat.** Removing all surfaces got "no depth, no personality, pale". The working answer landed on Journal: **gutter/label sits on the page ground, content sits on a raised surface**, and a low-alpha tint marks the head of a group. Depth from arrangement, not from shadow.
- **Wants references copied, not synthesised.** Every time a reference was named and then blended with my own judgement, the result was rejected. The one attempt that read a reference's actual DOM and followed its section order was the only one that got a neutral response. If they name a product, go look at it and match its structure.
- **Says "do X" and means the whole of X.** "Fix all 5", "port it", "finish it" are literal.
- **Corrects vocabulary precisely and it matters.** "Zero manual input" means *the app must be fully useful with none*, NOT *never offer input*. I got this wrong and it changed the Journal design.
- **Notices unported vs ported and cares.** Always state clearly which is which; never port without explicit approval.

## 2. Verification: what works here and what does not

| Need | Works | Does not work |
|---|---|---|
| Mobile viewport | **An iframe at 390px** — media queries key off the iframe width. Build a throwaway `public/__mobile.html` with iframes per route, screenshot, delete it after. | `resize_window` reports success but `innerWidth` never changes. |
| Is a chart broken? | Screenshot after a **settle delay**. | A screenshot immediately after a tab switch catches recharts mid-animation at zero height and looks exactly like broken data. This produced a whole false P0. |
| Recharts DOM checks | Nothing reliable. | `.recharts-bar-rectangle` is an empty `<g>` **even on charts that render correctly**. Do not build conclusions on it. |
| Page state | `read_console_messages` after a **reload** | Console history is stale; clear or reload first. |
| Layout overflow | `document.documentElement.scrollWidth > clientWidth` inside the iframe | — |

**Never dispatch a synthetic `window.resize` to "test" something.** It mutates page state and every later reading describes a page the user will never see.

## 3. The bug class that keeps appearing

**Guest mode returns `{}` for any unmocked GET.** `{}` is truthy, so `if (!data) return null` passes and the next line dereferences a missing nested field.

Hit **six times**: Habits (`data.sample` → rendered the string "You have ."), behaviour-cost, `BehaviorScoresCard` (`scores.drivers.tilt` → killed My Patterns), `ResponseStatsCard` (`stats.patterns.length` → killed the Alerts Patterns tab), Reports (rendered a plausible-but-false empty state), My Rules (rendered "connect your broker" to a demo user).

**When adding any screen: check `src/lib/guestMode.ts` for a fixture first.** Guard on the field the component actually needs, never on the object being non-null.

## 4. My repeated failure mode

**Broad regex / string replaces that hit more than intended. Four separate times this session**, all caught by typecheck or the browser rather than by me:

- rewrote a module-level `PIE_COLORS` to reference a hook-scoped variable
- mangled an emotion colour map into `bg-tm-profit text-tm-profit /20` and silently skipped `orange` because I only wrote patterns for the four colours I had counted
- a slice that removed a filter row also took the `{loading ? (` opener with it
- a `.replace()` that matched nothing at all and **failed silently** — I then committed and claimed a fix that never shipped

**Rules for next time:** assert the substitution matched; for anything under ~10 entries just write it out by hand; after any sweep, grep for the thing you were removing AND for artefacts you might have created.

## 5. Environment gotchas that cost real time

- **`index.css` applies `@apply text-foreground` to `h1`–`h5` globally.** On a page with its own dark ground, every heading renders near-black on near-black. Set heading colour explicitly on such pages.
- **`formatCurrency` drops the `+` sign.** A positive figure sits next to a negative one and they read as different kinds of number. `formatCurrencyWithSign` for per-trade, `formatCurrencyWhole` (added this session) for period totals where paise are noise.
- **`npx tsc --noEmit` is a no-op here.** Always `npm run typecheck`.
- **Heredocs break on em-dashes and JSX.** Write the Python to a file in the scratchpad and run it.
- Path alias `@/` → `src/`. Backend syntax check: `python -m py_compile`; boot check: `python -c "from app.main import app"`.

## 6. Skills

`.claude/skills/*` were **dangling symlinks** into a deleted `.agents/skills/`. Restored from the sources in `skills-lock.json`:

- `Leonxlnx/taste-skill` → `design-taste-frontend`, `high-end-visual-design`, `redesign-existing-projects`, `minimalist-ui`, `brandkit`
- `nextlevelbuilder/ui-ux-pro-max-skill` → `ui-ux-pro-max` (has a `scripts/search.py --design-system` generator; run it rather than guessing a direction)

**The skill registry loads at session start.** Restoring files mid-session does not register them; a restart is required.

## 7. Landing page — pending, all designs rejected

Six attempts, all rejected. `src/pages/_lab/LandingLab.tsx` at `/landing-lab`; **`src/pages/Welcome.tsx` is untouched and still live.**

Tried and rejected: three partial variants · a page from the repo's own research docs · one built to `design-taste-frontend` · one to `high-end-visual-design` (Soft Structuralism, Double-Bezel, floating nav) · one to `ui-ux-pro-max` (dark bento, gold + purple) · one copying the Lovable structure section-for-section. Last feedback: **"still looks very pale."**

**Do not iterate on any of these.** Get a page the user actually likes and copy it.

**Independent of the design, `Welcome.tsx` still carries three P0 truthfulness problems** (see `docs/LANDING_PAGE_AUDIT.md`): fabricated testimonials with named people and rupee outcomes on a product with zero users, five invented per-pattern costs presented as measured, and a "circuit breakers pause trading … predicts a cascade loss day" claim that is both charter-banned and contradicted by the page's own FAQ. **These need deleting whatever the visual direction turns out to be.**

## 8. Things worth knowing that are easy to miss

- **`GET /api/constitution/effective`** (added this session) returns declared-vs-enforced rule values with provenance. A declared rule only applies when it is *stricter* than the trader's own baseline, so My Rules had been displaying numbers the engine was not using. If anyone ever asks "why did this alert fire when I am under my limit", that endpoint is the answer.
- **`POST /api/risk/alerts/{id}/feedback` existed all along and nothing called it.** That, not user apathy, is why the record read "55 alerts, 0 outcomes". Worth remembering as a lesson: check whether the UI ever calls the endpoint before concluding users do not engage.
- **`LivePositionEngine` + migration 076 are done, applied, tested, and wired to nothing**, parked behind Zerodha multi-user approval and Gate 3. All 26 existing detectors require a `CompletedTrade`, so pre-close detection was new work, not rewiring — do not repeat the claim that it was mostly plumbing.
- The codebase carries **two vocabularies for the same rules** (`daily_trade_limit` on the profile vs `daily_trades` in the status payload), with `RULE_LABELS` mapping both so nobody notices. Logged, not fixed.
