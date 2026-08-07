# rev 6 — rev 5 with the gimmicks removed, Sensibull's discipline applied

**New folder.** `design/rev5`, `rev4`, `design/_recovered/*` and `src/` untouched.

rev 5 drew *"looks good but now became very gimmicky, especially the live alerts —
glowing icons emojis, it's all gimmicky and looks vibe coded."* Correct. The character
devices lifted from a **phone mockup** don't survive on a dense desktop tool: a 38px
pastel circle beside every alert is decoration in a product whose entire claim is that it
only shows facts.

So rev 6 keeps what rev 5 got right — the tinted neutral ramp, the palette, the
researched type pairing — and replaces every decorative device with something from
**Sensibull**, which was named as the reference and is the most disciplined data UI in
this market.

---

## What Sensibull actually does

Observed directly on the live product (FII/DII Data and Option Chain, 2026-08-08):

**1. Zero icons inside rows.** Not one. No circles, no badges, no emoji. Icons appear only
in navigation and as a small ⓘ affordance beside a column header that needs explaining.

**2. In-cell magnitude bars.** A pale tinted bar sits behind or beside a number and encodes
its size. The Option Chain's OI columns and the FII/DII "Strong Bullish / Medium Bearish"
pills both do this — **the label and the quantity are the same element.** This is their
signature device and the one worth taking outright.

**3. Very pale tinted backgrounds to group meaning.** Calls side faintly rose, puts side
faintly mint, ITM strikes faintly cream. Tint carries semantics; it is never a mood.

**4. Blue for interactivity, and only that.** Links, active tab underline, buttons,
checkboxes, toggles. Red and green never touch chrome — they are reserved entirely for
market direction.

**5. No shadows, no gradients, no rounded-everything.** Flat white surfaces, 1px grey
hairlines, ~4–6px radius. Depth is not simulated at all.

**6. Density is the point.** Option Chain rows run ~24px. The interface assumes a user who
wants more on screen, not more air around it.

---

## What changed from rev 5

| | rev 5 | rev 6 |
|---|---|---|
| Alert rows | 38px pastel circular icon badge | **no icon.** Severity rail + text pill |
| Session card | gradient tinted by the day | **flat band**, no gradient anywhere |
| Metric tiles | icon circle per tile | label + figure, and a **magnitude bar** where the number has a ceiling |
| Loss budget | a figure in a box | **in-cell bar** — Sensibull's device, and the one metric that genuinely has a maximum |
| Row height | 15px padding, airy | tightened to Sensibull-ish density |
| Radius | 12–16px | 6–8px |
| Shadow | soft wide shadow on every card | **none**, light or dark |
| Severity | pastel badge + pill | pill only, three strengths of one hue |

**Kept from rev 5**, because none of it was the problem:

- The tinted neutral ramp — ground `#F4F4FA`, ink `#1B1B2E` violet-black, not grey
- Three hues one job: accent `#4A46D6`, up `#0F9D76`, down `#D42F4E`
- **Plus Jakarta Sans** for text, **IBM Plex Mono for money figures only**
- Both themes in one file

## The one device taken outright

**The magnitude bar.** Loss budget is the only metric on the Dashboard with a real ceiling
— ₹16.1k of ₹25k — so it is the only one that gets a bar. Everything else is a figure.
That restraint is what makes the bar mean something when it appears; a progress bar under
every metric would be exactly the decoration this revision is removing.

## Where I deliberately did not follow Sensibull

**Their density is for an options terminal.** Option Chain rows at ~24px suit a screen the
user scans for a strike. Our alert rows carry a sentence of reasoning that has to be *read*,
so they stay taller. Density was tightened, not matched.

**They have no dark theme on the public tools.** Ours is kept, built the same way as rev 5 —
no shadows, separation from a lighter surface plus a hairline.
