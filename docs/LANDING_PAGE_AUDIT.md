# Landing page — audit

`src/pages/Welcome.tsx`, 701 lines. Reviewed 2026-08-04 against the product charter (`CLAUDE.md`, `PRODUCT.md`), `docs/DESIGN_SYSTEM.md`, and Indian financial-advertising norms.

**Findings only. Nothing changed.**

---

## P0 — Fix before this page is ever public

### 1. The testimonials are fabricated, and they carry financial performance claims

```
Arjun M. · NIFTY Options · 4 yrs · "₹82,000 saved"
  "…Down months dropped 60%."
Priya S. · Bank Nifty Intraday · 2 yrs · "₹1,20,000 saved"
  "The Blowup Shield stopped me on a day I thought I was fine…
   I would've blown the account."
Rahul K. · F&O Swing · 6 yrs · "₹65,000 saved"
  "…my Friday win rate is 18% vs 61% Mon–Thu."
```

**The product has no users.** Login is solo-only until Zerodha grants multi-user approval — that is the #1 item in `PENDING.md`. These are invented people, with invented rupee outcomes, presented as real customers of a financial product.

This is not a design problem:

- Invented testimonials with **specific monetary results** are the kind of claim consumer-protection and advertising regulators act on, and financial services are held to a higher bar than most.
- The page simultaneously displays **"SEBI compliant"** and a *"Not investment advice"* disclaimer, which makes fabricated performance claims sitting beside them worse, not better — it shows the compliance question was considered.
- One quote references **"the Blowup Shield"**, a feature that was retired and replaced by My Record. The testimonial describes a product that no longer exists.

**They have to come out.** Not be softened, not be labelled "illustrative" in small print — removed. A page with no testimonials is honest; a page with these is a liability, and the liability lands on you personally as the entity behind it.

If social proof is needed before there are users, the honest substitutes are: the research the detectors are built on, the fact that the data is read-only, or a plain statement that the product is new.

### 2. Invented per-pattern costs presented as fact

```
Overtrading       ₹4,200/session
FOMO Entry        ₹2,800/trade
No Stop-Loss      ₹11,200/incident
Meltdown Cascade  ₹22,000+/session
Early Exit        ₹1,900 left/trade
```

Nothing computes these. They read as measured averages and are not.

This also breaks the rule the whole product is built on: behaviour→money is **the realized P&L of the specific flagged trades**, never an estimate and never a counterfactual. The app was deliberately moved off "estimated cost" language; the landing page still leads with it.

### 3. The page advertises a blocker

> *"Opt-in circuit breakers that **pause trading** when behavioral data **predicts** a cascade loss day."*

Two charter breaches in one sentence. **Mirror, not blocker** is the founding constraint — the product shows facts and never restricts. And *predicts* is exactly the probabilistic attribution the analytics filter rules out.

It is also **contradicted by the page's own FAQ**, which asks *"Does it restrict my trading?"*. One of the two is wrong, and a visitor who reads both learns the page cannot be trusted.

---

## P1 — Charter and consistency

| Issue | Detail |
|---|---|
| **"AI Psychology Coach"** | Appears in features *and* as a paid-tier line item. This is the exact AI branding just removed from the Chat screen — §16: AI is invisible, intelligence shows through the answer. |
| **"track streaks", "Pattern Commitments"** | Gamification, explicitly banned. The streak card was removed from My Patterns for this reason; the landing page still sells it. |
| **"Greeks at a glance"** | No Greeks anywhere in the app. Verify before it stays — advertising a feature that does not exist is the other kind of false claim. |
| **"Turn insight into lasting change"** | Motivational copy, banned by the voice rules. |
| **Own font stack** | Plus Jakarta Sans + JetBrains Mono, against the app's Inter + Geist. A visitor moving from landing to product crosses a visible seam. |
| **36 hex literals + inline styles** | Largest single-file colour debt left. Wrong in one theme by construction. |

---

## P2 — Craft

- **Hero.** *"Trade better."* is generic and could headline any trading product. The Lovable landing page opens with *"Most losing days are made of 3 bad trades"* — a specific, falsifiable, uncomfortable claim that only this product can follow through on. That is the difference between a slogan and a hook.
- **The alert-card examples are the strongest asset on the page** and are buried below the fold. *"Re-entered NIFTY CE 3× in 18 min after losses. −₹14,200"* is concrete and unmistakably this product. It should lead.
- **CTA repetition.** "Connect Zerodha" appears in the nav, the hero, and again lower down with no variation in framing. It also asks for the biggest commitment available — broker OAuth — as the only action. There is no lighter step for someone not ready.
- **Pricing tiers describe features, not outcomes** — "Custom thresholds, full control" says nothing about what the buyer gets.
- **Section rhythm** is uniform: every block is heading + paragraph + card grid, so nothing is emphasised and the page reads flat.

---

## On "psychological hooks"

Worth separating two things, because the charter already has a position.

**Legitimate:** specificity, a concrete uncomfortable truth, showing real product surface, naming the cost of the problem. All of that is persuasion by being clear about what the thing does.

**Not legitimate here:** fake scarcity, fabricated social proof, countdown pressure, engagement mechanics. Not merely because they are distasteful — because this product's entire pitch is *"we show you the truth about your own behaviour."* A landing page that manipulates the reader to make that claim is self-refuting, and the charter cites Kailash Nadh on engagement being *"a thinly veiled proxy for user entrapment."* You cannot sell honesty dishonestly.

The strongest hook available is the one already sitting unused in the codebase: **the real alert examples.**

---

## Recommended order

1. **Delete the testimonials.** Non-negotiable, and it is a five-minute change.
2. Remove the invented per-pattern rupee figures, or replace them with the research they came from.
3. Fix the circuit-breaker claim — either the product blocks or it does not, and the charter says it does not.
4. Drop the AI branding and the streak/commitment language to match what the app now is.
5. Verify or remove the Greeks claim.
6. Then the craft pass: hook, hierarchy, CTA ladder, fonts, colour tokens.

Items 1–5 are truthfulness. Item 6 is design. Doing 6 first would mean building a better-looking page around claims that need deleting.
