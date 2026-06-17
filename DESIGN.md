# Design System: TradeMentor AI

> Optimized for Google Stitch screen generation.
> Single source of truth for all UI screens — dashboard, alerts, analytics, settings, landing.

---

## 1. Visual Theme & Atmosphere

**Design Read:** Daily-use behavioral cockpit for active Indian F&O traders. The atmosphere is clinical restraint with warmth — like a precision instrument built inside a quiet office. Not a startup dashboard, not a terminal. Somewhere between Notion's calm structure and a well-lit trading workstation.

- **Density: 7/10** — Data-rich but never cluttered. Numbers earn space by being consequential. Labels are always shorter than the data they describe.
- **Variance: 5/10** — Structured asymmetry. Two-column grids, section strips, horizontal scan zones. Not artsy, not perfectly symmetric. Information hierarchy creates the rhythm.
- **Motion: 4/10** — Functional only. P&L numbers count up. Alerts pulse once. Rows fade in. Nothing loops for decoration. The trader's eyes track data, not animations.

**Tone words:** Precise · Observational · Calm · Trustworthy · Serious without being cold

**What this is NOT:** An AI SaaS product. Not purple. Not glowing. Not "next-gen." Not a startup hackathon project. A daily tool that a serious trader opens every morning before 9:15 AM IST.

**Reference aesthetic:** Zerodha Kite (data density, restrained color), Dhan (clean card surfaces), Sensibull (structured hierarchy). NOT Robinhood, NOT Bloomberg terminal, NOT AI startup purple.

---

## 2. Color Palette & Roles

### Light Theme (Default)

- **Indigo Page** (`#F4F5FA`) — Page background. Blue-indigo undertone throughout. Not pure white. Creates immediate sense of calm structure.
- **Pure Surface** (`#FFFFFF`) — Card fills, modals, sheets. The brightest layer.
- **Elevated Surface** (`#F8F8FC`) — Sidebar, popover backgrounds. One step above page.
- **Hover Overlay** (`#EBEDF4`) — Row hover, dropdown items. Never used for borders.
- **Card Border** (`#E1E4EC`) — 1px card edges, section dividers. Slightly blue-tinted.
- **Subtle Divider** (`#E9EBF2`) — Row separators inside cards. Barely visible.

- **Charcoal Ink** (`#1E2233`) — Primary headings, key numbers, symbol names. Full weight.
- **Muted Steel** (`#6C7287`) — Labels, descriptions, secondary info. 60% presence.
- **Ghost Text** (`#9898AE`) — Timestamps, metadata, placeholder text. 40% presence.

- **Brand Indigo** (`#4453C9`) — Single accent. CTAs, active states, focus rings, brand chip. NEVER used for P&L or alerts.
- **Profit Green** (`#34A26C`) — ONLY for positive P&L, gains, win markers. Locked.
- **Loss Red** (`#E15A4D`) — ONLY for negative P&L, losses, danger alerts. Locked.
- **Alert Amber** (`#F0A21A`) — Behavioral observations, caution states, morning intent. Never used as a generic color.

### Dark Theme

- **Deep Navy** (`#16181F`) — Page background. hsl(226, 22%, 11%). Not pure black.
- **Dark Surface** (`#1E2029`) — Card fills. One step lighter than page.
- **Elevated Dark** (`#2A2D38`) — Sidebar, popovers, modals.
- **Muted Dark** (`#343746`) — Hover states, overlay rows.
- **Dark Border** (`#2E313D`) — Card edges, dividers.
- **Subtle Dark** (`#242732`) — Row separators inside cards.

- **Light Foreground** (`#E5E7EE`) — Primary text in dark mode.
- **Muted Foreground** (`#9498A5`) — Secondary text, labels.
- **Ghost Dark** (`#6C7287`) — Metadata, timestamps.

- **Brand Indigo Dark** (`#7785E0`) — Same semantic role, adjusted for dark contrast.
- **Profit Dark** (`#34A26C`) — Same hex. Green is green in both themes.
- **Loss Dark** (`#E26B5E`) — Slightly lighter red for dark mode legibility.
- **Amber Dark** (`#F0A21A`) — Same hex.

### Color Rules (Non-Negotiable)

- Max 1 accent color (Brand Indigo). No secondary accent.
- Profit green and Loss red are LOCKED to financial P&L only. Never use as decorative colors.
- Amber is LOCKED to behavioral observations and warnings.
- No purple. No teal. No neon. No gradient backgrounds.
- Shadows are tinted to the background hue — `rgba(68,83,201,0.06)` not `rgba(0,0,0,0.1)`.

---

## 3. Typography Rules

### Font Stack

- **Display & UI:** `Geist`, `Outfit`, `-apple-system`, `sans-serif` — Replace Inter entirely. Geist has sharper number rendering, cleaner headline weight, no "AI startup" associations.
- **Financial Numbers:** `DM Mono`, `Fira Code`, `ui-monospace` — Every ₹ amount, %, quantity, price. No exceptions. `font-variant-numeric: tabular-nums` always on.
- **Code/Meta:** `DM Mono` — Same family as numbers. Unified mono voice.

### Type Scale

| Role | Size | Weight | Tracking | Line Height | Notes |
|---|---|---|---|---|---|
| Card Title Label | `10–11px` | 700 | `+0.07–0.09em` | 1.2 | `uppercase` only for zone/section labels |
| Body Primary | `14px` | 500 | `0` | 1.5 | Alert text, descriptions |
| Body Secondary | `13px` | 400 | `0` | 1.45 | Supporting copy |
| Data Hero | `24px` (Mono) | 800 | `-0.02em` | 1.0 | Session P&L |
| Data Primary | `15–16px` (Mono) | 600 | `0` | 1.1 | Position P&L, subtotals |
| Data Secondary | `12.5–13px` (Mono) | 500 | `0` | 1.2 | Prices, quantities, ratios |
| Zone Label | `9.5px` | 700 | `+0.09em` | 1.0 | `uppercase` inside session strip |
| Caption | `11–11.5px` | 400 | `0` | 1.4 | Timestamps, metadata |
| Chip | `9.5px` | 700 | `+0.06em` | 1.0 | Severity chips, product badges |

### Typography Rules

- ALL financial numbers: `font-mono tabular-nums` no exceptions
- Zone labels in session strip: `uppercase tracking-[0.09em] text-[9.5px] font-bold`
- Card section headers: sentence case only. No Title Case.
- Headings track-tight at 20px+. Body text track-normal.
- Body text never wider than 65 characters.
- **Banned:** Inter as primary font. All-caps body copy. Gradient text. Generic serifs.

---

## 4. Component Stylings

### Session Strip (Compact Top Band)

The 72px horizontal band at the top of the dashboard. Replaces any "hero card." NOT a card — it's a surface band.

- Structure: `border-b border-border bg-card/60 backdrop-blur-sm`
- Full-bleed: `-mx-4 sm:-mx-6 md:-mx-8` so it touches viewport edges
- Desktop: `hidden md:flex divide-x divide-border` — single horizontal row
- Mobile: `md:hidden grid grid-cols-3 divide-x divide-border` — two rows of three
- Each zone: `flex flex-col justify-center px-4 py-3`
- Zone label: `text-[9.5px] font-bold uppercase tracking-[0.09em] text-muted-foreground/70 mb-1.5`
- Zone value: DM Mono, size varies by zone importance
- No shadow. No card border. It IS the surface.

### Cards (`tm-card`)

- Structure: `bg-white dark:bg-[#1E2029] border border-[#E1E4EC] dark:border-[#2E313D] rounded-xl overflow-hidden`
- No drop shadow by default
- Hover: `hover:shadow-[0_2px_8px_rgba(68,83,201,0.06)]` — indigo-tinted, 200ms transition
- Header zone: `px-5 py-3.5 border-b border-border flex items-center justify-between`
- Header label: `text-[10.5px] font-bold uppercase tracking-[0.07em] text-muted-foreground`
- Content zone: `p-5`
- Row separators: `border-b border-border/50` — subtle, not heavy
- Row hover: `hover:bg-muted/40` — never severity-colored

### Alert Rows (STRICT — no left border stripes)

The most important component rule in this design system.

- Each alert: `w-full flex items-start gap-3 px-5 py-3.5 border-b border-border`
- Hover: `hover:bg-muted/40` ONLY — no color tinting
- Left content: Pattern name (`font-semibold text-foreground`) + description (`text-muted-foreground`)
- Right column: Severity chip stacked above timestamp
- Acknowledged: `opacity-50` + inline `✓` after pattern name

**Severity Chip:**
- Danger → `bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400` — label "High"
- Caution → `bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400` — label "Med"
- Positive → `bg-green-100 text-green-700` — label "Good"
- Chip style: `text-[9.5px] font-bold uppercase tracking-[0.06em] px-1.5 py-0.5 rounded`

**ABSOLUTELY BANNED on alert rows:**
- `border-l-[3px]` or any width left border in a severity color
- `bg-red-50`, `bg-amber-50` tinted row backgrounds
- Full-color alert rows
- This is the single biggest "vibecoded" tell in trading dashboards

### Morning Intent Card (Amber — NOT an alert)

Completely separate visual language from alerts. Trader must see difference instantly.

- Container: `rounded-xl border bg-amber-50 dark:bg-amber-900/[0.12] border-amber-200/70 dark:border-amber-700/30`
- Header: Pencil icon (amber) + `text-[10px] font-bold uppercase tracking-[0.1em] text-amber-700` label
- Plan text: `text-[15px] font-medium italic text-amber-900 dark:text-amber-100` — quoted format `"Max 8 trades · ₹10,000 loss limit"`
- Commit button: `bg-amber-500 hover:bg-amber-600 text-white rounded-xl h-10 font-semibold text-[13px]`
- Override inputs: amber-tinted `bg-amber-100/60 border-amber-300/60`
- NEVER uses Brand Indigo. Completely amber palette throughout.

### Buttons

- **Primary:** `bg-[#4453C9] text-white rounded-lg px-4 py-2 text-sm font-semibold`
  - Hover: `bg-[#3a48b5]` (darken only, never lighten)
  - Active: `scale-[0.98] translate-y-[1px]` — tactile press, 100ms
  - No glow, no gradient, no outer ring on hover
- **Ghost:** `border border-border text-foreground bg-transparent hover:bg-muted/40`
- **Destructive:** `bg-[#E15A4D] text-white` — confirm-delete only
- **Amber:** `bg-amber-500 hover:bg-amber-600 text-white` — morning intent only
- All: `focus-visible:ring-2 focus-visible:ring-[#4453C9]` for keyboard nav
- Min height: 36px. Touch targets 44px on mobile.

### Position Cards (Mobile Horizontal Scroll)

- Container: `overflow-x-auto flex gap-3 px-4 py-3 snap-x snap-mandatory [-webkit-overflow-scrolling:touch]`
- Card: `flex-shrink-0 snap-start w-44 rounded-xl border p-3.5 bg-card`
- Border: `border-[#34A26C]/20` (profit) or `border-[#E15A4D]/20` (loss) based on P&L
- Hover: `hover:bg-muted/30 transition-colors`
- P&L number: `text-[16px] font-black font-mono tabular-nums` — largest element on card
- Symbol: `text-[13px] font-semibold` + small product chip
- No shadow on individual cards — border color is the only visual signal

### Data Tables (Desktop)

- Header row: `border-b border-border`
- Header cell: `py-3 text-[10.5px] font-semibold uppercase tracking-[0.07em] text-muted-foreground`
- Body row: `hover:bg-muted/30 transition-colors` + `border-b border-border/50`
- No alternating row colors (zebra). Dividers only.
- All numbers: `font-mono tabular-nums`
- Hidden on mobile (`hidden md:table`) — replaced by snap-scroll cards

### Product/Type Chips

- CE: `bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400`
- PE: `bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400`
- FUT/EQ: `bg-muted/60 text-muted-foreground`
- Style: `text-[9.5px] font-bold uppercase px-1.5 py-0.5 rounded`

### Loading States (Skeletons)

- `bg-muted animate-pulse rounded` matching EXACT content dimensions
- Never generic circular spinners
- Strip skeleton: single `h-[72px]` block
- Card header: `h-4 w-32 bg-muted animate-pulse rounded`
- Card rows: `h-10 bg-muted animate-pulse rounded` × 2–3
- Position scroll skeleton: `h-24 w-44 flex-shrink-0 bg-muted animate-pulse rounded-xl` × 2

### Empty States

- Centered inside card content area, `py-10–12`
- Icon: Lucide, `h-8–10 w-8–10 text-muted-foreground/30 mx-auto mb-2.5`
- Title: `text-sm font-medium text-foreground`
- Sub: `text-[13px] text-muted-foreground mt-0.5`
- No emojis. No exclamation marks. Calm, informational.

### Form Inputs

- Label: `text-[10.5px] font-medium text-muted-foreground mb-1` (above input)
- Input: `rounded-lg border border-border bg-background px-3 py-2 text-sm`
- Focus: `ring-1 ring-ring` (indigo ring)
- Error text below: `text-[12px] text-[#E15A4D] mt-1`
- No floating labels. No inner icons unless functionally necessary.

---

## 5. Layout Principles

### Dashboard Layout

**Desktop (≥1024px):** CSS Grid two-column `grid-cols-[65fr_35fr] gap-5`
- Left (65%): Alerts → Open Positions → Closed Trades
- Right (35%, `lg:sticky lg:top-4`): Morning Intent → Predictive Context → Setup Nudge → EOD Comparison

**Mobile (<1024px):** Single column stack
- Session Strip → Morning Intent → Alerts → Position Cards (horizontal scroll) → Trades → EOD → Setup Nudge

**Session Strip:** Full-bleed band, no card wrapping, no shadow. Sits between top nav and content.

### Grid Rules

- CSS Grid over Flexbox math — never `calc()` percentage hacks
- Section gaps: `gap-4` mobile, `gap-5` desktop
- No overlapping elements — every element occupies its own clear spatial zone
- `min-h-[100dvh]` for full-viewport heights, NEVER `h-screen`
- Max-width: `max-w-7xl mx-auto` on page wrapper

### Responsive Breakpoints

| Breakpoint | Width | Behavior |
|---|---|---|
| Mobile | `< 768px` | Single column, bottom nav, snap cards |
| Tablet | `768px–1023px` | Single column, wider cards |
| Desktop | `≥ 1024px` | Two-column dashboard grid |

### Spacing System (8px base)

- Between cards: `gap-4` (16px)
- Desktop column gap: `gap-5` (20px)
- Card header padding: `px-5 py-3.5`
- Card content padding: `p-5`
- Table cells: `px-3–5 py-3`
- Session strip zones: `px-4 py-3`
- Page padding: `px-4 sm:px-6 md:px-8 py-4 md:py-6`

---

## 6. Motion & Interaction

### Principles

Motion serves the trader, not the designer. Every animation communicates state change or confirms interaction. Nothing runs purely for aesthetics.

Hardware-accelerated only: `transform` + `opacity`. Never animate `top/left/width/height`.
Total animation budget per interaction: ≤300ms.

### Active Animations

| Element | Animation | Duration | Trigger |
|---|---|---|---|
| Session P&L | Count-up (useCountUp) | 500ms | Mount + value change |
| Price flash (up) | `text-[#34A26C]` → normal | 600ms | `last_price` increases |
| Price flash (down) | `text-[#E15A4D]` → normal | 600ms | `last_price` decreases |
| Alert dot | `animate-pulse` on amber circle | Infinite | While unread alerts exist |
| Card hover | Indigo shadow appear | 200ms | `hover:` |
| Button press | `scale-[0.98] translate-y-[1px]` | 100ms | `active:` |
| Alert row mount | `fade-in slide-in-from-top-1` | 150ms | Staggered by index × 50ms |
| Sheet open | Slide from right | 250ms | `data-[state=open]` |

### What Never Animates

- Page navigation (instant)
- Table content replacement (in-place)
- Skeleton → content transition (instant swap, no fade)
- Background elements, decorative shapes

---

## 7. Anti-Patterns (Banned)

These are the patterns that make TradeMentor look "vibecoded." Strictly forbidden:

### Typography Bans
- `Inter` as primary UI font — replace with `Geist`
- All-caps body copy (zone labels are the only uppercase exception, max 10.5px)
- Gradient text on headings or P&L numbers
- Generic serif fonts anywhere in the app UI
- Title Case On Every Card Header — sentence case only

### Color Bans
- Purple or violet anything in the app UI
- Neon glow shadows (`box-shadow: 0 0 20px rgba(...)`)
- Oversaturated accents (saturation > 80%)
- Pure black `#000000` backgrounds (use `#16181F` in dark mode)
- Multiple accent colors — max 1 (Brand Indigo `#4453C9`)
- Using Profit Green or Loss Red as decorative colors unrelated to financial P&L
- Mixing warm and cool grays within the same theme
- Purple/blue gradient hero backgrounds (the #1 AI design tell)

### Component Bans
- **`border-l-[3px]` colored left stripes on alert rows** — this is the #1 "vibecoded" pattern to eliminate
- **Tinted row backgrounds by severity** (`bg-red-50` rows, `bg-amber-50` rows)
- Generic circular loading spinners (use skeletons)
- "No data" empty states without icon + copy + guidance
- Standalone `MarginStatusCard` — margin belongs in session strip only
- `"Dashboard"` h1 heading on the dashboard page (redundant with sidebar nav active state)
- 3 equal columns as a feature/info display pattern

### Layout Bans
- Single-column sequential layout on desktop (wastes half the screen)
- Giant hero cards taking 30%+ of viewport for "dashboard feel"
- Overlapping absolute-positioned elements
- `h-screen` (use `min-h-[100dvh]`)
- `calc()` percentage math for column widths (use CSS Grid `fr` units)
- Centered hero sections in app UI

### Copy Bans
- AI copywriting clichés: "Elevate," "Seamless," "Unleash," "Next-Gen," "Game-changer"
- Fake round numbers: `₹1,00,000.00` — use realistic `₹1,04,280`
- Generic placeholder names: "John Doe," "Trader 1," "Sample User"
- Exclamation marks in success or empty states ("All clear!" → "All clear")
- Passive voice in alerts ("Trades were placed" → "You placed 12 trades")

### Motion Bans
- Perpetual decorative loops (floating cards, rotating background elements)
- Animating on every cursor move or keypress
- Transition duration > 400ms for UI feedback
- `animation: spin infinite` on non-loading elements

---

## 8. Dashboard-Specific Design Rules

### Data Hierarchy (Visual Weight Order)

1. **Session P&L** — always the largest number on screen (24px DM Mono font-black)
2. **Open Positions** — above closed trades, immediately actionable
3. **Behavioral Alerts** — left column, high on page, not buried below fold
4. **Morning Intent** — amber visual register, clearly distinct from alerts
5. **Risk/Limit Indicators** — in session strip, compact
6. **EOD/Predictive** — lower priority, right column

### Behavioral Alert Design Contract

- Tone: observational, not accusatory. "You placed 9 trades" not "You are overtrading."
- No colored row backgrounds. Severity chip only.
- Unacknowledged = full opacity. Acknowledged = `opacity-50` + check mark.
- Empty state: "All clear" — calm, not celebratory.
- "View full alert history" link always in card footer.

### Financial Number Rules

- Format: `formatCurrencyWithSign()` → `+₹4,280` or `−₹1,820` (explicit sign always)
- P&L zero: `text-muted-foreground` (neither profit nor loss color)
- Never orphan a number on a new line from its label
- Large numbers use Indian comma formatting: `₹10,04,280` not `₹1,004,280`

### Session Strip Zone Order (Desktop)

`SESSION P&L | REALIZED | UNREALIZED | TRADES | RISK | LOSS LIMIT | MARGIN`

### Mobile Position Cards (Snap Scroll)

Horizontal snap container. Cards `w-44` each. Border color = P&L direction. P&L = largest element. Symbol + chip visible without scrolling. No table on mobile.

---

## 9. Stitch Screen Prompting Notes

Use these descriptions when generating new screens via Stitch:

**Dashboard (Desktop):**
"A two-column trading psychology dashboard on a slightly blue-tinted off-white background (#F4F5FA). Top: a compact 72px full-width horizontal session strip with P&L, risk state, trades, loss limit zones separated by 1px vertical dividers — no card wrapper, just a bottom border. Left column (65%): behavioral alert card with clean white rows, amber/red/green small severity chips top-right, no left border stripes; open positions table with indigo brand headers; closed trades table. Right column (35%, sticky): amber sticky-note morning intent card (amber background, italic quote text, amber commit button); indigo-accented setup nudge; EOD comparison card. Brand color indigo (#4453C9). All financial numbers in DM Mono. No colored row backgrounds. No left-border stripes on alerts."

**Dashboard (Mobile):**
"Mobile trading dashboard. Top: compact 2-row 3-column session strip (P&L / Risk / Trades on row 1, Realized / Unrealized / Loss Limit on row 2). Below: amber morning intent card (visually distinct from alerts), clean behavioral alert list with severity chips, horizontal snap-scroll position cards (each 176px wide, border tinted profit/loss green/red), closed trades list. Bottom navigation: 5 icons, 72px height, white background. Background #F4F5FA. Indigo brand accent."

**Alerts Page:**
"Full-page behavioral alert history on white card surface. Each alert row: left side has pattern name (semibold foreground) + 2-line description (muted); right side has severity chip (High=red, Med=amber, Good=green) stacked above timestamp. Clean white rows, gray hover only. No left border stripes. Header: 'Behavioral Alerts' + '3 active' amber pill. Footer: 'View full alert history' indigo link."

**Analytics (Tab View):**
"Tabbed analytics interface. 8 tabs: Summary / Patterns / Trades / BTST / % Return / Edge Map / Expiry / Journal. Active tab: indigo (#4453C9) underline border. Tab bar: compact, text-sm. Content: recharts charts inside white cards on #F4F5FA background. Profit bars (#34A26C), loss bars (#E15A4D). DM Mono for all axis numbers. No gradients. Dense but structured."

**Landing Page:**
"Fintech landing page for Indian F&O traders. Two-column hero: left has overline 'For active F&O traders' in indigo, headline 'Know when your trading habits are working against you.' in Geist 600 clamp(40px,4.5vw,58px), body text, primary CTA 'Connect Your Broker' in indigo fill, trust line in gray. Right has browser-chrome-framed product screenshot showing the dashboard strip + alert feed + positions. Below: credibility strip with 4 stat cells (89% SEBI stat, ₹1.1L avg loss, 22 patterns, 83% alerts heeded). Sections: Recognition (4 trader quotes as large typography), Problems (3 patterns in 2-col zigzag), Pricing (2-card side by side). Background white with indigo accent. No purple. No gradient backgrounds."
