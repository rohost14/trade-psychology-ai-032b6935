# UI/UX Review
*Design system, component library, responsiveness, accessibility*

---

## Score: 8/10

---

## Design System

### Component Library: shadcn/ui
- Radix UI primitives (accessible by default) + Tailwind CSS
- All components in `src/components/ui/` (50+ components)
- Consistent spacing, typography, border-radius across all screens
- ✅ No custom CSS hacks — everything through Tailwind utility classes

### Colour System
```css
/* Risk-specific semantic colours (CSS variables) */
--risk-safe:    hsl(142 76% 36%)  /* green */
--risk-caution: hsl(45 93% 47%)   /* amber */
--risk-danger:  hsl(0 84% 60%)    /* red */

/* Theme-aware (dark/light) */
--background, --foreground
--card, --card-foreground
--muted, --muted-foreground
--primary, --primary-foreground
--border
```

### Typography
- Font: System font stack (fast, readable, familiar to Indian users)
- Scale: 2xl (hero) → xl (card headers) → sm (body) → xs (labels/metadata)
- ✅ Consistent hierarchy across all 7 screens

### Dark Mode
- `ThemeProvider` wraps entire app (`next-themes`)
- `ThemeToggle` button in header (every screen)
- CSS variables flip on `.dark` class — all components automatically theme-aware
- ✅ No hardcoded colour values — all `text-foreground`, `bg-card`, etc.

---

## Layout & Navigation

### Desktop (≥768px)
```
Top header bar (sticky, z-50):
  Left:  [Logo] [Nav links — 7 items]
  Right: [Connection status dot] [Alert bell] [Theme toggle]

Main content area:
  max-w-7xl mx-auto px-6 py-6
  Responsive grid: 1-4 columns depending on screen
```

### Mobile (<768px)
```
Top header:
  Left:  [Logo]
  Right: [Alert bell] [Theme toggle] [Hamburger menu]

Hamburger → full-screen nav overlay with all 7 links

Bottom navigation (fixed, z-50):
  5 items: Dashboard | Analytics | My Patterns | Chat | Radar
  (Blowup Shield and Settings via hamburger only)

Main content:
  px-4 py-6, pb-20 (space for bottom nav)
```

**Validation**:
- ✅ Bottom nav shows correct 5 items (first 5 from nav array)
- ✅ Active state highlighting works (NavLink + className callback)
- ✅ Mobile menu closes on nav click (`onClick={() => setMobileMenuOpen(false)}`)

---

## Screen-by-Screen UX Notes

### Dashboard
- **Hero card (RiskGuardian)** is immediately actionable — shows level, message, what to do
- **Card layout**: 2-column grid on desktop, stacked on mobile
- **Tables**: Horizontal scroll on mobile (no data truncation)
- **LTP updates**: Real-time without full re-render (WebSocket partial update)
- ⚪ No skeleton loading on initial mount (cards flash empty)

### Analytics
- **Period selector** (7d/30d/90d) persists across tab switches
- **Tab switching**: lazy-fetches each tab on first visit (no upfront loading)
- **Charts**: recharts — responsive containers, tooltips with ₹ formatting
- **Export**: single button, returns downloadable file (PDF/CSV)
- ⚪ Chart colours could use theme-aware variables (some recharts use hardcoded hex)

### My Patterns
- **Danger banner**: Immediately visible, colour-coded, actionable
- **Streak calendar**: 30-day grid, visual milestones (motivating, not punishing)
- **Commitments**: Free-form text, no forced templates
- ⚪ Streak calendar may look sparse for new users (empty cells visible)

### Chat
- **Follow-up chips**: Context-aware suggestions reduce typing friction
- **Streaming responses**: Reduces perceived wait time (tokens appear as generated)
- **Session restore**: Coming back to `/chat` shows previous conversation
- ✅ Scrolls to bottom on new message
- ⚪ No message timestamps shown

### Portfolio Radar
- **Position clock cards**: Dense information, needs good labelling
- **DTE badge**: Colour-coded (green=plenty, amber=close, red=expiring soon)
- **Concentration chart**: Donut chart for underlying exposure (clean, readable)
- ✅ Options-specific metrics (theta, breakeven) only shown for CE/PE — not for futures

### Blowup Shield
- **Honest design**: Calculating state shown (no fake ₹0 or estimates)
- **Negative money_saved shown** in red (not hidden) — honesty builds trust
- **Timeline cards**: expandable, sorted by date descending
- ✅ No motivational fiction — only real verified numbers get hero stats

### Settings
- **2 tabs** (was 5 tabs before session 16 redesign — much cleaner)
- **Immediate validation** (Zod) on save attempt — inline errors per field
- **Test notifications** button gives immediate feedback
- ✅ Disconnect clears localStorage — no stale connection state

---

## Onboarding

`src/components/onboarding/OnboardingWizard.tsx`

Triggered on first login (checked via `localStorage.tradementor_onboarded`):
1. Welcome screen (product intro)
2. Trading profile setup (style, capital)
3. Trading limits setup (daily loss, position size)
4. First commitment (optional)
5. Done — redirects to Dashboard

- ✅ Skippable (not forced)
- ✅ Profile data saved to DB immediately

---

## Error States

### App-Level ErrorBoundary (`src/components/ErrorBoundary.tsx`)
- Wraps entire app in `App.tsx`
- Catches: context/provider crashes, top-level render failures
- Shows: "Something went wrong" + Sentry ref ID + Reload button
- ✅ `Sentry.captureException()` with event ID shown to user

### Layout-Level ErrorBoundary (`src/components/Layout.tsx`)
- Wraps `<Outlet />` (all page content)
- Catches: per-page render failures
- Header/nav remains usable — user can navigate to another screen
- ✅ Added this session

### Network Error States
- API call failures: `toast.error("...")` with generic message
- Auth expiry: `TokenExpiredBanner` component (amber banner in header)
- WebSocket disconnect: auto-reconnects with backoff, shows connection status dot

---

## Performance

| Metric | Value | Notes |
|--------|-------|-------|
| Initial bundle | 739KB (gzipped ~180KB) | After code splitting (was 1.41MB) |
| Dashboard eager | ✅ | First screen loads immediately |
| Other routes | Lazy loaded | Each route is a separate chunk |
| LCP | Depends on API | First meaningful data in ~500ms on fast connection |
| WebSocket startup | ~100ms | Event subscriber fires on connection |
| Sentry overhead | <1ms | SDK is async, non-blocking |

---

## Accessibility

- **Radix UI** (shadcn base): ARIA roles, keyboard navigation, focus management
- **Semantic HTML**: `<header>`, `<main>`, `<nav>`, `<button>` (not `<div onClick>`)
- **Colour contrast**: Tailwind + shadcn defaults meet WCAG AA
- **Touch targets**: Mobile buttons ≥44px (shadcn defaults)
- ⚠️ No formal a11y audit done — recommended before public launch

---

## UX Issues to Address Before Launch

| Issue | Priority | Fix |
|-------|----------|-----|
| No skeleton/shimmer loading | P2 | Add `<Skeleton>` from shadcn while data loads |
| No empty state illustration for new users | P2 | Add illustrated empty states (0 trades, 0 alerts) |
| Chart colours hardcoded in recharts | P3 | Use CSS variable colours |
| No message timestamps in Chat | P3 | Add `<time>` element to message bubbles |
| Streak calendar sparse for new users | P3 | Add "Start your streak" prompt |
| No formal a11y audit | P2 | Screen reader + keyboard test before public launch |
