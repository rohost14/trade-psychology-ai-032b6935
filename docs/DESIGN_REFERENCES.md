# Reference specs — real numbers from products we respect

Research pass, 2026-07-30. Values marked **[S]** were mined from production CSS bundles or published design systems; **[I]** are inferred. Companion to `DESIGN_SYSTEM.md` (what we build) and `AI_SLOP_TELLS.md` (what we avoid).

**Framing correction that drove this:** TradeMentor is **not a trading terminal**. Nobody places an order here. It sits beside Kite — the trader executes there and comes here to understand their patterns. Bloomberg-style density is the wrong target. Everything below is about being *calm and credible*, not dense.

---

## 1. Zerodha Kite — the table spec, verified

Mined from `kite.zerodha.com/static/css/async/main.58fd101f.css`. **[S]**

```css
body        { font-family:"Open Sans"; font-size:14px; line-height:1.6; color:#444; background:#f8f8f8 }

table       { border-top:1px solid #f1f1f1; width:100% }
thead th    { padding:12px; font-weight:400; color:#9b9b9b; border-bottom:1px solid #f1f1f1 }
tbody td    { padding:10px 12px; border-bottom:1px solid #f1f1f1 }
th, td      { white-space:nowrap; font-variant-numeric:tabular-nums }
tr:hover td { background:#f8f8f8 }
td.pnl      { background:#f8f8f8 }   /* permanent vertical tint band on the P&L column */
```

Three things worth copying verbatim:

1. **`10px 12px` cell padding** — the real production value. Derived row height ≈ 43px desktop, ≈ 39px below 1366px. Kite never declares an explicit height. **[S/I]**
2. **`tabular-nums` on every cell.** TradingView does the same via `font-feature-settings:"tnum","lnum"`. **[S]**
3. **The P&L *column* gets a permanent background band — Kite uses no zebra striping anywhere.** For a calm aesthetic this is the better borrow: it separates the region that matters instead of decorating every row. **[S]**

**Mobile degradation ladder [S]:** cell padding `12px → 8px 4px` · `.data-table` font → 14px · status chips collapse to first letter at `0.6rem` via `:first-letter` + `font-size:0` · `overflow-x:auto` on the wrapper.

**Kite's colour, and the one rule that matters most [S]:**

| Role | Light | Dark |
|---|---|---|
| Profit | `#4caf50` | `#5b9a5d` |
| Loss | `#ff5722` | `#e25f5b` |
| Text primary / muted / disabled | `#444` / `#9b9b9b` / `#ccc` | `#bbb` / `#666` / `#616161` |

> **Kite desaturates its P&L colours in dark mode.** Saturated green and red on a dark surface is the single most common way a calm app starts looking like a casino.

Radius vocabulary is tiny: **2px chips, 3px inputs, 4px, 10px tooltips. Nothing rounder.** Layout: fixed **425px** left rail, wrapper capped 1366→1920, header 44px.

### Why Kite is praised — the doctrine [S, primary]

Kailash Nadh, [*User disengagement*](https://zerodha.tech/blog/user-disengagement/): engagement is *"a thinly veiled proxy for user entrapment."* In practice — no ads, **no engagement tracking at all**, push notifications never used for re-engagement, a nudge system that discourages risky trades at revenue cost, frictionless account closure.

That is our charter almost word for word. **A behavioural mirror that optimises for time-on-screen is self-refuting.**

---

## 2. The calm reference set — convergent rules

Mined from Linear, Stripe, Monzo, Mercury, Groww, Tickertape, Maybe. **[S]**

**Typography**
- **Monzo's leading rule:** `line-height = font-size + 6px` at every step. Simplest defensible system found.
- **Line-height falls as size rises.** Stripe 1.25 at 18px → 1.03 at 48px. Linear 1.6 at 15px → 1.0 at 48px.
- **Negative tracking on large type** — Stripe −0.01 to −0.02em.
- **Linear's weights are 300 / 400 / 510 / 590 / 680**, not 500/600/700. `590` reads as "semibold that isn't shouting."
- **Stripe sets every heading to `font-weight: 300`.** The whole restraint trick in one declaration.

**Region separation — the strongest finding**
- Linear uses **only 4 background levels** plus a `0.5px` hairline. Region shifts are ~4 luminance points.
- **None of them use border *and* shadow *and* fill together.** Pick one boundary mechanism per nesting level.
- **Text tiers cap at four** everywhere. Linear: `#282a30 / #3c4149 / #6f6e77 / #86848d`.
- **Neutrals are tinted, never pure.** Maybe's black is `#0B0B0B`, not `#000`.

**Spacing** — universal agreement on a **4px grid** with 2px for chip internals. Carbon and Tickertape converge exactly: `2 4 8 12 16 24 32 40 48 64 80 96`.

**Mercury's responsive gap tokens** are the pattern for mobile-first — the *token* changes at breakpoint, not the component: `--gap-section: 24px → 32px`, `--gap-card: 16px → 24px`, `--gap-item: 8px → 12px`.

**P&L colour across the set**

| Product | Up | Down |
|---|---|---|
| Kite | `#4caf50` | `#ff5722` |
| Groww | `#04b488` | `#ed5533` |
| Tickertape | `#19af55` | `#d82f44` |
| Stripe | `#00b261` | `#f3432a` |
| Mercury | `#188554` | `#d03275` (magenta, deliberately not red) |

Two takeaways: **Indian platforms all use an orange-leaning red**, not fire-engine red. And **every calm system ships a low-alpha tint of the same hue** for backgrounds (Tickertape 11%, Maybe 5%/10%) — you never fill a region with the full-strength semantic colour.

**Radius for data UI: 4px chips/inputs, 6–8px cards, nothing above 12px.**

---

## 3. Reflection products — our actual category

The most valuable section, because we had no reference for it.

### Oura's three-tier model [S — Instrument case study, with shipped metrics]

1. **At-a-glance** — daily insight, no reading required
2. **Focused** — enough for short-term patterns, deliberately not exhaustive
3. **Exploratory** — interactive long-term trends

Today tab is a "single source of truth" built around **one big thing**. Post-launch: **D5 stickiness 80% (+1pt), Today-tab CTR 42% (+7pts).** Rare case of a calm redesign with published numbers.

### WHOOP [S]

- Home = **exactly three numbers**: Recovery %, Strain, Sleep. Answers one question: *"how should I train today?"*
- **Strict three-colour vocabulary**, identical on every screen, nothing to relearn
- Hero score at **~72pt equivalent**; everything else small
- Progressive disclosure across **three separate screens, not collapsed sections** — "clean mental boundaries"
- Feels simple through **compression**: many signals collapse into one score

### What makes it insightful rather than judgemental [S]

| Finding | Source |
|---|---|
| *"More data without context or guidance often produces anxiety, not action — users would wake up to a low readiness score and feel worse about a day that hadn't even started."* | Oura redesign rationale |
| Exist.io's failure mode: *"correlations are offered without context — patterns surface, but you don't get a plain-language read or a concrete action to try."* | Correla comparison |
| Whoop reads as *"a demanding coach constantly analysing your output"*; Oura as *"a wellness consultant suggesting a balanced lifestyle."* | Oura/Whoop comparisons |

**Rules this yields for us:**

1. A detected pattern ships as **plain-language sentence + the number + one concrete action.** A correlation alone is the documented failure state.
2. **One hero insight per screen**, sized large. Everything else supports it.
3. **Three tiers on three screens**, not accordions on one.
4. **A fixed semantic colour vocabulary reused identically** across Dashboard, Alerts and My Patterns — meanings must not shift between screens.
5. Zero manual input is **validated** by Daylio's evidence: capture friction is what kills these products.
6. State the rupee number, state the behaviour, **do not editorialise.**

---

## 4. Dashboard composition

**Research base [S]:** *Dashboard Design Patterns*, Bach et al., IEEE VIS 2022 — 144 dashboards, 8 pattern groups, three genres. Ours is analytical-embedded. [arxiv.org/abs/2205.00757](https://arxiv.org/abs/2205.00757)

**NN/g on data tables [S]:** freeze header rows and the leftmost column · default column order reflects importance · related columns adjacent · **first column must be a human-readable identifier, not a generated ID** · signal horizontal overflow with **arrows or cut-off elements, never dots** — users overlook dots.

**How the references use horizontal space without a card grid [S]**

| Product | Pattern |
|---|---|
| Kite | Fixed **425px** persistent left rail (standing context) + fluid right region |
| Oura | One hero + supporting tiles, then **drill to a new screen** — never widens into a grid |
| Linear | Content capped at **1024px**; extra width becomes margin, not more cards |

**For our sparse four-block column [I]:** one full-width hero band carrying the single most important behavioural fact, then an asymmetric split beneath — roughly 62/38, or a fixed ~380–425px context rail à la Kite. Cap around 1280px; beyond that add margin, not columns.

> **Four equal cards stacked is the sparse-feeling failure. Four *unequal* regions with one dominant is not.**

---

## 5. Mobile-first, data-heavy

**Hard floors [S]**

| Spec | Value |
|---|---|
| WCAG 2.5.8 Target Size (Minimum), **AA** | **24 × 24 CSS px** |
| WCAG 2.5.5 (Enhanced), AAA | 44 × 44 |
| Apple HIG | 44 × 44 pt |
| Material | 48 × 48 dp + ≥8 dp spacing |

**A tappable row must be ≥44px on mobile.** A read-only row may go to 32–36px.

**Published row ladders [S]:** Carbon `xs 24 · sm 32 · md 40 · lg 48 · xl 64` · Pencil&Paper `40/48/56` · TradingView screener `48` · shadcn `~36–40` · Kite `~43` derived.

**NN/g Mobile Tables [S]:** sticky headers past one screen · freeze leftmost column whenever horizontal scroll exists · horizontal scroll is "nasty" but "somewhat acceptable for large tables" · rotation is "a last resort" · **complex/wordy entries → only 2 columns fit legibly**; number-heavy → 11 numeric columns fit without scrolling using abbreviations.

**Mobile table decision tree [S]**
```
≤3 columns                       → plain table, 48px rows
4–6 columns, all numeric         → freeze first column + horizontal scroll,
                                   signal with cut-off/arrow, never dots
>6 columns, or any wordy column  → collapse to card-per-row
comparison not required          → let the user pick the dataset first
rotation                         → last resort, never a requirement
```

**Zebra striping — the only controlled experiment with numbers [S].** Enders, A List Apart: 2,276 clean sessions, 15s per question under time pressure → significant accuracy gain on **3 of 8** questions, rest indistinguishable from noise; 1,200+ adults preferred single-colour single-row striping (31% "helps most" vs 4% "helps least"). Safe default, but **Kite ships none and tints the P&L column instead — the better borrow for a calm product.**

---

## 6. What this changes for us

| Finding | Our position | Action |
|---|---|---|
| Cards 6–8px radius, nothing above 12px | We use 10px, plus 136 stray `rounded-xl` and 18 `rounded-2xl` | Radius consolidation already logged in `DESIGN_MIGRATION.md`; consider 8px not 10px |
| Desaturate P&L in dark mode | Already done — `#47B88E` / `#CF6559` are desaturated | Hold; verify no saturated variants creep in |
| Orange-leaning red is the Indian convention | Ours is `#CF6559` / `#AF3A31` — brick, already orange-leaning | Correct by accident; now deliberate |
| 10% same-hue tint, never full-strength fills | We use `/10` fills and `/20` borders | Matches |
| Never border + shadow + fill together | Cards are fill + border, no shadow | Matches |
| Text tiers cap at 4 | We have primary / secondary / tertiary | Matches |
| Tabular numerals everywhere | Done | Matches |
| Tappable row ≥44px mobile | Our dense rows are 14px padding ≈ 40px | **Raise on mobile** |
| One hero insight per screen | Dashboard has a hero number but no hero *insight* | **The real gap** |
| Pattern = sentence + number + action | We ship sentence + number, no action | **The real gap** |

The last two are the same finding from two directions, and they match the deepest tell in `AI_SLOP_TELLS.md`: **our dashboard describes rather than decides.** Every reference product that succeeds at behaviour change leads with one insight and names one action.

---

## Sources

[zerodha.tech — User disengagement](https://zerodha.tech/blog/user-disengagement/) · [Dashboard Design Patterns, Bach et al.](https://arxiv.org/abs/2205.00757) · [NN/g — data tables](https://www.nngroup.com/articles/data-tables/) · [NN/g — mobile tables](https://www.nngroup.com/articles/mobile-tables/) · [A List Apart — zebra striping study](https://alistapart.com/article/zebrastripingmoredataforthecase/) · [IBM Carbon — data table](https://carbondesignsystem.com/components/data-table/style/) · [WCAG 2.5.8 Target Size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) · production CSS bundles: Kite, Linear, Stripe, Monzo, Mercury, Groww, Tickertape, Maybe
