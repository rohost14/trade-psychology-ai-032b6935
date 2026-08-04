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

Light is the primary theme; dark is specified rather than derived, because a
straight inversion makes oxblood muddy and forest green disappear.

| Token | Light | Dark | Meaning |
|---|---|---|---|
| `paper` | `#FAF9F7` | `#131317` | The ground. Warm off-white, never pure |
| `raised` | `#FFFFFF` | `#1B1B21` | A surface that has earned separation |
| `ink` | `#17171A` | `#F2F1EE` | Primary text, headings |
| `ink-2` | `#4A4A52` | `#B4B4BC` | Body |
| `ink-3` | `#85858F` | `#7C7C87` | Labels, secondary |
| `ink-4` | `#B8B8C0` | `#5A5A64` | Disabled, axis ticks |
| `rule` | `#E5E3DE` | `#2A2A32` | Hairlines. Warm in light, cool in dark |
| `accent` | `#2E4A7D` | `#7C97D4` | Everything that is not money |
| `up` | `#1A7F5A` | `#3FBF8C` | Money gained. Nothing else |
| `down` | `#A32A3C` | `#E5697C` | Money lost, and risk |

**Green means money and only money.** The moment it also means "connected" or
"fine", a trader can no longer find their P&L by colour alone.

---

## Scale

4px base. Spacing steps: `4 · 8 · 12 · 16 · 24 · 32 · 48 · 64`.
Radii: `2` (chips) · `4` (inputs, buttons) · `8` (cards) · `999` (pills).

Small radii on purpose. Large radii read friendly; this system is not trying to be
friendly, it is trying to be trusted.
