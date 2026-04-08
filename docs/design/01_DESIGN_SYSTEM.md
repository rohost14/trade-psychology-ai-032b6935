# TradeMentor AI — Design System
*Universal design tokens and component specs. Reference this in every screen spec. Never define a color, font size, or spacing value in a screen doc — use a token name from here.*

---

## STATUS: COLORS + TYPOGRAPHY CONFIRMED (Session 31, 2026-04-02)
*Spacing, radius, elevation confirmed. Component specs to be filled per screen design session.*

---

## 1. Color Tokens

### Theme Structure
**Dark chrome + light content.** Sidebar, header, footer = dark. Card surfaces and main content = white/light. One theme — no toggle for now.

### Dark Chrome (sidebar, header, footer)

| Token | Purpose | Hex | Tailwind approx |
|-------|---------|-----|----------------|
| `nav-bg` | Sidebar + header background | `#0F172A` | `bg-slate-900` |
| `nav-text` | Default nav text | `#CBD5E1` | `text-slate-300` |
| `nav-text-active` | Active nav item text | `#2DD4BF` | `text-teal-300` |
| `nav-active-bg` | Active nav item background tint | `#0D948812` | teal-700 at 12% opacity |
| `nav-border` | Borders within nav | `#1E293B` | `border-slate-800` |

### Light Content Area

| Token | Purpose | Hex | Tailwind approx |
|-------|---------|-----|----------------|
| `color-bg` | Page background (behind cards) | `#F1F5F9` | `bg-slate-100` |
| `color-surface` | Card / table wrapper background | `#FFFFFF` | `bg-white` |
| `color-surface-elevated` | Dropdowns, modals, bottom sheets | `#FFFFFF` | `bg-white` |
| `color-border` | Card borders, dividers, table wrappers | `#E2E8F0` | `border-slate-200` |
| `color-hover` | Table row hover background | `#F8FAFC` | `bg-slate-50` |

### Text (for light content area)

| Token | Purpose | Hex | Tailwind approx |
|-------|---------|-----|----------------|
| `color-text-primary` | Main readable text | `#0F172A` | `text-slate-900` |
| `color-text-secondary` | Labels, metadata, timestamps | `#64748B` | `text-slate-500` |
| `color-text-muted` | Disabled, placeholder, section labels | `#94A3B8` | `text-slate-400` |

### Brand — Teal

| Token | Purpose | Hex | Tailwind approx |
|-------|---------|-----|----------------|
| `color-brand` | Buttons, active states, links on light bg | `#0D9488` | `text-teal-700` / `bg-teal-700` |
| `color-brand-dark` | Active nav text, links on dark chrome | `#2DD4BF` | `text-teal-300` |
| `color-brand-subtle` | Hover bg, active nav bg tint | `#0D948812` | teal-700 at 12% opacity |

### Financial Semantic — LOCKED
**Never use these colors for anything that is not actual profit or loss.**

| Token | Purpose | Hex | Tailwind approx |
|-------|---------|-----|----------------|
| `color-profit` | Positive P&L, gains | `#16A34A` | `text-green-700` |
| `color-loss` | Negative P&L, losses | `#DC2626` | `text-red-600` |

*Why green-700 not green-500: darker green is clearly distinct from teal brand and reads well on white.*

### Behavioral Observation — Amber

| Token | Purpose | Hex | Tailwind approx |
|-------|---------|-----|----------------|
| `color-observation` | Alert severity dot, ⚠/✎ indicators, unread state | `#D97706` | `text-amber-600` |
| `color-observation-bg` | Background tint in full alert detail sheet | `#FEF3C7` | `bg-amber-50` |

**Rule:** Amber is for behavioral pattern observations ONLY. Never use for generic UI warnings.

**Rule:** `color-loss` (red-600) and critical-severity alerts are both red. Distinguish by font weight and size — never same weight/size in same view.

### Elevation / Shadow

| Level | Use | Value |
|-------|-----|-------|
| Flat (default) | All data cards, table wrappers | `border border-slate-200` only — no box-shadow |
| Sheet | Bottom sheets, modals | `shadow-xl` |
| Dropdown | Popovers, tooltips, command palette | `shadow-md` |

---

## 2. Typography

**Font family: Inter** (confirmed Session 31).
**Monospace fallback: `font-mono` (system mono)** for all financial numbers — ensures digit alignment in tables.

All body text: `font-sans` (Inter).
All numbers, prices, P&L, quantities, times: `font-mono tabular-nums`.

| Token | Use | Size | Weight | Line height | Tailwind |
|-------|-----|------|--------|------------|---------|
| `type-page-title` | Page heading ("Dashboard") | 20px | 600 | 28px | `text-xl font-semibold` |
| `type-h2` | Section title, card title | 16px | 600 | 24px | `text-base font-semibold` |
| `type-h3` | Sub-section label (ALL CAPS, tracked) | 12px | 500 | 16px | `text-xs font-medium uppercase tracking-widest` |
| `type-body` | Default readable text, table cells | 14px | 400 | 20px | `text-sm font-normal` |
| `type-body-medium` | Pattern names, emphasized content | 14px | 500 | 20px | `text-sm font-medium` |
| `type-body-sm` | Secondary info, metadata | 13px | 400 | 18px | `text-[13px] font-normal` |
| `type-caption` | Timestamps, footnotes | 12px | 400 | 16px | `text-xs font-normal` |
| `type-label` | Form labels, stat labels below numbers | 12px | 500 | 16px | `text-xs font-medium` |
| `type-mono` | Trade data, prices, P&L (table) | 14px | 500 | 20px | `text-sm font-mono font-medium tabular-nums` |
| `type-mono-lg` | Prominent numbers (Blowup Shield score) | 30px | 700 | 36px | `text-3xl font-bold font-mono` |
| `type-stat` | Page header stat numbers | 14px | 400 | 20px | `text-sm font-normal` |

---

## 3. Spacing Scale (4px grid)

| Token | Value | Tailwind | Use |
|-------|-------|---------|-----|
| `space-1` | 4px | `gap-1 / p-1` | Icon gaps, tight internal |
| `space-2` | 8px | `gap-2 / p-2` | Compact element padding |
| `space-3` | 12px | `gap-3 / p-3` | Table cell padding, chip padding |
| `space-4` | 16px | `gap-4 / p-4` | Standard card padding, mobile page padding |
| `space-5` | 20px | `gap-5 / p-5` | Section gap on mobile |
| `space-6` | 24px | `gap-6 / p-6` | Web page padding, section gap on web |
| `space-8` | 32px | `gap-8 / p-8` | Large section breaks |

---

## 4. Border Radius

| Token | Value | Tailwind | Use |
|-------|-------|---------|-----|
| `radius-sm` | 4px | `rounded-sm` | Chips, small badges |
| `radius-md` | 6px | `rounded-md` | Buttons, inputs |
| `radius-lg` | 8px | `rounded-lg` | Cards — MAXIMUM for any data screen |
| `radius-xl` | 12px | `rounded-xl` | Bottom sheets (top corners only), modals |
| `radius-full` | 9999px | `rounded-full` | Status dots, avatar circles |

**Rule:** No card on any data screen exceeds 8px radius. Larger only on overlays.

---

## 5. Layout Tokens

### Web
| Element | Value |
|---------|-------|
| Sidebar width | 208px |
| Main content max-width | 1200px |
| Page horizontal padding | 24px |
| Page top padding | 24px |
| Two-column split (dashboard) | Left 62% / Right 38% / Gap 24px |
| Section gap (vertical between sections) | 20px — use whitespace, not divider lines |
| Card internal padding | 16px (compact) or 24px (comfortable) |

### Mobile
| Element | Value |
|---------|-------|
| Bottom nav height | 64px |
| Safe area | `env(safe-area-inset-bottom)` |
| Page horizontal padding | 16px |
| Page top padding | 16px |
| Card internal padding | 16px |
| Section gap | 20px |

---

## 6. Density Modes

### HIGH density — Analytics tables, Alerts history
- Row height: 40px (`h-10`)
- Font: `type-body-sm` (13px)
- Cell horizontal padding: 12px
- No card elevation — table flush to wrapper edges

### MEDIUM density — Dashboard (positions tables, alert rows)
- Row height: 44px (`h-11`)
- Font: `type-body` (14px)
- Cell horizontal padding: 16px

### LOW density — Settings, Goals, Chat
- No table layout — section-based with labeled fields
- Font: `type-body` (14px), labels: `type-label`
- Section padding: 24px

---

## 7. Component Tokens

### Alert Severity Dot
- Size: 7px × 7px, `rounded-full`
- Critical / High: `bg-red-600` (same family as loss, but context distinguishes)
- Medium (default): `bg-amber-600` (`color-observation`)
- Low / Read: `bg-slate-400` (`color-text-muted`)
- Position: left-aligned in alert row, vertically centered

### Journal Icon States
- 16px pencil icon (Lucide `Pencil`)
- Not journaled: `text-slate-400` with amber 5px dot overlay top-right
- Journaled: `text-teal-700` (`color-brand`), no dot
- Tap area: 44px × 44px minimum

### Section Label
Applied to every section header (OPEN POSITIONS, CLOSED TODAY, etc.):
- `text-xs font-medium uppercase tracking-widest text-slate-400`
- `border-b border-slate-200` below it, `mb-2`
- Right side (count, status): `text-xs text-slate-400` or `text-amber-600` if actionable

### P&L Value
- Font: `type-mono` (tabular-nums, font-medium)
- Positive: `text-green-700` (`color-profit`)
- Negative: `text-red-600` (`color-loss`)
- Zero: `text-slate-400`
- Always include sign: `+₹2,400` or `–₹1,200` (use en-dash not hyphen)
- Always include ₹ prefix

### Bottom Sheet
- `rounded-t-xl` (12px top corners only)
- `bg-white shadow-xl`
- Drag handle: `w-10 h-1 bg-slate-200 rounded-full mx-auto mt-3 mb-4`
- Web: 480px wide, centered, fixed bottom
- Mobile: full width, fixed bottom
- Backdrop: `bg-black/40`, tap to close

---

## 8. Anti-Vibe-Code Rules (Non-Negotiable)

| Banned | Replacement |
|--------|------------|
| Rounded corners > 8px on data cards | `rounded-lg` max |
| Gradient backgrounds anywhere | Flat solid colors only |
| Glassmorphism / `backdrop-blur` | Never |
| Drop shadows on data cards | Border only (`border border-slate-200`) |
| Colored card backgrounds for alerts | White card, severity dot on row |
| Left colored border strips on cards | Small severity dot left of row |
| Card-per-alert layout | List rows in a section |
| Metric card grid (4 KPI tiles) | Inline stat line or stat section |
| Emoji in data UI | Lucide icons only |
| Bold/colored section headers | Small caps, `text-slate-400`, whisper-quiet |
| Animations on live-updating numbers | No animation on auto-updating data |
| Spring/bounce animations | Linear or ease-out only, ≤ 250ms |

---

## 9. Motion

| Use case | Animation | Duration |
|---------|-----------|---------|
| Bottom sheet open | Slide up (`translateY` 100% → 0) | 250ms ease-out |
| Bottom sheet close | Slide down | 200ms ease-in |
| Page transition | Fade (opacity 0→1) | 150ms |
| Tab switch | Cross-fade | 100ms |
| Toast | Slide in top-right | 200ms |
| Accordion expand | Height | 200ms ease |
| Hover state | Background color | 100ms |
| **Live number update** | **None** | **— never animate auto-updating data** |

---

*Screen specs: [`screens/`](./screens/) — one file per screen, web + mobile together*
*Checklist: [`DESIGN_CHECKLIST.md`](./DESIGN_CHECKLIST.md)*
*Philosophy + IA: [`00_OVERVIEW.md`](./00_OVERVIEW.md)*
