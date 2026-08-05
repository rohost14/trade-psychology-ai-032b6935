# Mirror — TradeMentor design system

**Source of truth for the Claude Design project of the same name.** Files here are
authored locally, versioned, and pushed with `DesignSync`. Edit here, not on the board.

This system is **derived from the running application**, not invented alongside it.
Every token below is the value already shipping in `src/index.css`; every screen in
this set reproduces a real route with its real density and its real content. Where
the system departs from the app it is marked **CHANGE**, with the reason.

---

## The idea

TradeMentor shows a trader what they actually did. Not advice, not restriction — a
record. The product word is *mirror*.

A mirror has one design obligation: **do not flatter, do not distort**. That rules
out the two obvious directions — the terminal aesthetic that manufactures urgency,
and the consumer-fintech aesthetic that softens bad news. What is left is a screen
that states an uncomfortable number plainly and gets out of the way.

---

## Six principles

**1. Full width. Always.**
No max-width cap on any route. A trader reads this on a 27" monitor next to Kite.
Centring 1080px of content in a 2560px viewport wastes the only advantage this
product has over a phone: room to put the fact and its context on the same line.

**2. Sections and rules, not cards.**
A container earns itself by holding something separable. Alert rows, positions,
rule rows and journal entries are lists — they get hairlines and edge-to-edge
width. Cards are for the two or three things that genuinely stand apart.

**3. The number is the interface.**
Mono, tabular, and the largest thing on the screen. Every currency figure carries
its sign. Losses are coral, not crimson: serious without being an emergency.

**4. One fact per line, with its evidence attached.**
`4× your average size — 8 min after ₹2,600 loss. Win rate on oversized entries:
28% vs 60% baseline.` The claim and the proof travel together or the claim is not
credible.

**5. Colour is evidence.**
Teal is the brand and every non-money accent. Green means money gained and nothing
else. Coral means money lost and risk. Amber means caution. Four hues, four jobs.

**6. Every state is designed.**
Loading, empty, error, degraded and success are components here, not afterthoughts.
A failed request is never rendered as an empty state — that is the single most
common bug class in this codebase and the design has to make the right thing easy.

---

## Colour

Taken verbatim from `src/index.css`. Dark is the default and the one the product
was designed in; light is a full re-specification, not an inversion.

| Token | Dark | Light | Meaning |
|---|---|---|---|
| `sidebar` | `#101114` | `#F7F7F6` | Deepest / recessed nav |
| `page` | `#121316` | `#F6F5F3` | The ground |
| `surface` | `#191B1F` | `#FFFFFF` | A card that earned itself |
| `overlay` | `#232529` | `#F0EFED` | Hover rows, wells |
| `border` | `#2A2C32` | `#DCDAD6` | Card edges |
| `divider` | `#1E2024` | `#EDEBE8` | Row hairlines |
| `ink` | `#EEECE8` | `#16181D` | Headings, figures |
| `ink-2` | `#939698` | `#60646C` | Body, labels |
| `ink-3` | `#646670` | `#96969F` | Timestamps, metadata, axis |
| `brand` | `#59C0B4` | `#155B56` | Nav active, links, non-money accent |
| `profit` | `#47B88E` | `#226D4F` | Money gained. Nothing else |
| `loss` | `#CF6559` | `#AF3A31` | Money lost, danger |
| `caution` | `#D39145` | `#B16B1B` | Caution severity, warnings |

**CHANGE — the light theme flips the sidebar too.** The shipping app leaves the
sidebar at `#101114` when the rest of the page goes to paper, which reads as a
rendering fault rather than a choice. Light is specified end to end here.

**CHANGE — light drops the warm cast on text.** Ground stays `#F6F5F3` (it is
already shipping and it is fine), but ink moves to the cool `#16181D` already in
the file and metadata to a neutral grey. Warm paper plus warm ink is what makes a
light theme read as an unfinished draft.

---

## Type

| Role | Face | Where |
|---|---|---|
| UI | **Inter** | Everything that is words |
| Figures | **DM Mono** | Every number, tabular by default |

Both already ship. Scale, 7 steps:

| Step | Size / line | Use |
|---|---|---|
| `hero` | 40 / 1.0 mono | Day P&L, the one figure per page |
| `fig-l` | 26 / 1.0 mono | Card figures, tab hero |
| `fig` | 15 / 1.0 mono | Table cells, inline metrics |
| `title` | 19 / 1.25 | Page title |
| `body` | 13.5 / 1.6 | Alert bodies, descriptions |
| `sm` | 12 / 1.45 | Secondary rows, sublines |
| `label` | 10.5 / 1, `.09em`, caps | Section and metric labels |

No serif. The app is Inter + DM Mono today and a system whose adoption starts with
a font swap is a system that does not get adopted.

---

## Scale

4px base: `4 · 8 · 12 · 16 · 20 · 24 · 32 · 48`.
Radii: `3` chips · `6` inputs and buttons · `8` cards · `999` pills.
Page padding `24px 32px`. Sidebar `244px`. Row height, list: `56–72px` natural.

---

## Severity

Four levels, one vocabulary, used identically on every surface.

| Level | Dot | Text badge | Left rail |
|---|---|---|---|
| `critical` | loss | `CRITICAL` on solid loss | 3px loss |
| `danger` | loss | `DANGER` loss on transparent | 3px loss |
| `caution` | caution | `CAUTION` amber | none |
| `info` | brand | `INFO` teal | none |

**CHANGE — the left rail is a rule, not a one-off.** The shipping Dashboard puts a
coral rail on the first alert only, which reads as "newest" rather than "worst".
Here the rail means danger or worse, everywhere, or it means nothing.
