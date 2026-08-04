# Evidence — design system

**Source of truth for the Claude Design project of the same name.** Files here are
authored locally, versioned, and pushed with `DesignSync`. Editing the remote board
by hand will be overwritten; edit here.

---

## The idea

TradeMentor shows a trader what they actually did. Not advice, not restriction — a
record. The product word for it is *mirror*. The design word is **evidence**.

That single idea decides everything else, because it rules out both of the obvious
directions:

**Not a trading terminal.** Dark, dense, red-and-green flashing. That aesthetic
exists to create urgency, and urgency is the thing this product is trying to
reduce. An interface that raises your heart rate cannot credibly tell you that you
trade badly when your heart rate is up.

**Not consumer fintech.** Rounded, pastel, encouraging. That aesthetic softens bad
news, and softening bad news is exactly the failure mode here. A trader who lost
₹45,000 to tilt should not be handed it in a friendly bubble.

**What is left is the middle: a written record.** An equity research note. A medical
report. Something that states an uncomfortable fact plainly, in a form that reads
as considered rather than reactive. Calm, but not comforting.

---

## Five principles

**1. The number is the interface.**
Everything else is scaffolding for figures. The type scale is built around tabular
numerals, and the largest thing on any screen is a number or a verdict.

**2. Calm under bad news.**
Losses are legible, never alarming. No red floods, no shouting, no shake
animations. Oxblood rather than crimson is a deliberate choice: it reads serious
without reading emergency.

**3. Structure from rules, not boxes.**
Hairlines and whitespace carry hierarchy. A container has to earn itself by holding
something genuinely separable — see *Cards & sections*.

**4. Colour is evidence, not decoration.**
Three hues, one job each: money up, money down, and one accent for everything that
is not money. Nothing is coloured because it looked flat.

**5. Every state is designed.**
Loading, empty, error and success are specified here as first-class components.
They are where products actually feel unfinished, and they are always the ones
left out of a design.

---

## Typography

| Role | Face | Why |
|---|---|---|
| Display | **Source Serif 4** | The report voice. Used for verdicts and page titles only — a serif at 40px says "considered", which is the whole positioning |
| UI | **Inter** | Neutral, dense, excellent at 12–14px where most of the interface lives |
| Figures | **DM Mono** | Tabular by default, so columns of money align without tricks |

Two of the three are already in the app. That is deliberate: a design system whose
adoption starts with three font swaps is a design system that does not get adopted.

---

## Colour

The ground is **warm paper**, not off-white grey. That single change is what makes
the system read as a written record rather than a default web application — and it
is what oxblood and forest green were chosen against.

**Three ground levels, not two.** A grey page and a white card is the arrangement
every web app already has, and it is why a two-level system reads as basic no
matter how good the type is. The third level lets a table header or an inset well
recede without needing a border to say so.

| Token | Light | Dark | Meaning |
|---|---|---|---|
| `inset` | `#EEEAE1` | `#16161C` | Wells, table headers, anything pressed in |
| `paper` | `#F6F3ED` | `#1B1B22` | The ground |
| `raised` | `#FFFDFA` | `#24242E` | A surface that has earned separation |
| `ink` | `#1A1815` | `#F2F0EA` | Headings, primary text. Warm near-black |
| `ink-2` | `#4E4A44` | `#B9B5AC` | Body |
| `ink-3` | `#8A857C` | `#8A857C` | Labels, secondary |
| `ink-4` | `#BAB4A8` | `#5E5A54` | Disabled, axis ticks, timestamps |
| `rule` | `#E2DCD0` | `#33333F` | Hairlines |
| `accent` | `#2E4A7D` | `#8AA4DC` | Everything that is not money |
| `up` | `#1A7F5A` | `#3FBF8C` | Money gained. Nothing else |
| `down` | `#A32A3C` | `#E5697C` | Money lost, and risk |

**Green means money and only money.** The moment it also means "connected" or
"fine", a trader can no longer find their P&L by colour alone.

**Dark is specified, not inverted.** The ground sits at `#1B1B22` rather than
near-black — a true void gives the eye no surface to rest against and every card
starts to glow. Both money colours are lifted and desaturated. Anything solid in
`accent` or `down` takes **dark text**: white on `#E5697C` fails contrast.

---

## Scale

4px base. Spacing steps: `4 · 8 · 12 · 16 · 24 · 32 · 48 · 64`.
Radii: `2` (chips) · `4` (inputs, buttons) · `8` (cards) · `999` (pills).

Small radii on purpose. Large radii read friendly; this system is not trying to be
friendly, it is trying to be trusted.
