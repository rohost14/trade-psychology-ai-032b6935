# TradeMentor AI — Design Checklist
*Master checklist for every screen, both web and mobile. Check off as designs are completed and implemented.*

---

## How This Works

Each page goes through 4 stages:
1. **Discussed** — brainstormed in conversation, decisions made
2. **Specced** — written in `02_WEB_SCREENS.md` / `03_MOBILE_SCREENS.md` at pixel/component level
3. **Designed** — mockup created in Stitch or Figma
4. **Built** — implemented in code

Legend: ⬜ not started | 🔄 in progress | ✅ done

---

## Phase 0: Foundation (Do First)

| Item | Status | Notes |
|------|--------|-------|
| Design System doc (`01_DESIGN_SYSTEM.md`) — tokens, colors, type, spacing | 🔄 shell created | Need to fill in every token |
| Component Library spec — buttons, cards, tables, badges, inputs | ⬜ | |
| Layout grids — web (sidebar + main), mobile (bottom nav + safe area) | ⬜ | Defined in 00_OVERVIEW.md but needs pixel values |

---

## Phase 1: Core App Screens (Daily Use)

### 1. Dashboard / Home
| | Web | Mobile |
|--|-----|--------|
| Discussed | ✅ | ✅ |
| Specced | ✅ | ✅ |
| Designed (Stitch/Figma) | ⬜ | ⬜ |
| Built | ⬜ | ⬜ |

Spec: [`screens/01_dashboard.md`](screens/01_dashboard.md)

Key decisions locked:
- Alerts full-width at top (list rows, not cards), max 3 on dashboard
- Two-column below: Left 62% (positions + closed trades) | Right 38% sticky (Blowup Shield + Session Pace)
- No metric card grid, no left border on alert rows, no behavioral score, no margin components
- Stat line in page header: trades · P&L · alerts count · unjournaled count · goal (if set)
- Closed trades: unjournaled sorted first, 5 rows shown, drops to 3 when all journaled
- Journal = bottom sheet on trade row tap. Alert detail = bottom sheet on alert row tap.
- Mobile: alerts first, then positions, then closed, then right-column stats stacked at bottom

---

### 2. Behavioral Observations (route: /alerts, nav label: "Patterns" on mobile)
| | Web | Mobile |
|--|-----|--------|
| Discussed | ⬜ | ⬜ |
| Specced | ⬜ | ⬜ |
| Designed | ⬜ | ⬜ |
| Built | ⬜ | ⬜ |

Key decisions to make:
- Observation card component — evidence section design
- 3 tabs: Recent / History / By Pattern
- Swipe-to-acknowledge on mobile
- Filter sidebar (web) vs filter chips (mobile)

---

### 3. Analytics (5 tabs)
| | Web | Mobile |
|--|-----|--------|
| Discussed | ⬜ | ⬜ |
| Specced | ⬜ | ⬜ |
| Designed | ⬜ | ⬜ |
| Built | ⬜ | ⬜ |

Sub-tabs to spec individually:
- [ ] Behavior tab (default) — pattern frequency, emotional tax, BTST, persona
- [ ] Trades tab — full trade list with pattern tags + journal emotion tags
- [ ] Timing tab — P&L/win rate by hour heatmap
- [ ] Progress tab — goal streak history chart
- [ ] Summary tab — overall P&L metrics

---

### 4. AI Coach (route: /chat)
| | Web | Mobile |
|--|-----|--------|
| Discussed | ⬜ | ⬜ |
| Specced | ⬜ | ⬜ |
| Designed | ⬜ | ⬜ |
| Built | ⬜ | ⬜ |

Key decisions to make:
- Left context panel "Today's Brief" on web — exact contents
- Collapsible top bar on mobile
- Message bubble design
- "Save to journal" action within chat

---

## Phase 2: Protection & Growth Screens

### 5. My Patterns (route: /my-patterns)
| | Web | Mobile |
|--|-----|--------|
| Discussed | ⬜ | ⬜ |
| Specced | ⬜ | ⬜ |
| Designed | ⬜ | ⬜ |
| Built | ⬜ | ⬜ |

Key decisions to make:
- Pattern list + detail panel (web side-by-side) vs single column (mobile)
- Emotional correlation section design
- Pattern calendar heatmap component
- Improving/worsening/stable trend indicator per pattern

---

### 6. Blowup Shield (route: /blowup-shield)
| | Web | Mobile |
|--|-----|--------|
| Discussed | ⬜ | ⬜ |
| Specced | ⬜ | ⬜ |
| Designed | ⬜ | ⬜ |
| Built | ⬜ | ⬜ |

Key decisions to make:
- Shield score display (what does it look like — gauge? number? text?)
- Per-event card: capital defended vs. "market recovered" honest display
- Timeline visualization on web
- Compact timeline list on mobile

---

### 7. Session Limits (route: /session-limits, renamed from Danger Zone)
| | Web | Mobile |
|--|-----|--------|
| Discussed | ⬜ | ⬜ |
| Specced | ⬜ | ⬜ |
| Designed | ⬜ | ⬜ |
| Built | ⬜ | ⬜ |

Key decisions to make:
- Limit status cards (within bounds / approaching / active)
- Active limit state — calm informational, not alarming
- Configuration inputs for thresholds
- Recent event history list

---

### 8. Goals (route: /goals)
| | Web | Mobile |
|--|-----|--------|
| Discussed | ⬜ | ⬜ |
| Specced | ⬜ | ⬜ |
| Designed | ⬜ | ⬜ |
| Built | ⬜ | ⬜ |

Key decisions to make:
- 30-day consistency calendar heatmap component
- Goal card design — what data it shows
- Goal modification 24-hour cooldown UI state
- Mobile: card stack with primary goal in focus

---

## Phase 3: Data & Tools

### 9. Portfolio Radar (route: /portfolio-radar)
| | Web | Mobile |
|--|-----|--------|
| Discussed | ⬜ | ⬜ |
| Specced | ⬜ | ⬜ |
| Designed | ⬜ | ⬜ |
| Built | ⬜ | ⬜ |

Key decisions to make:
- Options metrics per-position card (strike, breakeven, premium decay, DTE)
- Concentration chart — by expiry week + by underlying
- Directional skew visualization
- GTT order summary section

---

### 10. Reports (route: /reports)
| | Web | Mobile |
|--|-----|--------|
| Discussed | ⬜ | ⬜ |
| Specced | ⬜ | ⬜ |
| Designed | ⬜ | ⬜ |
| Built | ⬜ | ⬜ |

Key decisions to make:
- Report types: Morning Brief, EOD, Weekly
- Emotional journey timeline component (trades + emoji)
- AI narrative section
- PDF download affordance

---

### 11. Settings (5 tabs)
| | Web | Mobile |
|--|-----|--------|
| Discussed | ⬜ | ⬜ |
| Specced | ⬜ | ⬜ |
| Designed | ⬜ | ⬜ |
| Built | ⬜ | ⬜ |

Sub-tabs:
- [ ] Profile
- [ ] Risk Limits
- [ ] Notifications
- [ ] Account
- [ ] Personalization

---

## Phase 4: Public / System Screens

### 12. Welcome / Landing (route: /welcome)
| | Web | Mobile |
|--|-----|--------|
| Discussed | ⬜ | ⬜ |
| Specced | ⬜ | ⬜ |
| Designed | ⬜ | ⬜ |
| Built | ⬜ | ⬜ |

---

### 13. Onboarding Wizard (modal, 5 steps)
| | Web | Mobile |
|--|-----|--------|
| Discussed | ⬜ | ⬜ |
| Specced | ⬜ | ⬜ |
| Designed | ⬜ | ⬜ |
| Built | ⬜ | ⬜ |

---

### 14. Terms of Service (route: /terms)
| Status | Done — content exists, design is minimal |
|--------|------------------------------------------|

### 15. Privacy Policy (route: /privacy)
| Status | Done — content exists, design is minimal |
|--------|------------------------------------------|

### 16. Maintenance Page (route: /maintenance)
| Status | Done — functional, minimal design acceptable |
|--------|----------------------------------------------|

---

## Phase 5: Admin Screens

> Admin is internal-only. Design priority is functional clarity, not visual polish. Standard shadcn components acceptable without custom design.

| Screen | Web Status |
|--------|-----------|
| Admin Login | ✅ Built |
| Admin Overview | ✅ Built |
| Admin Users | ✅ Built |
| Admin User Detail | ✅ Built |
| Admin System Health | ✅ Built |
| Admin Insights | ✅ Built |
| Admin Broadcast | ✅ Built |
| Admin Audit Log | ✅ Built |
| Admin Config | ✅ Built |

Admin has no mobile design requirement (internal tool, desktop only).

---

## Progress Summary

| Phase | Total screens | Designed | Built |
|-------|--------------|----------|-------|
| 0 — Foundation | 3 items | 0 | 0 |
| 1 — Daily Use | 4 | 0 | 0 |
| 2 — Protection | 4 | 0 | 0 |
| 3 — Tools | 3 | 0 | 0 |
| 4 — Public/System | 4 | 0 | partial |
| 5 — Admin | 9 | — | ✅ all |

---

*Update this file as each stage completes. The design session notes live in `02_WEB_SCREENS.md` and `03_MOBILE_SCREENS.md`.*
