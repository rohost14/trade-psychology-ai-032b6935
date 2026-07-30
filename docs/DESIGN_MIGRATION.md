# Design migration — working file

> **Delete this file when the status table in §7 is green.**
>
> **Nothing here is a design rule.** The rules live in `docs/DESIGN_SYSTEM.md`. This file records only where the code stands against them, what has to change, and in what order. Every number and file reference here rots — that is why it is not in the design doc.

**Two tracks. Read this before doing any work.**

| | **Track A — design (in scope now)** | **Track B — deferred (after design is signed off)** |
|---|---|---|
| What | tokens, type, colour, spacing, containers, icons, motion, copy tone, layout of blocks that already exist, state *design* | removing a feature, merging surfaces, changing what is fetched or computed, fixing logic bugs |
| Test | does it change pixels only? | does it change behaviour, data, or what exists? |

**Anti-pattern violations already shipped get documented, not executed.** The streak card, the score card, the donut, the coach button, the auto-opening journal sheet and the Journal filter rows all stay on screen and get restyled where they are. A design rule the code doesn't satisfy is a target, not a contradiction.

**One consequence, stated plainly:** error and empty states can be *styled* in Track A but **not verified**, because the failure paths still render as empty until the Track B wiring lands. Do not sign off a screen believing its error state was checked.

---

## 1. Current-state audit

Measured across `src/**/*.tsx` (excluding `_archive/`, which is unrouted) on 2026-07-30.

`src/index.css` ships two complete, conflicting systems. That divergence — not the palette — is what makes the app read as inconsistent.

| Concern | v1 (dominant) | Uses | Target | Uses |
|---|---|---|---|---|
| Card surface | `.tm-card` — `rounded-xl`, shadow, **no border** | **240** | per `DESIGN_SYSTEM.md` §9: mostly **no container**; `.desk-card` where justified | 12 |
| Numbers | `.t-mono*` / `font-mono` — DM Mono | **309** | `.font-tabular` — Inter tabular-nums | 59 |
| Screen title | `.t-heading-lg` — 20px | 16 | 22px / 600 | — |
| Display number | `.t-display` — 28px / 700 | 6 | 30px / 600 | 6 |
| Section label | `.tm-label` / `.t-overline` — 11px, `0.07em` | 57 | `.t-label` — 11px, `0.12em` | 4 |

**Raw colour debt:** 721 raw Tailwind palette classes and 11 hard-coded hex values. `tailwind.config.ts` defines **no** `amber-*`, `red-*`, `teal-*`, `blue-*`, `violet-*`, `green-*`, `orange-*`, `purple-*`, `zinc-*`, `emerald-*`, `stone-*` or `slate-*` tokens — every such class is Tailwind's default palette, i.e. debt against the `tm-*` / `tm-status-*` system that already exists and goes almost unused.

Worst live offenders: `components/dashboard/MorningIntentCard.tsx` (58) · `pages/Reports.tsx` (54) · `components/settings/NotificationsTab.tsx` (32) · `pages/Journal.tsx` (22) · `components/patterns/PatternCalendar.tsx` (20) · `pages/Chat.tsx` (18) · `components/dashboard/EodComparisonCard.tsx` (18).

**Dead utilities, 0 uses — safe to delete:** `.page-shell` (also stale, still `max-w-[1400px]` while the layout uses `max-w-7xl`) · `.card-body` · `.stat-value` · `.t-heading-md`.

**Utilities to retire:** `.tm-page-bg` (dark radial gradients) · `.tm-coach-cta` (gradient, and unused) · `animate-float` · `animate-zap-pulse`. Keep `.landing-bg` — Welcome is the one permitted marketing surface, though it too drops gradients per the design doc.

**To re-express in tokens:** `.badge-success/-warning/-danger` and `.tm-chip-ce/-pe/-eq` are defined in raw palette colours.

## 2. Environment gotchas

- **Root font-size is 17px** (`src/index.css`) and must revert to **16px** — the design doc specifies 16. The bump scales rem-based Tailwind (`text-sm` → 14.9px, all spacing) but **not** arbitrary px classes, which is why the two coexist confusingly. **This revert is Track A step 1.**
- Animation utilities (`animate-fade-in-up`, `animate-slide-in-up`, `animate-badge-pulse`) live in `src/index.css`, not `tailwind.config.ts`, which defines only `accordion-down/up` and `pulse-slow`. Verify none are referenced but undefined.
- `tailwind.config.ts` extends no `fontSize` scale — the type utilities are custom CSS classes, not theme tokens, so they aren't discoverable from the config.
- `ui/card.tsx` from the component library is imported nowhere; every card is a hand-rolled div. ~25 other library components are also unused. This is the inverse of the "default library styling" risk — the real problem is 240 one-off surfaces.

## 3. Deprecation map

Mechanical, per screen. **Never a global find-and-replace** — `.tm-card` differs from the target in radius, border, and shadow, and most sites should lose their container entirely rather than swap it (design doc §9).

| Remove | Replace with |
|---|---|
| `.tm-card` | no container (default) — or `.desk-card` where §9 justifies one |
| `.t-mono` / `-sm` / `-lg` / `-display` | `.font-tabular` + a size from the §7 scale |
| `.t-heading-lg` | `text-[22px] font-semibold tracking-tight` |
| `.t-display` | `font-display text-[30px] font-semibold font-tabular` |
| `.t-heading-sm`, `.t-body*`, `.t-caption` | §7 px classes |
| `.tm-label`, `.t-overline` | `.t-label` |
| `.stat-value`, `.stat-label`, `.table-header` | §17 / §18 recipes |
| `.badge-*`, `.tm-chip-*` | semantic tints (`bg-{profit,warning,loss}/10` + matching text) |
| `.tm-page-bg`, `.tm-coach-cta` | flat `bg-background` / `bg-primary` |
| raw palette + hex | §6 tokens |
| rem text classes used for typography | §7 px classes |

Both systems coexist until §7 is green, then the v1 block is deleted from `index.css` in one commit.

## 4. Track A — visual debt

### Shared work, before any screen

These are consumed by every screen and are themselves built on the old card class. **Migrate first or they fight every page.**

- `src/components/ErrorState.tsx` — full-block mode is built on `.tm-card`. Its `classify()` → 7 error kinds is good and stays.
- `src/components/ui/skeletons.tsx` — all five (`CardSkeleton`, `StatRowSkeleton`, `ListSkeleton`, `TableSkeleton`, `ChartSkeleton`) are built on `.tm-card`.
- **New:** a chart colour module that resolves tokens to concrete strings at runtime, per design doc §20. Recharts cannot take classes. Without this, chart colour cannot be themed and the hex problem below cannot be fixed.
- `src/index.css` — 17px → 16px; delete the four dead utilities; retire the gradient and decorative-loop utilities.
- `src/components/Sidebar.tsx` + `src/components/Layout.tsx` — reconcile nav grouping to the one canonical structure in design doc §24. Desktop currently leaves My Rules ungrouped and has no Account group; mobile puts My Rules under Risk and adds Account. Labels and membership must match.

### Cross-cutting visual debt

- **Hard-coded chart hex** `#16a34a` / `#dc2626` as `Cell fill`, `stroke`, and gradient stops in six files: `OverviewTab`, `EdgeTab`, `TradeDnaTab`, `SessionsTab`, `BtstTab`, `InstrumentPanel`. Also `#0d9488` (a reference line in `TradeDnaTab`) and a six-hex `PIE_COLORS` array in `OverviewTab`. These files use `text-tm-profit` for text right beside the literal — the most mechanically fixable debt in the repo once the colour module exists.
- **Micro-type used as body copy:** `SessionsTab` calendar day values at `text-[8px]` and weekday headers at `text-[9px]` · `EdgeTab` at `text-[9px]` and `text-[10px]` · `EdgeLeakCard` at `text-[9px]`. Design doc floor is 10px, table headers only.
- **`TradeDnaTab`** — two percent axes have no explicit `width`, so axis gutters misalign against every other chart.
- **`BtstTab`** — the only chart using raw `formatter` / `contentStyle` instead of a named tooltip component; also the only tab with no `ErrorState` at all.
- **`PatternCalendar`** — the entire severity vocabulary is raw `green-500` / `amber-500` / `red-600`, bypassing tokens; and it uses a bespoke `bg-card rounded-xl border` shell instead of any shared class.
- **`BehaviorScoresCard`** — raw `amber-500` / `amber-600` for the middle severity step only; both ends use tokens.
- **`AiCoachFab`** — raw `from-teal-600 to-teal-700` gradient, bypassing the brand token entirely (invisible to a token-only sweep).
- **`Dashboard`** — two inline bespoke error blocks reimplementing `ErrorState` in place; raw `amber-*` / `red-*` banner colours.
- **`TradeJournalSheet`** — raw `teal-50` / `red-50` / `amber-*` throughout; ad-hoc `rounded-xl bg-muted/40` shells instead of a shared component.
- **Off-spec token spellings:** `NotFound` uses `bg-[rgb(var(--tm-brand))]/10` instead of `bg-tm-brand/10`; `ProfileTab` hard-codes `accent-[#0D9488]` on a range input.
- **`Welcome`** — the single biggest divergence: 701 lines of inline `style={{}}` driven by hand-rolled `LIGHT`/`DARK` const palettes, 43 hard-coded hex values, and its own fonts (Plus Jakarta Sans, JetBrains Mono) injected via a runtime `<link>`. The hero mixes a few real tokens into the inline system inconsistently. Fold onto tokens and the app's faces; composition, copy, and the consent-gated flow stay identical.

### Screen order

Foundation first, then a small screen to prove it, then the hard ones.

1. Shared work above (including the 16px revert and nav reconciliation)
2. **My Record** — 9 containers, zero raw palette, already clean. Proves the container-stripping approach cheaply. **Also add the missing broker gate here** (decided Track A): every other screen gates a not-connected user, this one silently no-ops via an early return, leaving a dead search box. Inconsistent gating costs trust, and shipping a screen known to be broken on a Track-A/B technicality is the wrong call. Copy: *"Connect your broker to view your personal trading record."*
3. **Dashboard** — the reference screen; closest to target, and clears its two inline error blocks.
4. **Alerts** — best severity implementation in the app (`src/lib/alertSeverity.ts`) and it should become the canonical source everything else uses.
5. **My Patterns** — needs `PatternCalendar` re-tokenised.
6. **Analytics** — largest surface, most charts, needs the colour module in place.
7. **Journal**, **Reports** — heaviest de-palette.
8. **My Rules**, **Settings** — the two screens where cards legitimately stay.
9. **Chat**, then **Welcome**.
10. System screens.
11. Delete the v1 block from `index.css`.

## 5. Track B — deferred backlog

**Do not execute any of this during the reskin.** Each item names the rule or bug it represents and the decision it needs.

### Anti-pattern violations (design doc §4)

| Item | Rule broken | Decision needed |
|---|---|---|
| `components/goals/StreakTrackerCard.tsx` — currently the hero of My Patterns | no gamification | cut, or demote to a plain factual clean-day count with no reward framing |
| `components/patterns/BehaviorScoresCard.tsx` — "Behavior Risk" headline + 4 driver bars from `/api/risk/scores` | no invented scores | show the formula in-product, or cut |
| `CompletedTrade.quality_score` — populated by no service; a constant rendered as a number | fake precision | wire it to something real, or remove from all UI |
| `analytics/OverviewTab.tsx` — P&L Attribution donut | no donuts (and it duplicates the Edge leaderboard) | replace with a ranked table; resolves a duplicate story at the same time |
| `dashboard/AiCoachFab.tsx` — floating coach button on every screen | coach-everywhere, no gradients, decorative motion | remove, or scope to screens where it adds value |
| `dashboard/TradeJournalSheet.tsx` — auto-opens 45s after every close | modal overload, zero manual input | stop auto-opening; keep it user-initiated |
| `pages/Journal.tsx` — three filter rows over only the loaded page | unnecessary filters, and they misreport | either filter server-side or reduce to what the loaded data can honestly support |
| `positive` severity treatment; `EdgeLeakCard`'s "No consistent leak — nice." | no praise copy | restate factually |

### Duplicate stories (design doc §25)

1. `ReportCard`'s biggest strength/leak **is** `EdgeLeakCard`'s two columns — same endpoint, same top item, two surfaces.
2. **Time-of-day P&L appears four times:** `EdgeTab` hour-of-day chart · `EdgeTab` "F&O Session Windows" *directly above it in the same tab* · `HabitsTab` time-of-day list · `SessionsTab` hourly breakdown.
3. `OverviewTab` attribution donut vs `EdgeTab` instrument leaderboard — same underlying breakdown.
4. `BehaviorTab` and `SessionsTab` both render conditional-performance cards for the same keys with near-identical markup.
5. `StrategyCard` rows are visually identical to `EdgeTab`'s leaderboard rows.
6. `HabitsTab`'s own header comment says it avoids re-plotting Edge/Advanced — then re-plots time-of-day and instrument.

Plus: **`TradeDnaTab` bundles six unrelated stories** in 447 lines (quality tiers, best/worst five, risk-reward + disposition effect, intraday sequence, hold time, and a searchable 50-row trade log). The trade log in particular is a broker feature and fails the differentiation bar.

### Logic bugs

- **Two conflicting definitions of "clean day" on the same screen** — `MyPatterns.tsx` excludes `'high'` severity from its streak logic; `PatternCalendar.tsx`'s `worstSeverity()` counts `'high'` as danger.
- **`SessionsTab` hardcodes `days: 90`** for its overview call while the rest of the tab honours the page's period prop — the selector silently lies.
- **Live P&L computed twice** — `Dashboard.tsx` and `OpenPositionsTable.tsx` independently derive `(last_price − avg_entry) × qty × multiplier` from the same array.

### Consolidations

- **Three pattern-label dictionaries → one:** `AlertContext`'s `BACKEND_TO_FRONTEND_TYPE` + `formatPatternName`, `BehaviourCostCard`'s `PATTERN_LABEL`, `MyPatterns`' `patternRecs` keys.
- **Two severity normalisers → one:** `AlertContext.normalizeSeverity` duplicates `lib/alertSeverity.normalizeSeverityStr`. The latter is better and Alerts already routes everything through it.
- **`AlertContext` has no `error` field** — so every consumer (Dashboard, Alerts, My Patterns, the alerts card) inherits an indistinguishable "no alerts" state on any fetch failure.
- **Dead components in live folders:** `dashboard/BehaviorRiskBadge.tsx` and `dashboard/ClosedTradesTable.tsx` are imported nowhere; the latter duplicates `ClosedPositionsCard`'s empty-state statistics array byte-for-byte. Archive, don't delete.
- **`hooks/useFetch.ts` exists and exactly one component uses it** (`HabitsTab`). Everything else hand-rolls `useState` + `useEffect` + `try/catch` — which is precisely why the misleading-empty list below is so long.

### Misleading-empty wiring (~14 sites)

A failed request rendering as "no data" (design doc §14). Designed in Track A, wired in Track B.

Worst first: `SessionLog` collapses loading, error and empty into one blank render · `BtstTab` has no `ErrorState` at all · `PatternCalendar`'s `catch {}` carries a comment saying "show empty grid" · `InstrumentPanel`, `StrategyCard`, `EdgeLeakCard`, `OptionsBehaviorCard`, `BehaviourCostCard`, `BehaviorScoresCard` all vanish entirely on failure (misleading-*absent*, worse than misleading-empty) · `ReportCard` treats a rejected promise as empty · `InsightsTab` renders "Not enough data yet" on an API failure · `Settings` profile fetch failure shows default values as though they were the trader's · `TradeJournalSheet` resets to a blank form · `SetupNudgeCard` renders as fully-set-up.

**Already correct — preserve during the reskin:** `Journal`'s three disambiguated empty reasons · `Alerts` History tab error handling · `MyRecord`'s error-as-data with an honest message · `ClosedPositionsCard`'s separate error and empty states · `MyRules`' `loadFailed` distinct from zero violations.

*(No open calls. The My Record broker gate was moved to Track A — see §4.)*

## 6. Definition of done — Track A

A screen is done when all of:

- [ ] Zero `tm-card` / `t-mono*` / `t-heading-lg` / `tm-label` / `t-display` / `stat-value` / `table-header`
- [ ] Zero raw palette classes, zero hex
- [ ] Containers per design doc §9 — sections by default, cards only where justified, stated per block
- [ ] Type only from the §7 scale; nothing below 10px; no rem text classes for typography
- [ ] All numbers tabular; currency axes use the compact formatter with a fixed width
- [ ] Charts per §20 — no donut, pie, radial; colour from the token module
- [ ] Loading = skeleton matching the real shape · action = spinner · error = `ErrorState` · empty states carry the actual cause
- [ ] Cold-start state exists and names the no-history constraint
- [ ] All eight interaction states present on every interactive element (§11)
- [ ] View state persists per §12
- [ ] Verified in **both** themes, at 375 / 768 / 1440
- [ ] `npm run typecheck && npm run lint && npm run test` clean

**Explicitly not required, and explicitly not claimed:** verified error and empty states. They are styled but unreachable until the Track B wiring lands.

## 7. Status

| Screen | Track A |
|---|---|
| Shared foundation (16px, primitives, chart colour, nav, `index.css`) | ⬜ |
| My Record | ⬜ |
| Dashboard | ⬜ |
| Alerts | ⬜ |
| My Patterns | ⬜ |
| Analytics | ⬜ |
| Journal | ⬜ |
| Reports | ⬜ |
| My Rules | ⬜ |
| Settings | ⬜ |
| Chat | ⬜ |
| Welcome | ⬜ |
| System screens | ⬜ |
| v1 block deleted from `index.css` | ⬜ |

All screens inherit the palette, centring, and Inter already, so nothing looks broken — they are on the old container model, type scale, and colour classes.

## 8. Regression gate

The gate is the only thing that prevents drift returning once this file is deleted. A grep-based CI check over `src/` (excluding `_archive/`), failing the build on each of the following.

### Colour
| Ban | Pattern |
|---|---|
| Raw Tailwind palette | `(text\|bg\|border\|ring\|from\|via\|to)-(red\|green\|blue\|amber\|emerald\|teal\|orange\|yellow\|purple\|indigo\|violet\|fuchsia\|pink\|rose\|sky\|cyan\|lime\|slate\|gray\|zinc\|stone\|neutral)-[0-9]{2,3}` |
| Hex in a class | `\[#[0-9a-fA-F]{3,6}\]` |
| Hex or rgb in a string literal | `['"\`]#[0-9a-fA-F]{3,6}['"\`]`, `rgb\(` outside `index.css` |
| Gradients | `bg-gradient`, `bg-\[linear-gradient`, `bg-\[radial-gradient` |

### Type
| Ban | Pattern |
|---|---|
| Rem text sizes used for typography | `text-(xs\|sm\|base\|lg\|xl\|2xl\|3xl\|4xl\|5xl\|6xl)\b` |
| Sub-10px type | `text-\[[0-9]px\]` |
| Off-scale px type — anything not 10 / 11 / 12.5 / 14 / 17 / 22 / 30 | `text-\[(?!10px\|11px\|12\.5px\|14px\|17px\|22px\|30px)[0-9.]+px\]` |

### Shape and depth
| Ban | Pattern |
|---|---|
| Off-scale radius | `rounded-(xl\|2xl\|3xl)` |
| Shadows outside floating layers | `shadow-(sm\|md\|lg\|xl\|2xl)` — allowed only in the sheet/dialog/popover/dropdown primitives |

### Retired utilities
`tm-card` · `t-mono` · `t-mono-sm` · `t-mono-lg` · `t-mono-display` · `t-heading-lg` · `t-heading-sm` · `t-display` · `tm-label` · `t-overline` · `stat-value` · `stat-label` · `table-header` · `badge-success` · `badge-warning` · `badge-danger` · `tm-page-bg` · `tm-coach-cta` · `page-shell` · `animate-float` · `animate-zap-pulse`

### Charts
`<Pie` · `PieChart` · `RadialBar` · `RadialBarChart` · `<Cell` with a literal `fill=` string

### Inline style
`style={{` containing `color`, `background`, `padding`, `margin`, `gap`, `fontSize`, or `borderRadius`.

### Four caveats — the gate needs these or it cannot pass

1. **Shadows are legal on floating layers** (design doc §8) — modal, sheet, popover, dropdown. Allowlist those primitive files rather than banning shadow outright.
2. **`text-sm` and friends appear inside third-party component primitives.** Either migrate `src/components/ui/*` onto the px scale first, or scope the type rules to exclude that directory. Do not ship a gate that fails on unmigrated library primitives — a gate that always fails gets disabled.
3. **Inline style is legitimate for computed values** — a proportional bar width, a chart dimension, a transform driven by state. Ban only the static properties listed above; allow `width`, `height`, `transform`, and anything interpolating a variable.
4. **"No new component variants outside the design system" is not greppable.** That one is a review item, not a CI check — it lives in design doc §28.

Land this **after** the migration so it cannot fail on known debt. Keep it forever after this file is deleted.
