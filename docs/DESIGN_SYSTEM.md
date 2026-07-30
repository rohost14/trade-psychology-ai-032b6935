# TradeMentor AI — Design System & Page Specification

**Status:** authoritative. Last updated 2026-07-30.
**Scope:** every user-facing page in `src/pages/` + shared components. Admin has its own kit (§14).

This is the single source of truth for the reskin. Rules:

1. **If a value isn't in this doc, don't invent it** — add it here first, then use it.
2. **Tokens only.** No hard-coded hex, no raw Tailwind palette colors (`text-red-500`, `bg-stone-100`).
3. **This doc describes the target, and §2 records how far the code currently is from it.** Neither half is aspirational — §15 tracks page-by-page progress.

Implementation lives in `src/index.css` (CSS vars + `@layer components/utilities`) and `tailwind.config.ts`.

---

## 1. Product design principles

The app is a **mirror, not a blocker** — it shows a trader facts about their own behaviour. Design consequences:

| Principle | Implication |
|---|---|
| **Calm, not casino** | Desaturated semantics. Never vivid red/green. No confetti, no streak fireworks, no alarm styling. |
| **Facts, not verdicts** | Numbers first, one plain-language sentence second. No probabilistic language, no "you could have made ₹X". |
| **Money on every behavioural row** | A pattern without a rupee figure attached is not shippable. |
| **Zero manual input** | The trader never types or taps to make a feature work. No rating widgets, no "how did you feel?" prompts, no forms as core flows. (Proven: 55 alerts → 0 outcomes recorded.) |
| **Broker-grade density** | Traders compare us to Kite. Tabular numbers, tight rows, no decorative whitespace inside data tables — but generous space *between* sections. |
| **One story per page** | See the page-ownership split (§13.0). Never tell the same story twice in two places. |

---

## 2. Current-state audit (why this doc exists)

The app feels inconsistent because `src/index.css` ships **two complete, conflicting systems**. Measured usage across `src/**/*.tsx` on 2026-07-30:

| Concern | Old system (v1) | Uses | New system (Lovable, target) | Uses |
|---|---|---|---|---|
| Card surface | `.tm-card` — `rounded-xl`, shadow, **no border** | **240** | `.desk-card` — `rounded-lg`, **1px border**, no shadow | 12 |
| Numbers | `.t-mono*` — **DM Mono** | **309** | `.font-tabular` — Inter tabular-nums | 59 |
| Page title | `.t-heading-lg` — 20px | 16 | 22px / 600 (§4 H1) | — |
| Display number | `.t-display` — 28px/700 | 6 | 30px/600 `.font-display` | 6 |
| Section label | `.tm-label` / `.t-overline` — 11px, `0.07em` | 57 | `.t-label` — 11px, `0.12em` | 4 |

Plus:

- **721** raw Tailwind palette color usages and **11** hard-coded hex values in `src/**/*.tsx`. Worst live offenders: `MorningIntentCard.tsx` (58), `Reports.tsx` (54), `settings/NotificationsTab.tsx` (32), `Journal.tsx` (22), `patterns/PatternCalendar.tsx` (20), `Chat.tsx` (18), `EodComparisonCard.tsx` (18). (`_archive/**` also shows up — ignore, it is unrouted.)
- **Dead utilities** with 0 uses: `.page-shell`, `.card-body`, `.stat-value`, `.t-heading-md`.
- **Drift already:** `.page-shell` still says `max-w-[1400px]`; `Layout.tsx` now uses `max-w-7xl`.
- **Gradient utilities** (`.tm-page-bg` dark radials, `.landing-bg`, `.tm-coach-cta`) contradict "no gradients". Keep `.landing-bg` (marketing surface, §13.11); retire the other two in-app.
- `.badge-*` and `.tm-chip-*` are defined in raw palette colors (`teal-50`, `red-600`, `green-700`, `stone-100`) — they must be re-expressed in tokens.

**Root font-size is 17px** (`src/index.css:181`). This scales rem-based Tailwind (`text-sm` → 14.9px, all spacing) but **not** arbitrary px classes (`text-[14px]`). Therefore:

> **Typography rule: use the px scale in §4 for text.** Do not use Tailwind's rem `text-xs/sm/base/lg/xl` for typography — they drift with the root size and produce fractional sizes. Rem spacing (`p-4`, `gap-3`) is fine and intentional.

§10 is the migration map that closes all of the above.

---

## 3. Color

Semantic tokens only, bound to CSS vars in `src/index.css`. Both themes are first-class; dark is default.

### 3.1 Surfaces & text

| Token | Class | Dark | Light | Use |
|---|---|---|---|---|
| Page | `bg-background` | `#121316` | `#F6F5F3` (paper) | body only |
| Card | `bg-card` | `#191B1F` | `#FFFFFF` | every card surface |
| Elevated | `--layer-elevated` | `#26272C` | `#FBFAF9` | sidebar, modals, sheets, popovers |
| Hover row | `bg-muted` / `--layer-overlay` | `#232529` | `#F2F0EE` | row hover, tab track |
| Border | `border-border` | `#2A2C32` | `#DCDAD6` | card edges |
| Divider | `--layer-border-subtle` | `#1E2024` | `#EDEBE8` | row dividers inside a card |
| Foreground | `text-foreground` | `#EEECE8` | `#16181D` (ink) | headings, values |
| Secondary | `text-muted-foreground` | `#939698` | `#60646C` | labels, descriptions |
| Tertiary | `--text-tertiary` | `#646670` | `#96969F` | timestamps, metadata only |

**Two in-app surfaces only** — `bg-background` and `bg-card`. `elevated` is for things that float above the page (sidebar/modal/popover), not a third card tier.

### 3.2 Accent & semantics

| Token | Class | Dark | Light | Use |
|---|---|---|---|---|
| **Primary (pine-teal)** | `text-primary` `bg-primary` | `#59C0B4` | `#155B56` | the one accent: CTA, active nav, links, focus ring |
| Profit | `text-profit` `bg-profit/10` | `#47B88E` | `#226D4F` | gains, BUY, improving |
| Loss | `text-loss` `bg-loss/10` | `#CF6559` | `#AF3A31` | losses, SELL, danger |
| Warning | `text-warning` `bg-warning/10` | `#D39145` | `#B16B1B` | caution |

- **One accent, full stop.** Everything else is neutral + the three semantics.
- Semantics are **deliberately desaturated**. If it looks like a Bloomberg terminal alarm, it's wrong.
- Tints are always `/10` fills with `/20` borders. Never a solid semantic fill behind body text.
- Legacy aliases `--tm-profit/-loss/-obs/-brand` and `text-tm-*` map to the same values and remain valid; prefer `text-profit` / `text-loss` / `text-warning` / `text-primary` in new code.

### 3.3 Severity → color

The engine's severity vocabulary is `info` / `caution` / `danger` / `critical`:

| Severity | Color token | Treatment |
|---|---|---|
| `info` | `primary` | icon tint only |
| `caution` | `warning` | icon tint + `border-l-2 border-l-warning` |
| `danger` | `loss` | icon tint + `border-l-2 border-l-loss` |
| `critical` | `loss` | same as danger + bolder value; **no** pulsing, no red page chrome |

### 3.4 P&L sign coloring

Profit → `text-profit`. Loss → `text-loss`. **Exactly zero → `text-muted-foreground`**, never green. Always render the sign (`+₹1,240` / `−₹890`).

---

## 4. Typography

- **Body:** Inter (400/500/600). **Headings / display:** Geist via `.font-display`. **Numbers:** Inter with `font-variant-numeric: tabular-nums` (`.font-tabular`).
- **DM Mono is retired** for numbers — see §10. Tabular Inter reads denser and matches the Lovable target.

### The 7-step scale — do not invent sizes

| Role | Size / weight | Recipe |
|---|---|---|
| **Display** — hero P&L, score | 30px / 600, tabular | `font-display text-[30px] font-semibold tracking-tight font-tabular` |
| **H1** — page title | 22px / 600 | `text-[22px] font-semibold tracking-tight` |
| **H2** — card / section title | 17px / 600 | `text-[17px] font-semibold tracking-tight` |
| **Body** — default | **14px / 400** | `text-[14px]` |
| **Small** — secondary copy | 12.5px / 400 | `text-[12.5px] text-muted-foreground` |
| **Label** — uppercase | 11px / 500, `tracking-[0.12em]`, muted | `.t-label` |
| **Micro** — dense table column headers **only** | 10px / 500, uppercase, `tracking-wider` | inline |

Rule of thumb: card titles 17 · values 14–16 · big numbers 20–32 · labels 11 uppercase. **Reaching for 9–10px for anything other than a table column header means the layout is wrong, not the font.**

Element defaults in `index.css` (`h1` 22 / `h2` 16 / `h3` 14) are the fallback; explicit classes win.

---

## 5. Numbers & money

- **P&L is RAW only:** `(exit − entry) × qty × multiplier`. **Never** brokerage, STT, or taxes. Never build a charge estimator.
- Every numeric cell gets `.font-tabular` so columns align across rows.
- Currency: `formatCurrency` for display. **Chart axes must use `formatAxisCurrency`** plus explicit `width={52}` on a currency `YAxis` — `formatCurrency` overflows the axis and drops the minus sign, making losses read as gains.
- Percentages: one decimal (`62.5%`). Rupees in body: no decimals (`₹1,240`). Large: `₹1.2L` / `₹3.4Cr` via the formatter, never raw.
- Behaviour→money is always **realized P&L of flagged trades** (fact, via `trigger_completed_trade_id`) — never a counterfactual "estimated cost" or "money saved".

---

## 6. Layout & spacing

- **App shell:** `Layout.tsx` — sidebar (desktop) / bottom nav + More sheet (mobile). Content wrapper: `w-full mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-4 sm:py-6`. **Content is centred and capped at 1280px — the app is not full-bleed.**
- **Between sections:** `space-y-5` (or `space-y-6`). **Inside grids:** `gap-3` / `gap-4`.
- **Card header:** `.card-head` = `px-4 sm:px-6 h-12 border-b border-border flex items-center justify-between gap-3`.
- **Card body:** `px-4 sm:px-6 py-4`. Dense rows: `px-4 sm:px-6 py-3.5`.
- **Radius:** cards `rounded-lg` (10px, `--radius`) · chips `rounded` · pills & dots `rounded-full`.
- **Elevation:** in-app cards use a **1px border, no shadow**. `--shadow-elevated` / `--shadow-sheet` are for floating layers only (modals, sheets, popovers, dropdowns).
- **Breakpoints:** mobile-first. `sm:` 640 · `md:` 768 (nav flips to sidebar) · `lg:` 1024 · `xl:` 1280. Data tables collapse to stacked rows below `sm`, never horizontal-scroll a primary table on mobile.

---

## 7. Motion

One duration, one easing. `transition-colors duration-150` for hovers; `duration-200` for toggles and chevron rotates. Existing `animate-fade-in-up` (0.2s) is fine for list/card entry.

Allowed: count-up on the hero P&L **only**; the alert-badge pulse (4s, subtle). Banned: bouncy easing, decorative float/zap loops on live pages, anything that animates continuously in a data view.

---

## 8. Component recipes

Reuse these. Do not re-style per page.

**Card**
```tsx
<section className="desk-card overflow-hidden">
  <div className="card-head"><span className="t-label">Cost leaks · 30d</span><span>…</span></div>
  <div className="divide-y divide-border">{rows}</div>
</section>
```

**Stat / KPI card** — `desk-card p-3` → label `text-[11px] text-muted-foreground font-medium` → value `text-xl font-bold font-tabular mt-0.5` (colored by sign) → sub `text-[11px] text-muted-foreground mt-0.5 font-tabular`. Highlight variant: `bg-profit/10 border-profit/20` (or loss).

**Metric grid (hairline dividers)** — `grid grid-cols-2 sm:grid-cols-5 gap-px bg-border rounded-lg overflow-hidden border border-border`, each cell `bg-card px-3 py-2.5`; label 10px uppercase, value 14px bold tabular. The `gap-px bg-border` *is* the separator — don't add borders.

**Ranked list row** — rank `text-[11px] font-bold font-tabular text-muted-foreground w-4` → name 14px → sub 11px tabular → right-aligned ₹ (bold tabular, sign-colored).

**Severity row** — icon in `h-7 w-7 rounded-md bg-{sev}/10 text-{sev}` + `border-l-2 border-l-{sev}` on the row.

**Category pill** — `text-[10px] font-semibold uppercase tracking-wider`, colored by kind (SIZE / PACE / EMOTIONAL / RISK).

**Instrument chip** — `.tm-chip` + CE / PE / EQ variant (must be re-tokenized, §10).

**Trend arrow** — ↗ worsening (`loss`) · ↘ improving (`profit`) · → stable (muted). Direction encodes *value*, not raw delta.

**Tabs** — `TabsList` `bg-muted/60 p-0.5 h-9`; `TabsTrigger` `text-xs h-8 px-3`. Underline-style tabs (Settings, Analytics) use `border-b-2 border-primary` on active, transparent bg.

**Buttons** — primary `bg-primary text-primary-foreground` · ghost `text-foreground hover:text-primary` · destructive `bg-loss/10 text-loss border border-loss/20`. Inline "View all →" = `text-[11px] font-medium text-primary uppercase tracking-wider`.

**Accordion (drill-down)** — `desk-card` wrapper, trigger `px-5 sm:px-6 py-4 hover:no-underline`, content `border-t border-border`. This is the canonical pattern for consolidated→detail (see Dashboard closed trades).

---

## 9. States: loading, empty, error

**The dominant bug class is misleading-empty** — `catch { setX([]) }` renders "no data" on a network failure. A failed fetch must render an error, never an empty state.

| State | Treatment | Primitive |
|---|---|---|
| Content loading | **Skeleton** matching final layout | `components/ui/skeletons`, `.skeleton` |
| Action in flight | **Spinner** in the button, button disabled | — |
| Error | Type-aware message + retry | `components/ErrorState` |
| Empty (genuinely no data) | Icon + one-line reason + one action | see below |
| Not connected to broker | Full-page connect prompt | shared broker-gate block |

**Empty state recipe:** `desk-card` → centered `py-12` → muted icon in `p-3 rounded-full bg-primary/10` → 14px foreground line stating *why* it's empty → 12.5px muted sub → at most one primary action. Never a bare "No data".

**Cold start is the default, not an edge case.** Kite provides **no trade history** — a new user has an empty app until they import a Console CSV. Every page needs a first-run state that explains this and points at the import, not a shrug.

Fetch/error plumbing: `hooks/useFetch`, and the `api.ts` interceptor already toasts silent 5xx / network / timeout — don't double-toast.

---

## 10. Deprecation map (v1 → target)

Mechanical, page-by-page during each reskin. Never a global find-and-replace — `tm-card` differs from `desk-card` in radius, border, and shadow, so layouts need eyes on them.

| Remove | Replace with | Notes |
|---|---|---|
| `.tm-card` (240) | `.desk-card` | `rounded-xl`+shadow → `rounded-lg`+1px border |
| `.t-mono` / `-sm` / `-lg` / `-display` (309) | `.font-tabular` + a §4 size | drops DM Mono |
| `.t-heading-lg` (16) | `text-[22px] font-semibold tracking-tight` | 20 → 22px |
| `.t-display` (6) | `font-display text-[30px] font-semibold font-tabular` | |
| `.t-heading-sm` / `.t-body*` / `.t-caption` | §4 px classes | |
| `.tm-label` (55) / `.t-overline` (2) | `.t-label` | `0.07em` → `0.12em` tracking |
| `.stat-value`, `.stat-label`, `.table-header` | §8 stat recipe, `.t-label` | |
| `.badge-success/-warning/-danger` | `bg-{profit,warning,loss}/10 text-{…}` | de-palette |
| `.tm-chip-ce/-pe/-eq` | token equivalents (`bg-primary/10`, `bg-loss/10`, `bg-muted`) | de-palette |
| `.tm-page-bg`, `.tm-coach-cta` gradients | flat `bg-background` / `bg-primary` | keep `.landing-bg` for marketing only |
| `raw palette` (721) + hex (11) | §3 tokens | |
| Rem text classes for typography (`text-sm`…) | §4 px classes | root is 17px |

**Cleanup, safe now:** delete unused `.page-shell` (also stale at 1400px), `.card-body`, `.t-heading-md` from `index.css` — 0 uses each. Retire the `animate-float` / `animate-zap-pulse` decorative loops.

Keep during migration (both systems coexist until §15 is all-green), then delete the v1 block in one commit.

---

## 11. Charts

Recharts. Chart rules are design rules:

- One accent + the three semantics. A categorical series never introduces a new hue — use `primary`, then muted neutrals.
- **Currency `YAxis`: `tickFormatter={formatAxisCurrency}` + `width={52}`.** Non-negotiable (see §5).
- Grid: horizontal lines only, `stroke` = border token, no vertical grid, no chart border.
- Tooltips: a **named component** passed as a JSX element — `content={<MyTooltip />}`, never an inline `content={fn}` (remounts every render).
- Axis/legend text: 11px muted. No bold axis labels. No 3D, no area gradients, no drop shadows.
- Empty chart → §9 empty state, not an empty axis frame.

---

## 12. Accessibility

- Focus: global `:focus-visible` ring (2px `--ring`, 2px offset) — never remove it. `.focus-ring` for custom controls.
- Contrast: body text on `bg-card` ≥ 4.5:1 in **both** themes. Desaturated semantics are pre-checked; tint-on-tint (`text-profit` on `bg-profit/10`) is verified at `/10` only — don't deepen the fill.
- Color is never the only signal: sign on numbers, arrow on trends, label on severity.
- Icons: Lucide at `stroke-width: 1.5` (set globally). Icon-only buttons need `aria-label`.
- Tabs use `role="tablist"` / `role="tab"` / `aria-selected` (Analytics is the reference).

---

## 13. Page specification

### 13.0 Page-ownership split (governs everything below)

| Story | Owned by | Others may |
|---|---|---|
| Quantified behaviour cost | **Analytics** | link to it |
| Live alert loop + response stats | **Alerts** | show latest 3 (Dashboard) |
| At-a-glance pattern scorecard | **My Patterns** | link to it |
| Today's session (P&L, positions) | **Dashboard** | — |
| Pre-trade personal record | **My Record** | — |

**Never recompute the same story on two pages.** Cross-link instead.

### 13.1 Dashboard — `/dashboard` (reference implementation)

**Purpose:** what is happening *right now*, in one screen. The only page a trader keeps open during market hours.

**Layout:** single column, `space-y-5`. No side rail, no AI-analysis cards, no streak widget.

1. `SessionHeroCard` — Display P&L for the **session window** (not calendar midnight), one Day-P&L story with a breakdown line. Live, count-up on change.
2. `SetupNudgeCard` — conditional, first-run / setup gaps only.
3. `RecentAlertsCard` — latest few alerts, session-windowed, links to Alerts.
4. `OpenPositionsTable` — live prices via WS, client-side P&L, tabular.
5. Closed trades — `Accordion` (`defaultValue="closed"`) → `ClosedPositionsCard`, Zerodha-style consolidated with drill-down.

**States:** cold start → import prompt · market closed → session summary, not zeros · disconnected → broker gate.
**Open issue:** two `tm-card` usages remain (`Dashboard.tsx:592,611`).

### 13.2 Analytics — `/analytics`

**Purpose:** the quantified story over 30/60/90 days. Owns cost attribution.

**Layout:** H1 + day-range selector → `ReportCard` hero (always-visible front door, above tabs) → tab bar → lazy tab content with `TabIntro` + skeleton.
**Tabs (5):** Overview · Edge · Behaviour · Habits · | Advanced (second `group`, visually separated by the divider in the tab bar).
**Rules:** every metric factual and provable, differentiated from what Kite already shows. **Rejected forever:** what-if simulation, discipline counterfactuals, options-moneyness/VIX overlays, P&L heatmap, anything probabilistic.
**Reskin:** `t-heading-lg` → 22px H1; `tm-card` → `desk-card`; charts to §11.

### 13.3 Alerts — `/alerts`

**Purpose:** the live behavioural loop — what fired, when, and how the trader responded.

**Layout:** H1 → response-stats strip → filter row → alert list (`border-l-[3px]` severity, `divide-y` rows).
**Rules:** severity per §3.3. Praise/positive alerts read in `profit`, not gold. No modal interrupts — the app is a mirror, not a blocker. **No outcome-capture widgets** (zero-manual-input constraint).
**Reskin:** heavy — 8+ `tm-card` sites, custom `border-l-[3px]`.

### 13.4 My Patterns — `/my-patterns`

**Purpose:** at-a-glance scorecard — which patterns are mine, which are worsening.

**Layout:** H1 → top-pattern cards (`border-l-2` by severity) → 3-up stat row → pattern table → calendar.
**Reskin:** `PatternCalendar.tsx` has 20 raw palette colors — must move to `profit`/`loss`/`warning` tints.

### 13.5 My Record — `/my-record`

**Purpose:** pre-trade lookup — "what has actually happened when I've traded this setup before". Replaced Blowup Shield; `/blowup-shield` → 301.

**Layout:** H1 → search/lookup card → record verdict (`border-l-4`) → supporting stat cards → history table → footnote strip.
**Rules:** facts from the trader's own history only. No prediction, no score, no "don't do this".

### 13.6 Chat — `/chat`

**Purpose:** AI coach over the trader's real data.

**Layout:** H1 → full-height `desk-card` chat column (`h-[calc(100%-4rem)]`), messages `divide-y`-free bubbles, composer pinned bottom.
**Rules:** user bubble `bg-muted`; assistant plain on card. **Retire `.tm-coach-cta` gradient** → flat `bg-primary`. Feature-killable via Global Settings → disabled renders a 403 state (not the maintenance redirect).

### 13.7 Reports — `/reports`

**Purpose:** periodic (daily / weekly) written summary the trader can read after the close.

**Reskin:** worst live offender — **54** raw palette colors. Full de-palette + `desk-card` + §4 type.

### 13.8 Journal — `/journal`

**Purpose:** auto-generated session log — what happened each session, no typing required.

**Layout:** H1 → 3-up stat row → session cards (`px-5 py-3.5`) → empty state.
**Rules:** entries are **generated**, never a text box the trader must fill. 22 palette colors to fix.

### 13.9 My Rules — `/my-rules`

**Purpose:** the trader's constitution + the override flow.

**Layout:** H1 → rule group cards (`divide-y` rows, control on the right).
**Rules:** **tighten = instant; loosen = 409 `override_required`** → confirm step with the consequence stated plainly. Destructive/loosening affordances use the destructive button style, never primary.

### 13.10 Settings — `/settings`

**Purpose:** profile, notifications, insight prefs, data rights.

**Layout:** H1 → underline tabs: Profile · Notifications · Insights · **Danger Zone** (active state `text-loss border-loss`).
**Rules:** Danger Zone (export / delete / import tradebook) needs typed confirmation + irreversibility stated. `NotificationsTab.tsx` has 32 palette colors.
**Note:** Guardian fields live on `User`, not `UserProfile` — a data quirk, but it shapes the form grouping.

### 13.11 Static & system pages

`Welcome` (marketing — **keeps `.landing-bg`**, the only gradient surface) · `Terms` · `Privacy` · `Maintenance` · `NotFound` · `ImpersonateEntry`.
Prose pages: single column `max-w-[68ch]`, 14px body, 1.6 line-height, H2 17px, generous `space-y-4`.

---

## 14. Admin (`/admin/*`)

Ten sub-pages (Overview · Users · User detail · System · Insights · Broadcast · Audit log · Admins · Config · Login). **Deliberately a separate visual language** — denser, tool-like, built on `src/pages/admin/_ui/kit.tsx` + shadcn.

It shares §3 tokens and §4 type but **not** the trader-facing recipes. Admin changes don't touch this doc's §13, and vice versa. Do not "unify" them.

---

## 15. Reskin status & definition of done

A page is **done** when all of:

- [ ] Zero `tm-card` / `t-mono*` / `t-heading-lg` / `tm-label` / `t-display` / `stat-value`
- [ ] Zero raw palette colors and zero hex
- [ ] Type only from the §4 scale (no rem text classes for typography)
- [ ] All numbers `.font-tabular`; currency axes use `formatAxisCurrency` + `width={52}`
- [ ] Loading = skeleton · action = spinner · error = `ErrorState` · **no misleading-empty**
- [ ] Cold-start / first-run state exists and explains the no-history constraint
- [ ] Verified in **both** themes, and at 375px / 768px / 1440px
- [ ] `npm run typecheck && npm run lint && npm run test` clean

| Page | Status |
|---|---|
| Dashboard | ✅ reference (2 stray `tm-card` to clear) |
| Analytics | ⬜ next |
| Alerts | ⬜ |
| My Patterns | ⬜ |
| My Record | ⬜ |
| Reports | ⬜ (heaviest de-palette) |
| Journal | ⬜ |
| My Rules | ⬜ |
| Chat | ⬜ |
| Settings | ⬜ |
| Static pages | ⬜ |
| `index.css` v1 block deleted | ⬜ (last step, after all above) |

All pages currently inherit palette + centering + Inter, so nothing looks broken — they're just on the old component structure and type scale.

---

## 16. Do / Don't

**Do:** one accent · tabular numbers · 14px body · `desk-card` everywhere · `gap-px bg-border` grids · money on every behavioural row · both themes checked · skeleton-then-content.

**Don't:** 9–10px body text · a second accent color · vivid red/green · ad-hoc card styles · per-page bespoke spacing · hard-coded hex or raw palette classes · gradients or heavy shadows in-app · DM Mono for numbers · rem text sizes for typography · empty state on a failed fetch · any feature that needs the trader to type.
