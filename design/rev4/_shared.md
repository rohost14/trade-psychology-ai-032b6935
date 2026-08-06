# rev 4 — rev 2 crossed with the shipping app

**New folder. `design/_recovered/rev2` and `rev3` are frozen and must not be edited;
`src/` is untouched.** This is a fresh set that takes what worked from each side.

---

## Why a mix rather than another rewrite

rev 2 drew *"these are good but you made every card component"*. rev 3 drew *"grey and
white thats it"*. The shipping app draws *"very bland basic, either everything is card
or none of it is"*.

Read together, those three notes are one note: **the craft in rev 2 was fine, the
containment logic was not, and the shipping app already gets containment roughly right
while looking thin.** So rev 4 keeps rev 2's surfaces and the app's structure, instead
of inventing a third system.

## What comes from where

| Element | rev 2 | Shipping app | rev 4 takes |
|---|---|---|---|
| Session hero | inside a card | bare, large, open | **bare** — a card around the one number the page exists for adds nothing |
| Metric row | cards nested in a card | bare figures, visually weak | **inset wells** — from neither; rev 2's inset idea at the app's inline placement |
| Alerts / positions | carded, like everything else | contained blocks | **contained** — both agreed, and both were right |
| Alert category chips | dropped | `SIZE` `PATTERN` `EMOTIONAL` | **restored** — real content rev 2 lost |
| Status tags | dropped | `DELAYED`, `2 TO JOURNAL` | **restored** |
| Border + shadow craft | proper elevation | thin, near-invisible | **rev 2** |
| Dark palette | none | the one that was called good | **shipping app** |
| Light palette | cool, no beige | warm paper | **rev 2** |

## The containment rule, stated once

**Contained:** repeating lists — alerts, positions, rules, journal entries. A block that
holds *n* of something gets a border, so the eye can see where the set begins and ends.

**Bare:** the hero, the intent line, the page title. Singular things the page is *about*.
A container around a single figure is decoration.

**Inset:** metric wells, table headers, chart tracks. Pressed *into* the surface rather
than raised off it — depth without another border.

That is three treatments on one page, which is what "half in card and half other way"
actually means.

## Tokens

Light is rev 2's ramp, with one correction: `ink-3` moves `#7C8899 → #667485`, because
`#7C8899` on white is about 4.3:1 and carries timestamp text.

| | Light | Dark |
|---|---|---|
| page | `#EEF1F5` | `#121316` |
| surface | `#FFFFFF` | `#191B1F` |
| sidebar | `#FFFFFF` | `#101114` |
| inset | `#E4E9F0` | `#212530` |
| border | `#D6DEE8` | `#2A2C32` |
| divider | `#E8EDF3` | `#1E2024` |
| ink | `#0F1724` | `#EEECE8` |
| ink-2 | `#4A5768` | `#9AA3AF` |
| ink-3 | `#667485` | `#8A929E` |
| brand | `#0E7A6E` | `#59C0B4` |
| profit | `#12795B` | `#47B88E` |
| loss | `#C2372B` | `#CF6559` |
| caution | `#A96A0C` | `#D39145` |

Dark `ink-3` is lifted from the app's `#646670`, which measures ~3.1:1 on `#191B1F` and
fails for text.

**Elevation differs by theme on purpose.** Light uses rev 2's two shadows. Dark uses
none — a shadow on a dark ground renders as nothing, so separation comes from the
surface being lighter than the page plus a `1px` border.

## Layout

Canvas caps at **1440 and centres**; above that the page ground shows as a wider margin.
Sidebar `244px`. Content padding `24px 32px`, block gap `16px`.

Both themes ship in one file — the toggle at the top right is a lab control, not part of
the design.
