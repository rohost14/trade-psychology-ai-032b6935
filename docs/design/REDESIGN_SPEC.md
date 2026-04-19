# TradeMentor AI — Redesign Specification
*Aesthetic direction: "Precision Dark/Light" — refined minimal, data-forward, trustworthy.*
*Last updated: 2026-04-19*

---

## 0. Design Philosophy

TradeMentor is a trading psychology mirror for F&O traders. The UI must signal:

- **Trustworthiness** — people are reviewing their worst financial decisions here
- **Precision** — every pixel deliberate, every number readable at a glance
- **Calm authority** — serious, not flashy; not gamified
- **Premium** — worth ₹499–₹999/month

**Both themes are equal priority.** Dark is the default (traders stare at screens all day).
Light is a first-class citizen — not an afterthought or simple color inversion.

**Core rule:** The app must feel identical in quality and intention in both modes.

---

## 1. Layer System — Visual Depth

The single biggest quality gap in the current UI is that everything looks flat.
Dark mode is `#0B0B0B` background on `#141414` cards — a delta of 9 brightness points.
Cards are indistinguishable from the page.

We fix this with a **4-level layer system** where each level has a clear background, border,
and shadow. The color palette uses a consistent **blue-purple undertone** (`hsl(240, ~10%, L%)`)
across both themes. This tint is subtle — never "blue-tinted" to the eye — but it creates
cohesion so the app feels designed rather than assembled.

### Dark Theme Layers

| Level | Name | Hex | HSL | Use |
|---|---|---|---|---|
| 0 | Page | `#09090C` | `hsl(240, 15%, 4.5%)` | Body background |
| 1 | Surface | `#111116` | `hsl(240, 12%, 8%)` | Cards, panels |
| 2 | Elevated | `#1A1A22` | `hsl(240, 13%, 12%)` | Sidebar, modals, sticky elements |
| 3 | Overlay | `#232330` | `hsl(240, 15%, 17%)` | Hover states, active rows, tooltips |
| — | Border | `#2A2A38` | `hsl(240, 15%, 20%)` | Card edges, dividers |
| — | Border subtle | `#1E1E2A` | `hsl(240, 15%, 15%)` | Inner dividers, row separators |

### Light Theme Layers

| Level | Name | Hex | HSL | Use |
|---|---|---|---|---|
| 0 | Page | `#F2F2F7` | `hsl(240, 13%, 96%)` | Body background |
| 1 | Surface | `#FFFFFF` | `hsl(0, 0%, 100%)` | Cards, panels |
| 2 | Elevated | `#F8F8FC` | `hsl(240, 20%, 98%)` | Sidebar, modals, sticky elements |
| 3 | Overlay | `#EEEFF6` | `hsl(235, 18%, 95%)` | Hover states, active rows |
| — | Border | `#E2E2EE` | `hsl(240, 18%, 91%)` | Card edges, dividers |
| — | Border subtle | `#EBEBF5` | `hsl(240, 20%, 94%)` | Inner dividers, row separators |

The light page (`#F2F2F7`) gives white cards something to sit on.
The elevated layer (`#F8F8FC`) ensures modals and the sidebar feel distinct.

---

## 2. Shadow System

**Dark mode:** Drop shadows are invisible on dark backgrounds.
Use **inner edge highlights** + **ring borders** to create depth.

```css
/* Dark — Level 1 (card) */
--shadow-card: inset 0 1px 0 rgba(255, 255, 255, 0.06);

/* Dark — Level 2 (elevated: sidebar, modals) */
--shadow-elevated: 0 0 0 1px rgba(255, 255, 255, 0.08),
                   0 8px 32px rgba(0, 0, 0, 0.5);

/* Dark — Level 3 (sheets, command palette) */
--shadow-sheet: 0 0 0 1px rgba(255, 255, 255, 0.10),
                0 24px 80px rgba(0, 0, 0, 0.7);
```

**Light mode:** Conventional layered drop shadows with very low opacity.

```css
/* Light — Level 1 (card) */
--shadow-card: 0 1px 2px rgba(0, 0, 0, 0.06),
               0 1px 4px rgba(0, 0, 0, 0.04);

/* Light — Level 2 (elevated) */
--shadow-elevated: 0 2px 8px rgba(0, 0, 0, 0.08),
                   0 4px 20px rgba(0, 0, 0, 0.06);

/* Light — Level 3 (sheets) */
--shadow-sheet: 0 8px 32px rgba(0, 0, 0, 0.12),
                0 24px 80px rgba(0, 0, 0, 0.08);
```

---

## 3. Color System

### 3a. Brand Color — Teal (Unchanged)

Teal is TradeMentor's identity. It's distinctive in Indian fintech (everyone else is blue).
It reads as calm, precise, financial — not generic SaaS blue.

| Context | Dark | Light |
|---|---|---|
| Brand primary (buttons, active states) | `#2DD4BF` | `#0F766E` |
| Brand hover | `#5EEAD4` | `#0D9488` |
| Brand subtle bg (active nav row) | `rgba(45,212,191,0.10)` | `rgba(15,118,110,0.08)` |
| Brand text / icon on page | `#2DD4BF` | `#0F766E` |

*Dark uses teal-400 (`#2DD4BF`) — bright enough to read on dark surfaces.*
*Light uses teal-700 (`#0F766E`) — dark enough to meet 4.5:1 contrast on white.*

### 3b. Financial Tokens — LOCKED

These four tokens are sacred. Never repurpose them for non-financial meaning.

**Why the light values differ from current:** The current light `--tm-profit` (`#0F8E7D`) is
only 3.8:1 contrast on white — fails WCAG AA. The new values all pass 4.5:1 minimum.

| Token | Dark | Light | WCAG ratio on bg |
|---|---|---|---|
| Profit (gains, positive P&L) | `#4ADE80` | `#15803D` | 4.6:1 ✓ |
| Loss (losses, negative P&L) | `#F87171` | `#B91C1C` | 6.4:1 ✓ |
| Observation (alerts, caution) | `#FBBF24` | `#92400E` | 7.4:1 ✓ |
| Brand (teal, primary actions) | `#2DD4BF` | `#0F766E` | 4.6:1 ✓ |

Financial background tints (for cards/rows showing P&L):

| Token | Dark | Light |
|---|---|---|
| Profit bg | `rgba(74,222,128,0.08)` | `rgba(21,128,61,0.06)` |
| Loss bg | `rgba(248,113,113,0.08)` | `rgba(185,28,28,0.06)` |
| Observation bg | `rgba(251,191,36,0.08)` | `rgba(146,64,14,0.06)` |

### 3c. Text Hierarchy

**Three tiers — always use the right one:**

| Tier | Token | Dark | Light | Use |
|---|---|---|---|---|
| Primary | `--text-primary` | `#F0F0F8` | `#0C0C14` | Headings, key data, active labels |
| Secondary | `--text-secondary` | `#9898B0` | `#60607A` | Descriptions, supporting labels |
| Tertiary | `--text-tertiary` | `#5A5A72` | `#9898AE` | Timestamps, metadata, placeholders |

*Dark primary is not pure white (`#FFFFFF`) — slightly blue-tinted `#F0F0F8` reduces eye strain
and matches the layer palette. Light primary is not pure black — same logic.*

### 3d. Status System — Alert Backgrounds

Used for alert rows, warning banners, and status indicators.

| Status | Dark bg | Dark border | Dark text | Light bg | Light border | Light text |
|---|---|---|---|---|---|---|
| Danger | `rgba(248,113,113,0.10)` | `rgba(248,113,113,0.25)` | `#F87171` | `rgba(185,28,28,0.07)` | `rgba(185,28,28,0.20)` | `#B91C1C` |
| Caution | `rgba(251,191,36,0.10)` | `rgba(251,191,36,0.25)` | `#FBBF24` | `rgba(146,64,14,0.07)` | `rgba(146,64,14,0.20)` | `#92400E` |
| Success | `rgba(74,222,128,0.10)` | `rgba(74,222,128,0.25)` | `#4ADE80` | `rgba(21,128,61,0.07)` | `rgba(21,128,61,0.20)` | `#15803D` |
| Info | `rgba(96,165,250,0.10)` | `rgba(96,165,250,0.25)` | `#60A5FA` | `rgba(29,78,216,0.07)` | `rgba(29,78,216,0.20)` | `#1D4ED8` |

### 3e. Sidebar Colors

Sidebar sits at Layer 2 in both themes — slightly distinct from both the page and the cards.

| | Dark | Light |
|---|---|---|
| Sidebar background | `#1A1A22` (Layer 2) | `#F0F0F8` (slightly deeper than page) |
| Sidebar border-right | `rgba(255,255,255,0.06)` | `rgba(0,0,0,0.07)` |
| Section header text | `#5A5A72` (tertiary) | `#9898AE` (tertiary) |
| Nav item default | transparent | transparent |
| Nav item hover bg | `rgba(255,255,255,0.06)` | `rgba(0,0,0,0.05)` |
| Nav item active bg | `rgba(45,212,191,0.10)` | `rgba(15,118,110,0.08)` |
| Nav item active text | `#2DD4BF` | `#0F766E` |
| Nav item active indicator | `3px left border #2DD4BF` | `3px left border #0F766E` |

---

## 4. Typography

### Font Stack

```css
/* Body — all text, labels, UI */
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

/* Numbers — ALL financial values, percentages, counts */
--font-mono: 'DM Mono', 'Fira Code', 'Cascadia Code', monospace;
```

**Rule:** Every `₹` amount, `%` percentage, trade count, P&L, score — must use `font-mono`.
This creates an immediate visual language: "if it's in mono, it's a number that matters."

Load via Google Fonts:
```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
```

### Type Scale

| Token | Class | Size | Weight | Line-height | Letter-spacing | Use |
|---|---|---|---|---|---|---|
| Display | `.t-display` | 28px | 700 | 1.15 | -0.03em | Hero numbers (session P&L, score) |
| Heading LG | `.t-heading-lg` | 20px | 600 | 1.25 | -0.02em | Page titles |
| Heading MD | `.t-heading-md` | 16px | 600 | 1.35 | -0.015em | Card titles |
| Heading SM | `.t-heading-sm` | 14px | 600 | 1.4 | -0.01em | Section headers within cards |
| Body | `.t-body` | 14px | 400 | 1.5 | 0 | Primary reading text |
| Body SM | `.t-body-sm` | 13px | 400 | 1.5 | 0 | Descriptions, secondary copy |
| Caption | `.t-caption` | 12px | 400 | 1.4 | 0.01em | Timestamps, metadata |
| Overline | `.t-overline` | 11px | 500 | 1 | 0.07em | Section category labels (UPPERCASE) |
| Mono | `.t-mono` | 14px | 500 | 1 | 0 | Inline financial numbers |
| Mono SM | `.t-mono-sm` | 12px | 500 | 1 | 0 | Table numbers, compact data |
| Mono LG | `.t-mono-lg` | 20px | 600 | 1 | -0.01em | Medium hero numbers |
| Mono Display | `.t-mono-display` | 28px | 700 | 1.1 | -0.02em | Large hero numbers (P&L, score) |

### Typography Rules (Never Break These)

1. **Numbers are always mono font.** `₹`, `%`, integer counts, P&L — never Inter for these.
2. **Hero numbers use `t-mono-display` (28px/700).** The most important number on a card should
   be the biggest thing visually.
3. **Section labels use `t-overline` + UPPERCASE.** Never use heading styles for category labels.
4. **Page titles use `t-heading-lg` (20px/600).** Not `text-lg` (18px) — that extra 2px matters.
5. **Descriptions use `t-body-sm` (13px) in `--text-secondary` color.** Not `text-sm text-muted-foreground`.
6. **Timestamps use `t-caption` (12px) in `--text-tertiary` color.** The dimmest tier.

---

## 5. Spacing Grid

**Base unit: 4px.** Every spacing value is a multiple of 4.

### Component Spacing Standards (Enforce These — No Exceptions)

| Context | Value | Tailwind | Rule |
|---|---|---|---|
| Card header (with border-bottom) | `px-5 py-3.5` | 20px / 14px | **Always** |
| Card body | `p-5` | 20px all | **Always** |
| Card body (dense table inside) | `p-0` | 0 | Table handles its own rows |
| Table row | `px-5 py-2.5` | 20px / 10px | **Always** |
| Section gap on page | `gap-4` | 16px | **Always** |
| Item gap within section | `gap-3` | 12px | **Always** |
| Page horizontal padding | `px-4 md:px-6` | 16px / 24px | **Always** |
| Page top padding | `pt-6` | 24px | **Always** |
| Sidebar width (expanded) | `w-60` | 240px | Fixed |
| Sidebar width (collapsed) | `w-16` | 64px | Icon only |

### Border Radius Standards

| Token | Value | Use |
|---|---|---|
| `rounded-sm` | 4px | Chips, tiny badges |
| `rounded` | 6px | Buttons, inputs, small elements |
| `rounded-lg` | 8px | Dropdowns, tooltips |
| `rounded-xl` | 12px | **Cards (primary radius for all cards)** |
| `rounded-2xl` | 16px | Modals, bottom sheets |
| `rounded-full` | 9999px | Status dots, avatar, pills |

**Rule:** All `tm-card` / `DataCard` components use `rounded-xl`. No exceptions.

---

## 6. Sidebar Navigation

### Structure

```
┌─────────────────────────────┐
│  ◈ TradeMentor              │  ← Logo + brand name, 20px/600, brand color
│  ─────────────────          │  ← border-subtle divider
│                             │
│  Dashboard                  │  ← Primary nav (no section header)
│  Analytics                  │
│                             │
│  INSIGHTS                   │  ← t-overline, tertiary color
│    My Patterns              │  ← 16px left indent, icon 16px
│    Discipline               │
│    Reports                  │
│                             │
│  RISK                       │  ← t-overline
│    Alerts          ● 3      │  ← red pill badge right-aligned
│    Blowup Shield            │
│    Guardrails               │
│                             │
│  ─────────────────          │  ← flex-1 spacer pushes below to bottom
│                             │
│  Chat                       │
│  Settings                   │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─       │
│  [●] Connected              │  ← connection status, token expiry warning
└─────────────────────────────┘
```

### Sidebar Nav Item Anatomy

```
│  [icon 16px]  Label          [badge?]  │
│  ↑ 3px left accent bar when active     │
```

- Icon: 16px, `--text-secondary` default, `brand` when active
- Label: `t-body` (14px/400) default, `t-heading-sm` (14px/600) when active
- Left border: 3px solid brand color when active (NOT the full background)
- Background: `nav-item-active-bg` (brand tint) when active
- Height: 36px per item
- Padding: `px-4 py-2`

### Collapsed Mode (64px / icon-only)

- Shows only the icon, centered
- Active item: brand-colored icon
- Tooltip on hover showing the label
- Section headers hidden
- Logo shrinks to icon only

### Mobile (unchanged pattern, style updated)

Bottom tab bar — 4 primary items:
- Dashboard, Analytics, Alerts (with badge), Chat
- "More" opens a bottom sheet with remaining items
- Height: 56px (current 64px is too tall)
- Active indicator: 2px top border on the tab (current thin bar stays)

---

## 7. Card Anatomy — Standard `DataCard`

Every card in the app must use this identical structure:

```
┌────────────────────────────────────────────┐
│  Title                     [Optional CTA]  │  ← Header: px-5 py-3.5 + border-b
│  Optional subtitle                         │  ← Same header div
├────────────────────────────────────────────┤  ← border-subtle (1px)
│                                            │
│  Content                                   │  ← Body: p-5 (or p-0 for tables)
│                                            │
└────────────────────────────────────────────┘
└── rounded-xl, overflow-hidden, shadow-card ──┘
```

**CSS classes on the root element (always):**
```
rounded-xl overflow-hidden [shadow-card]
```

- `overflow-hidden` is non-negotiable — without it, child content bleeds outside the radius
- Every card uses it, no exceptions

**What the card is NOT:**
- Not clickable by itself (the content inside may have clickable rows)
- Not animated on mount (only content inside animates)
- Not `rounded-2xl` — that's for modals

---

## 8. Interactive States

### Buttons

| State | Primary (teal) | Secondary / Ghost |
|---|---|---|
| Default | brand bg, white text | transparent, border |
| Hover | brand-hover bg, 150ms | muted-bg, 150ms |
| Active | `scale(0.98)`, 80ms | `scale(0.98)`, 80ms |
| Focus | `ring-2 ring-brand ring-offset-2` | same |
| Disabled | 40% opacity, no pointer | same |

### Clickable Rows (trade rows, alert items)

| State | Dark | Light |
|---|---|---|
| Default | transparent | transparent |
| Hover | `rgba(255,255,255,0.04)` overlay | `rgba(0,0,0,0.03)` overlay |
| Active | `rgba(255,255,255,0.07)` | `rgba(0,0,0,0.06)` |
| Transition | 120ms ease-out | same |

### Form Inputs

| State | Dark | Light |
|---|---|---|
| Default | `border-border` | `border-border` |
| Hover | `border-border/70` brighter | slightly darker border |
| Focus | `border-brand` + `ring-2 ring-brand/20` | same |
| Error | `border-loss` + `ring-2 ring-loss/20` | same |

### Navigation Items (sidebar)

| State | Transition |
|---|---|
| Hover → shows overlay bg | 100ms |
| Active → left border slides in | 150ms, the border "appears" not "flashes" |
| Active text → becomes brand color | 150ms |

---

## 9. Alert / Status Visual Language

### Alert Row Severity (Alerts page, Dashboard alerts section)

**Danger:**
```
│▌ [● red 8px]  TITLE                    │
│  Left 3px border: #F87171 dark / #B91C1C light
│  Row bg: status-danger-bg
│  Icon: AlertTriangle, 16px, loss color
```

**Caution:**
```
│▌ [● amber 8px]  TITLE                  │
│  Left 3px border: #FBBF24 dark / #92400E light
│  Row bg: status-caution-bg
```

**Current:** `border-l-2 border-tm-obs` — easy to miss, no background.
**New:** 3px border + background tint — immediately visible in peripheral vision.

### Inline Status Chips

```
[● ▲]  DANGER      ← red fill dot, red text, 10px/500
[● ▲]  CAUTION     ← amber fill dot, amber text
[●   ]  INFO        ← blue fill dot
```

---

## 10. Financial Number Treatment

### Hero Number Pattern

Used when a number is the primary content of a card:

```
P&L Today                           ← t-overline, tertiary color
-₹12,450                            ← t-mono-display (28px/700), loss color
▼ 2.3% from yesterday               ← t-body-sm, secondary color, trend icon
```

**Never:** Use the same text size for the label and the number.
**Always:** The number is the largest element in the card.

### Inline Number Pattern (tables, breakdowns)

```
SYMBOL      QTY      P&L           ← t-overline, column headers
NIFTY24     50       +₹2,450       ← t-body-sm (symbol) + t-mono-sm (numbers)
BANKNIFTY   25       -₹1,200
```

Numbers right-aligned. Column headers left-aligned (or right if column is numeric).

### Percentage Change Chips

```
▲ 4.2%    ← green, t-mono-sm, rounded-sm, profit-bg bg
▼ 1.8%    ← red, t-mono-sm, rounded-sm, loss-bg bg
```

Used sparingly — only on KPI cards, not in tables.

---

## 11. Micro-interactions

### Keep (already correct)

- Spring easing: `cubic-bezier(0.16, 1, 0.3, 1)` for all enter transitions
- `fadeInUp` on first content mount (not on every re-render)
- `slideInUp` on bottom sheets and modals
- Skeleton loading states (already in place on most pages)

### Add

| Interaction | Implementation | Duration |
|---|---|---|
| Skeleton → content | Crossfade: skeleton fades out, content fades in simultaneously | 150ms |
| Number load | Count up/down from 0 to final value (P&L hero, score gauge) | 600ms ease-out |
| Alert badge | Subtle pulse `scale(1.0→1.12→1.0)` every 4s when unread > 0 | 300ms |
| Sidebar collapse | Width transitions smoothly 240→64px | 200ms ease-in-out |
| Nav active indicator | Left border slides from prev to current (translate transform) | 150ms |

### Remove

- Page-level entry animations on every render (only on initial mount)
- Hover scale on non-interactive card containers
- Any animation that repeats on every data refresh

---

## 12. Implementation Phases

### Phase 1 — Token Foundation (index.css + tailwind.config.ts)
*Impact: Every screen improves simultaneously*

Changes:
- Replace layer colors (dark + light) — the `#09090C / #111116 / #1A1A22` system
- Add 3-tier text colors (`--text-primary/secondary/tertiary`)
- Add status system tokens (danger/caution/success/info bg+border+text)
- Add shadow tokens (card/elevated/sheet for both themes)
- Add DM Mono as font-family, register as Tailwind token
- Add type scale as Tailwind utilities (`t-display`, `t-heading-lg`, etc.)
- Add sidebar color tokens
- Fix financial token contrast (light mode profit/loss/obs all currently fail WCAG)

Files: `src/index.css`, `tailwind.config.ts`

### Phase 2 — Navigation (Sidebar)
*Impact: Biggest single visual quality upgrade*

Changes:
- New `Sidebar.tsx` component replacing top-nav in `Layout.tsx`
- Collapsible state (240px ↔ 64px) stored in localStorage
- Section grouping, active state with left border indicator
- Alert badge on Alerts item
- Connection status / token expiry at bottom
- Mobile: clean up bottom tab bar (56px height, style update)

Files: `src/components/Layout.tsx`, new `src/components/Sidebar.tsx`

### Phase 3 — Card Anatomy
*Impact: Eliminates spacing inconsistency across all pages*

Changes:
- Create `src/components/ui/data-card.tsx` — single `DataCard` wrapper
- Replace all `tm-card overflow-hidden` + manual header/body divs with `DataCard`
- Enforce `rounded-xl overflow-hidden shadow-card` on all cards
- Standardize `px-5 py-3.5` header + `p-5` body everywhere

Files: New `data-card.tsx`, then sweep all pages

### Phase 4 — Interactive States
*Impact: Makes the app feel alive and responsive*

Changes:
- Update shadcn/ui button variants to new states
- Add hover/active to all trade rows, alert rows
- Update form inputs (focus ring, error state)
- Update sidebar nav item states

Files: `src/components/ui/button.tsx`, `src/index.css`, alert/trade row components

### Phase 5 — Typography Pass
*Impact: Hierarchy becomes immediately readable*

Changes:
- Apply type scale tokens page by page
- Apply `t-mono-display` / `t-mono-lg` to all hero numbers
- Apply `t-overline` to all section category labels
- Apply `t-caption` + tertiary color to all timestamps/metadata
- DM Mono font applied to all financial numbers

Files: All page components and shared components

### Phase 6 — Alert Visual Language
*Impact: Danger/caution severity is instantly visible*

Changes:
- Update all alert row components with 3px left border + status bg tint
- Update severity dots to 8px filled circles
- Update Dashboard alert list
- Update Alerts page list view

Files: Alert components, Dashboard, Alerts page

### Phase 7 — Micro-interactions
*Impact: App feels polished and premium*

Changes:
- Skeleton → content crossfade
- Number count-up animation for hero P&L and score gauge
- Alert badge pulse
- Sidebar collapse animation

Files: `src/index.css`, Skeleton wrapper, hero number components

---

## 13. What Does NOT Change

| Item | Reason |
|---|---|
| Teal brand color | It's ours, distinctive in Indian fintech |
| Inter for body text | Correct for data-dense fintech |
| shadcn/ui components | Keep as base, style on top |
| CSS variable system | Infrastructure is correct, just updating values |
| Financial token names (tm-profit/loss/obs/brand) | Used everywhere, just changing the values |
| Bottom nav on mobile | Pattern is right, just styling update |
| Behavioral alert logic | No UI for that changes here |
| Page layouts / routing | No structural changes to page content |

---

## 14. Quick Reference Cheatsheet

```
DARK LAYERS          LIGHT LAYERS
Page:    #09090C     Page:    #F2F2F7
Surface: #111116     Surface: #FFFFFF
Elevated:#1A1A22     Elevated:#F8F8FC
Overlay: #232330     Overlay: #EEEFF6
Border:  #2A2A38     Border:  #E2E2EE

TEXT (DARK)          TEXT (LIGHT)
Primary:  #F0F0F8    Primary:  #0C0C14
Secondary:#9898B0    Secondary:#60607A
Tertiary: #5A5A72    Tertiary: #9898AE

FINANCIAL (DARK)     FINANCIAL (LIGHT)
Profit: #4ADE80      Profit: #15803D
Loss:   #F87171      Loss:   #B91C1C
Obs:    #FBBF24      Obs:    #92400E
Brand:  #2DD4BF      Brand:  #0F766E

FONTS
Body:    Inter 400/500/600/700
Numbers: DM Mono 400/500 (ALL ₹ % counts)

CARD RADIUS: rounded-xl (12px) — always
CARD PADDING: header px-5 py-3.5 | body p-5 — always
SIDEBAR: 240px expanded | 64px icon-only
```
