# Mirror — TradeMentor design system (light)

**Source of truth for the Claude Design project of the same name.** Files here are
authored locally, versioned, and pushed with `DesignSync`. Edit here, not on the board.

Derived from the running application — every screen reproduces a real route with its
real content and density. Where the system departs from the shipping code it is
marked **CHANGE**, with the reason.

---

## What changed in this revision

The previous pass was dark-first with a warm-paper light theme, and it had two faults
the moment it was viewed in light:

**1. Beige.** Warm paper (`#F6F5F3`) reads as stationery, not as a trading tool. The
whole neutral ramp is now **cool** — a blue-grey page under near-black-blue ink. No
warm greys anywhere in the file.

**2. Everything blended into the background.** The old rule was "sections and rules,
not cards", which on a dark ground worked and on a light ground produced a flat sheet
where the page and its content were the same colour. **That rule is reversed here.**

---

## Depth is the point

Three levels, and the gap between them is deliberately wider than the shipping app's.

| Level | Token | Value | What sits here |
|---|---|---|---|
| 0 · ground | `page` | `#EEF1F5` | The page. Never holds content directly |
| 1 · surface | `surface` | `#FFFFFF` | Cards. Border **and** shadow, always both |
| 2 · inset | `inset` | `#E4E9F0` | Wells, table headers, chart tracks, inputs |

**Level 0 to level 1 is a 12-point luminance step**, plus a `1px #D6DEE8` border, plus
`--sh-1`. The shipping app steps `#F6F5F3` to `#FFFFFF` — four points, no shadow — which
is why its cards vanish into the page. Three signals, not one, because any single one
of them is invisible to someone on a dim laptop panel at an angle.

```
--sh-1: 0 1px 2px rgba(15,23,36,.05), 0 1px 3px rgba(15,23,36,.06);   /* cards */
--sh-2: 0 2px 4px rgba(15,23,36,.04), 0 8px 20px rgba(15,23,36,.08);  /* hero, popovers */
```

Shadows are **blue-black** (`rgba(15,23,36,…)`), never neutral black. A grey shadow on a
cool page turns the edge muddy.

---

## Cards and hairlines — the actual rule

Both, at different scales. This is the correction to the previous pass, which used one
and not the other.

**A card wraps a subject.** "Open positions" is one card. "What we caught today" is one
card. The card is what tells you where one idea stops and the next begins, and on a
light ground it is the only thing that does.

**Hairlines divide repetition inside a card.** Rows of positions, alerts, rules and days
are separated by `1px #E8EDF3` — never by nested cards, never by gaps. A card per alert
row is the failure the previous pass was reacting against; the fix is one card holding
hairline-separated rows, not no card at all.

**A card header is `#FFFFFF` with a `--divider` bottom rule**, not a filled bar. Filled
headers add a fourth surface colour and buy nothing.

So: **page → card → hairline rows.** If you find yourself putting a card inside a card,
the inner one should be a hairline group or an inset well.

---

## Colour

Cool neutrals. No warm grey, no beige, no cream.

| Token | Value | Meaning |
|---|---|---|
| `page` | `#EEF1F5` | Ground |
| `surface` | `#FFFFFF` | Cards |
| `inset` | `#E4E9F0` | Wells, table headers, chart tracks |
| `sidebar` | `#FFFFFF` | Nav rail, with a `--border` right edge |
| `border` | `#D6DEE8` | Card edges |
| `divider` | `#E8EDF3` | Row hairlines |
| `ink` | `#0F1724` | Headings, figures |
| `ink-2` | `#4A5768` | Body |
| `ink-3` | `#7C8899` | Timestamps, labels, axis |
| `brand` | `#0E7A6E` | Active nav, links, anything not money |
| `profit` | `#12795B` | Money gained. Nothing else |
| `loss` | `#C2372B` | Money lost, danger |
| `caution` | `#A96A0C` | Caution severity |

Tints for badges and rails, each the hue at ~8% over white:
`brand-t #E2F2EF` · `profit-t #E3F3EE` · `loss-t #FBE9E7` · `caution-t #FBF0DF`.

**Green means money and only money.** Brand teal and profit green sit close in hue, so
the separation is enforced by rule: the moment teal also means "up", a trader can no
longer find their P&L by colour on a page carrying nine teal links.

---

## Type

Inter for words, DM Mono (tabular) for every number. Both already ship.

| Step | Size / line | Use |
|---|---|---|
| `hero` | 40 / 1.0 mono | Day P&L — one per page |
| `fig-l` | 26 / 1.0 mono | Card figures |
| `fig` | 15 / 1.0 mono | Table cells, inline metrics |
| `title` | 19 / 1.25 | Page title |
| `card` | 14 / 1.2 · 600 | Card header |
| `body` | 13.5 / 1.6 | Alert bodies, descriptions |
| `sm` | 12 / 1.45 | Sublines |
| `label` | 10.5 / 1 · `.09em` caps | Metric labels |

---

## Scale

4px base: `4 · 8 · 12 · 16 · 20 · 24 · 32 · 48`.
Radii: `4` chips · `6` inputs, buttons · `10` cards · `999` pills.
Page padding `24px 32px`. Sidebar `244px`. Card padding `18px 20px`.
**Card gap `16px`** — enough for the shadow to read, not so much the page falls apart.

Still **no max-width cap**. Full width, every route.

---

## Severity

| Level | Dot | Badge | Left rail |
|---|---|---|---|
| `critical` | loss | `CRITICAL`, solid loss, white text | 3px loss |
| `danger` | loss | `DANGER` on `loss-t` | 3px loss |
| `caution` | caution | `CAUTION` on `caution-t` | none |
| `info` | brand | `INFO` on `brand-t` | none |

**CHANGE — the rail is a rule, not an accent.** The shipping Dashboard draws it on the
first alert only, which reads as "newest" rather than "worst". Here it means
danger-or-worse everywhere, or it is not drawn.
