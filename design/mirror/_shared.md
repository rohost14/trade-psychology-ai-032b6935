# Mirror — TradeMentor design system (light)

**Source of truth for the Claude Design project of the same name.** Authored locally,
versioned, pushed with `DesignSync`. Edit here, not on the board.

Derived from the running app. Token *structure* is adapted from Fluent 2 (Fluent UI
React v9) after a detailed read of its published tokens; token *values* are ours.
Deviations from Fluent are marked **DEVIATION** with the reason.

---

## Revision 3 — what changed and why

**Rev 2 made everything a card. That was wrong.** The brief was "half in card and half
other way"; the result was a page where every block had a border and a shadow, which is
just as flat as no borders at all — when everything is elevated, nothing is.

**Rev 3 composition: one canvas, flat sections inside it.**

```
ground  (#EEF1F5)  the page. Shows as a margin around the canvas
  └ canvas (#FFFFFF, radius 12, --sh-4)  ONE surface, holds the page
      ├ band     hero / page header — flat, divided by a rule
      ├ section  header + hairline rows — flat, no border, no shadow
      ├ section
      └ callout  a real card. 1–2 per page, maximum
```

Depth now comes from three places, none of which is a per-block border:
1. the **canvas edge** — one clear step off the ground, for the whole page at once
2. **inset wells** (`#E9EDF3`) that go *darker* than the canvas — metric chips, table
   headers, chart tracks, inputs
3. **hairlines** (`#E3E8EF`) for repetition inside a section

A card is now reserved for something that must interrupt: a callout, an empty state, an
error, a popover. If a page has more than two, one of them is wrong.

---

## Revision 4 — colour (option C, chosen 2026-08-05)

Rev 3 was **about 2% chromatic**: four badges, six figures, one nav item. Removing the
cards removed every tinted surface — the accidental cost of that fix — and the brand
never appeared above 13px, so teal read as a link colour rather than an identity.

Four changes, none decorative. **Every coloured field is either chrome that holds no
data, or a direct read of state.**

**1 · Ink rail.** The sidebar is `#111820` with a `#3FBFA8` accent. It is the one large
colour field on screen and it holds no data, so it carries weight without competing with
a figure. It also restores the dark scheme deliberately, rather than as the half-applied
artefact the shipping app produces in light mode.

| Rail token | Value | Contrast on rail |
|---|---|---|
| `rail` | `#111820` | ground |
| `rail-2` | `#1A232D` | selected item |
| `rail-ink` | `#E8EDF2` | 15.1:1 |
| `rail-ink-2` | `#8FA0B2` | 6.7:1 — nav items |
| `rail-ink-3` | `#6B7C8E` | 4.2:1 — icons only, never text |
| `rail-label` | `#7B8B9C` | 5.1:1 — group labels |
| `rail-accent` | `#3FBFA8` | 7.9:1 |

**2 · State band.** The hero is tinted by what the session actually is, and flips on an
up day. A losing session previously announced itself with one coral figure; now the band
carries it and the answer arrives before any reading.

```css
--state-down: linear-gradient(180deg, #FBEAE6 0%, #FFFFFF 100%);  /* + 3px loss rule */
--state-up:   linear-gradient(180deg, #E4F4EC 0%, #FFFFFF 100%);  /* + 3px profit rule */
--state-flat: linear-gradient(180deg, #EEF3F8 0%, #FFFFFF 100%);  /* pre-open, no rule */
```

The wash is weak and a **3px top rule does the actual work** — a saturated field would be
the colour-field hero already rejected once. Strengthened from the first proposal, where
up-day and down-day were nearly indistinguishable and the tint therefore earned nothing.

**3 · Section icons.** Every section header takes a 22px tinted icon — brand for neutral
sections, status colour where the section has a state. This is what puts the palette at a
readable size instead of only at 10px.

**4 · Solid `DANGER`.** The worst severity takes the solid fill; caution and info stay
tinted. This is the reason the four-token status ramp exists. Table headers move from grey
`inset` to `brand-tint`, which is the largest single neutral area on most screens.

---

## Layers

**DEVIATION from Fluent's numbering.** Fluent uses `colorNeutralBackground1..6`, where
`1` is the primary content surface and the theme decides whether that is lighter or
darker than what sits behind. We use four named layers instead of six numbered ones,
because we have four and naming them is clearer at this size. The *principle* is taken:
a layer is defined by its role in the stack, not by its lightness, so a dark theme is a
value swap rather than a redesign.

| Layer | Light | Dark (spec) | Role |
|---|---|---|---|
| `ground` | `#EEF1F5` | `#0D0F12` | Page margin. Never holds content |
| `canvas` | `#FFFFFF` | `#191B1F` | The one surface the page sits on |
| `inset` | `#E9EDF3` | `#101216` | Wells, table headers, chart tracks, inputs |
| `raised` | `#FFFFFF` + `--sh-8` | `#22252A` + `--sh-8` | Callouts, popovers, menus |

---

## Elevation

**Adopted from Fluent wholesale — this was the strongest thing in their system.**
Every shadow is **two layers: ambient + key**. Blur equals the token number; the key
y-offset is half of it; the ambient stays tiny because it is a contact shadow, not a glow.

```css
--sh-2:  0 0 2px rgba(15,23,36,.12), 0 1px  2px rgba(15,23,36,.14);
--sh-4:  0 0 2px rgba(15,23,36,.12), 0 2px  4px rgba(15,23,36,.14);
--sh-8:  0 0 2px rgba(15,23,36,.12), 0 4px  8px rgba(15,23,36,.14);
--sh-16: 0 0 2px rgba(15,23,36,.12), 0 8px 16px rgba(15,23,36,.14);
--sh-28: 0 0 8px rgba(15,23,36,.12), 0 14px 28px rgba(15,23,36,.14);
--sh-64: 0 0 8px rgba(15,23,36,.12), 0 32px 64px rgba(15,23,36,.14);
```

**Dark keeps identical geometry and doubles both alphas** — `.12→.24`, `.14→.28`. That is
the whole dark elevation story, and it is why the previous revision had none: it hand-tuned
opacities per theme instead of deriving them.

Shadow colour is blue-black `rgba(15,23,36,…)`, never neutral black.

**Elevation → usage.** Fixed mapping, not per-component judgement:

| Token | Used by |
|---|---|
| `--sh-2` | Resting rows that lift on hover; segmented-control thumb |
| `--sh-4` | **The canvas.** Nothing else |
| `--sh-8` | Callouts, dropdowns, context menus |
| `--sh-16` | Tooltips, hover cards |
| `--sh-28` | Popovers over a scrolled page |
| `--sh-64` | Dialogs, side panels |

---

## Colour

Cool neutrals throughout. No warm grey, no beige.

| Token | Value | Contrast on canvas |
|---|---|---|
| `ink` | `#0F1724` | 16.9:1 |
| `ink-2` | `#4A5768` | 7.9:1 |
| `ink-3` | `#647285` | **4.9:1** — the floor for any text |
| `rule` | `#E3E8EF` | hairlines inside the canvas |
| `edge` | `#D3DBE4` | the canvas border |
| `stroke-strong` | `#5E6B7A` | **5.4:1** — control borders only |

**`stroke-strong` is a P0 fix.** The previous revision drew input and search borders in
`#D6DEE8`, about **1.3:1** against white, which fails WCAG 2.1 SC 1.4.11 (non-text
contrast, 3:1) for interactive controls. Decorative hairlines may stay light — they carry
no state. Anything a user can focus or type into takes `stroke-strong`.

### Status — four tokens each, not one

**Adopted from Fluent's split.** A colour that works as a solid fill fails as text on
white, and vice versa. One value cannot do both jobs.

| | solid (white text) | text on light | tint | edge |
|---|---|---|---|---|
| brand | `#0E7A6E` | `#0B6155` 7.5:1 | `#E4F3F1` | `#B4DDD7` |
| profit | `#12795B` | `#0E6249` 7.5:1 | `#E7F4EF` | `#B9DFD0` |
| loss | `#C2372B` 5.4:1 | `#A62B21` 7.0:1 | `#FCEEEC` | `#EFC0BA` |
| caution | `#96600C` 5.3:1 | `#8F5A0B` 5.8:1 | `#FDF4E6` | `#EBD8B4` |

Caution's solid is darkened from the display hue specifically so white text on it clears
4.5:1 — the badge type is 10px, so the large-text exemption does not apply.

**Green means money and only money.** No Fluent equivalent; keep it. Brand teal and profit
green are close in hue, so the separation is enforced by rule or a trader loses the ability
to find P&L by colour on a page carrying nine teal links.

### Interaction states

**P1 fix — the previous revision defined none.** Every hover was undefined.

| Token | Value | Applies to |
|---|---|---|
| `hover` | `#F5F8FA` | rows, list items, ghost buttons |
| `pressed` | `#EDF1F5` | same, active |
| `selected` | `#E4F3F1` | current nav item, selected row |
| `focus` | 2px `#0E7A6E`, 2px offset | everything focusable |

Focus is a ring with offset, never a colour change — a colour-only focus state is invisible
against `selected`.

---

## Type

**DEVIATION: role-named, but on our own scale.** Fluent bundles family + size + weight +
line-height into one token per role, which we adopt. Their body is 14/20; ours stays
**13.5/20** because this app is deliberately denser than an M365 productivity surface.

| Role | Size / LH | Weight | Use |
|---|---|---|---|
| `hero` | 40 / 48 mono | 500 | Day P&L. One per page |
| `figure` | 22 / 28 mono | 500 | Metric values |
| `figure-s` | 15 / 20 mono | 500 | Table cells, inline figures |
| `title` | 20 / 28 | 600 | Page title |
| `section` | 14 / 20 | 600 | Section header |
| `subtitle` | 16 / 22 | 600 | Callout headline |
| `body-strong` | 13.5 / 20 | 600 | Row titles |
| `body` | 13.5 / 20 | 400 | Alert bodies, descriptions |
| `caption` | 12 / 16 | 400 | Metadata, sublines |
| `label` | 10 / 14, `.09em`, caps | 600 | Metric and column labels |

**Weights are 400 and 600 only.** Fluent states Bold is "limited usage"; the previous
revision put **700 on every badge**, which at 10px buys nothing 600 does not. Removed.

Inter for words, DM Mono (tabular) for every number.

---

## Spacing

**Adopted from Fluent, including the "Nudge" half-steps**, which the previous revision
lacked and paid for: badge padding was `5px 7px`, chips `4px 6px`, gaps `9/11/13px` — all
off-grid, all invented per component.

`0 · 2 · 4 · 6 · 8 · 10 · 12 · 16 · 20 · 24 · 32`

`6` and `10` exist exactly so dense controls fit without leaving the grid.

**Vertical and horizontal are separate ramps** with the same values, so row rhythm can be
tuned without touching gutters.

Radius: `2` chips · `4` controls · `6` inputs · `8` wells · `12` canvas · `999` pills.
The previous `10` is gone — off-ramp.
Stroke: `1` hairline · `2` emphasis · `3` severity rail · `4` unused.

---

## Motion

**Adopted from Fluent.**

```css
--dur-fast:   150ms;   /* hover, press */
--dur-normal: 200ms;   /* expand, reveal */
--dur-gentle: 250ms;   /* panel, drawer */
--ease-enter: cubic-bezier(0, 0, 0, 1);      /* decelerate */
--ease-exit:  cubic-bezier(1, 0, 1, 1);      /* accelerate */
--ease:       cubic-bezier(0.33, 0, 0.67, 1);
```

**Things enter decelerating and leave accelerating.** Never `transition-all` — name the
properties. A blanket transition animated `background-color` through a theme switch during
this project and produced a mid-transition value that disagreed with the DOM for long enough
to send a bug hunt in the wrong direction.

Respect `prefers-reduced-motion`: durations collapse to `1ms`, nothing translates.

---

## Layout

Breakpoints — four, and deliberately not more:

| Name | Range | Sidebar | Canvas |
|---|---|---|---|
| mobile | `< 640` | bottom bar, 56px | full bleed, no radius |
| tablet | `640 – 1023` | icon rail, 64px | 16px gutter |
| laptop | `1024 – 1439` | full, 244px | 24px gutter |
| desktop | `≥ 1440` | full, 244px | **caps at 1440, centred** |

**The canvas caps at 1440 and centres.** Above that the ground shows as a wider margin on
both sides. No ultra-wide tier, no reflow into extra columns — a table stretched to 2560px
puts the symbol and its P&L two feet apart.

**DEVIATION from Fluent**, which defines six breakpoints up to `1920+` and keeps expanding.
That suits M365 apps built to fill a monitor. This one is read, not filled.

Content padding `20px 24px`. Sidebar `244px`, fixed, its own scroll.

---

## Accessibility

Beyond `stroke-strong` and focus rings:

**Live regions.** Alerts arrive over WebSocket without user action. Fluent ships an
`Announced` component for exactly this; we have no equivalent, so a screen-reader user
currently gets **nothing** when a DANGER alert fires. Specified in `20-states.html`:
`aria-live="assertive"` for danger and critical, `polite` for caution and info, announcing
title and one-line reason only.

**Hit targets** 32px minimum, 44px on mobile.
**Never colour alone** — every severity carries a dot, a text badge and, above caution, a rail.
