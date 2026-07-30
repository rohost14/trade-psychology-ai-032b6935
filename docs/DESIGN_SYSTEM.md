# TradeMentor AI — Design System & Screen Specification

**Status:** authoritative. This document is the single source of truth for how TradeMentor looks and behaves.

It is self-contained: every value needed to build a screen correctly is in here. You should not need to read the codebase to know what size a label is, whether a block gets a card, or what an empty state says.

It contains no counts, no file references, and no progress tracking — those live in `docs/DESIGN_MIGRATION.md`, which is disposable and gets deleted when the migration finishes. If this document and the code disagree, **this document is the target and the code is behind.**

**Extending the system:** extend it before introducing a new pattern. Add the token, size, or recipe here first, then use it. Don't fork a one-off. See §27.

**This system is meant to be stable, not exhaustive.** Once it is complete it is frozen: a change requires a concrete reason — a new product capability, a demonstrated usability problem, or an inconsistency to resolve — never personal preference. A design system becomes valuable because it stops moving. Adding a rule every week is how it becomes ignored.

---

## 0. Quick reference

The fifteen rules that catch almost every mistake. This is the page to keep open while building; the rest of the document is the detail behind it.

```
PURPOSE
  ✓  One screen = one story          ✓  No duplicated metrics across screens
  ✓  One primary metric per screen   ✓  Every screen has a first-run state

STRUCTURE
  ✓  Cards must justify themselves — sections + dividers are the default
  ✓  Tables before charts
  ✓  Density is a feature — no whitespace for its own sake

TYPE & COLOUR
  ✓  14px body · 11px labels · 10px floor (table headers only)
  ✓  Tabular numbers, always
  ✓  One accent colour + three semantics, desaturated

STATE
  ✓  Skeleton (content) → Spinner (action) → Error → Empty — four distinct renders
  ✓  A failed request is NEVER an empty state
  ✓  Empty states state the cause and the next action

COPY
  ✓  Evidence, not encouragement — no motivational copy
  ✓  AI is invisible — no "I noticed…", no AI branding
```

**Banned outright:** donut · pie · radial gauge · circular progress · gradients · glassmorphism · animated backgrounds · gamification (badges, XP, streaks-as-achievement, trophies, confetti) · invented scores whose formula can't be shown · text below 10px · decorative icons · a second accent colour.

Before opening a PR, run §28.

---

# Part I — Direction

## 1. What this product is, visually

TradeMentor is a professional tool that serious traders trust to make better decisions. It is not an AI startup, not a SaaS dashboard, not a template.

The design language communicates **calmness, precision, credibility, and clarity** — never excitement or novelty. Every design decision reinforces that this is a behavioural trading platform, not another analytics dashboard.

Five words to design against, in priority order:

| | Meaning |
|---|---|
| **Calm** | Nothing competes for attention. No motion, colour, or size used to excite. |
| **Dense** | More useful information per screen. Scanning speed beats breathing room. |
| **Precise** | Numbers align. Values are exact. Nothing is approximated for looks. |
| **Honest** | If data is missing, say why. If a number is derived, say how. |
| **Purposeful** | Every element exists because it serves a job, not because it fills space. |

Prefer function over decoration. Prefer stable and trustworthy over trendy. An interface a trader will use for four hours a day should be forgettable in the best sense — invisible until needed.

## 2. References and anti-references

**Study these** — for how they organise information, not for their visuals. Do not copy their look.

| Reference | What to learn from it |
|---|---|
| **Zerodha Kite** | Density, trust, trader-first workflow. Our users compare us to this daily. |
| **Bloomberg Terminal** | Information architecture, data hierarchy, precision. Learn the structure, not the styling. |
| **Tickertape** | Clean financial presentation of complex data. |
| **Linear** | Spacing discipline, interaction quality, polish. |
| **Stripe Dashboard** | Forms, settings, detail pages, and consistency across a large surface. |

**Design away from:** Vercel, Supabase, Notion, and generic modern AI-SaaS templates. Their visual language signals "software product" — ours must signal "professional instrument".

## 3. Product stance that drives design

These are product decisions with direct visual consequences. They are not negotiable at the design layer.

| Stance | Design consequence |
|---|---|
| **Mirror, not blocker** | We show a trader facts about their own behaviour. Nothing blocks, restricts, or interrupts. No modal stands between a trader and their positions. |
| **Facts, not verdicts** | Numbers first, one plain sentence second. No probabilistic language. No "you could have made ₹X". |
| **Money on every behavioural row** | A pattern without a rupee figure attached is not shippable. |
| **Zero manual input** | The trader never types or taps to make a feature work. No rating widgets, no "how did you feel?" prompts, no form as a core flow. Evidence: 55 alerts fired, 0 outcomes recorded. Designing for input that never comes produces empty screens. |
| **One screen, one story** | A metric appears on exactly one screen. Others cross-link to it. See §25. |
| **Cold start is the default state** | The broker API provides no trade history — a new account is empty until a Console CSV import. First-run is not an edge case; it is what most users see first. Every screen needs a real first-run state (§15). |

## 4. Hard don't list

Each of these is banned, with the reason. They are not stylistic preferences — every one of them makes the product read as generated rather than built.

**Visual effects**
- **Glassmorphism, neumorphism** — decorative depth with no informational meaning.
- **Gradients** — a gradient encodes nothing. Two colours where one would do.
- **Animated or blurred backgrounds, floating decorative shapes, glow** — motion and light with no data behind them read as a marketing page.
- **Neon or vivid colour** — fights the calm requirement and destroys the profit/loss signal by competing with it.

**Layout**
- **Oversized KPI cards, four coloured stat boxes** — the single clearest "generated dashboard" tell.
- **Dozens of unrelated cards on one screen** — a card grid is an admission that the information wasn't organised.
- **A card around every block** — see §9. Containers are the exception, not the default.
- **Whitespace for aesthetics** — vertical space spent on nothing is information the trader has to scroll for.
- **Generic SaaS dashboard layout** — sidebar plus card grid plus donut is a template, not a design.

**Colour and type**
- **Rainbow palettes, multiple competing accents** — every added hue reduces the meaning of the ones that matter.
- **Billboard typography** — giant numbers on every screen. One primary metric per screen may be large; nothing else.

**Content**
- **Gamification** — badges, XP, levels, streaks framed as achievement, trophies, flames, confetti, celebration. This is a behavioural coaching platform, not Duolingo. Rewarding a trader for behaviour corrupts the mirror.
- **Motivational or exaggerated copy** — "Great job!", "Keep going!", "You're crushing it!", "Trade smarter with AI!". Show evidence, not encouragement.
- **Fake AI personality or AI branding** — "I noticed…", "AI suggests…", "Our AI analysed…". Intelligence shows in the quality of the observation, never in announcing itself.
- **Fake precision and invented scores** — "confidence 98%", "Behaviour Score 84.2", Productivity/Performance/Health Index. A number is shippable only if the engine genuinely produces it *and* the trader can see how it was computed. A score whose formula can't be shown gets cut, not rounded.
- **Duplicate metrics across screens** — the same number in three places with three windows destroys trust in all three.

**Data display**
- **Decorative charts** — a chart that answers no stated question is removed, not restyled.
- **Donut, pie, radial gauge, circular progress** — overused in generated dashboards, poor at comparison, and almost always worse than a table or bar. See §20.
- **Decorative icons** — an icon either carries meaning or it goes.
- **Unnecessary filters** — ten dropdowns look feature-rich and solve nothing. Every filter must answer a real question.
- **Generic illustrations and stock 3D graphics** — they add zero trust to a financial product.

**Process**
- **Features added because they are trendy** — see §27 for the bar a new surface has to clear.
- **Default component-library styling** — primitives from a component library are encouraged; shipping their out-of-the-box appearance is what reads as vibe-coded.

---

# Part II — Foundations

## 5. Component hierarchy

Four layers. Each owns different decisions. When adding something new, identify its layer first — that tells you what you're allowed to decide locally.

| Layer | Contains | Owns | Never decides |
|---|---|---|---|
| **Primitives** | colour token, type step, spacing step, radius, icon, dot, chip, divider | nothing on its own — pure values | layout, meaning |
| **Components** | Section, Card, Stat, MetricStrip, Row, Table, Pill, Button, Input, Tabs, Sheet | internal padding, internal type, its own states | where it sits, what data it holds |
| **Patterns** | section stack, filter-adjacent-to-data, consolidated→drill-down, loading/empty/error triad, confirmation ladder | composition of components, interaction sequence | screen purpose, which data |
| **Screens** | the 11 product screens (§26) | which patterns appear, in what order, and what the screen owns | inventing new component styling |

**Rule:** a screen may not invent component styling. If a screen needs something a component can't express, the component changes here — for everyone — or a new component is added to §17. This is the mechanism that prevents each screen growing its own card, spacing, and type conventions.

## 6. Colour

One accent. Three semantics. Everything else neutral. **Colour communicates meaning, never decoration.**

### Surfaces and text

| Role | Dark | Light | Use |
|---|---|---|---|
| Page | `#121316` | `#F6F5F3` | the page body, nothing else |
| Surface | `#191B1F` | `#FFFFFF` | a card, when a card is justified (§9) |
| Elevated | `#26272C` | `#FBFAF9` | things that float above the page — sidebar, modal, sheet, popover |
| Hover / track | `#232529` | `#F2F0EE` | row hover, tab track, inset wells |
| Border | `#2A2C32` | `#DCDAD6` | section dividers, card edges, table rules |
| Divider (subtle) | `#1E2024` | `#EDEBE8` | row-to-row separators inside a dense list |
| Text primary | `#EEECE8` | `#16181D` | headings, values, numbers |
| Text secondary | `#939698` | `#60646C` | labels, descriptions, column headers |
| Text tertiary | `#646670` | `#96969F` | timestamps and metadata only — never body copy |
| Sidebar | `#101114` | `#FBFAF9` | app chrome |

Two in-app surface levels only: page and surface. `Elevated` is for floating layers, not a third card tier. Depth comes from a 1px border, never a shadow (§8).

### Accent and semantics

| Role | Dark | Light | Use |
|---|---|---|---|
| **Primary (pine-teal)** | `#59C0B4` | `#155B56` | the one accent — active nav, links, focus ring, primary action |
| Profit | `#47B88E` | `#226D4F` | gains, BUY, improving |
| Loss | `#CF6559` | `#AF3A31` | losses, SELL, danger |
| Warning | `#D39145` | `#B16B1B` | caution |

- Semantics are **deliberately desaturated**. If it looks like a terminal alarm, it's wrong.
- Tints are `10%` fills with `20%` borders. Never a solid semantic fill behind body text. Never deepen the fill to make it "pop".
- The accent is not used to decorate. If something is teal, it is interactive or it is the brand mark.

### Severity → colour

The behavioural engine emits four severities. They map to three colours by design — `critical` earns emphasis through weight and position, not a fifth hue.

| Severity | Colour | Treatment |
|---|---|---|
| `info` | primary | icon tint only |
| `caution` | warning | icon tint + 2px left border |
| `danger` | loss | icon tint + 2px left border |
| `critical` | loss | as danger, plus bolder value and top position. No pulsing, no red page chrome. |

### P&L sign

Profit → profit colour. Loss → loss colour. **Exactly zero → text secondary, never green.** Always render the sign: `+₹1,240` / `−₹890`. Use a true minus (`−`), not a hyphen.

## 7. Typography

Hierarchy comes from **type and spacing, not colour or size inflation**. Headings are subtle. Few sizes, used strictly.

**Faces:** Inter for body and all numbers. Geist for display and headings. Numbers always use `font-variant-numeric: tabular-nums` so columns align exactly — this is non-negotiable in a product where traders compare figures down a column.

There is no monospace face. Tabular Inter aligns as well and reads denser.

### The scale — seven steps, no others

| Step | Size | Weight | Line-height | Tracking | Role |
|---|---|---|---|---|---|
| **Display** | 30px | 600 | 1.15 | −0.03em | A screen's single primary metric. One per screen, or none. |
| **H1** | 22px | 600 | 1.25 | −0.025em | Screen title |
| **H2** | 17px | 600 | 1.35 | −0.015em | Section or card title |
| **Body** | 14px | 400 | 1.5 | 0 | The default. All primary reading text and data values. |
| **Small** | 12.5px | 400 | 1.5 | 0 | Secondary copy, descriptions, help text |
| **Label** | 11px | 500 | 1 | 0.12em, uppercase | Section labels, metric labels. Text secondary colour. |
| **Micro** | 10px | 500 | 1 | 0.06em, uppercase | Dense table column headers **only** |

**Rules**
- Section titles 17. Data values 14–16. Labels 11 uppercase. The primary metric 30.
- **Nothing below 10px, ever, and 10px only for a table column header.** If a layout seems to need 8 or 9px, the layout is wrong — remove content or restructure, don't shrink type.
- Big numbers are reserved for the one primary metric per screen. A screen with four 30px numbers has no hierarchy at all.
- Do not use relative (rem-based) text sizes for typography. **Root font size is 16px**; the scale above is absolute so it stays stable regardless of root changes.

## 8. Spacing, density and rhythm

Density is an explicit goal, not a side effect. The user is an active trader, not a casual consumer: show more useful information in the same screen without crowding it. Scanning speed beats visual breathing room.

**Scale:** 4px base. Use 4 · 8 · 12 · 14 · 16 · 20 · 24 · 32. Nothing else.

| Context | Value |
|---|---|
| Between top-level sections | 20px |
| Inside a grid | 12px, or 16px for two-column |
| Section header height | 44px |
| Dense data row (table, list) | 14px vertical |
| Standard block padding | 16px vertical |
| Horizontal page gutter | 16px · 24px at `sm` · 32px at `lg` |
| Content max width | 1280px, centred. The app is not full-bleed. |

**Radius:** 10px for cards and inset blocks · 6px for chips and small controls · full for pills and dots. Nothing larger — large radii read as consumer software.

**Elevation:** in-app blocks use a **1px border and no shadow**. Shadows are reserved for genuinely floating layers (modal, sheet, popover, dropdown). A shadow on a static block is decoration.

**Density check:** if a screen shows fewer than roughly a dozen meaningful data points above the fold on a laptop, it is too sparse. Remove padding and containers before removing information.

## 9. Container discipline

**This is the most consequential rule in this document.**

> **Default: a plain labelled section with a divider. A card must justify itself.**

A card around every block is the single clearest signal of a generated dashboard. It also costs real space: each container spends border, radius, and padding to communicate nothing. Sections, dividers, grouping, and tables carry the same structure for free — and let a table run edge to edge, which is how trading software presents rows.

### Section anatomy — the default block

```
LABEL · qualifier                                      right-aligned summary
──────────────────────────────────────────────────────────────────────────
content — rows, table, stat line, or chart, full width
```

- Label: Label step (11px uppercase, text secondary). Optional muted qualifier after a `·`.
- Right-aligned summary value on the same line — the section's total, count, or status. Body step, tabular.
- A single divider under the header. No box, no background, no radius.
- Content runs the full content width. Tables have no inset.

### When a card *is* justified

A card earns its border only when at least one is true:

1. **It is a distinct interactive object** in a set the user chooses between — a settings group, a selectable option, a report entry that expands.
2. **It floats** — modal, sheet, popover, dropdown.
3. **It is a genuine aside** — content that must read as separate from the page's flow, such as a broker-connection gate or a first-run prompt.
4. **It is a form group** on a configuration screen, where grouping fields is the whole point (see the Stripe Dashboard reference, §2).

**Never:** a card per data block · a card inside a card · a card whose only purpose is to hold a heading and a number · a grid of cards standing in for a table.

### Worked example

```
BEFORE — card per block                 AFTER — labelled sections
┌──────────────────────┐                DAY P&L
│ Day P&L              │                +₹12,480    booked 8,240 · unreal 4,240
│ +₹12,480             │                ─────────────────────────────────────────
└──────────────────────┘                LIVE ALERTS                            3
┌──────────────────────┐                 Revenge trade      NIFTY      −₹2,100
│ Live Alerts       3  │                 Size escalation    BANKNIFTY  −₹890
│ • Revenge trade      │                ─────────────────────────────────────────
│ • Size escalation    │                OPEN POSITIONS            unreal +₹4,240
└──────────────────────┘                SYMBOL        QTY    LTP     CHG      P&L
┌──────────────────────┐                NIFTY24C50    50   182.40   +2.1%  +1,240
│ Open Positions       │                BANKNIFTY25   25   410.20   −0.8%    −890
│ ...                  │
└──────────────────────┘

3 borders, 3 radii, 6 paddings          1 divider each, tables edge to edge
~40% of vertical space is chrome        same information, ~30% less height
```

## 10. Iconography

Icons are functional. **An icon either carries meaning or it is deleted.**

- **Set:** Lucide, `stroke-width: 1.5`. The default weight of 2 reads heavy and cheap at small sizes.
- **Sizes:** 14px inline with body text · 16px in section headers and buttons · 20px maximum. Nothing larger. Oversized icons are decoration.
- **Never:** an icon beside every label · an icon to fill empty space · an icon larger than the text it accompanies · a coloured icon where the colour means nothing.

### Semantic vocabulary

Fixed meanings. Do not substitute.

| Meaning | Icon | Colour |
|---|---|---|
| `info` severity | information | primary |
| `caution` severity | triangle-alert | warning |
| `danger` / `critical` severity | octagon-alert | loss |
| Worsening | arrow up-right | loss |
| Improving | arrow down-right | profit |
| Stable | arrow right | text secondary |
| Market open | filled dot | profit |
| Market closed | filled dot | text secondary |
| Live data flowing | filled dot | profit |
| Data stale or paused | filled dot | warning |

**Accessibility:** an icon-only control requires a text label for assistive technology. A meaningful icon adjacent to text is decorative to assistive technology and should be hidden from it.

---

# Part III — Behaviour

## 11. Interaction states

Every interactive element defines all eight states. An element missing a state has a bug, not a gap.

| State | Treatment |
|---|---|
| Default | as specified by the component |
| **Hover** | background steps to the hover token, or text steps to primary. 150ms colour transition. |
| **Active / pressed** | one step darker than hover, no transition (instant feedback) |
| **Focus-visible** | 2px primary ring, 2px offset. Always visible. **Never removed.** |
| **Disabled** | 50% opacity, no pointer events, cursor default |
| **Loading** | spinner replaces the label in place; width does not change (no layout shift) |
| **Selected** | primary text plus a 2px primary underline or left border. Not a filled background. |
| **Error** | loss-coloured border plus a message below. The field keeps its value. |

**Two rules that get broken most often:**

1. **Hover is never the only affordance.** If an action or a piece of information is only discoverable on hover, it does not exist on touch. Row actions must be visible or reachable by tap.
2. **Disabled must communicate why.** A greyed-out button with no explanation is a dead end. State the reason adjacently — "Connect your broker to sync", "No trades to export" — or don't render the control.

## 12. Interaction design

Prioritise **speed and predictability**. A trader mid-session has no patience for discovery.

- **Minimum clicks to important information.** Anything a trader needs during market hours is at most one interaction from the Dashboard.
- **View state survives navigation.** Filters, sort order, selected tab, and period selection persist when the user leaves a screen and returns, and across reload. A trader who set 90 days, opened a trade, and came back to 30 days has lost trust in the screen. Persist in the URL where the state is shareable, otherwise in local storage.
- **Progressive disclosure.** Show the summary; let the detail be one interaction away. A consolidated row that expands beats two screens.
- **Actions live next to the data they affect.** No action bar at the top of the page controlling rows at the bottom.
- **Filters sit adjacent to the data they filter**, are compact, and never exceed what the screen genuinely needs (§19).
- **Keyboard:** every interactive element reachable by tab in visual order. Escape closes any overlay. A command palette provides direct navigation. Tables support arrow-key row movement where rows are actionable.

## 13. Motion

One duration, one easing. **The user should barely notice animation.** In a trading product, constant motion reads as instability.

| Purpose | Duration |
|---|---|
| Colour transitions (hover, focus) | 150ms |
| Expand / collapse, chevron rotate, toggle | 200ms |
| Content entry (a list or section appearing) | 200ms, fade with a small upward offset |
| Live price change flash | 600ms, fades out |

**Allowed:** hover and focus transitions · expand/collapse · loading indicators · a brief flash on a live price update · a count-up on the single primary metric · a subtle badge pulse when unread items exist.

**Banned:** continuous or looping animation on a data screen · glowing borders · animated gradients · bouncing or elastic easing · parallax · floating elements · confetti, fireworks, celebration of any kind · anything that animates to attract attention.

Respect the reduced-motion preference: transitions drop to instant, the price flash becomes a static tint, count-up is skipped.

## 14. Async, feedback and optimistic updates

**Skeleton for content. Spinner for actions.** A skeleton mirrors the shape of what is loading — same section stack, same row count, same column widths — so the page doesn't jump. A spinner belongs inside the button that was pressed.

### Three distinct renders

Loading, empty, and error are **three different screens**. Collapsing any two of them is the most damaging error-handling mistake in this product:

> **A failed request is never an empty state.** If the network fails, the user must see that the network failed. Rendering "no data" on a failure teaches the trader that their account is empty when in fact the platform is broken — and during live validation it hides real outages.

| Situation | Render |
|---|---|
| Request in flight, no prior data | skeleton |
| Request in flight, prior data exists | keep prior data, show a subtle refreshing indicator |
| Request succeeded, genuinely no rows | empty state (§15), stating the cause |
| Request failed | error state: what went wrong, in plain language, plus retry |
| Partial failure | render what succeeded; the failed block carries its own inline error |

Error messages are classified by cause, not by status code — offline, timed out, network, forbidden, not found, rate-limited, server error — each with its own plain-language sentence. Support contact appears only for causes the user cannot resolve.

### Optimistic updates

Optimistic only where the action is reversible and low-stakes: dismissing a nudge, expanding a row, toggling a local preference, marking an alert reviewed.

**Never optimistic:** anything involving money, position state, rule changes, or destructive actions. These wait for confirmation. A trader must never see a P&L or a position that the server does not agree with.

Every optimistic update has an explicit rollback: on failure, restore the previous value and surface the error inline — never silently.

### Feedback channel

| Channel | When |
|---|---|
| Inline, next to the element | validation, block-level failure, anything the user can fix here |
| Toast | background action completed or failed with no on-screen anchor |
| Blocking dialog | irreversible confirmation only (§19) |

Never a toast for something the screen can say in place. Never two channels for one event.

## 15. Empty states

**Never "No data available", "No insights yet", or any variant.** An empty state that doesn't explain itself reads as a broken product.

Every empty state has three parts:

1. **The cause**, stated concretely.
2. **The next action**, if one exists — one action, not a menu.
3. **Nothing else.** No decorative illustration, no motivational line. An icon is allowed only if it carries meaning.

| Situation | Say this, not that |
|---|---|
| New account, no history | "Kite doesn't provide historical trades. Import your Console CSV to see past sessions." — not "No trades yet" |
| Feature needs a minimum sample | "Habits appear after 20 completed trades. You have 6." — not "Not enough data" |
| Filter excludes everything | "No alerts match this filter." plus a clear-filter action — not "No alerts" |
| Period excludes everything | "No trades in the last 7 days. You have 34 in the last 90." — not "No trades" |
| Nothing happened, and that's good | "No behavioural alerts this session." — factual, not congratulatory |
| Market closed, no activity | "Market closed. Session summary below." — not zeros with no explanation |

**Distinguish the reasons.** "No entries at all", "entries exist but outside this period", and "entries hidden by a filter" are three different messages. Showing one message for all three is why users think data is lost.

First-run must feel **intentional, not unfinished**. A cold-start screen is a designed state with a clear next step, not a blank page.

## 16. Copywriting and AI presence

### Voice

An experienced trading mentor: factual, direct, evidence-based. Never a motivational coach, never a marketing page.

- Numbers first, one plain sentence second.
- Every statement is backed by the trader's actual behaviour. If you cannot point at the data behind a sentence, cut the sentence.
- Let the numbers tell the story. "Revenge trades cost you ₹18,400 across 11 trades" needs no adjective.
- Second person, present tense, no exclamation marks.

**Banned phrasings:** "Great job!" · "Keep going!" · "You're crushing it!" · "Nice!" · "Trade smarter with AI" · "Unlock your potential" · "Stay disciplined" · "You've got this" — and any praise attached to an outcome. Praise-shaped copy in a behavioural mirror is a category error: we report, we don't approve.

Positive findings are still reported factually. "Your morning trades are profitable: +₹34,200 across 46 trades" — not "Great work in the mornings!"

### AI presence

**AI is invisible.** The intelligence shows in the quality of the observation, never in announcing itself.

- No "I noticed…", "I think…", "AI suggests…", "Our AI analysed…", "Powered by AI".
- No AI branding on surfaces that merely use it. A detection is presented as an observation about the trader's behaviour, not as a machine's opinion.
- No chat personality bleeding into the interface. The coach has a voice inside the coach screen; the rest of the product does not.
- **Every recommendation states its evidence.** "Your position size after two losses averages 2.3× your baseline" — the evidence *is* the recommendation.
- No confidence percentages, no scores, unless the formula is shown (§4).

---

# Part IV — Components and data

## 17. Component specs

Each component below gives the semantic spec — the durable rule, in real values — followed by an italic *Implementation* note naming the utility that delivers it. **The spec is the rule; the implementation note is a replaceable footnote.**

### Section — the default block
Label (11px uppercase, text secondary) on the left, optional summary value right-aligned, 44px header height, 1px bottom divider, content full width beneath. No border, no background, no radius.
*Implementation: `.card-head` on a plain wrapper; no `.desk-card`.*

### Card — the exception
1px border, 10px radius, surface background, no shadow. Header 44px with a bottom divider; body padding 16px vertical, 16/24px horizontal. Only when §9 justifies it.
*Implementation: `.desk-card` + `.card-head`.*

### Stat
Label (11px, text secondary) above value (Body or larger, 600, tabular, sign-coloured), optional sub-line (11px, text secondary, tabular). No container by default.

### MetricStrip
A row of 2–6 stats separated by hairlines: a 1px-gap grid over a border-coloured background, each cell on surface, 12px horizontal / 10px vertical padding. Column header at Micro, value at Body 600 tabular. The hairlines are the separation — no borders per cell.
*This is not a KPI-card grid: no radius per cell, no shadow, no padding inflation. It is a dense strip.*

### Row (list row)
Dense: 14px vertical padding, separated by subtle dividers. Content left, value right-aligned and tabular. Whole row is the hit target when it drills down.

### SeverityRow
A Row plus a 2px left border in the severity colour and a 28px icon tile at 10% severity tint. Severity label and relative time at Small. Money value right-aligned.

### RankedRow
Rank (11px, 600, tabular, text secondary, fixed 16px width) · name (Body) · qualifier (11px tabular, text secondary) · right-aligned money (600, tabular, sign-coloured). Optional proportional bar beneath at 2px height in a semantic tint.

### Pill / Chip / Dot
**Pill:** full radius, 11px 500, 10% tint background, semantic text colour. Status only.
**Chip:** 6px radius, 10px 600 uppercase, for instrument or category classification.
**Dot:** 8px, full radius, semantic fill. Status indicator; always paired with text.

### Tabs
Underline style: transparent background, 2px primary bottom border and primary text on the selected tab, text secondary otherwise. Body size, 36px height, 12px horizontal padding. Horizontally scrollable on narrow screens with the scrollbar hidden. Groups separated by a vertical hairline, not a gap.

### Buttons
| Variant | Spec |
|---|---|
| Primary | primary background, contrasting text, 6px radius, 36px height, Body 500 |
| Secondary | 1px border, transparent background, foreground text |
| Ghost | no border, foreground text, hover to primary |
| Destructive | 10% loss tint background, loss text, 20% loss border |
| Inline link | 11px 500 uppercase, primary, tracking 0.12em — for "View all →" |

### Inputs
1px border, 6px radius, 36px height, 12px horizontal padding, Body text. Focus: primary border plus focus ring. Error: loss border plus message below. Label above at Small 500; help text below at Small, text secondary.

### Accordion drill-down
Trigger row at standard density, chevron rotating 200ms on the right, content separated by a top divider. Used for consolidated → detail. No underline on hover; the row background steps instead.

### Filter row
Compact, immediately above the data it filters. Segmented pills for mutually exclusive choices; each pill Small 500, 28px height. Selected pill gets primary text and a surface background. Never a dropdown where fewer than five options exist.

### Sheet / Dialog / Popover
| Use | When |
|---|---|
| Popover | a small, non-blocking choice anchored to a control |
| Dialog | irreversible confirmation, or a focused edit that must block |
| Sheet | mobile detail and mobile forms; slides from the bottom |

Elevated background, shadow, escape and backdrop dismiss. **Never** used to deliver information the screen could have shown in place (§4). Never auto-opened without a user action.

## 18. Tables and lists

**Tables are first-class.** In trading software a table is frequently the *best* presentation, not a fallback for when a chart won't do. A well-built table beats every chart type for comparison, precision, and scanning.

### Structure
- Column headers at Micro (10px uppercase, text secondary), no background fill, single divider beneath.
- Rows at 14px vertical padding, separated by subtle dividers. Row hover steps the background.
- **Numeric columns right-aligned and tabular.** Text columns left-aligned. Never centre a number.
- Consistent column order across screens: identifier → quantity → price → change → value.
- The table runs edge to edge within its section — no inset, no card.

### Behaviour
- **Footer totals** where a column sums to something meaningful, in the section header's right-aligned summary slot rather than a footer row where possible.
- **Consolidate, then drill down.** Show one row per instrument with aggregated values; expanding reveals the individual legs. Never present forty raw rows where eight consolidated rows answer the question.
- **Cap volume.** Show the meaningful subset with an explicit "View all N" control. Never render an unbounded list.
- **Sort** on any column whose order carries meaning; the current sort persists per §12.
- Mobile: collapse to stacked rows (§23). **Never horizontally scroll a primary table.**

### Table or chart?
Use a table when the user needs exact values, comparison across more than two dimensions, or the ability to find a specific row. Use a chart only when shape over time is the point (§20). When in doubt, table.

## 19. Forms and inputs

Forms are a **secondary surface** in this product. The core loops require zero typing (§3); configuration screens are where forms legitimately live. Design them to be completed once and forgotten.

- **Label above the field.** Help text below, at Small, text secondary. Error replaces help text and is loss-coloured.
- **Validate on blur, not per keystroke.** Validating as the user types is hostile. Re-validate on submit.
- **Group related fields** into a card (§9 justification 4) with a section title, not into one long undifferentiated column.
- **Unsaved changes:** a persistent save affordance appears when the form is dirty and states what will be saved. Actions that depend on saved state are disabled with the reason given (§11).
- **Fewer than five options → segmented control, not a dropdown.** A dropdown hides the choices.
- **Filters** are compact and adjacent to their data (§17). Every filter must solve a stated problem — if you cannot name the question a filter answers, remove it.

### The confirmation ladder

Friction proportional to consequence:

| Consequence | Confirmation |
|---|---|
| Reversible (toggle, filter, expand) | none |
| Lossy but recoverable (clear a session, discard a draft) | inline confirm, stating what is lost |
| Weakening a self-imposed safeguard | a dialog naming the specific safeguard and its current value, with a destructive-styled action |
| Irreversible (delete account, delete data) | typed exact-match of a value only the owner knows, verified again server-side |

Destructive actions never use the primary style. A destructive action never sits adjacent to a routine one.

## 20. Charts

**A chart is included only when it answers a question the screen has explicitly asked.** A chart added because dashboards have charts is removed, not restyled.

### Allowed forms
Equity curve (cumulative, area or line) · time series bars (daily or periodic P&L) · distribution and histogram · sparkline (inline, in a row or stat) · calendar heatmap · horizontal bars for ranked comparison.

### Banned forms
**Donut, pie, radial gauge, circular progress.** They compare poorly, waste space, are the most overused shape in generated dashboards, and in every case here a table or a horizontal bar communicates more. Composition of a whole is better shown as a ranked table with proportional bars.

### Rules
- **Colour comes from the token system, resolved at runtime, never a literal.** A chart library needs a concrete colour string, so read the token — a hardcoded hex breaks in one of the two themes by definition.
- One accent plus the three semantics. A series never introduces a new hue; additional series use neutral steps.
- Currency axes use the compact formatter (`₹1.3k` / `₹2.5L` / `₹1.2Cr`) with a fixed axis width, so the minus sign is never clipped — a clipped minus turns a loss into a gain, the worst defect a chart can have.
- Horizontal grid lines only, in the border colour. No vertical grid, no chart border, no gradient fill, no drop shadow, no 3D.
- Axis and legend text at Label size, text secondary. Never bold.
- Tooltips are a defined component, not an inline formatter, so every tooltip in the product looks and behaves identically.
- **An empty chart renders the empty state (§15), never an empty axis frame.**

## 21. Numbers and money

- **P&L is RAW only:** `(exit − entry) × quantity × multiplier`. Never brokerage, STT, or taxes. Never build a charge estimator. A number the trader can't reproduce from their own contract note is a number they won't trust.
- **Behaviour → money is realized P&L of flagged trades** — a fact, tied to the specific triggering trade. Never a counterfactual, never "estimated cost", never "money saved".
- Always show the sign, using a true minus.
- Rupees in body text: no decimals (`₹1,240`). Prices: two decimals (`182.40`). Percentages: one decimal (`62.5%`).
- Large values compact to `L` and `Cr` — Indian conventions, since the audience is Indian F&O traders.
- Indian digit grouping throughout (`12,48,000`).
- Every number carries `tabular-nums`. No exceptions.
- Relative time for recency ("4m ago"), absolute for the record ("28 Jul 2026").

## 22. Accessibility

- **Focus:** a visible 2px primary ring with 2px offset on every focusable element. Never removed, never replaced with a colour change alone.
- **Contrast:** body text on any surface meets 4.5:1 in **both** themes. Verify both — the desaturated palette is closer to the floor than a vivid one.
- **Colour is never the only signal.** Numbers carry a sign, trends carry an arrow, severity carries a label and an icon, status carries text beside the dot.
- **Semantics:** tab sets use proper tablist roles and selection state. Live-updating regions announce politely. Expandable rows expose their expanded state.
- **Touch targets:** 44px minimum on mobile. A dense 14px row satisfies this with its padding; a 14px icon button does not.
- **Reduced motion** is respected per §13.
- Every icon-only control has a text label for assistive technology.

## 23. Responsive and mobile

**Mobile is not a compressed desktop.** It is a re-prioritised layout.

| Breakpoint | What changes |
|---|---|
| `< 640px` | single column · bottom navigation · tables become stacked rows · sheets replace dialogs · gutters 16px |
| `640px` | two-column grids permitted · gutters 24px |
| `768px` | sidebar replaces bottom navigation · full table layouts |
| `1024px` | gutters 32px · multi-column sections |
| `1280px` | content caps and centres |

### Mobile rules
- **Most important information first.** Re-order for mobile; do not simply stack the desktop order. On a live screen, the primary metric and open risk come before history.
- **Stack logically, don't shrink.** A table becomes stacked rows with the identifier on the first line and labelled values beneath — never a shrunken grid or a horizontal scroll.
- **Bottom sheets, not dialogs**, for detail and forms.
- **Comfortable touch targets without wasting space** — 44px effective, achieved through padding on dense rows rather than by inflating everything.
- Secondary navigation lives in a "More" sheet using the same grouping as the sidebar — the two must never disagree.
- Anything that only appears on hover must have a tap equivalent (§11).

---

# Part V — Screen specification

## 24. Screen inventory

**26 routes. 11 product · 5 system · 10 admin.**

| # | Product screen | Route |
|---|---|---|
| 1 | Dashboard | `/dashboard` |
| 2 | Analytics | `/analytics` |
| 3 | Alerts | `/alerts` |
| 4 | My Patterns | `/my-patterns` |
| 5 | My Record | `/my-record` |
| 6 | Chat | `/chat` |
| 7 | Reports | `/reports` |
| 8 | Journal | `/journal` |
| 9 | My Rules | `/my-rules` |
| 10 | Settings | `/settings` |
| 11 | Welcome (pre-auth) | `/welcome` |

**System screens:** Terms of Service · Privacy Policy · Maintenance · Not Found · Impersonation entry.

**Admin:** ten screens (Overview · Users · User detail · System · Insights · Broadcast · Audit log · Admins · Config · Login). Admin is **deliberately a separate, denser tool language** with its own kit. It shares the tokens in §6 and the scale in §7 and nothing else. Do not unify it with the product screens; changes here do not apply there.

### Navigation

One canonical structure, identical on both platforms. Desktop shows it as a sidebar; mobile shows the four primaries in a bottom bar and the rest in a "More" sheet using the same group names.

| Group | Screens |
|---|---|
| *(primary)* | Dashboard · Analytics · Alerts · Chat |
| Insights | My Patterns · Reports · Journal |
| Risk | My Rules · My Record |
| Account | Settings |

The mobile bottom bar carries the four primaries plus More. Grouping and labels never differ between platforms.

## 25. Ownership map

**A metric lives on exactly one screen.** Everything else links to it.

| Story | Owner | Others may |
|---|---|---|
| What is happening right now | Dashboard | — |
| What behaviour was detected, and the response record | Alerts | show the newest few (Dashboard) |
| What behaviours cost money over time | Analytics | link |
| Which habits define this trader | My Patterns | link |
| What happened last time I traded this setup | My Record | — |
| Explain and answer using real history | Chat | — |
| The written periodic record | Reports | link |
| The per-session log | Journal | link |
| The trader's constitution and standing against it | My Rules | show a breach count (Dashboard, Alerts) |

**Cross-link, never recompute.** If two screens need the same figure, one owns it and the other links. Two screens computing the same thing over different windows is how a product loses credibility.

## 26. Per-screen specification

Each screen is specified with the same eight fields.

---

### 1. Dashboard — `/dashboard`

**Responsibility.** What is happening right now. The only screen a trader keeps open during market hours.

**Owns.** Live session P&L · open positions and live risk · today's closed round-trips · the newest behavioural alerts.
**Does not own.** Alert history or response statistics (Alerts) · long-term cost (Analytics) · the habit scorecard (My Patterns) · anything requiring a period selector.

**Primary metric.** Day P&L, at Display size. The only 30px number on the screen.

**Layout.** Single column, 20px between sections. No side rail.

| Block | Container | Notes |
|---|---|---|
| Market rail | none — a thin status line | Title, market open/closed dot, IST clock, close countdown |
| Day P&L | section | Display value · booked / unrealized breakdown at Small · session stats as a MetricStrip (trades, loss budget used, win rate, unrealized) |
| Setup nudge | card (justification 3) | Conditional: first-run and setup gaps only. Dismissible. |
| Live alerts | section | Label + count, then SeverityRows. Caps at four with "View all →" to Alerts. Announces politely as items arrive. |
| Open positions | section | Right-aligned unrealized total. Edge-to-edge table: symbol, qty, entry, LTP, change %, P&L. Live price flash per §13. |
| Closed positions | section | Right-aligned booked total. Consolidated one row per instrument, expanding to legs. |

**Charts vs tables.** **No charts.** Nothing on this screen is a question about shape over time — every block is a current value or a list. A chart here would be decoration.

**States.**
- Loading: skeleton mirroring the section stack.
- Market closed, no trades today: "Market closed. Session summary below." with the last session's figures — never a screen of zeros.
- Cold start: "Kite doesn't provide historical trades. Import your Console CSV to see past sessions."
- Fetch failure on a block: that block shows an inline error with retry; the rest of the screen still renders.
- Not connected: broker gate (card, justification 3).

**Mobile.** Order: Day P&L → open positions → live alerts → closed positions. Session stats collapse behind a toggle. Tables stack. Market rail condenses to a dot plus the clock.

**Must never appear here.** Any chart · a period selector · a streak or score · long-term or historical metrics · a floating coach button · anything auto-opening over the screen.

---

### 2. Analytics — `/analytics`

**Responsibility.** What behaviours cost money over time — the quantified evidence, over 7, 30, or 90 days.

**Owns.** All period-based cost attribution, edge analysis, and behavioural cost quantification.
**Does not own.** Live session data (Dashboard) · the alert response loop (Alerts) · the at-a-glance habit scorecard (My Patterns).

**Primary metric.** Net P&L for the selected period, at Display size, inside the verdict block.

**Layout.**

| Block | Container | Notes |
|---|---|---|
| Header | none | H1 + period control (7/30/90) + export. Period persists per §12. |
| Verdict | section | Primary metric · one plain sentence naming the period's biggest cost · win rate and profit factor inline |
| Tab bar | none | Underline tabs, hairline before the deep group |
| Tab content | sections | Each tab is a stack of labelled sections |

**Tabs.** Overview (totals, equity curve, daily P&L, attribution) · Edge (where money is made and lost — instrument, time, size) · Behaviour (how habits shaped results) · Habits (zero-input tendencies) · Advanced (session and expiry depth).

**Charts vs tables.** Charts where shape over time is the question: equity curve, daily P&L bars, hour-of-day and day-of-week bars, calendar heatmap. **Tables everywhere else** — instrument and strategy comparison are ranked tables with proportional bars, not charts. No donut for attribution; a ranked table with bars answers it better.

**States.** Per-tab skeleton matching that tab's own shape, not one generic skeleton. Per-tab error with retry. Sample-gated blocks state the threshold and the current count. Not connected: broker gate.

**Mobile.** Tab bar scrolls horizontally. Charts keep full width at reduced height. Ranked tables stack. Period control stays reachable at the top.

**Must never appear here.** Donut, pie, or radial anything · the same dimension charted twice · live session figures · a metric already owned by another screen.

---

### 3. Alerts — `/alerts`

**Responsibility.** What behaviour was detected — and whether the trader acted on it.

**Owns.** The full alert record, severity presentation, per-pattern frequency, and the response statistics.
**Does not own.** Behavioural cost in money over a period (Analytics) · the habit scorecard (My Patterns).

**Primary metric.** None. Counts appear inline in the header; nothing on this screen earns Display size.

**Layout.**

| Block | Container | Notes |
|---|---|---|
| Header | none | H1 + inline counts (total, danger, unreviewed) |
| Tabs | none | Unreviewed · History · Patterns |
| Filter row | none | Adjacent to the list: period and severity as segmented pills |
| Alert list | sections of SeverityRows | 2px left border, tinted icon tile, pattern name, category chip, relative time, money value |
| Response record | section | On the Patterns tab: how often alerts were acted on, ignored, or traded through |

**Charts vs tables.** No charts. Frequency is a ranked table with proportional bars. A distribution over time may be a sparkline inside a row, never a full chart.

**States.** Skeleton rows while loading. Three distinct empty messages: "No behavioural alerts this session." · "No alerts in this period." · "No alerts match this filter." plus clear-filter. Failure shows an error with retry, never an empty list.

**Mobile.** Filters collapse to a single row of pills. Rows keep the left border and drop the category chip. Detail opens in a bottom sheet.

**Must never appear here.** Any outcome-capture control (§3) · a blocking interruption · praise for a clean session beyond a factual statement · a severity colour outside §6.

---

### 4. My Patterns — `/my-patterns`

**Responsibility.** Which habits define this trader — the at-a-glance scorecard.

**Owns.** The behavioural summary view: which patterns are the trader's own, which are worsening, and the day-level history.
**Does not own.** Per-pattern frequency counts (Alerts) · money quantification over a period (Analytics).

**Primary metric.** None, or the single worst pattern's realized cost.

**Layout.**

| Block | Container | Notes |
|---|---|---|
| Header | none | H1 + refresh |
| Standing | section | Current behavioural state, with the specific triggers named and their values |
| Top patterns | section | RankedRows, each with realized money attached (§3) |
| Day history | section | Calendar heatmap: clean, caution, danger, no data — using semantic tints only |
| Cooldown history | section | Dense rows |
| Cross-link | none | Inline link to the Alerts pattern breakdown |

**Charts vs tables.** The calendar heatmap is the one chart — it answers "when", which a table cannot show at a glance. Everything else is a ranked table.

**States.** Skeleton for the standing block and the heatmap. Empty: "No behavioural patterns detected across N trades." Failure: inline error — never a silently absent block, and never an all-clean heatmap standing in for a failed request.

**Mobile.** Heatmap scrolls horizontally by week — this is the one exception to the no-horizontal-scroll rule, because a calendar is inherently a wide grid and stacking it destroys the pattern. Everything else stacks.

**Must never appear here.** A streak framed as an achievement · a composite score whose formula isn't shown (§4) · a raw colour outside the semantic set · a duplicate of the Alerts frequency table.

---

### 5. My Record — `/my-record`

**Responsibility.** What happened the last time I traded this setup — a pre-trade lookup over the trader's own realized history.

**Owns.** Instrument-level personal history: this hour, best and worst hours, conditional situations, holding behaviour.
**Does not own.** Anything predictive. This screen never estimates, scores, or advises.

**Primary metric.** Net P&L of the looked-up record, at Display size.

**Layout.**

| Block | Container | Notes |
|---|---|---|
| Lookup | card (justification 1) | Search input plus instrument chips seeded from the trader's own history |
| Record | section | Primary metric · trade count and win rate · scope note if the scope was widened, stated plainly |
| Right now | section | 2px left border coloured by this hour's record. Sample warning when thin. |
| Best / worst hour | section | Two stats side by side |
| In these situations | section | Table: after a loss, after two or more losses, expiry day, quick re-entry |
| Holding | section | Average and longest hold |

**Charts vs tables.** No charts. Every question here is "what is the number" — tables and stats only.

**States.** Skeleton on lookup. No trades for this instrument: "No completed trades in NIFTY. Your record covers 14 other instruments." Thin sample: state the count rather than hiding the figure. Cold start: the import message. **This screen needs the same broker gate as the others** — a not-connected user must see the gate, not a silently inert search box.

**Mobile.** Search first and sticky. Situations table stacks. Best/worst hour stack.

**Must never appear here.** Any prediction, probability, or recommendation · a verdict on whether to take the trade · a score.

---

### 6. Chat — `/chat`

**Responsibility.** Explain, coach, and answer questions using the trader's actual history.

**Owns.** The conversational surface and the saved insight.
**Does not own.** Any metric. It cites figures the other screens own.

**Primary metric.** None.

**Layout.**

| Block | Container | Notes |
|---|---|---|
| Header | none | H1 + clear-session action |
| Session snapshot | section | A thin strip: today's P&L, trade count, alert count, risk state |
| Messages | none | Full-height scroll. Trader's message on a hover-token background; the response plain on the page. Timestamps at Label. |
| Suggestions | none | Context chips — few, specific, derived from the trader's data |
| Composer | none | Auto-resizing input, send, depth toggle |

**Charts vs tables.** None inline. If a figure needs a shape, link to the screen that owns it.

**States.** No skeleton — an empty conversation is the intentional first state, with starter questions drawn from the trader's real data, not generic prompts. Stream failure surfaces as an inline error with retry, not as a message pretending to be the coach apologising. Feature-disabled renders a plain explanation. Not connected: broker gate.

**Mobile.** Composer pinned above the bottom navigation. Snapshot collapses to one line. Suggestions scroll horizontally.

**Must never appear here.** AI branding or persona framing (§16) · a floating entry point on other screens · clearing the session without confirmation (§19) · motivational framing of any answer.

---

### 7. Reports — `/reports`

**Responsibility.** Provide periodic summaries that help the trader review what happened after the market, identify the biggest drivers of performance, and understand long-term progress through factual, generated reports.

**Owns.** The periodic written record and its detail.
**Does not own.** Live data (Dashboard) · interactive period analysis (Analytics).

**Primary metric.** None. The headline figure belongs to the individual report entry.

**Layout.**

| Block | Container | Notes |
|---|---|---|
| Header | none | H1 + type filter as segmented pills |
| Comparison | section | Latest against previous |
| Report list | cards (justification 1) | Each entry is a selectable, expandable object — a legitimate card. Type chip, date, headline figure, chevron. |
| Load more | none | Explicit, not infinite scroll |

**Charts vs tables.** No charts in the list. An expanded report may contain a single sparkline if the report's subject is a trend.

**States.** Skeleton entries while loading. Empty: "No reports yet. The first end-of-day report is generated after your first trading session." Detail-fetch failure shows an inline error inside the expanded entry — never an entry that expands to nothing.

**Mobile.** Filter pills scroll. Entries full width. Expansion in place, not a sheet.

**Must never appear here.** Motivational summary copy · AI attribution on the report itself · a metric restated from Analytics without linking.

---

### 8. Journal — `/journal`

**Responsibility.** Maintain an automatically generated chronological record of every trading session, capturing what happened, why key events occurred, and the behavioural context — without requiring manual journaling.

**Owns.** The per-session log and its entries.
**Does not own.** Behavioural detection (Alerts) · pattern identification (My Patterns).

**Primary metric.** None.

**Layout.**

| Block | Container | Notes |
|---|---|---|
| Header | none | H1 + entry count |
| Intent | card (justification 3) | Session intent, conditional |
| Summary | section | MetricStrip: journalled P&L, plan adherence, dominant emotion |
| Filters | none | Period, emotion, plan adherence — adjacent to the list |
| Entries | sections | Dense rows expanding in place |

**Charts vs tables.** No charts.

**States.** Skeleton entries. Three distinct empties, kept distinct: no entries at all · entries exist outside this period, with the count that do exist · entries hidden by the current filter, with a clear action. Failure: error with retry.

**Mobile.** Filters collapse to one scrolling row. Entries full width.

**Must never appear here.** A rating widget or any control whose value the trader must type (§3) · filters that operate on a partial dataset while appearing to filter everything · a star rating presented as a score.

---

### 9. My Rules — `/my-rules`

**Responsibility.** Define, monitor, and enforce the trader's personal risk framework by showing current standing, breaches, and rule changes — while ensuring any weakening of a safeguard is deliberate.

**Owns.** The trader's self-imposed limits, the standing against them today, breaches, and the change history.
**Does not own.** Behavioural patterns (My Patterns) · alerts raised by a breach (Alerts).

**Primary metric.** None. Standing is shown per rule.

**Layout.**

| Block | Container | Notes |
|---|---|---|
| Header | none | H1 + edit action |
| Pending change | section | 2px warning left border, conditional |
| Today against your rules | section | Per-rule rows: name, limit, used, proportional bar |
| Breaches | section | Today's list, period count, per-rule tally |
| History | section | Collapsed by default |
| Edit | dialog | Grouped fields (justification 4) |
| Loosen confirmation | dialog | Names the specific rule and its current value; destructive-styled action |

**Charts vs tables.** No charts. Proportional bars inside rows carry the standing.

**States.** Skeleton for the standing block. Empty: "No rules set. Set your daily loss limit to start." Failure: error with retry — a rules screen that fails silently is dangerous, because absent rules read as no rules.

**Mobile.** Rows stack with the bar full width beneath. Edit opens as a sheet.

**Must never appear here.** Tightening a rule behind friction — tightening is instant · a loosening path without the confirmation dialog · praise for adherence.

---

### 10. Settings — `/settings`

**Responsibility.** Manage account configuration, broker connectivity, notifications, preferences, and data ownership — without affecting behavioural analysis or trading workflows.

**Owns.** Broker connection, profile and limits, notification configuration, personalisation, and data rights.
**Does not own.** Rule semantics (My Rules).

**Primary metric.** None.

**Layout.**

| Block | Container | Notes |
|---|---|---|
| Header | none | H1 + save affordance, visible when dirty |
| Broker connection | card (justification 4) | Always visible above the tabs |
| Tabs | none | Profile · Notifications · Insights · Danger Zone (loss-coloured when selected) |
| Field groups | cards (justification 4) | This is the one screen where cards are the default — grouped configuration is their purpose |

**Charts vs tables.** None.

**States.** Skeleton while loading. **A failed profile load must surface an error** — silently showing default values as though they were the trader's settings is the most damaging failure on this screen. Sample-gated insights state the threshold and the current count rather than "not enough data". Guest sessions see a read-only notice in place of destructive controls.

**Mobile.** Tabs scroll. Fields full width. Segmented controls wrap rather than shrink. Save affordance pinned.

**Must never appear here.** A destructive action without the ladder from §19 · a hard-coded colour on a control · an irreversible action reachable in one tap.

---

### 11. Welcome — `/welcome` (pre-auth)

**Responsibility.** Convert a visiting trader into a connected account by demonstrating what the product observes.

**Owns.** The pre-auth narrative, pricing, and consent-gated connection.
**Does not own.** Any real user data.

**Primary metric.** None — figures here are illustrative and must be labelled as such.

**Layout.** Navigation → hero with a live demonstration and a consent-gated action → proof strip → the loss-spiral walkthrough → three feature narratives → detector table → testimonials → pricing → questions → closing action → footer.

**Charts vs tables.** The detector list is a table. Demonstrations may animate as they represent live behaviour — this is the single screen where motion is content.

**States.** No loading or empty states — content is static.

**Mobile.** Single column, hero demonstration scaled not cropped, pricing stacked, table becomes stacked rows.

**Must never appear here.** Fabricated user data presented as real · claims not backed by the product · a look that fails to match the product behind the login. **This is the only screen permitted a hero and marketing composition — and it still uses the tokens in §6, the scale in §7, and no gradients.** A visitor must recognise the product they see here when they get inside.

---

### System screens

| Screen | Spec |
|---|---|
| **Terms of Service**, **Privacy Policy** | Single column, 68ch maximum, Body at 1.6 line-height, H2 section headings, 16px between blocks. One warning-tinted callout permitted for the advice disclaimer. A data-use table where a table is clearer than prose. |
| **Maintenance** | Centred, single message from a fixed set chosen by reason code. Warning icon, one line of explanation, no action. This route is public and unauthenticated — it must never render caller-supplied text. |
| **Not Found** | Centred, meaningful icon in a primary tint, the path that failed, one action back to the Dashboard, one to report it. |
| **Impersonation entry** | Full-width banner making an administrative session unmistakable, persistent, with an exit action. |

## 27. Extending the system

Adding to the system is expected. Doing it locally is not.

**Adding a colour.** Almost certainly wrong — the palette is one accent plus three semantics by design (§6). If a new semantic meaning genuinely exists, add the token to both themes, verify contrast in both, and document its meaning here. A colour added for visual variety is rejected.

**Adding a type size.** Almost certainly wrong. The seven steps in §7 cover every case in this product. If content doesn't fit a step, restructure the content.

**Adding a component.** Add it to §17 with its full spec and all eight states from §11 before using it. A component used on one screen and specified nowhere becomes that screen's private style.

**Adding a pattern.** Document it in Part III or IV, name which components it composes, and state when to use it versus the existing alternative.

**Adding a screen.** It must have a single responsibility no existing screen owns (§25), a first-run state (§15), and a defined mobile layout (§23). If its responsibility overlaps an existing screen, extend that screen instead.

**The bar for a new surface.** It answers a question the trader actually has · it is factual and provable from their own data · it is differentiated from what their broker already shows · it needs no manual input · it earns its space against everything already competing for the same screen. A feature that fails any of these is not built, however easy it would be.

**The system is frozen once complete.** A change requires a concrete reason — a new product capability, a demonstrated usability problem, or an inconsistency to resolve. Never preference, never a trend, never "while we're in here". Record the reason alongside the change. A system that keeps moving is a system nobody trusts enough to follow.

## 28. Design review checklist

Run this before opening a PR that touches the interface, and again as the reviewer. It is deliberately short enough to actually use.

**Purpose**
- [ ] Does this screen own exactly one story (§25)?
- [ ] Is any metric here already owned by another screen?

**Visual**
- [ ] Does every card justify its existence against the four tests in §9?
- [ ] Is the density right — could this show more without crowding?
- [ ] Is the hierarchy obvious at a glance, from type and spacing rather than colour or size inflation?
- [ ] One primary metric, or none?

**Components**
- [ ] Did this reuse existing components, or invent local styling?
- [ ] If something new was added, was it genuinely necessary — and is it specified in §17?

**Data**
- [ ] Is every number factual, and produced by the engine rather than assembled in the view?
- [ ] Can every displayed metric be explained to the trader, including how it was derived?
- [ ] Is P&L raw (§21)?

**States**
- [ ] First-run state present, naming the real cause?
- [ ] Empty state distinct from error, stating the cause and one next action?
- [ ] Error state reachable and honest — no failed request rendering as empty?
- [ ] Loading state a skeleton matching the final shape, not a spinner?

**Mobile**
- [ ] Does it stack logically, re-prioritised rather than compressed?
- [ ] Any horizontal scrolling on a primary table?
- [ ] Touch targets at least 44px effective?
- [ ] Is anything reachable only on hover?

**Copy**
- [ ] Evidence-based, with the data behind every sentence?
- [ ] No AI personality, no AI branding?
- [ ] No motivational or congratulatory language?

**Performance**
- [ ] No layout shift as data arrives — skeletons match final dimensions?
- [ ] No avoidable re-renders (tooltips and chart children defined outside render, stable keys)?

**Both themes and three widths**
- [ ] Verified in light and dark?
- [ ] Verified at 375, 768, and 1440?
