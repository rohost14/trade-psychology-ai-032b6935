# Analytics — what good analytics screens do, and what ours does wrong

Researched 2026-08-01. Three sources: published dashboard-design practice, the Lovable mockup (`DESIGN_TARGET_LOVABLE.md`), and this repo's own screen specification (`docs/design/02_WEB_SCREENS.md`). Findings and a decision, not options.

---

## 1. What the research actually says

**The inverted pyramid.** Effective analytics screens are three bands: **status at the top** (where do I stand), **trends and comparisons in the middle** (what explains the movement), **detail at the bottom** (which rows, which trades). Summary first, granular last, matching how people read.

**Five to seven primary metrics per view.** Beyond that, comprehension drops. Good dashboards are described as *opinionated* — they show the handful of metrics that matter rather than everything available.

**The five-second rule.** A viewer should be able to state the screen's main message within five seconds. If not, the hierarchy is wrong.

**Time-based views beat trade lists for behaviour.** The sharpest line from the trading-journal literature: *"A list of trades tells you which individual trades won or lost. A calendar tells you when you trade well and when you do not."* For a behavioural product this is decisive — the unit of insight is the session, not the fill.

## 2. What Lovable does

Its Analytics is: **ranked cost leaks · 4 hero KPIs · a performance-snapshot grid · a daily-P&L strip.** Four blocks. Ours has roughly fifteen.

But the important part is not the block list, it is the encoding rule. Lovable's stated core visual language is **money on everything**: every alert, pattern and rule row carries a ₹ amount, an occurrence count, and a trend direction — `−₹18,400 across 12 occurrences`, `−₹769/hit`, `↗ worsening`. Behaviour→money *is* the aesthetic.

Ours shows behaviour and money in separate places and never on the same row.

## 3. What this repo's own spec says — and the shipped page ignores

`docs/design/02_WEB_SCREENS.md` §3 specifies Analytics with a **Behaviour tab as the default**, and states the reason plainly: *behavioural insight is TradeMentor's unique value.* It puts the P&L summary **last**. Its centrepiece is a table:

```
Pattern            Occurrences    Cost       Trend
Overtrading        12×            −₹4,200    ↓ Improving
Revenge trading     4×            −₹2,800    → Stable
No stop-loss        8×            −₹1,100    ↑ Worsening
```

The shipped page does the opposite: it **opens on Overview**, which is generic P&L statistics, and buries Behaviour in tab three.

*(One correction to that spec: it labels the column "Est. Cost". Estimation is banned here — behaviour→money is the realized P&L of the exact flagged trades, via `trigger_completed_trade_id`. The backend already returns the factual version.)*

---

## 4. The verdict

### 4.1 The headline problem: we lead with our least differentiated screen

Analytics opens on **Overview — P&L, win rate, profit factor, equity curve, daily P&L**. Every one of those is in Zerodha Console already, free, from the same broker account. A trader has no reason to come to us for them.

The one thing only we can compute — **which behaviours ran money down, how often, and whether they are getting better** — is three tabs deep.

This is not a styling problem and no amount of restyling fixes it. **The first screen of Analytics should be the ranked behavioural cost leak.** Research, Lovable, and our own written spec all say the same thing, and the shipped page contradicts all three.

### 4.2 We already built the centrepiece and mounted it on the wrong page

`src/components/patterns/BehaviourCostCard.tsx` **is** the ranked cost-leak table — pattern, occurrences, trade count, realized P&L, sorted by money. It renders on **My Patterns** only.

Our own page-ownership split says **Analytics owns quantified cost**; My Patterns owns the at-a-glance scorecard. The component is on the wrong side of that line. It is also hardcoded to `days={90}`, so it ignores whatever period the user selected.

Nothing needs inventing. It needs moving and wiring to the selector.

### 4.3 The inverted pyramid is inverted

| Band | Should be | Currently is |
|---|---|---|
| Top | Status | ReportCard hero **and then the same three numbers again** in the KPI strip |
| Middle | Trends explaining movement | Equity curve, daily P&L — correct |
| Bottom | Detail | Donut, product mix, two streak cards restating a caption |

The top band is duplicated and the bottom band is padding.

### 4.4 Too many metrics, no primary

Research says five to seven. Overview alone gives display-size treatment to the hero figure, six KPI cells and two streak integers; Behaviour adds three tier counts and a `1.90 ratio`. Roughly a dozen numbers compete to be the answer, so none is.

### 4.5 Every tab opens with a sentence explaining the tab

`TabIntro` × 5 — *"The full picture — your P&L, how consistent it is, and where it came from over the period."* If a screen needs a caption to say what it is, the screen is wrong. It also pushes the actual content below the fold, which is precisely what the five-second rule measures.

### 4.6 The calendar is the most under-used thing on the page

Per the research, a P&L calendar answers *when do I trade well* better than any table — and for a behavioural product that is the central question. Ours is buried at the bottom of **Advanced**, the least-visited tab, sitting outside the card system with a legend that belongs to nothing.

---

## 5. What we are doing about it

In order of value, not effort:

1. **Behaviour becomes the default tab**, and the ranked cost leak becomes the first thing on it. Analytics stops leading with what Console already gives away.
2. **`BehaviourCostCard` moves to Analytics** and takes the page's period selector instead of its hardcoded 90 days. My Patterns keeps its scorecard and cross-links, per the ownership rule.
3. **Every row that names a behaviour carries money, count, and trend** — the Lovable encoding rule, applied consistently.
4. **The top band stops repeating itself** (done — the KPI strip no longer restates the hero) and the padding at the bottom goes (done — donut and streak cards removed).
5. **`TabIntro` is deleted.** Five captions explaining five tabs.
6. **The calendar is promoted** out of Advanced.

Items 4 is already shipped in the lab. The rest follow here.

## 6. What we are explicitly not copying

- **TradeZella's seven display modes** (dollars / percentage / R / ticks / pips / points / privacy). Options are not insight, and six of the seven are meaningless for Indian F&O.
- **"Est. cost" framing** anywhere. Realized P&L on flagged trades, always — a number reconcilable against a contract note, never a counterfactual.
- **More tabs.** Lovable has six, we have five, the spec has five. The problem was never tab count; it was which tab opens first.

---

**Sources:** [Dashboard design principles — UXPin](https://www.uxpin.com/studio/blog/dashboard-design-principles/) · [Effective dashboard design — DataCamp](https://www.datacamp.com/tutorial/dashboard-design-tutorial) · [Dashboard design principles — Yellowfin](https://www.yellowfinbi.com/blog/key-dashboard-design-principles-analytics-best-practice) · [What a trading journal dashboard should track — GASPNTRADER](https://gaspntrader.com/blog/trading-journal-dashboard) · [How to build a trade journal — TradeZella](https://www.tradezella.com/blog/how-to-build-a-trade-journal) · [Best trading journals 2026 — StockBrokers.com](https://www.stockbrokers.com/guides/best-trading-journals)
