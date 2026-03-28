# TradeMentor AI — Component Inventory

> Canonical reference for every reusable UI component in the app. Each entry has: purpose, variants, prop contract, anatomy, usage rules, and anti-patterns.

This document exists so that new components are never invented when an existing pattern already serves the need. Build from this inventory. Add to it when genuinely new patterns are introduced.

---

## Component Index

**Data Display**
1. [MetricTile](#1-metrictile)
2. [PositionRow](#2-positionrow)
3. [TradeRow / TradeCard](#3-traderow--tradecard)
4. [AlertCard](#4-alertcard)
5. [PatternBadge](#5-patternbadge)
6. [SeverityDot](#6-severitydot)
7. [StatusIndicator](#7-statusindicator)
8. [PnLDisplay](#8-pnldisplay)

**Layout & Navigation**
9. [PageHeader](#9-pageheader)
10. [SectionHeader](#10-sectionheader)
11. [TabBar](#11-tabbar)
12. [BottomSheet](#12-bottomsheet)
13. [EmptyState](#13-emptystate)

**Input & Action**
14. [ChipSelect](#14-chipselect)
15. [RangeSlider](#15-rangeslider)
16. [ActionButton](#16-actionbutton)
17. [InlineFilter](#17-inlinefilter)

**Feedback**
18. [Toast](#18-toast)
19. [SkeletonLoader](#19-skeletonloader)
20. [LoadingDot](#20-loadingdot)

**Composite / Page-level**
21. [GettingStartedCard](#21-gettingstartedcard)
22. [TokenExpiredBanner](#22-tokenexpiredbanner)
23. [GuestBanner](#23-guestbanner)
24. [MarketStatusBar](#24-marketstatusbar)

---

## 1. MetricTile

**Purpose:** Display a single KPI with a label and optional secondary info. Used in 4-tile rows on Dashboard and Analytics.

**Variants:**
- `default` — number + label
- `with-trend` — number + trend arrow + label
- `with-bar` — number + horizontal fill bar (e.g., margin used)
- `status` — dot indicator + text status

**Anatomy:**
```
┌────────────────────┐
│  Label text        │  ← text-xs font-medium text-muted-foreground uppercase tracking-wide
│                    │
│  Primary value     │  ← text-2xl font-semibold font-mono (for numbers) / text-xl (for text)
│                    │
│  Secondary / trend │  ← text-xs text-muted-foreground
└────────────────────┘
```

**Props:**
```tsx
interface MetricTileProps {
  label: string
  value: string | number
  valueClassName?: string    // for P&L coloring: text-success or text-danger
  secondary?: string
  trend?: 'up' | 'down' | 'neutral'
  bar?: { value: number; max: number; warnAt?: number }
  status?: 'safe' | 'caution' | 'danger' | 'insolvency'
  loading?: boolean
}
```

**Usage rules:**
- Always use `font-mono tabular-nums` for numeric values — they must not shift layout as they update
- P&L values: `text-success` (>0), `text-danger` (<0), `text-foreground` (=0)
- Never put a colored background on the tile itself. Color lives only in the value.
- On mobile: 2-per-row in a grid. On desktop: 4-per-row.

**Anti-patterns:**
- Do not add icons to metric tiles (they clutter, add no information)
- Do not put two different "primary values" in one tile — split into two tiles
- Do not animate the value on update — numbers change silently

---

## 2. PositionRow

**Purpose:** Display a single open position in the positions table.

**Web variant (table row):**
```
Symbol          Qty    Avg      LTP      P&L        Change
NIFTY 24500CE   50     ₹140.00  ₹162.50  +₹1,125    +15.9%
```

**Mobile variant (card-style row):**
```
NIFTY 24500CE
50 qty · +₹1,125   +15.9%
```

**Props:**
```tsx
interface PositionRowProps {
  tradingsymbol: string
  product: 'MIS' | 'NRML' | 'MTF'
  quantity: number
  averagePrice: number
  lastPrice: number
  pnl: number
  pnlPercent: number
  onClick?: () => void    // opens detail bottom sheet on mobile
}
```

**Usage rules:**
- `pnl` coloring: `text-success` if positive, `text-danger` if negative
- No transition animation when price updates — values change silently
- Quantity uses `tabular-nums` — numbers align in column
- Product badge (MIS/NRML) shown only if user has mixed products — not by default

**Anti-patterns:**
- Do not show the LTP with excessive decimal places — 2 decimal places max for equities, 2 for F&O
- Do not add "Buy"/"Sell" labels to positions — quantity sign convention (+ = long, - = short) is sufficient and compact

---

## 3. TradeRow / TradeCard

**Purpose:** Show a completed trade in a list. Web = table row with sortable columns. Mobile = card.

**Web TradeRow:**
```
Date     Symbol         Qty   Entry    Exit     P&L       Hold    Pattern
Mar 27   NIFTY 24500CE  50    ₹140     ₹162    +₹1,100   22m     —
```
Plus: journal icon (right), click to expand inline detail.

**Mobile TradeCard:**
```
┌────────────────────────────────┐
│  Mar 27 · NIFTY 24500CE       │
│  +₹1,100  ·  22 min hold      │
│  50 qty  ·  ₹140 → ₹162       │
│  [📝 Revenge]                  │  ← pattern tag, if any
└────────────────────────────────┘
```

**Props:**
```tsx
interface TradeRowProps {
  trade: CompletedTrade
  compact?: boolean          // mobile card vs web row
  showJournal?: boolean      // show journal icon (default: true)
  onJournalClick?: (trade: CompletedTrade) => void
  onClick?: (trade: CompletedTrade) => void
}
```

**Usage rules:**
- P&L: `text-success`/`text-danger` — always semantic
- Hold time format: `< 1m` | `22m` | `1h 14m` | `3h 42m` — no seconds
- Pattern tag (if detected): small `bg-warning/10 text-warning` chip — only shows if a pattern is linked
- Journal icon: `PencilLine` (Lucide), gray when empty, `text-primary` when journaled

---

## 4. AlertCard

**Purpose:** Display a behavioral alert with evidence and action buttons.

**Full variant (Alerts page):**
```
┌───────────────────────────────────────────────────────┐
│  [SeverityDot]  Pattern Name           [Timestamp]    │
│  Evidence: "8 trades in the last 2 hours"             │
│  [Symbol chips: NIFTY CE, BANKNIFTY, +2 more]         │
│  Est. cost: -₹1,200                                   │
│  [Acknowledge]  [View trades]                          │
└───────────────────────────────────────────────────────┘
```

**Compact variant (Dashboard recent alerts):**
```
[SeverityDot]  Pattern Name · Evidence summary · Time
```

**States:**
- `unread` — `bg-primary/5` subtle background
- `read` (acknowledged) — default `bg-card`, muted timestamp
- `new` — small "NEW" badge (text-xs, badge-style), removed after 30 seconds

**Props:**
```tsx
interface AlertCardProps {
  alert: RiskAlert
  compact?: boolean
  onAcknowledge?: (id: string) => void
  onViewTrades?: (alert: RiskAlert) => void
}
```

**Usage rules:**
- Never bold the entire card for critical severity. Only the SeverityDot changes color.
- Pattern name: use human-readable label ("Overtrading", not "overtrading_v2")
- Symbol chips: max 5 visible, "+N more" for overflow
- Acknowledge button: only on full variant, not compact
- Compact variant: no action buttons — tap the full Alerts page for actions

---

## 5. PatternBadge

**Purpose:** Inline label showing which behavioral pattern is linked to a trade or alert.

**Variants:**
```
[Overtrading]    ← bg-warning/10 text-warning  (medium severity)
[Revenge]        ← bg-danger/10 text-danger    (high severity)
[FOMO]           ← bg-muted text-muted-foreground  (low severity)
```

**Props:**
```tsx
interface PatternBadgeProps {
  pattern: string        // display name
  severity: 'low' | 'medium' | 'high' | 'critical'
}
```

**Usage rules:**
- Used inline in trade rows/cards when a pattern is detected for that trade
- Not a clickable element — just an identifier
- Keep label text short (1–2 words): "Overtrading", "Revenge", "No SL", "FOMO", "Early Exit"

---

## 6. SeverityDot

**Purpose:** Colored dot indicating alert severity. The ONLY place where severity is visually encoded.

```
● Critical  → bg-destructive (red)
● High      → bg-danger (orange-red)
● Medium    → bg-warning (amber)
● Low       → bg-muted-foreground (gray)
```

Size: `w-2 h-2 rounded-full` (inline) or `w-2.5 h-2.5` (card header)

**Usage rules:**
- Always paired with text label — never the sole indicator (accessibility)
- Never pulse or animate — static dot
- Never used for anything other than alert severity

---

## 7. StatusIndicator

**Purpose:** Small indicator showing market status or connection status.

**Variants:**
```
● LIVE        → pulsing amber dot + "LIVE" text (market open)
● Market Closed → static gray dot + "Market Closed"
● Connected   → static green dot (WebSocket)
● Disconnected → static red dot (WebSocket) + reconnect spinner
● Reconnecting → spinner (small, 14px)
```

**The pulsing animation (LIVE state only):**
```css
@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.4; }
}
```

**Usage rules:**
- Market "● LIVE" appears only in the Dashboard page header — nowhere else
- WebSocket connection dot appears in the Layout header (persistent)
- Never use pulsing animation for anything other than "live market hours" state
- Disconnected state: amber pulsing dot (not red) — amber = "needs attention", red = "financial loss"

---

## 8. PnLDisplay

**Purpose:** Consistently formatted P&L value across the entire app.

**Format rules:**
- Positive: `+₹1,240` in `text-success`
- Negative: `-₹550` in `text-danger`
- Zero: `₹0` in `text-foreground` (no +/- sign)
- Large values: Indian number system — `₹1,24,500` (not ₹1,24K)
- Compact (for small tiles): `+₹1.2L` (L = Lakh), `+₹1.2Cr` (Cr = Crore) — no K suffix

**Props:**
```tsx
interface PnLDisplayProps {
  value: number
  compact?: boolean     // uses L/Cr format
  size?: 'sm' | 'md' | 'lg' | 'xl'
  showSign?: boolean    // default true
}
```

**Usage rules:**
- Always `font-mono tabular-nums` — numbers must not shift layout
- Never use K (thousand) abbreviation — Indian convention is L (lakh) and Cr (crore)
- Size lg/xl = Dashboard hero. Size md = tile values. Size sm = table cells.

---

## 9. PageHeader

**Purpose:** Top bar of each page with title and optional actions.

**Web:**
```
[Title text]                          [Action buttons / badge]
```
Height: 40px. `text-xl font-semibold`. No background — inherits page background.

**Mobile:**
```
[Title text]                          [Action]
```
Height: 44px. `text-lg font-semibold`.

**Props:**
```tsx
interface PageHeaderProps {
  title: string
  badge?: string | number   // e.g., unread count
  actions?: React.ReactNode
  status?: React.ReactNode  // e.g., MarketStatusBar, "● LIVE"
}
```

---

## 10. SectionHeader

**Purpose:** Visually separate sections within a page.

```
SECTION TITLE                          [Count badge or action link]
──────────────────────────────────────────────────────
```

Title: `text-xs font-medium uppercase tracking-wide text-muted-foreground`
Divider: `border-b border-border mb-3`
Action link: `text-xs text-primary hover:underline` — "View all →"

**Usage rules:**
- Used to separate "Open Positions", "Recent Alerts", "Today's Trades" sections on Dashboard
- Never use a SectionHeader for tabs — use TabBar instead
- Count badge: `text-xs bg-muted text-muted-foreground rounded px-1.5` — subtle

---

## 11. TabBar

**Purpose:** Horizontal tab navigation within a page (not the bottom nav).

**Web (underline style):**
```
[Summary]  [Behavior]  [Trades]  [Timing]  [Progress]
            ───────────  ← active indicator (bottom border, text-primary)
```

**Mobile (pill style):**
```
[Summary] [Behavior] [Trades] [Timing] [Progress]
          ██████████  ← active = bg-primary/10 text-primary rounded-full
```

**Props:**
```tsx
interface TabBarProps {
  tabs: { key: string; label: string; badge?: number }[]
  activeTab: string
  onChange: (key: string) => void
  variant?: 'underline' | 'pill'  // default: underline on web, pill on mobile
  scrollable?: boolean            // for 5+ tabs on mobile
}
```

**Usage rules:**
- Scrollable on mobile when there are 4+ tabs
- Never use TabBar for top-level app navigation — that's BottomNav / Sidebar
- Active tab label: `text-primary font-medium`. Inactive: `text-muted-foreground`.
- No borders, no card backgrounds on the tab bar itself

---

## 12. BottomSheet

**Purpose:** Slide-up panel for contextual detail on mobile. Replaces right-panel from web layout.

**Used for:**
- Position detail
- Trade detail + journal
- Report reading
- "More" navigation
- Full history views (when list item says "View all →")

**Anatomy:**
```
Backdrop (rgba(0,0,0,0.4)) — dismisses on tap
┌────────────────────────────────┐
│  ────  ← drag handle (4×32px) │  ← always present
│                                │
│  [Content]                     │
│                                │
└────────────────────────────────┘
```

**Props:**
```tsx
interface BottomSheetProps {
  isOpen: boolean
  onClose: () => void
  title?: string
  height?: 'auto' | '60vh' | '90vh' | 'full'  // default: auto (content-determined)
  children: React.ReactNode
}
```

**Animation:**
```css
/* Open */
transform: translateY(0);
transition: transform 250ms ease-out;

/* Closed */
transform: translateY(100%);
```

**Usage rules:**
- Always include the drag handle
- Always dismiss on backdrop tap
- Never use BottomSheet on desktop — use a right panel or modal instead
- For "full" height sheets (reports), add close button in top-right corner

---

## 13. EmptyState

**Purpose:** Placeholder when a section has no data yet.

**Anatomy:**
```
[Optional icon — monochrome, 32px, text-muted-foreground]
[Primary message — text-sm text-muted-foreground text-center]
[Secondary message — text-xs text-muted-foreground text-center (optional)]
[CTA button — only if there's a clear action to take]
```

**Props:**
```tsx
interface EmptyStateProps {
  message: string
  detail?: string
  cta?: { label: string; onClick: () => void }
  icon?: LucideIcon
}
```

**Usage rules:**
- Never use a red or warning color for empty state — it's neutral, not an error
- No illustration assets (per "no decoration" rule for data screens)
- CTA only when there's a genuine next step (not just "Go somewhere else")
- Keep message text concise — 1–2 lines max

**Standard messages:** (use these, don't invent new ones)
```
No open positions → "Positions will appear here once you trade in Zerodha Kite."
No alerts → "No alerts yet. Alerts appear after 10+ trades."
No patterns → "Your patterns will appear after 10+ trades."
No trades → "Trade at least once to see your performance."
No reports → "Your first report will be ready after your first trading day."
No goals → "You haven't set any goals. Add your first commitment."
```

---

## 14. ChipSelect

**Purpose:** Multi-option selector using clickable chips. Used in journal and onboarding.

**Single-select:**
```
[Calm] [Anxious] [● Confident] [Distracted] [Fearful]
                  ─ selected ─
```

**Multi-select:**
```
[● F&O] [● Equity] [Both] [Currency]
```

**Props:**
```tsx
interface ChipSelectProps {
  options: { value: string; label: string }[]
  value: string | string[]
  onChange: (value: string | string[]) => void
  multi?: boolean
}
```

**Selected state:** `bg-primary/10 text-primary border-primary/30`
**Unselected state:** `bg-transparent text-muted-foreground border-border`
**All chips:** `border rounded-full px-3 py-1 text-sm cursor-pointer`

---

## 15. RangeSlider

**Purpose:** Numeric range input for risk limits in Settings and Onboarding.

**Anatomy:**
```
Max daily loss
━━━━━━━━━━●──────  ₹5,000  (~4.2% of capital)
₹0                          ₹50,000
```

**Props:**
```tsx
interface RangeSliderProps {
  label: string
  value: number
  min: number
  max: number
  step: number
  onChange: (value: number) => void
  formatValue?: (value: number) => string   // default: Indian ₹ format
  hint?: string                             // e.g., "% of capital" calculation
}
```

**Usage rules:**
- Always show the current value next to the slider (not just on the thumb)
- Show percentage hint when user has capital configured
- Pair with a text input for power users who want to type the exact value

---

## 16. ActionButton

**Purpose:** The app's button hierarchy. Uses shadcn/ui Button variants.

**Hierarchy:**
```
Primary    → bg-primary text-primary-foreground          "Connect Zerodha"
Secondary  → border border-border text-foreground        "Sync now"
Ghost      → text-muted-foreground hover:bg-muted        "Skip"
Destructive→ bg-destructive text-destructive-foreground  "Delete all data"
Link       → text-primary underline                      "View all →"
```

**Sizes:**
```
sm  → h-8 px-3 text-xs    (compact tables, badges)
md  → h-9 px-4 text-sm    (default — most buttons)
lg  → h-10 px-6 text-sm   (primary CTAs)
```

**Usage rules:**
- Only ONE primary button per view — for the single most important action
- Destructive buttons require confirmation before executing
- Never use a primary button for navigation — navigation uses links
- On mobile: buttons in sheets are full-width. Inline buttons stay auto-width.

---

## 17. InlineFilter

**Purpose:** Filter controls that live above a list/table without requiring a separate filter panel.

**Web (compact row):**
```
[Segment ▼]  [Product ▼]  [Result ▼]  [Date range ▼]    Search: [____________]
```

**Mobile (scrollable chips):**
```
[All] [F&O] [Equity] [Options] [Futures] [Today] [This week]
→ scrollable row, no wrap
```

**Props:**
```tsx
interface InlineFilterProps {
  filters: FilterDef[]
  activeFilters: Record<string, string>
  onChange: (key: string, value: string) => void
  search?: { value: string; onChange: (v: string) => void; placeholder?: string }
}
```

---

## 18. Toast

**Purpose:** Non-blocking notification for real-time events (new alert) and operation results (settings saved).

**Types:**
```
info     → bg-card border border-border text-foreground
success  → bg-card border border-success/30 (subtle green border only)
error    → bg-card border border-destructive/30
```

**Alert toast (new behavioral alert):**
```
┌────────────────────────────────────┐
│ [⚡] Overtrading detected          │
│      8 trades in 2h   [View →]    │
└────────────────────────────────────┘
```

**Operation toast (settings saved):**
```
┌──────────────────────┐
│ ✓  Settings saved    │
└──────────────────────┘
```

**Specs:**
- Position: top-right on web, top-center on mobile (above content, below status bar)
- Duration: 4 seconds, then fade out
- Max 3 toasts stacked
- No X close button — auto-dismisses

**CRITICAL rules:**
- Never block interactive elements with a toast
- Never require a click to dismiss a toast
- Alert toasts must not dominate — same visual weight as success toasts
- Never play a sound unless the user has explicitly granted notification permission

---

## 19. SkeletonLoader

**Purpose:** Placeholder while data is loading. Prevents layout shift.

**Variants:**
```
SkeletonText   → rounded gray bar, mimics text line height
SkeletonTile   → full metric tile skeleton (4 per row)
SkeletonRow    → table row skeleton (3–5 per table)
SkeletonCard   → card-shaped skeleton (for trade cards on mobile)
```

**Implementation:**
```css
@keyframes shimmer {
  0%   { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.skeleton {
  background: linear-gradient(90deg,
    hsl(var(--muted)) 25%,
    hsl(var(--muted-foreground) / 0.1) 50%,
    hsl(var(--muted)) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
```

**Usage rules:**
- Show skeleton on initial page load and on manual refresh
- Do NOT show skeleton on WebSocket-triggered updates (data updates silently)
- Skeleton height must match the actual content height — no layout shift on data arrival
- All 4 analytics tabs show skeleton on first open (they're lazy-loaded)

---

## 20. LoadingDot

**Purpose:** Minimal loading indicator for in-progress states (AI coach response, syncing).

```
●  ●  ●    ← 3 dots, staggered fade-in-out animation
```

**Usage:**
- AI Coach: appears between user message and first streamed word
- Sync button: appears during `POST /trades/sync`
- Never used for page-level loading (that's SkeletonLoader)

---

## 21. GettingStartedCard

**Purpose:** 4-step setup checklist shown on Dashboard for new users.

```
┌────────────────────────────────────────────────────────┐
│  Get started                                     [×]   │
│  ✓ Connect Zerodha    ○ Complete profile               │
│  ○ Set risk limits    ○ Enable alerts                  │
└────────────────────────────────────────────────────────┘
```

**Auto-hide condition:** `onboarding_complete === true` AND `trade_count >= 3`
**Manual dismiss:** [×] button — stores dismissal per `broker_account_id` in localStorage
**Mobile variant:** slim 40px banner at top of home screen, not a full card

---

## 22. TokenExpiredBanner

**Purpose:** Persistent amber banner when Zerodha session needs re-authentication.

```
┌────────────────────────────────────────────────────────┐
│  Your Zerodha session expired.  [Reconnect →]          │
└────────────────────────────────────────────────────────┘
```

- Background: `bg-warning/10 border-b border-warning/30`
- Text: `text-sm text-foreground`
- Appears at the very top of the main content area (below sidebar on web, below header on mobile)
- Persists until reconnected — no dismiss button
- Does NOT block the rest of the app

---

## 23. GuestBanner

**Purpose:** Amber banner indicating the user is in guest/demo mode.

```
┌────────────────────────────────────────────────────────────────┐
│  You're viewing demo data.  [Connect Zerodha →]   [Exit guest] │
└────────────────────────────────────────────────────────────────┘
```

- Same visual treatment as TokenExpiredBanner (amber, non-blocking)
- "Connect Zerodha →" starts OAuth flow
- "Exit guest" returns to /welcome (no data lost — there was no data)

---

## 24. MarketStatusBar

**Purpose:** Inline indicator of current market state. Used in Dashboard page header.

**States:**
```
● LIVE  09:42         ← amber pulsing dot + time  (market open)
Market Closed         ← gray text, no dot         (market closed)
Pre-Market            ← gray text, no dot         (before 9:15)
```

**Usage rules:**
- Only visible in the Dashboard page header — no other page needs this
- The pulsing amber dot is the only permitted animation in the data-heavy parts of the app
- "LIVE" text: `text-xs font-medium text-warning` with the pulsing dot
- "Market Closed": `text-xs text-muted-foreground`, no animation

---

## Dark Mode Notes

All components must work in both light and dark modes. The app uses `darkMode: ["class"]` — toggling the `.dark` class on `<html>`.

**Do not:**
- Hardcode `#` hex colors in component styles — always use Tailwind tokens
- Use `bg-white` or `text-black` — use `bg-background` and `text-foreground`
- Use opacity tricks like `text-gray-500` — use `text-muted-foreground`

**Shadow convention:**
- Light mode: `shadow-sm` (subtle drop shadow)
- Dark mode: no shadow; instead `border border-border` provides separation
- This is handled automatically if you use `bg-card` for surfaces

---

## Spacing Conventions

```
Page padding:       px-6 py-6 (web), px-4 py-4 (mobile)
Section gap:        mb-6 between sections
Card internal:      p-4 (standard), p-5 (comfortable), p-3 (compact)
Table row height:   h-10 (compact), h-11 (default)
Tile height:        min-h-[100px] (desktop tiles)
Input height:       h-9 (default), h-8 (compact)
```

---

## Typography Scale

```
text-2xl font-semibold     → Dashboard hero P&L
text-xl font-semibold      → Page titles
text-lg font-medium        → Section headlines, card titles
text-sm font-medium        → Table headers, field labels
text-sm                    → Body text, default
text-xs font-medium        → Metadata, timestamps, badges
text-xs                    → Secondary metadata, section labels

font-mono tabular-nums     → All numeric values (prices, P&L, counts)
```

---

*This is a living document. When a new component is built that will be reused, add it here before building a second instance.*
