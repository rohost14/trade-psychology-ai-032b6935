# What makes an interface look AI-generated — and where we stand

Research pass, 2026-07-30. ~30 sources, strongest listed at the end. Companion to `DESIGN_SYSTEM.md`: that document says what to build, this one says what to avoid and why, with our own audit against it.

**The single most useful finding, up front:**

> Negative prompting does not produce a decision. It produces the next-most-probable default.

One researcher built a slop detector and ran it over 41 generated builds: forbid indigo and the model reaches for **emerald**; forbid gradients and it reaches for the **amber-and-cream "tasteful startup" wash**. Avoiding tells is not a design direction. Only a committed positive decision is.

The second most useful: **the counter-signal is not an aesthetic, it is craft.** Linear ships Inter, the supposedly damning font. What differs is that everything around it was decided — focus rings, empty states, motion timing, hairlines, loading skeletons. *"Every visible element has visible decisions behind it."*

---

## 1. The tells, by category

Only the checkable ones. Vague advice discarded.

### Colour
| # | Tell | Why it happens |
|---|---|---|
| C1 | Indigo→violet gradient on CTAs, heroes, headline text | Verified causal chain. Adam Wathan, Tailwind's creator: *"I'd like to formally apologize for making every button in Tailwind UI `bg-indigo-500` five years ago, leading to every AI generated UI on earth also being indigo."* Placeholder → tutorials → training corpus. |
| C2 | Gradient text on headings and metrics | Decoration substituting for hierarchy |
| C3 | Coloured glow / bloom shadow behind cards on dark | Reads as "premium" in the corpus; encodes nothing |
| C5 | The escape hatches are now tells too — cream/beige surfaces, amber-and-cream, emerald accents | These are where models land when the obvious defaults are forbidden |
| C6 | shadcn tokens shipped unchanged — slate/zinc neutrals, `--radius: 0.5rem`, `slate-200` borders | Not a style; the absence of one |
| D4 | No colour budget — everything coloured, so nothing is an exception | Anomalies stop popping |

### Typography
| # | Tell | Why |
|---|---|---|
| T3 | Flat hierarchy: sizes 2px apart (14/16/18/20), nothing dominates | A model generating token-by-token has no global view of what matters first. It emits locally plausible sizes. |
| T5 | Monospace for body copy | Costume |
| T1 | One family, no pairing, no decision visible | — |
| T4 | Uppercase tracked eyebrow above every heading, often with leading dot and trailing hairline | Two independent sources converge on this |

### Layout
| # | Tell | Why |
|---|---|---|
| **L6** | **Left-edge accent bar, thick, colour cycling per card** | Called flatly *"the most recognizable tell of AI-generated UIs."* Mechanism: *"makes a box of text feel designed without committing to real layout."* |
| **L5** | **Monotonous spacing — same padding, same radius, same card height everywhere** | Uniform generous spacing prevents breakage at unexpected widths without requiring any layout reasoning. The cheapest way to not break. Fix is *intentional variation*: 8px between related fields, 24px between sections, 48px around what matters. |
| L3 | Cards nested in cards nested in cards | The card is a decision-avoidance wrapper — the default container for anything the model can't lay out |
| K6 | Radius uniform at 12–16px, escalating to 24px+ when asked to look "modern" | Radius is a taste axis with defensible positions anywhere on it — 0px, 8px, 999px are all decisions. **The generated middle is the absence of one.** |
| L4 | Everything centred, single column, stacked | — |
| L9 | `py-24` everywhere → dead space at 1440px | — |

### Components & states
| # | Tell |
|---|---|
| K1 | Library defaults left visible |
| K2 | Missing interaction states — the six-state test: default, hover, **focus**, active, disabled, loading |
| K4 | Missing empty / loading / error states |
| K5 | Cards where a table belongs — destroys column alignment, which destroys scannability |
| K3 | Status dots with no state behind them |

### Motion
| # | Tell |
|---|---|
| M1 | One fade-in-up, identical duration and easing, on everything |
| M2 | Bounce / elastic easing on interface elements |
| M3 | Animation in the wrong latency band — sub-100ms animation makes an app feel **slower** |
| M4 | Decorative blinking cursor, marquee, pulsing dot |

### Content
| # | Tell |
|---|---|
| P1 | Em-dash density |
| P7 | Fake data — testimonials, logos, metrics, "trusted by" |
| P10 | Placeholder numbers suspiciously round |
| P4 | Emoji standing in for icons |

### The two that survive visual polish
| # | Tell | Why it matters most |
|---|---|---|
| **D1** | **The hero-metric block: big number, small label, three supporting stats** | *"Used everywhere, trusted nowhere."* |
| **D3** | **Dashboards that describe instead of decide** | Every chart answers "how many?" and none answers "what should I do?" A case study found an AI dashboard *"visually improved while still answering the wrong question."* **This is the deepest tell — it survives a full visual redesign.** |

---

## 2. Counter-signals — what reads as domain competence

| | Signal |
|---|---|
| CS1 | Six designed states per interactive element. **The keyboard focus ring is the cheapest single upgrade with the highest signal** — it proves someone navigated without a mouse. |
| CS2 | A constrained published type scale, 4–6 sizes max. Monospace reserved for code and IDs, nowhere else. |
| CS3 | **`font-variant-numeric: tabular-nums`** — highest-value, lowest-cost fintech signal. Without it a P&L column visibly ripples as prices tick, *"which is precisely how a real trader spots a toy."* >96% browser support. |
| CS5 | P&L encoded by sign or arrow **as well as** colour. ~8% of men have colour-vision deficiency. Since red already means loss, use amber for warnings — never give "stock declined" and "account compromised" the same red. |
| CS6 | **Speed treated as a design property.** Bloomberg's real superpower is instantaneous data, not density. Linear achieves it with optimistic UI and local-first sync. *This is the counter-signal a generated app never has, because it requires architecture, not styling.* |
| CS7 | Keyboard-first with discoverability built in |
| CS8 | Deliberate friction proportional to consequence — uniform affordance for non-uniform consequences is a strong domain-ignorance signal |
| CS9 | Bloomberg's CTO: *"the secret to dealing with increasing complexity is to conceal it from the user."* Conceal, not delete. |
| CS10 | Skeletons shaped like the thing arriving — which requires knowing its shape |
| CS11 | Domain-correct micro-decisions: `12 Jun 2025` not `2025-06-12`, sticky headers, frozen first column |

---

## 3. Dense product UI — where landing-page advice actively harms

Almost all slop writing targets marketing pages. Several prescriptions **invert** for a dashboard.

The reframe that makes it tractable: **density = value the user gets ÷ time and space the interface occupies.** The failure mode of generated UI is *high visual density of decoration with low information density* — cards, badges, glows and icon tiles occupying space that carries no data.

| Landing-page rule | What it does to a dashboard |
|---|---|
| "Generous whitespace" (16–24px) | Forces scrolling for data that should be co-visible. Dense UI uses a **4 / 8 / 12px** rhythm. *"You're not removing whitespace, you're compressing it with discipline."* |
| "Big hero typography" | Steals viewport from data |
| "Everything in cards" | Breaks column alignment, kills scannability |
| "Delight with motion" | Decorative motion on live-updating numbers is actively harmful |
| "Rich vibrant palette" | Destroys exception-spotting. Most of the surface must stay quiet so anomalies pop. |
| "Mobile-first spacing" | 375px spacing on a 1440px monitor produces hollow layouts and endless scroll |
| "Reduce choices" (naive Hick's Law) | Wrong fix. *"The fix isn't fewer options. It's structured options."* 50 ungrouped links are slow; the same 50 in 6 labelled categories are fast. |

**Concrete dense-UI numbers** — body 14px/20px line-height · padding on a 4/8/12 grid · buttons 32–36px tall · three font weights maximum · two-tier ink (one strong for active values, one muted for support) · functional text ≥11px, body ≥12px · line-height ≥1.3.

**The three-question density audit:** Is every visible element relevant to the current task? Can the primary element be identified within 2 seconds? Would removing any element cost an extra click?

**Density is audience-dependent.** Bloomberg users expect maximum density; Robinhood users need progressive disclosure. A product serving both — which is ours (see `PRODUCT.md`) — needs **two densities, not a compromise between them.**

---

## 4. Where sources disagree

1. **Is shadcn the cause?** No consensus. Safest formulation: **unchanged defaults are the tell, not the library.**
2. **Is Inter a problem?** Contested, and the escape fonts (Geist, Space Grotesk, Instrument Serif) have themselves become tells. This is a treadmill, not a fix.
3. **Why Bloomberg works.** Two incompatible explanations: density-as-professional-status (*"the more painful the UI, the more satisfied these users are"*) versus speed-and-value-density. **They lead to opposite prescriptions. Build on the speed argument; do not cite Bloomberg as proof that density is objectively good.**
4. **Zerodha Kite complicates the density argument** and is worth noting since it is our direct reference: Kite is praised for being *minimalist* while serving serious traders — ~10.6 MB against 36–55 MB for competitors, with speed from in-memory databases and optimised backends. **Kite suggests the counter-signal is craft and speed, not density per se.**

---

## 5. Our audit — measured 2026-07-30

| # | Check | Result |
|---|---|---|
| 1 | Visible keyboard focus ring | **Pass** — global `:focus-visible`, 2px ring |
| 2 | Tabular numerals | **Pass** — `font-tabular` / `tabular-nums` |
| 3 | P&L encoded beyond colour | **Pass** — sign always rendered, true minus |
| 4 | No gradient / glow | **2 failures** — `alerts/TokenExpiredBanner.tsx:52`, `analytics/ReportCard.tsx:93` |
| 5 | Committed radius scale | **Fail, badly** — see below |
| 6 | Left-edge accent bars | **18 uses.** Ours are semantic (severity), not cycling decoration, so this is defensible — but the *thick bar on a rounded card* geometry clash is real and should be reviewed |
| 7 | Cards nested in cards | **Pass** after the surface rework |
| 8 | Empty / loading / error states, skeletons matching layout | **Partial** — primitives exist; ~14 sites still render a failed fetch as empty (tracked in `DESIGN_MIGRATION.md`) |
| 9 | Charts decide, not describe | **Fail** — see below |
| 10 | Placeholder numbers suspiciously round | **Fail** — demo data uses 500000, 25000 |

### The radius finding

The design system specifies three radii: 10px cards, 6px chips, full pills. Actual usage across `src/`:

```
rounded-lg    208     rounded-md    68
rounded-full  204     rounded-sm    35
rounded-xl    136     rounded-2xl   18
rounded       91      rounded-none  10
```

**Seven radii in active use.** This is not the "uncommitted middle" the research describes — it is no commitment at all, and it is the direct answer to *"why is everything so rounded?"*: 136 uses of `rounded-xl` (12px) and 18 of `rounded-2xl` (16px), neither of which the design system permits.

Consolidating to the three specified values is mechanical, measurable, and probably the single highest-value visual fix available.

### The two that matter most

**D1 — our Day P&L block is exactly the canonical hero-metric arrangement**: big number, small label, three supporting stats. *"Used everywhere, trusted nowhere."*

**D3 — our Dashboard describes rather than decides.** It answers "what is my P&L, what fired, what is open." It does not answer "what should I do differently in the next hour." Given the product's entire premise is behavioural change, this is the most serious finding in this document, and it is not a styling problem — no visual pass fixes it.

---

## Sources

Strongest first. Weak sources are SEO-driven agency marketing recycling the same observations and are excluded here.

- [impeccable.style/slop](https://impeccable.style/slop/) — 61 enumerated patterns, backs a lint tool; the most concrete source in the corpus
- [solodesign.cc — AI design slop: the tells](https://solodesign.cc/blog/ai-design-slop-the-tells/) — author built a ~50-rule detector and ran it against 41 overnight builds
- [Adam Wathan on the indigo origin](https://x.com/adamwathan/status/1953510802159219096) — primary source
- [Matt Ström — UI Density](https://mattstromawn.com/writing/ui-density/) — the density-as-value-per-space reframe
- [Superhuman — how to build a remarkable command palette](https://blog.superhuman.com/how-to-build-a-remarkable-command-palette/) — primary
- [Mantlr — Stripe / Linear / Vercel premium UI](https://mantlr.com/blog/stripe-linear-vercel-premium-ui) — the craft-not-aesthetic argument
- [Paul Wallas — designing for data density](https://paulwallas.medium.com/designing-for-data-density-what-most-ui-tutorials-wont-teach-you-091b3e9b51f4)
- [A List Apart — web typography: tables](https://alistapart.com/article/web-typography-tables/) — tabular numerals
- [Bloomberg — how Terminal UX designers conceal complexity](https://www.bloomberg.com/company/stories/how-bloomberg-terminal-ux-designers-conceal-complexity)
- [UX Magazine — the impossible Bloomberg makeover](https://uxmag.com/articles/the-impossible-bloomberg-makeover) — the contested density-as-status argument
- [Software at Scale — building Zerodha with Kailash Nadh](https://www.softwareatscale.dev/p/software-at-scale-37-building-zerodha-with-kailash-nadh)
- [freedesignmd — the shadcn trap](https://freedesignmd.com/blog/shadcn-looks-generic)
- [ColorArchive — financial UI colour guide](https://colorarchive.org/guides/financial-ui-color-guide/)
- [Fountain Institute — signs of vibe-coded UI](https://www.thefountaininstitute.com/blog/signs-vibe-coded-ui)
- [Slopless / Malewicz](https://www.slopless.design/)
