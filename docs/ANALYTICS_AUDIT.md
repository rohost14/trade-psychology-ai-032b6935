# Analytics — production-readiness audit

Audited 2026-08-01 against `docs/DESIGN_SYSTEM.md`, in the browser (guest mode, all five tabs) and in code. **Findings only — no code changed.**

Scope: `src/pages/Analytics.tsx` + the 15 live components in `src/components/analytics/`.

---

## Verdict

Analytics is the least production-ready screen in the app, and the gap is not primarily cosmetic. There are **five defects that make the page factually wrong or visibly broken**, and they matter more than any amount of restyling: a page whose charts render empty and whose copy prints `You have .` does not read as a product that can be trusted with money.

Underneath that, the screen is **entirely on the retired v1 design system** — 119 `tm-card`, 209 raw palette classes, 71 hex literals, 389 rem-scale type classes. The Dashboard reskin has not been applied here at all, so the two screens currently look like two different products.

Fix order should be **P0 → P2 → P1**: correctness first, then the structural hierarchy problems, then the token sweep. The token sweep is the largest volume of edits but the lowest risk, and doing it first would mean re-doing it after the structural changes move things around.

---

## P0 — Broken. Fix before anything visual.

| # | Finding | Evidence |
|---|---|---|
| ~~**P0-1**~~ | ~~Two charts on Edge render completely empty.~~ **RETRACTED 2026-08-01 — not a bug.** See "Retracted" below. | — |
| **P0-2** | **Habits prints a broken sentence:** `You have . Import your Console tradebook (Settings → or the banner on Dashboard) to see them straight away.` `{data.sample}` resolves empty, and the parenthetical is malformed — the arrow points at nothing. | `HabitsTab.tsx:92` |
| **P0-3** | **Habits gate contradicts the page.** Habits says *"unlock after 5 completed trades"* while the KPI strip on Overview reports **15 trades** for the same period. Two components disagree about the same fact on one screen. | `HabitsTab.tsx` vs `OverviewTab.tsx` |
| **P0-4** | **"Worst 5 Trades" renders 4 rows.** The heading is a hardcoded string; the list is `.slice(0, 5)` over whatever exists. Any short list makes the heading a false statement. Same pattern in "Best 5 Trades". | `TradeDnaTab.tsx:153,158,219,250` |
| **P0-5** | **The 3-month calendar ignores the period selector.** It builds its own three months regardless of 7D/30D/90D, so changing the period visibly does nothing to it. Two of the three months render entirely empty. | `SessionsTab.tsx:81–100` |

### Retracted: P0-1

**P0-1 was a measurement error, not a defect.** On a clean load, all three Edge charts render their bars correctly.

What happened: recharts animates bars from zero height on mount, over roughly 1.5s. The screenshot was taken immediately after clicking the Edge tab, catching every bar at zero height. The captions underneath are plain text, so they painted instantly — which produced the convincing but false impression of "data present, series missing."

Two follow-on errors made it worse rather than catching it:

- DOM probing looked at `.recharts-bar-rectangle`, which is an empty `<g>` **even on charts that render correctly** — Overview's working Daily P&L reports zero shapes by the same selector. That reading was worthless in both directions and should have been discarded, not built on.
- Dispatching a synthetic `window.resize` to "test re-layout" mutated the page state mid-diagnosis, so later readings described a page the user would never see.

Worth keeping as a lesson: a first screenshot after a tab switch is not evidence about animated content, and a selector that reports "broken" for a component you can see working is a broken selector, not a broken component. The claimed smoke-test gap ("never asserts a series drew") was downstream of this error and is also withdrawn.

**The remaining four P0s were verified in both code and rendered output and stand as written.**

---

## P1 — Design-system violations (systematic, mechanical)

Counts across `src/components/analytics/` + `Analytics.tsx`:

| Violation | Count | Rule |
|---|---|---|
| Raw Tailwind palette classes | **209** | `tailwind.config.ts` defines no amber/red/green/slate tokens — every one is untokenised debt, wrong in one theme by construction |
| Hex colour literals | **71** | §20 — chart colour comes from a token-reading source |
| `tm-card` | **119** | Retired v1 container |
| `tm-label` / `t-mono` / `table-header` | 32 / 19 / 13 | Retired v1 utilities |
| `text-sm` / `text-xs` / `text-lg`… | **389** | §7 — px scale only, never the rem scale |
| `text-[10px]` / `[9px]` / `[8px]` | 64 | Micro-type used as body copy |

Three of these deserve specific attention because they are visible, not just untidy:

- **P1-1 — Chart colours are the wrong green and red.** Charts use `#16a34a` / `#dc2626` (bright Tailwind defaults) while the rest of the UI uses the deliberately desaturated `--tm-profit` `#226D4F` and `--tm-loss` `#AF3A31`. Side by side on Overview the charts are visibly louder than the numbers beside them. **The literals have already drifted** — the same red appears as both `#dc2626` and `#DC2626`, the same green as `#16a34a` and `#16A34A`, which is the proof that hex-by-hand does not hold. `useChartColors()` already exists, is theme-reactive and has 10 passing tests; nothing consumes it.
- **P1-2 — The donut chart is banned outright** (§20: no donut, pie, radial, circular progress). Worse than the ban: it is a **five-hue rainbow** — teal, cyan, purple, orange, red — where the hues carry no meaning, sitting directly above a legend that colours the same rows green and red by sign. **Two contradictory colour systems inside one card.** The legend beneath it already gives instrument, share and P&L, ranked — the donut adds nothing the list doesn't already say better.
- **P1-3 — Minus signs are inconsistent, sometimes within a single axis.** The Daily P&L y-axis prints `-₹8.5k` (ASCII hyphen) and `−₹17k` (true minus U+2212) as adjacent ticks. Also mixed between cards: `−₹13,000.00` in Worst Trades vs `-30.2%` in Risk:Reward. A minus that changes shape mid-column is exactly the tell that reads as unfinished.

---

## P2 — Hierarchy, layout, alignment, density

**P2-1 — The hero and the KPI strip tell the same story twice, 400px apart.** ReportCard shows `+₹7,990.00`, win rate `60%`, profit factor `1.28`. The KPI strip immediately below shows P&L `+₹7,990.00`, win rate `60%`, profit factor `1.28`. Identical numbers, stacked. §25's cross-link-don't-recompute rule, broken on the page's first screen.

**P2-2 — Streaks appear twice.** "Best streak: 4 consecutive wins · Worst streak: 3 consecutive losses" as a caption under the Equity Curve, then again as two large cards at the bottom of Overview. The two cards spend a full row on two integers.

**P2-3 — Too many things are large.** §7 reserves display sizes for a screen's single primary metric. Overview alone gives display treatment to the hero figure, six KPI values, two streak integers; Behaviour adds three quality-tier counts and `1.90 ratio`. When everything is big, the hierarchy carries no information.

**P2-4 — Fake precision everywhere.** `+₹7,990.00`, `+₹11,770.00`, `−₹13,000.00`. Paise on a 30-day total is noise; it also widens every column and forces the wrapping in P2-5.

**P2-5 — Text truncation and wrapping breaks alignment.**
- `Where to focus` clips mid-word: *"the biggest drai…"*
- Disposition Effect clips its last line: *"This is costing you significantly."*
- `100% WR` wraps to two lines in the instrument leaderboard where `57% WR` does not, which shifts that row's rank number out of alignment with its neighbours.

**P2-6 — Two-column card pairs don't align.** Worst 5 / Best 5 sit side by side, but Worst rows carry behaviour chips and Best rows don't, so row heights differ and the shorter card leaves a block of empty space. Same on P&L Attribution / Product Mix, where Product Mix's two rows are stretched to match the donut's height.

**P2-7 — The instrument leaderboard bars mislead.** Bar length is `|P&L|` and every bar grows rightward from a shared left origin, so a −₹6,500 loss draws a *longer* bar than a +₹3,990 profit. Length reads as magnitude-of-good. Needs a centre baseline or a mirrored scale.

**P2-8 — Fourteen grids never collapse.** `grid-cols-2` / `-3` with no responsive prefix. `grid-cols-3 divide-x` at 390px leaves ~120px per cell for a currency figure. Mobile is stated as the priority; these are the sites that break it. (`grid-cols-7` in the calendar is legitimate — it's a week.)

**P2-9 — The calendar sits outside the card system.** Its title renders on the page background while its three month panels are cards — inconsistent with every other section, which is a titled card. Its Profit/Loss legend floats top-right above all three, belonging to none of them.

**P2-10 — Tab switching preserves scroll position.** Switching from a long tab to a short one lands you mid-page, sometimes below all content.

**P2-11 — Every tab has a decorative icon.** §10: an icon either carries meaning or is deleted. A chart glyph next to the word "Overview" carries none.

**P2-12 — Equity curve labels all 20 days on the x-axis.** Illegible at any width and unnecessary — endpoints plus a few interior ticks is the convention.

---

## P3 — Copy and voice

- **P3-1 — `TabIntro` is filler.** *"The full picture — your P&L, how consistent it is, and where it came from over the period."* Five of these, one per tab, each restating what the tab visibly is. §16 bans explanatory padding; the content should be self-evident from its own headings.
- **P3-2 — Inconsistent units.** `5t · 60% WR` in session windows vs `7 trades` in the leaderboard. Pick one.
- **P3-3 — Max Drawdown is coloured red.** It is negative by definition, so the colour encodes nothing. §6: colour communicates meaning, never decoration.

---

## Per-tab summary

| Tab | State | Worst issue |
|---|---|---|
| **Overview** | Dense, duplicative | Donut (P1-2); hero/KPI duplication (P2-1) |
| **Edge** | **Functionally broken** | Two empty charts (P0-1) |
| **Behaviour** | Misaligned, over-emphasised | "Worst 5" showing 4 (P0-4); column misalignment (P2-6) |
| **Habits** | **Broken copy + contradicts page** | P0-2, P0-3 |
| **Advanced** | Ignores page controls | Calendar ignores period, ⅔ empty (P0-5) |

---

## What the references actually do differently

Checked against the products named in `docs/DESIGN_SYSTEM.md` §2 as the direction for this product.

- **Zerodha Console** — the closest comparison, same market and data. Reports are **tables first, charts second**, one accent, no decorative colour. Its P&L breakdown is a ranked table with a bar column, which is precisely the replacement §20 prescribes for our donut. Numbers are whole rupees in summaries.
- **Tickertape** — one number is large per view, everything else steps down hard. Our Overview has roughly a dozen competing large numbers.
- **Stripe Dashboard** — charts label endpoints and a handful of interior ticks, never every point (our P2-12). Empty states never render an axis with no series (our P0-1): they replace the plot area with a stated cause.
- **Linear** — section headers are small, quiet and uppercase; hierarchy comes from spacing, not from size inflation. Matches §7 and is roughly the opposite of Analytics today.

The honest summary: **none of the references would ship a chart frame with no data in it, and none use more than one accent hue for a single quantity.** Those two are our biggest visible gaps, and both are P0/P1 here.

---

## Recommended order

1. **P0-1 through P0-5** — correctness. Small, contained, and until they are done, no visual judgement of the page is reliable.
2. **Extend the smoke test to assert a series actually rendered**, not just that headings appear and no `NaN` shows. This is the gap that let P0-1 through.
3. **P2 structural** — remove the duplicated hero/KPI story, kill the donut for a ranked bar table, drop the streak cards, fix the leaderboard baseline, collapse the 14 grids. This moves things, so it must precede the token sweep.
4. **P1 token sweep** — `useChartColors()` into all seven chart files, `tm-card` → the new container language, px type scale, palette classes → tokens. Highest volume, lowest risk, entirely mechanical.
5. **P3 copy.**

Item 3 is where the variants belong — one tab at a time behind a switcher, per the method that worked on Dashboard.
