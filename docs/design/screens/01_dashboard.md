# Screen: Dashboard
*Primary screen. Active session hub. Answers: "What have I done today and what has the system noticed about how I'm trading?"*

**Status:** Spec complete — ready for Stitch/Figma
**Discussed:** 2026-04-02
**Route:** `/dashboard`

---

## Design Decisions (rationale locked)

- **Top navbar** (not sidebar) — more content width, familiar to Indian F&O traders (matches Zerodha/Sensibull pattern)
- No behavioral score hero — score is a trend metric, not a moment-to-moment number
- Session Summary card (4 stats: P&L, Win Rate, Unread Alerts, Pending Journals) — replaces old "Current Session" teal card. No risk status, no "Stable", no Edge Score.
- Alerts section in a card wrapper, max 4 rows visible, scrollable if more, "View all →" always present
- Alerts are the primary feature — full width, above positions
- Positions exist only to make journaling one tap away — journal is the core action
- Journal icons: orange pencil (unjournaled) + green checkmark (journaled)
- No margin components — redundant with Zerodha Kite, behavioral consequence shows as alert
- No My Patterns or AI Coach widgets — wrong context, those are reflective/slow features
- Closed trades sort: unjournaled first within the visible set

---

## Web

### Viewport & Layout

```
Top navbar (60px fixed) + Full-width content area below
Content: max-width 1280px, centered, horizontal padding 24px, top padding 24px
Two-column below alerts+session: Left 62% | Right 38% | gap 24px between columns
```

---

### 1. Top Navbar

Fixed at top. Height: 60px. Background: `#0F172A` (nav-bg, dark slate). Full viewport width.

```
[TM Logo + "TradeMentor"]   Dashboard  Alerts[3]  Analytics  Coach  My Patterns  More▾     12 trades · Goal 8/10     [🔔] [⚙] [avatar]
```

**Left — Logo + Brand:**
- TM logomark (teal square icon) + "TradeMentor" in `text-white font-semibold text-base`
- Clickable → `/dashboard`

**Center — Primary Nav Items:**
- `Dashboard` | `Alerts` | `Analytics` | `Coach` | `My Patterns` | `More ▾`
- Font: `text-sm font-medium`
- Inactive: `text-slate-300` (`nav-text`)
- Active (current page): `text-teal-300` (`nav-text-active`) with `border-b-2 border-teal-400` underline
- Hover: `text-white`
- Alerts item has an unread badge: small `bg-amber-500` circle, `text-white text-xs`, positioned top-right of the text
- `More ▾` opens a dropdown containing: Blowup Shield · Session Limits · Goals · Portfolio Radar · Reports · Settings

**Center-right — Compact stat line:**
- `12 trades · Goal 8/10` — `text-sm text-slate-400`
- Goal shown only if set. Hidden if no goal.
- This is the only text in the navbar center-right area — no P&L here (P&L lives in Session Summary card)

**Right — Actions:**
- Bell icon (🔔): `text-slate-300`, 20px. Unread dot if notifications exist.
- Gear icon (⚙): `text-slate-300`, 20px. Links to Settings.
- Avatar circle: 32px, shows user initials or profile photo.
- All icons: hover → `text-white`, transition 100ms.

---

### 2. Session Summary Card

Full width. Sits between navbar and behavioral alerts. Margin-bottom: 20px.

**Container:** `bg-white border border-slate-200 rounded-lg px-6 py-4`

**Layout:** 4 stats in a horizontal row, equal width columns, separated by `1px border-slate-200` vertical dividers.

| Stat | Value style | Label style |
|------|------------|-------------|
| P&L Today | `text-2xl font-bold font-mono` · green if positive, red if negative | `text-xs text-slate-400` below |
| Win Rate | `text-2xl font-bold` · `text-slate-900` | `text-xs text-slate-400` below |
| Unread Alerts | `text-2xl font-bold` · amber (`text-amber-600`) if > 0, slate if 0 | `text-xs text-slate-400` below |
| Pending Journals | `text-2xl font-bold` · amber if > 0, slate if 0 | `text-xs text-slate-400` below |

- No card background tint. White only.
- No icons per stat. Numbers do the work.
- No individual card per stat — one card, 4 columns inside it.
- If no trades yet: P&L shows `—`, Win Rate shows `—`

---

### 3. Behavioral Alerts Section

**Full width.** Sits between Session Summary and the two-column layout below. Margin-bottom: 20px.

**Container:** `bg-white border border-slate-200 rounded-lg` — card wrapper around the entire section.
**Max height:** `~220px` (~4 rows). Scrollable internally (`overflow-y: auto`) if more than 4 alerts. Custom scrollbar: thin, `bg-slate-200` track.
**"View all →" link:** Always pinned at the bottom of the card, outside the scrollable area. `sticky bottom-0 bg-white border-t border-slate-100 px-4 py-2`.

**Section label row:**
- Left: `BEHAVIORAL ALERTS` — `text-xs font-medium uppercase tracking-widest text-muted-foreground`
- Right: `3 unread` — `text-xs text-warning` (amber). If 0 unread, show nothing on the right.
- Bottom border: `1px border-border` below the label row, 8px margin before first alert row

**Alert rows (max 3 shown on dashboard):**

Each row: height `h-11` (44px), full width, `cursor-pointer`

```
[dot]  Pattern Name          Evidence phrase, specific data          11:45  [›]
```

- **Dot:** 7px × 7px circle, `rounded-full`. Amber (`bg-warning`) if unread, slate-400 (`bg-muted-foreground/40`) if read. Left-aligned, vertically centered. Left padding 0.
- **Pattern name:** `text-sm font-medium text-foreground`. 120px min-width.
- **Evidence:** `text-sm text-muted-foreground`. Truncated at 1 line with ellipsis. This text is generated from real trade data — never hardcoded. Takes remaining width.
- **Timestamp:** `text-xs text-muted-foreground`. Right-aligned. Always HH:MM format.
- **Chevron `›`:** `text-muted-foreground`, 16px. Visible on row hover only (opacity-0 default, opacity-100 on hover).
- **Hover state:** `bg-muted/40` on the full row. Transition 100ms.
- **Unread indicator:** When dot is amber, pattern name is `font-medium`. When read, pattern name drops to `font-normal`.
- **Click:** Opens alert detail bottom sheet (see Section 6 below).

**"View all X →" link:**
- Appears below the last row, 8px margin-top
- `text-sm text-primary` (teal)
- Shows count: "View all 5 alerts →" or "View all →" if exact count unknown
- Right-aligned within the section

**Empty state (no alerts today):**
- Section label still shows
- Single row: `text-sm text-muted-foreground` — "No behavioral alerts today"
- No dot, no chevron

---

### 3. Two-Column Layout

Starts immediately below the Behavioral Alerts section. No horizontal divider line — gap (24px) only.

---

### 4. Left Column — Open Positions

**Section label row:**
- Left: `OPEN POSITIONS` — `text-xs font-medium uppercase tracking-widest text-muted-foreground`
- Right: `3` — `text-xs text-muted-foreground` (count of open positions)
- `● LIVE` — only during market hours (09:15–15:30 IST). `●` is a 6px amber pulsing dot. `LIVE` is `text-xs text-muted-foreground`. Hidden when market closed.
- Bottom border: `1px border-border`, 8px margin

**Table:**
- No card wrapper. The section sits directly on the page background with a subtle `1px border border-border rounded-lg` wrapping the rows.
- Background: `bg-card` (white on light theme)

| Column | Width | Alignment | Style |
|--------|-------|-----------|-------|
| Symbol + instrument | auto (flex grow) | Left | `text-sm font-medium` + `text-xs text-muted-foreground` below (e.g., "NIFTY · CE · 24500") |
| Side | 48px | Center | `text-xs font-medium`. BUY=`text-profit`, SELL=`text-danger` |
| Qty | 56px | Right | `text-sm font-mono text-foreground` |
| Avg | 72px | Right | `text-sm font-mono text-muted-foreground` |
| LTP | 72px | Right | `text-sm font-mono text-foreground` |
| P&L | 88px | Right | `text-sm font-mono font-medium`. Positive=`text-profit`, Negative=`text-danger` |
| Journal | 40px | Center | 16px pencil icon. `text-muted-foreground` if no note, `text-primary` (teal) if note exists |

- Row height: `h-11` (44px)
- Row hover: `bg-muted/30`
- Clicking the journal icon (or anywhere on the row): opens journal bottom sheet for that trade
- Journal icon tap area: `44px × 44px` minimum (pad with invisible area)

**Empty state:** `text-sm text-muted-foreground p-4` — "No open positions"

---

### 5. Left Column — Closed Today

Directly below Open Positions. Margin-top: 16px.

**Section label row:**
- Left: `CLOSED TODAY` — same style as other labels
- Right: `8 trades` (count) + if unjournaled > 0: ` · ✎ 2 need journaling` in `text-xs text-warning`
- Bottom border: same as above

**Table:** Same border/bg wrapper as Open Positions.

| Column | Width | Alignment | Style |
|--------|-------|-----------|-------|
| Symbol + instrument | auto | Left | Same as above |
| Side | 48px | Center | Same as above |
| P&L | 88px | Right | `font-mono font-medium`. Color by positive/negative |
| Duration | 72px | Right | `text-xs text-muted-foreground` — "2h 14m" |
| Journal | 40px | Center | Pencil icon. Amber dot overlay (top-right of icon) if unjournaled. Teal if journaled. |

- **Sort order:** Unjournaled rows first, then journaled rows (most recent journaled at bottom). Within unjournaled: most recent first.
- **Unjournaled row indicator:** The journal column shows a pencil icon with a small amber 5px dot overlay in the top-right corner. No other row highlighting.
- **Journaled row indicator:** Pencil icon is `text-primary` (teal), no dot.
- **Rows shown:** 5. After user journals trades, unjournaled rows surface. When all journaled, show 3.
- **"View X more →"** link: same style as alerts section view-all link.

---

### 6. Right Column — Blowup Shield

`position: sticky; top: 24px` so it stays visible while left column is scrolled.

**Container:** `border border-border rounded-lg bg-card p-4`

**Content:**
- Label: `BLOWUP SHIELD` — `text-xs font-medium uppercase tracking-widest text-muted-foreground`
- Score: `82` — `text-3xl font-bold text-foreground`. Inline: `/100` — `text-lg text-muted-foreground`
- Sub-label: `Shield Score` — `text-xs text-muted-foreground` below the number
- Divider: `1px border-border` margin-top/bottom 12px
- Stats row: `2 protections this month` — `text-sm text-foreground`
- Last event: `Last · Mar 28 · ₹4,200 saved` — `text-xs text-muted-foreground`
- Link: `View full history →` — `text-sm text-primary` margin-top 12px

**Empty state (no events):** Score shows `—`, stats show "No protection events yet"

---

### 7. Right Column — Session Pace

Directly below Blowup Shield. Margin-top: 16px.

**Container:** `border border-border rounded-lg bg-card p-4`

**Content:**
- Label: `SESSION PACE` — same label style
- Main: `12 trades today` — `text-sm font-medium text-foreground`
- Context: `Your average: 5 per day` — `text-sm text-muted-foreground`
- Status line:
  - 0–110% of average: no status line shown
  - 111–149%: `↑ 30% above your average` — `text-xs text-muted-foreground`
  - 150%+: `↑ 140% above your average` — `text-xs text-warning` (amber)
  - Below average: `↓ Below your average today` — `text-xs text-muted-foreground`

---

### 8. Alert Detail Bottom Sheet

Opens when any alert row is clicked. Slides up from the bottom of the screen.

**Sheet specs:**
- Width: 480px, centered, `rounded-t-xl` (12px top corners only)
- Background: `bg-card`
- Shadow: `shadow-xl`
- Drag handle: `w-10 h-1 bg-border rounded-full mx-auto mt-3`
- Max height: 80vh, scrollable inside

**Contents:**
- Pattern name: `text-lg font-semibold text-foreground`
- Timestamp + severity label: `text-sm text-muted-foreground`
- `1px border-border` divider
- **Evidence paragraph:** `text-sm text-foreground leading-relaxed` — full narrative with real numbers. E.g., *"You placed 8 trades between 9:18 AM and 11:12 AM — one trade every 14 minutes. Your average session has 5 trades. Net P&L during this window: ₹-3,240."*
- **Trades that triggered this** (sub-label style):
  - List of all triggering trades: `text-sm font-mono` — Symbol · Side · Time · P&L. Each row is tappable → journal sheet.
- `1px border-border` divider
- **Actions row:**
  - `Journal these trades →` — `text-sm text-primary`
  - `Discuss with AI Coach →` — `text-sm text-primary`
- Close: tap backdrop or drag down

---

### 9. Journal Bottom Sheet

Opens when journal icon is tapped on any trade row (open or closed).

**Sheet specs:** Same width/style as alert detail sheet.

**Contents (existing implementation — chip-select form):**
- Trade summary at top: Symbol, Side, P&L, Time — `text-sm font-mono`
- `1px border-border` divider
- Emotion before entry: multi-select chips (9 options)
- Plan adherence: single-select chips (Yes / Partially / No)
- Deviation reason: conditional, shown if "Partially" or "No" selected
- Exit reason: single-select chips (6 options)
- Setup quality: 5-star tap
- Would repeat: single-select chips (Yes / Maybe / No)
- Market condition: single-select chips (5 options)
- Free text note: `textarea`, max 280 chars, optional
- Save button: `bg-primary text-white rounded-md` full-width at bottom
- Close without saving: tap backdrop or `×` icon

---

### 10. GettingStartedCard (new users only)

Shown above the page header. Auto-hides when: onboarding complete AND ≥ 3 trades synced. Per-account dismiss in localStorage.

**Container:** `border border-border rounded-lg bg-card p-4` full width, margin-bottom 16px

**Content:** 4-step checklist with inline actions (existing implementation). No redesign needed for now.

---

## Mobile

### Viewport & Layout

```
Width: 390px (iPhone 14 baseline)
Bottom nav: 64px fixed
Safe area: env(safe-area-inset-bottom) internal padding
Page padding: horizontal 16px, top 16px
```

---

### 1. Page Header (Mobile)

**Row 1:**
- Left: `Dashboard` — `text-lg font-semibold text-foreground`
- Right: sync icon button — `text-muted-foreground` 20px

**Row 2 (4px below row 1):**
- `12 trades · ₹ -2,340 · ⚠ 3 · ✎ 2`
- `text-sm text-muted-foreground`. P&L colored (profit/danger). `⚠` and `✎` amber if > 0.
- Tappable: `⚠ 3` navigates to `/alerts`. `✎ 2` scrolls to Closed Today section.

---

### 2. Behavioral Alerts (Mobile)

Full width. Margin-top: 16px.

**Section label:** Same style as web.

**Alert rows:** Max 2 shown on mobile (not 3).
- Same row structure as web: dot · pattern name · evidence · timestamp
- Evidence truncated to fit (shorter truncation than web)
- Row height: `h-12` (48px) for better tap target
- `"View all X →"` link if > 2 alerts

---

### 3. Open Positions (Mobile)

Full width. Margin-top: 20px.

**Simplified columns (390px can't fit 7 columns):**

| Column | Style |
|--------|-------|
| Symbol + instrument (2 lines) | `text-sm font-medium` + `text-xs text-muted-foreground` |
| P&L | `text-sm font-mono font-medium` colored. Right-aligned. |
| Journal icon | 44×44 tap target. Right edge. |

Hidden on mobile: Avg, LTP, Qty, Side. Tap row → opens a mini detail sheet showing all fields + journal form together.

---

### 4. Closed Today (Mobile)

Full width. Margin-top: 20px.

**Same simplified columns as Open Positions.** Same sort logic (unjournaled first). Same 5-row limit with "View more →".

**Unjournaled indicator:** Amber dot on journal icon.

---

### 5. Blowup Shield + Session Pace (Mobile)

Stacked vertically below Closed Today. Margin-top: 20px.

**Blowup Shield:**
- Horizontal layout within card: Score `82/100` on left (large), stats on right ("2 this month", "Last: Mar 28")
- `border border-border rounded-lg bg-card p-4`

**Session Pace:**
- Single line: `12 trades today · your avg: 5 · ↑ 140%` — `text-sm`
- `border border-border rounded-lg bg-card p-4`
- Margin-top: 12px

---

### 6. Alert Detail & Journal Sheets (Mobile)

**Alert detail:** Full-width bottom sheet. `rounded-t-xl`. Max height 85vh. Otherwise identical content to web version.

**Journal sheet:** Full-width bottom sheet. Max height 90vh (more form fields need more height). Scrollable. Save button is sticky at the bottom of the sheet.

---

### 7. Bottom Navigation

```
[🏠 Home] [⚡ Alerts] [📊 Analytics] [💬 Coach] [⋯ More]
```

- Height: 64px + `env(safe-area-inset-bottom)`
- Background: `bg-card border-t border-border`
- Active tab: `text-primary` (teal)
- Inactive: `text-muted-foreground`
- Unread badge on Alerts: small `bg-warning` circle. Count when ≥ 3, plain dot when 1–2.
- "More" opens bottom sheet with secondary pages

---

## Empty States

| Scenario | Web | Mobile |
|----------|-----|--------|
| No trades today | Stat line: "0 trades". Open Positions shows "No open positions". Closed Today shows "No closed trades today." | Same |
| No alerts today | Alert section shows "No behavioral alerts today" | Same |
| New user (0 trades ever) | GettingStartedCard visible above header | Slim banner version |
| Market closed | LIVE indicator hidden. Positions table has "Market closed" label in header | Same |

---

## States Checklist

- [ ] Default (trades + alerts present)
- [ ] No alerts today
- [ ] No trades today (pre-market / weekend)
- [ ] All trades journaled (no amber indicators)
- [ ] New user empty state
- [ ] Market closed state
- [ ] Sync in progress (spinner on sync button, data is stale)
- [ ] WebSocket disconnected (reconnecting indicator in sidebar footer)
