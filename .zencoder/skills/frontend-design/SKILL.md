---
name: tradementor-frontend
description: "Design and build all frontend UI for TradeMentor AI — the behavioral risk platform for Indian F&O traders. Use this skill for every component, page, and screen: dashboards, trade logs, analytics, navigation shells, modals, alerts, and the AI mentor chat. Covers both web (React + Vite) and mobile (Capacitor-wrapped responsive web). Defines the complete design system grounded in the actual token setup (shadcn + Tailwind CSS). Always use this over the generic frontend-design skill for any TradeMentor work."
---

# TradeMentor AI — Frontend Design Skill

**Read this fully before writing code.** This skill is grounded in direct study of Zerodha Kite, Sensibull, Tickertape, and Stripe — and in the actual tech stack: React 18, Tailwind CSS, shadcn/ui, CSS keyframe animations (no Framer Motion).

---

## 1. How These 4 Apps Actually Look (The Real Patterns)

Before building anything, understand what these references actually do — not what people say they do.

### Zerodha Kite
- Muted teal-blue surfaces. Single accent color. Color appears only on brand actions and P&L values.
- Layout: left sidebar on web, bottom tabs on mobile. Content area is **full width** — not a grid.
- Data lives in **lists and tables**, not card grids. Watchlist, order book, positions — all lists.
- Whitespace between sections is generous. Within sections, data is compact.
- Zero decoration. No shadow-heavy cards, no large border-radius, no gradients anywhere.
- Numbers are the hero, not the UI chrome.

### Sensibull
- Slightly more saturated blue-teal family.
- Layout: horizontal split — left panel (context/filters) + right panel (primary data). Tabs switch data views.
- Screens are **full-width table-first**. Options chains, strategies, P&L tables — all full-width.
- Dense but never cluttered. Density through tight row heights and compact type, not by removing page-level whitespace.
- Flat surfaces. Borders define sections. No elevation shadows.
- Card patterns exist but they span full width — they are **bands**, not boxes in a grid.

### Tickertape
- Metric tiles in **horizontal rows** — never in equal-sized grids.
- Filter chips above tables. Horizontal scroll on mobile for data-heavy tables.
- Color-coding on tiles: green-tinted background for positive, red-tinted for negative. Subtle, not aggressive.
- Information hierarchy: label above, value large, context below. Consistent across all tiles.

### Stripe (Borrowed for Craft, Not Aesthetic)
- What we take: 8px spacing grid applied with discipline, typography precision (hierarchy through weight variation, not size alone), button and input quality, subtle border system.
- What we do NOT take: its color family, gradient hero sections, or checkout aesthetic.

### The Shared Pattern Across All 4
The layout pattern across all these apps: **sidebar or bottom nav + full-width vertical content sections**. Not a CSS grid of equal-sized cards. Data screens are table-first. Dashboard screens have 3–4 horizontal metric tiles in a row, then full-width sections stacked below. This is the foundation of TradeMentor's layout.

---

## 2. What Makes Fintech UIs Look Vibe-Coded (Specific to This Context)

Generic "no glassmorphism" rules miss the point. These are the actual tells in fintech:

**Layout tells:**
- 3-column grid of equal-sized cards on a dashboard — looks like a template, not a product
- Using `<Card>` from shadcn for every section without customising padding or width
- Sidebar exactly `w-64` — no fintech app does this, they size to content
- Metric tiles stacked vertically instead of in a horizontal summary row
- Page content constrained to a narrow center column — feels like a blog, not a tool

**Data tells:**
- Tables that break into stacked cards on mobile instead of horizontal scrolling
- Showing P&L in the same color (gray or black) as non-financial text
- Inconsistent number formatting — mixing ₹1,234 and ₹1234 and ₹ 1,234 in the same screen
- Using the same font size for column headers as column values
- Showing `undefined` or `NaN` instead of `—` when data is absent

**Color tells:**
- Red and green used for non-P&L UI elements (trains the eye to ignore semantic color)
- More than one accent color visible simultaneously
- Pure `#FFFFFF` backgrounds with no surface hierarchy — everything bleeds together
- Background colors that feel "app-like" (deep navy, purple, dark grey) instead of neutral
- Hardcoding `text-green-500` or `text-red-500` directly instead of using semantic tokens

**Component tells:**
- The default shadcn `<Badge>` with its default colors unchanged
- Every interactive element with `rounded-xl` or `rounded-2xl` (too soft for a financial tool)
- `rounded-full` on non-pill elements
- Toast notifications for form validation errors instead of inline messages
- Modals that are the same max-width regardless of content complexity

**Mobile tells (Capacitor context):**
- Hover states as the only interactive feedback — no `active:` pressed states
- Tap targets below 44px on any interactive element
- Modals instead of bottom sheets on mobile
- Sidebar navigation visible on mobile instead of bottom tab bar
- Tables not horizontally scrollable — data clipped or broken

---

## 3. Token System (How to Use Colors Correctly)

The project uses **shadcn/ui's CSS variable system** wired into Tailwind. There is one token system — the Tailwind classes. Never hardcode hex values or use bare `rgb()` in component code.

### The Token Map

| Purpose | Tailwind class | CSS variable |
|---|---|---|
| Page background | `bg-background` | `--background` |
| Card / panel surface | `bg-card` | `--card` |
| Inset / alt rows / pressed | `bg-muted` | `--muted` |
| Primary text | `text-foreground` | `--foreground` |
| Secondary / caption text | `text-muted-foreground` | `--muted-foreground` |
| Borders | `border-border` | `--border` |
| Input border | `border-input` | `--input` |
| Primary action (teal) | `bg-primary text-primary-foreground` | `--primary` |
| **Profit (green)** | `text-success` | `--success` |
| **Loss (red)** | `text-danger` | `--danger` |
| Warning (amber) | `text-warning` | `--warning` |
| Destructive (errors) | `text-destructive` | `--destructive` |
| Focus ring | `ring-ring` / `focus-ring` utility | `--ring` |

### P&L Coloring — Always Use Semantic Tokens

```tsx
// WRONG — hardcoded Tailwind color scale
<span className="text-green-500">+₹4,230</span>
<span className="text-red-500">-₹1,800</span>

// RIGHT — semantic tokens, work in light and dark mode
<span className="text-success">+₹4,230</span>
<span className="text-danger">-₹1,800</span>
```

Profit/loss tinted tile backgrounds — add to `index.css` or use inline style when needed:
```tsx
// Tickertape-style tinted tile: profit
<div className="bg-success/10 border border-success/20 ...">

// loss
<div className="bg-danger/10 border border-danger/20 ...">
```

### Dark Mode
Dark mode uses the `.dark` class on `<html>`. Tailwind handles it with `dark:` prefix automatically via `darkMode: ["class"]` in `tailwind.config.ts`. Never use `[data-theme="dark"]`.

```tsx
// Works automatically:
<p className="text-muted-foreground dark:text-muted-foreground">
// (token already switches via .dark)

// Custom dark overrides when needed:
<div className="bg-white dark:bg-zinc-900">
```

### Border Radius
Use Tailwind's radius scale (wired to `--radius: 0.5rem`):
- `rounded-sm` → 4px — tags, small chips
- `rounded` or `rounded-md` → 6–8px — buttons, inputs, cards ✓
- `rounded-lg` → 8px — modals, bottom sheets
- `rounded-full` → pills and avatar circles only

**Never use `rounded-xl` or `rounded-2xl`** on fintech UI elements. It reads as consumer/lifestyle app.

---

## 4. Typography

### Fonts in Use
```css
/* index.css — already loaded */
font-family: 'Inter', system-ui, -apple-system, sans-serif;  /* all UI text */

/* Tailwind: font-mono maps to system monospace stack */
font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
```

All financial numbers — prices, P&L values, quantities, percentages — must use `font-mono tabular-nums`. This is non-negotiable: monospace prevents the layout from shifting as numbers change, and tabular-nums aligns decimal points in tables.

### Type Scale

| Use | Tailwind classes |
|---|---|
| Page title | `text-2xl font-semibold tracking-tight` |
| Section header / card title | `text-xl font-semibold tracking-tight` |
| Sub-section title | `text-lg font-semibold` |
| Group label | `text-base font-medium` |
| Default body | `text-sm text-muted-foreground` |
| Button label | `text-sm font-medium` |
| Table column header | `text-xs font-medium uppercase tracking-wide text-muted-foreground` |
| Caption / helper | `text-xs text-muted-foreground` |
| Status tag / chip | `text-xs font-medium uppercase tracking-wide` |
| **Financial number (inline)** | `text-sm font-mono tabular-nums font-semibold` |
| **Financial number (card primary)** | `text-lg font-mono tabular-nums font-bold` |
| **Financial number (metric tile)** | `text-2xl font-mono tabular-nums font-bold tracking-tight` |
| **Financial number (hero)** | `text-3xl font-mono tabular-nums font-bold tracking-tight` |

All `font-mono` usages must also include `tabular-nums` class (defined in `index.css` as `font-variant-numeric: tabular-nums`).

---

## 5. Layout Patterns

### 5.1 Web Layout (sidebar + full-width content)

```tsx
// The app shell. Sidebar is w-52 (208px) — closer to Zerodha's compact nav.
<div className="flex h-screen overflow-hidden bg-background">

  {/* Sidebar — hidden on mobile */}
  <aside className="hidden md:flex w-52 shrink-0 flex-col h-full
    border-r border-border bg-card">
    <SidebarNav />
  </aside>

  {/* Main content — full width, not constrained to a narrow center column */}
  <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
    <main className="flex-1 overflow-y-auto">
      <div className="px-6 py-6 mx-auto max-w-[1280px]">
        {children}
      </div>
    </main>
  </div>
</div>
```

### 5.2 Mobile Layout (Capacitor / responsive)

```tsx
<div className="flex flex-col h-[100dvh] bg-background">

  {/* Content area — no sidebar */}
  <main className="flex-1 overflow-y-auto pb-16"> {/* pb-16 = 64px bottom nav */}
    <div className="px-4 py-4">
      {children}
    </div>
  </main>

  {/* Bottom tab bar — mobile only */}
  <nav className="fixed bottom-0 left-0 right-0 h-16 md:hidden
    bg-card border-t border-border
    flex items-center justify-around px-2 z-40
    pb-[env(safe-area-inset-bottom)]">
    {tabs.map(tab => <BottomTab key={tab.id} {...tab} />)}
  </nav>
</div>
```

**Bottom tab items:** Dashboard, Trades, Analytics, Mentor, More. Max 5. Each tab: icon (20px) + label (`text-xs`) stacked. Active: `text-primary`. Inactive: `text-muted-foreground`.

### 5.3 Page Density Rules

**Dashboard / Home (Zerodha-spacious):**
- 3–4 metric tiles in one horizontal row at the top
- Full-width sections stacked below — never a 2-column or 3-column grid of sections
- `gap-8` (32px) between major sections, `gap-6` (24px) between related groups
- One primary number dominates the fold. Everything else supports it.

**Analytics / Trade Log (Sensibull-dense):**
- Full-width table as the primary element
- Filter chips row above the table
- Left panel (filters) + right panel (table) split at tablet and above
- `p-6` card padding, `h-10` or `h-11` row heights
- Tabs to switch between data views (not separate pages)

**Mobile (all screens):**
- Single column always
- Summary stats in a `grid grid-cols-2 gap-3` compact grid (not full metric tiles)
- Tables: horizontal scroll (never break into stacked cards)
- No split panels — sections stack vertically

---

## 6. Indian Financial Data Formatting

```typescript
// src/lib/formatters.ts — use existing formatters, extend here

/** Indian numbering: ₹1,23,456 — not ₹1,234,56 */
export const formatINR = (value: number, decimals = 0): string =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency', currency: 'INR',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);

/**
 * Compact: ₹12.4L, ₹2.1Cr — used in metric tiles and mobile.
 * No "K" suffix — not an Indian convention. Go straight to L (lakh).
 */
export const formatINRCompact = (value: number): string => {
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs >= 1_00_00_000) return `${sign}₹${(abs / 1_00_00_000).toFixed(2)}Cr`;
  if (abs >= 1_00_000)    return `${sign}₹${(abs / 1_00_000).toFixed(1)}L`;
  return `${sign}₹${abs.toLocaleString('en-IN')}`;
};

/** P&L Tailwind class — always use this, never hardcode colors on financial values */
export const pnlClass = (value: number): string =>
  value > 0 ? 'text-success'
  : value < 0 ? 'text-danger'
  : 'text-muted-foreground';

/** P&L with mandatory sign prefix */
export const formatPnL = (value: number, compact = false): string => {
  const sign = value >= 0 ? '+' : '';
  return sign + (compact ? formatINRCompact(value) : formatINR(value));
};

/** Percentage with sign */
export const formatPct = (value: number, decimals = 2): string =>
  `${value >= 0 ? '+' : ''}${value.toFixed(decimals)}%`;

/** Lot size: "2 lots · 100 qty" */
export const formatLots = (qty: number, lotSize: number): string => {
  const lots = qty / lotSize;
  return `${lots} lot${lots !== 1 ? 's' : ''} · ${qty} qty`;
};

/** Option display: "NIFTY 24500 CE · 30 Jan" */
export const formatOption = (
  symbol: string, strike: number, optType: 'CE' | 'PE', expiry: Date
): string => {
  const exp = expiry.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
  return `${symbol} ${strike.toLocaleString('en-IN')} ${optType} · ${exp}`;
};

/** Time in IST: "10:32 AM" */
export const formatTime = (date: Date): string =>
  date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });

/** Date: "Mon, 14 Jan" */
export const formatDate = (date: Date): string =>
  date.toLocaleDateString('en-IN', { weekday: 'short', day: '2-digit', month: 'short' });

/** Absent data — always show dash, never undefined/NaN/null */
export const formatOrDash = (value: number | null | undefined, formatter: (v: number) => string): string =>
  value == null || isNaN(value) ? '—' : formatter(value);
```

---

## 7. Core Components

### Metric Tile (Tickertape-style horizontal row)

```tsx
// Tiles always appear in a horizontal row — never stacked vertically
// Mobile: 2 per row compact variant
<div className="grid grid-cols-2 md:grid-cols-4 gap-3">
  <MetricTile label="Today's P&L" value="+₹4,230" changeValue={2.1} change="+2.1%" type="profit" />
</div>

// Tile anatomy: label → value → change (always this order)
<div className="bg-card border border-border rounded-md p-4 md:p-5">

  {/* Label: micro, uppercase, muted */}
  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">
    {label}
  </p>

  {/* Value: large mono, primary text */}
  <p className="text-2xl font-bold font-mono tabular-nums tracking-tight text-foreground">
    {value}
  </p>

  {/* Change: small, semantic color — only profit/loss/neutral */}
  {change && (
    <p className={`mt-1.5 text-xs font-medium ${pnlClass(changeValue)}`}>
      {change}
    </p>
  )}
</div>
```

### Buttons

```tsx
{/* Primary — one per screen section */}
className="inline-flex items-center gap-2 px-4 py-2.5 min-h-[40px]
  bg-primary text-primary-foreground
  hover:bg-primary/90 active:bg-primary/90
  text-sm font-medium rounded-md
  transition-colors duration-150
  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2
  active:scale-[0.98]"

{/* Secondary — outlined */}
className="inline-flex items-center gap-2 px-4 py-2.5 min-h-[40px]
  bg-transparent hover:bg-muted active:bg-muted
  border border-border
  text-foreground text-sm font-medium rounded-md
  transition-colors duration-150
  active:scale-[0.98]"

{/* Ghost — low-emphasis, tertiary actions */}
className="inline-flex items-center gap-2 px-3 py-2 min-h-[36px]
  bg-transparent hover:bg-muted active:bg-muted
  text-muted-foreground hover:text-foreground
  text-sm font-medium rounded-sm
  transition-colors duration-150"
```

### Inputs

```tsx
<div className="flex flex-col gap-1.5">
  <label className="text-xs font-medium text-foreground">{label}</label>
  <input
    className="w-full px-3 py-2.5 min-h-[40px]
      bg-card border border-border rounded-md
      text-sm text-foreground placeholder:text-muted-foreground
      hover:border-input
      focus:outline-none focus:border-primary focus:ring-2 focus:ring-ring/20
      transition-all duration-150"
  />
  {helper && <p className="text-xs text-muted-foreground">{helper}</p>}
</div>
```

### Badges / Status Tags

```tsx
// Use existing global classes from index.css — extend as needed:
// .badge-success / .badge-warning / .badge-danger

// Or inline for custom variants:
const badgeVariants = {
  profit:  'bg-success/10 text-success border border-success/20',
  loss:    'bg-danger/10  text-danger  border border-danger/20',
  warning: 'bg-warning/10 text-warning border border-warning/20',
  neutral: 'bg-muted text-muted-foreground border border-border',
  active:  'bg-primary/10 text-primary border border-primary/20',
};

<span className={`inline-flex items-center px-2 py-0.5
  rounded-sm text-xs font-medium uppercase tracking-wide
  ${badgeVariants[variant]}`}>
  {label}
</span>
```

### Table (the primary data component)

```tsx
// Always full-width. On mobile: horizontal scroll container.
<div className="overflow-x-auto">
  <table className="w-full min-w-[600px] text-sm">
    <thead>
      <tr className="border-b border-border">
        <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Symbol
        </th>
        <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wide text-muted-foreground">
          P&amp;L
        </th>
      </tr>
    </thead>
    <tbody>
      {rows.map(row => (
        <tr key={row.id}
          className="border-b border-border hover:bg-muted/50 transition-colors cursor-pointer">
          <td className="px-4 py-3 text-foreground">{row.symbol}</td>
          <td className={`px-4 py-3 text-right font-mono tabular-nums font-semibold ${pnlClass(row.pnl)}`}>
            {formatPnL(row.pnl)}
          </td>
        </tr>
      ))}
    </tbody>
  </table>
</div>
```

---

## 8. Animation

Animation decisions follow a strict framework. The goal is invisible correctness — transitions that feel right without being noticed.

### Step 1: Should this animate at all?

| How often will users see this? | Decision |
|---|---|
| 100+ times/day (table row click, filter chip, tab switch, any repeated action) | No animation. Ever. |
| Tens of times/day (hover states, repeated tab switches) | Remove or cut to absolute minimum |
| Occasional (modals, bottom sheets, toasts, page transitions) | Standard animation |
| Rare / first-time (onboarding, empty state, first load) | More delight allowed |

TradeMentor is used during market hours under stress. Most interactions are repeated dozens of times a session. Err toward less, not more.

### Step 2: Use the existing animation utility classes

All animations are pure CSS keyframes defined in `src/index.css`. **No Framer Motion. No animation libraries.**

```tsx
// Page/section enter — most common
<div className="animate-fade-in">...</div>      // fade only, 200ms
<div className="animate-fade-in-up">...</div>   // fade + lift from below, 200ms

// Modal / dropdown appear
<div className="animate-fade-in-scale">...</div> // scale(0.95)→1 + fade, 200ms

// Banners / toasts sliding in from top
<div className="animate-slide-in-down">...</div> // spring-like overshoot, 350ms

// Mobile bottom sheet / menu sliding in from bottom
<div className="animate-slide-in-up">...</div>   // spring-like overshoot, 350ms

// Removing a card (e.g. dismissing an alert card)
<div className="animate-card-exit">...</div>     // fade + scale + lift, 180ms

// Skeleton / loading pulse
<div className="animate-pulse">...</div>          // Tailwind built-in

// Icon accent animations (use sparingly — icons only, never content areas)
<span className="animate-float">...</span>        // gentle float, 4s loop
<span className="animate-zap-pulse">...</span>    // rotation pulse, 3s loop
```

### Step 3: Stagger for lists

When multiple items appear together (alert cards, a list of results), stagger with `animation-delay`:
```tsx
{items.map((item, i) => (
  <div
    key={item.id}
    className="animate-fade-in-up"
    style={{ animationDelay: `${i * 45}ms` }} // 45ms stagger — not 100ms (too slow)
  >
    {/* content */}
  </div>
))}
```

### Step 4: Exit animations

CSS keyframes only handle entry. For exit, you have two options:

**Option A — Skip exit animation** (preferred for frequently used UI)
Remove the element directly. Users don't need to watch things leave.

**Option B — JS-controlled exit class** (for modals, bottom sheets)
```tsx
const [isClosing, setIsClosing] = useState(false);

const handleClose = () => {
  setIsClosing(true);
  setTimeout(onClose, 180); // match animate-card-exit duration
};

<div className={isClosing ? 'animate-card-exit' : 'animate-fade-in-scale'}>
  {/* content */}
</div>
```

### Easing philosophy

Never use raw CSS `ease` or `ease-in-out`. The existing keyframes use:
- `cubic-bezier(0.16, 1, 0.3, 1)` — strong ease-out for enter (fast start, smooth settle)
- `ease-in` for exit only — starts slow, which is fine because users aren't watching exits closely

**Never use `ease-in` for entering elements.** It starts slow at exactly the moment the user is watching.

### Duration reference

| Element | Duration |
|---|---|
| Button press / hover color change | 100–150ms |
| Tooltips, small popovers | 125–175ms |
| Dropdown, filter chip | 150–200ms |
| Modal, side panel, page section | 200ms (`animate-fade-in-scale`) |
| Bottom sheet, banner | 280–350ms (`animate-slide-in-up/down`) |

**All UI animations stay under 350ms.** Anything over that reads as slow.

### What never animates in TradeMentor

- Table rows populating or re-sorting
- Numbers updating from data refresh (no count-up animations)
- Filter chips applying
- Any repeated action (clicking through trades, switching tabs repeatedly)
- Background / ambient / looping animations on content areas
- Loading states beyond a simple `animate-pulse` skeleton

### Performance rule

Only animate `transform` and `opacity`. These are composited by the GPU. Never animate `height`, `width`, `padding`, `margin`, or `top/left` — they trigger full layout recalculation and drop frames under market-hours load.

```css
/* CORRECT — GPU composited */
@keyframes myAnim {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* WRONG — triggers layout */
@keyframes myAnim {
  from { margin-top: -8px; }
  to   { margin-top: 0; }
}
```

### Button press feedback (apply to every pressable element)

```css
/* Add active:scale-[0.97] or active:scale-[0.98] to interactive elements */
/* transition-transform duration-150 ease-out */
```
```tsx
className="... active:scale-[0.97] transition-transform duration-150"
```

Scale: 0.95–0.98. No bigger. Makes the UI feel like it's responding.

### Hover states — gate behind media query (critical for Capacitor/mobile)

```css
/* Only fires on real pointer devices, not touch */
@media (hover: hover) and (pointer: fine) {
  .element:hover {
    background: hsl(var(--muted));
  }
}
/* Always define active state separately — works on both touch and pointer */
.element:active {
  background: hsl(var(--muted));
}
```

Or in Tailwind: `hover:bg-muted active:bg-muted` — hover is already pointer-only in most modern browsers, but `active:` ensures touch devices get feedback.

### prefers-reduced-motion

```css
@media (prefers-reduced-motion: reduce) {
  .animate-fade-in,
  .animate-fade-in-up,
  .animate-fade-in-scale,
  .animate-slide-in-down,
  .animate-slide-in-up {
    animation: fadeIn 0.15s ease both; /* keep opacity, remove movement */
  }
}
```

---

## 9. Mobile-Specific Patterns (Capacitor)

**All interactive elements: minimum 44px touch target.**
Apply `min-h-[44px]` or padding to achieve this even if the visual element appears smaller.

**Bottom sheets replace modals on mobile:**
```tsx
const isMobile = useMediaQuery('(max-width: 768px)');

// Mobile: bottom sheet
// Web: centered modal
{isMobile ? (
  <div className="fixed inset-0 z-50 flex flex-col justify-end md:hidden">
    {/* Backdrop */}
    <div className="absolute inset-0 bg-black/40" onClick={onClose} />

    {/* Sheet */}
    <div className="relative bg-card rounded-t-lg max-h-[90dvh] overflow-y-auto
      pb-[env(safe-area-inset-bottom)] animate-slide-in-up">
      {/* Drag handle */}
      <div className="flex justify-center pt-3 pb-1">
        <div className="w-10 h-1 rounded-full bg-border" />
      </div>
      <div className="px-4 pb-6">{children}</div>
    </div>
  </div>
) : (
  <Modal {...props} />
)}
```

**Tables on mobile — horizontal scroll, never break into cards:**
```tsx
<div className="overflow-x-auto -mx-4 px-4">
  {/* -mx-4 breaks out of container padding so scroll reaches the edge */}
  <table className="min-w-[600px] w-full">
    {/* table content */}
  </table>
</div>
```

**Active/pressed feedback on mobile** — hover doesn't fire on touch:
```tsx
// Add to all interactive list items, rows, and buttons:
className="... active:bg-muted active:scale-[0.99] transition-all duration-100"
```

**Safe areas for iOS:**
```tsx
// Bottom sheet / fixed bottom elements:
className="pb-[env(safe-area-inset-bottom)]"

// Full-screen containers:
className="h-[100dvh]"  // dvh handles iOS Safari bottom bar correctly
```

---

## 10. Skeletons and Empty States

**Skeletons mirror the exact shape of the content they replace:**
```tsx
{/* Metric tile skeleton */}
<div className="bg-card border border-border rounded-md p-4 md:p-5 animate-pulse">
  <div className="h-2.5 w-16 bg-muted rounded mb-3" />
  <div className="h-7 w-24 bg-muted rounded mb-2" />
  <div className="h-2 w-14 bg-muted rounded" />
</div>

{/* Table row skeleton */}
<tr className="border-b border-border animate-pulse">
  <td className="px-4 py-3"><div className="h-3 w-20 bg-muted rounded" /></td>
  <td className="px-4 py-3"><div className="h-3 w-12 bg-muted rounded" /></td>
  <td className="px-4 py-3 text-right"><div className="h-3 w-16 bg-muted rounded ml-auto" /></td>
</tr>

{/* Text line skeleton */}
<div className="h-4 w-48 bg-muted rounded animate-pulse" />
```

**Empty states must be screen-specific — never "No data found":**
```tsx
<div className="flex flex-col items-center justify-center py-16 px-6 text-center">
  {/* Lucide icon — 40px, text-muted-foreground, no animation */}
  <SomeIcon className="w-10 h-10 text-muted-foreground mb-4" />

  <p className="text-base font-medium text-foreground">
    {screenSpecificTitle}  {/* e.g. "No trades synced yet" */}
  </p>

  <p className="text-sm text-muted-foreground mt-1.5 max-w-[280px]">
    {screenSpecificDescription}  {/* Specific to context, never generic */}
  </p>

  {primaryAction && (
    <button className="mt-5 /* primary button */">{primaryAction}</button>
  )}
</div>
```

---

## 11. Quick Anti-Pattern Checklist

Before shipping any component, check these:

- [ ] No hardcoded hex/rgb colors — using Tailwind semantic tokens only
- [ ] P&L values use `text-success` / `text-danger` — never `text-green-*` / `text-red-*`
- [ ] All financial numbers use `font-mono tabular-nums`
- [ ] All currency uses `formatINR` / `formatINRCompact` (Indian locale, no K suffix)
- [ ] Absent values show `—` not `undefined`, `null`, `NaN`, or blank
- [ ] No `rounded-xl` or `rounded-2xl` on any element
- [ ] No equal-sized card grids — metric tiles are horizontal rows, not grids
- [ ] Tables scroll horizontally on mobile — not stacked cards
- [ ] All interactive elements have `active:` state (not just `hover:`)
- [ ] All tap targets minimum 44px height
- [ ] No Framer Motion imports — use CSS animation utility classes from `index.css`
- [ ] No looping/ambient animations on content areas
- [ ] Dark mode tested — using `.dark` class toggle, not `[data-theme="dark"]`
- [ ] No more than one accent color visible at once
- [ ] Skeletons match the exact shape of the content they replace
