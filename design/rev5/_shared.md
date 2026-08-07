# rev 5 — character, subtle colour, researched type

**New folder.** `design/rev4`, `design/_recovered/rev2`, `rev3` and `src/` are all
untouched.

rev 4 was structurally right and visually dead: grey and white with colour only on the
money. The note was *"white and grey not good at all, something better subtle and not as
plain — our original or maybe in demo looks still better."*

So rev 5 goes back to **`demo_images/`** — the reference that drew *"it has good
personality"* — and brings its character to the desktop app, at a subtlety the demo
itself doesn't have to worry about because it was a phone mockup.

---

## Where the character actually came from

Looking at the demo screens again, the personality is five devices, not a colour:

1. **Pastel tinted circular icon badges** — amber circle with `!`, indigo circle with a
   sparkle, rose circle with a warning. This is the single biggest one.
2. **Pill badges** — `Risk Guardian Active` on mint, `HIGH SEVERITY` on rose, `+12.4%`
   on mint. Rounded, tinted, never outlined.
3. **A gradient used once** — the mint "State: Secure" card, and a violet→coral gradient
   edge on the coach insight. Once per screen, never as wallpaper.
4. **Soft diffuse shadow** — `0 4px 24px rgba(31,35,51,.06)`. Wide and faint, nothing
   like a hard two-layer elevation ramp.
5. **Indigo accent**, not teal and not blue-grey.

## Colour — subtle, and not grey

The correction to rev 4 is that **the neutrals themselves carry a hue**. rev 4's ground
was `#EEF1F5`, a true cool grey; every surface under it read as absence of colour. Here
the whole neutral ramp is tinted a few degrees toward the indigo accent, so the page
reads as *quiet*, not *empty*.

| | Light | Dark |
|---|---|---|
| ground | `#F4F4FA` | `#131320` |
| surface | `#FFFFFF` | `#1C1C2C` |
| raised | `#FFFFFF` | `#222234` |
| inset | `#F0F0F8` | `#191926` |
| line | `#E7E7F1` | `#2C2C40` |
| ink | `#1B1B2E` | `#ECECF4` |
| body | `#55566B` | `#A5A6BC` |
| muted | `#82849C` | `#8688A0` |

Ink is `#1B1B2E`, not `#000` and not a neutral grey — a violet-black. On a tinted ground
that difference is most of the "character" people can't name.

**Three hues, one job each** — carried over from the Soft Precision study, and the rule
that made it work:

| | Light | Tint | Dark | Job |
|---|---|---|---|---|
| accent | `#4A46D6` | `#ECEBFB` | `#8B87F5` | Everything that is not money |
| up | `#0F9D76` | `#E4F3EE` | `#35C79B` | Money gained. Nothing else |
| down | `#D42F4E` | `#FBE8EC` | `#F2637E` | Money lost, and risk |

Severity is three **strengths of down**, not a fourth hue. Amber is gone: it only ever
existed to sit between red and grey, and a lighter red does that without adding a colour.

## Typography — the researched part

Sources: [Datawrapper on fonts for data visualisation](https://www.datawrapper.de/blog/fonts-for-data-visualization),
[fonts for dense dashboards](https://fontalternatives.com/blog/best-fonts-dense-dashboards/),
[fintech typefaces](https://fontalternatives.com/best-fonts-for/fintech/).

What the research settles:

- **Tabular lining figures are mandatory** in money columns. Equal-width digits so
  decimals stack; misaligned figures actively undermine trust in the number.
- **Tall x-height is what makes a face survive 11–13px**, which is the measurable reason
  Inter reads where others don't.
- **Bold for emphasis only.** Regular and medium carry body text; bold everywhere flattens
  hierarchy rather than creating it.
- **No thin weights** — they read as a lighter colour, not a lighter weight.
- **Glyph differentiation** (`0/O`, `1/l/I`) matters wherever a misread digit costs money.

**The conclusion, and why the demo's font does not survive it.** The demo uses **Poppins**.
It is the right instinct for character — geometric, warm, contemporary — and the wrong
face for this product: geometric-round means a circular `O` barely distinct from `0`, it
runs wide so tables need more width for the same data, and none of the sources above
recommend it for dense figures.

So: **pair, rather than compromise.**

| Role | Face | Why |
|---|---|---|
| Everything text | **Plus Jakarta Sans** | The same geometric warmth as Poppins, drawn for interfaces — taller x-height, tighter widths, holds at 12px where Poppins softens |
| Money figures only | **IBM Plex Mono** | Built where data accuracy matters. Unmistakable `0` and `1`, and monospacing makes column alignment structural rather than a font-feature toggle |

Mono is confined to **money**. Not timestamps, not counts, not quantities — the moment
everything numeric is mono, nothing reads as the figure that matters.

| Step | Size / line | Weight | Face |
|---|---|---|---|
| hero | 40 / 44 | 700 | Mono |
| display | 28 / 34 | 700 | Jakarta |
| figure | 20 / 26 | 600 | Mono |
| title | 16 / 22 | 600 | Jakarta |
| section | 14 / 20 | 600 | Jakarta |
| body | 13.5 / 20 | 400 | Jakarta |
| small | 12.5 / 18 | 400 | Jakarta |
| label | 11 / 14, `.06em`, caps | 600 | Jakarta |

Weights are **400 / 600 / 700**. Nothing thinner than 400, and 700 only on the two
largest steps.

## Shape and depth

Radius `12` on cards, `10` on wells, `8` on controls, `999` on pills and icon badges.
Softer than rev 4's 10, far short of the demo's 20 — that was a phone.

One shadow, wide and faint: `0 4px 20px rgba(27,27,46,.06)`. Dark gets none; a shadow on
a dark ground renders as nothing, so separation there is a lighter surface plus a hairline.

**One gradient per screen, on the session state card only**, tinted by whether the day is
up or down. It is the demo's single most characterful move and the only place the palette
is allowed to be loud.
