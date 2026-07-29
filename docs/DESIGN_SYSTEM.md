# TradeMentor Design System (ported from Lovable · calm-trade-clinic)

The single source of truth for every page reskin. If a value isn't here, don't invent one — add it here first. This is what keeps the app consistent instead of "random / vibe-coded". Tokens live in `src/index.css` (CSS vars) + `tailwind.config.ts`; utilities in `src/index.css`.

## 1. Color (semantic tokens — never hard-code hex)

Use Tailwind classes bound to CSS vars. **Never** `text-[#...]` or `text-red-500`.

| Token | Class | Dark | Light | Use |
|---|---|---|---|---|
| Background | `bg-background` | #121316 | #F6F5F3 (paper) | page |
| Card | `bg-card` | #191B1F | #FFFFFF | every card surface |
| Foreground | `text-foreground` | #EEECE8 | #16181D (ink) | primary text, numbers |
| Muted text | `text-muted-foreground` | #939698 | #60646C | labels, secondary |
| Border | `border-border` | #2A2C32 | #DCDAD6 | 1px low-contrast edges |
| **Primary (teal)** | `text-primary` `bg-primary` | #59C0B4 | #155B56 | accent, CTA, active, links |
| Profit | `text-profit` `bg-profit/10` | #47B88E | #226D4F | gains, BUY, improving |
| Loss | `text-loss` `bg-loss/10` | #CF6559 | #AF3A31 | losses, SELL, danger |
| Warning | `text-warning` `bg-warning/10` | #D39145 | #B16B1B | caution |

- **Only ONE accent** (teal). Everything else is neutral + the 3 semantics. Semantics are deliberately **desaturated** — never vivid.
- Two surfaces only: `bg-background` (page) and `bg-card` (cards). No third tier, no gradients, no decorative shadow.

## 2. Typography

- **Body font:** Inter. **Headings/display:** Geist (`.font-display`). **All numbers:** tabular (`.font-tabular` / `font-variant-numeric: tabular-nums`).
- **Strict 7-step scale — do not invent sizes:**

| Role | Size / weight | Class / recipe |
|---|---|---|
| Display (hero P&L) | 30px / 600, `.font-display`, tabular | `font-display text-[30px] font-semibold tracking-tight font-tabular` |
| H1 (page title) | 22px / 600 | `t-h1` (or `text-[22px] font-semibold tracking-tight`) |
| H2 (card/section title) | 17px / 600 | `text-[17px] font-semibold tracking-tight` |
| **Body** | **14px / 400** | `text-[14px]` — this is the default; STOP using 10-11px for body |
| Small (secondary copy) | 12.5px / 400 | `text-[12.5px] text-muted-foreground` |
| **Label** (uppercase) | 11px / 500, `tracking-[0.12em]`, uppercase, muted | `t-label` |
| Micro (table headers) | 10px / 500, uppercase, `tracking-wider` | only for dense table column headers |

**Rule of thumb:** card titles 17, values 14–16, big numbers 20–32, labels 11 uppercase. If you're reaching for 9–10px for anything other than a table column header, it's wrong.

## 3. Spacing & layout

- **Page shell:** `.page-shell` = `max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-4 sm:space-y-6`. (Content is centred + capped — the app is NOT full-bleed.)
- **Between sections:** `space-y-5` (or `space-y-6`). **Inside grids:** `gap-3` / `gap-4`.
- **Card header:** `.card-head` = `px-4 sm:px-6 h-12 border-b flex items-center justify-between`.
- **Card body:** `.card-body` = `px-4 sm:px-6 py-4`. Dense rows: `px-4 sm:px-6 py-3.5`.
- **Radius:** cards `rounded-lg` (10px), chips/dots `rounded` (6px) / `rounded-full` for pills+dots.

## 4. Component recipes (reuse — don't re-style per page)

- **Card:** `<section className="desk-card overflow-hidden">` → `.card-head` (label + right-aligned value) → body / `divide-y divide-border` rows.
- **Section label:** `<span className="t-label">Cost leaks · 30d</span>` + optional muted sub.
- **Stat / KPI card:** `desk-card p-3` → label `text-[11px] text-muted-foreground font-medium` → value `text-xl font-bold font-tabular mt-0.5` (colored by sign) → sub `text-[11px] text-muted-foreground mt-0.5 font-tabular`. Highlight card = `bg-profit-muted border-profit/20` (or loss).
- **Metric grid (elegant dividers):** `grid grid-cols-2 sm:grid-cols-5 gap-px bg-border rounded-lg overflow-hidden border border-border`, each cell `bg-card px-3 py-2.5` (label 10px uppercase + value 14px bold tabular). The `gap-px bg-border` gives hairline separators.
- **Category pill:** `text-[10px] font-semibold uppercase tracking-wider` colored by kind (SIZE/PACE/EMOTIONAL/RISK).
- **Severity:** icon in `h-7 w-7 rounded-md bg-{sev}/10 text-{sev}` + left border `border-l-2 border-l-{sev}`.
- **Trend arrow:** ↗ worsening (loss) · ↘ improving (profit) · → stable (muted).
- **Ranked list row:** rank `text-[11px] font-bold font-tabular text-muted-foreground w-4` + name (14px) + sub (11px tabular) + right ₹ (bold tabular, colored).
- **Tabs:** `TabsList` `bg-muted/60 p-0.5 h-9` + `TabsTrigger` `text-xs h-8 px-3`.
- **Buttons:** primary = `bg-primary text-primary-foreground`. Ghost link = `text-foreground hover:text-primary`. "View all →" = `text-[11px] font-medium text-primary uppercase tracking-wider`.

## 5. Motion
One duration, one easing. `transition-colors duration-150` for hovers; `duration-200` for toggles/rotates. No bouncy/decorative animation. Count-up on the hero P&L only.

## 6. Do / Don't
- **Do:** one accent, tabular numbers, 14px body, `desk-card` everywhere, `gap-px bg-border` grids, money on every behavioural row.
- **Don't:** 9–10px body text, multiple accent colors, vivid red/green, ad-hoc card styles, per-page bespoke spacing, hard-coded hex, gradients/heavy shadows.

## Status
- **Dashboard** — fully on this system (reference implementation).
- **All other pages** — inherit palette + centering + Inter, but still old component structure/typography. Reskin each against this doc, page by page (next: Analytics).
