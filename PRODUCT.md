# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Primary: Indian F&O traders on Zerodha, spanning two experience levels.**

- **Serious active traders** — multiple trades a day, live in Kite during market hours, read an option chain without help. On live screens they want everything co-visible and will trade whitespace for information.
- **Improving traders** — one to two years in, still learning, and the ones the behavioural product is really for. They need the analysis explained, not just displayed.

This mix is a confirmed product fact, not a hedge: it means the product needs **two densities** rather than one compromise. Live screens (what is happening now) serve the first group; analysis and reflection screens (what happened and what it cost) serve the second.

The situation is high-stakes and time-pressured during market hours (09:15–15:30 IST), and reflective after the close. The job is: *understand my own trading behaviour well enough to stop repeating what loses me money.*

## Product Purpose

TradeMentor observes a trader's real executed trades through the Zerodha Kite API, detects behavioural patterns in them, and reports what those patterns cost in rupees.

Success is a trader recognising a pattern in their own tape that they had not seen, and changing it. Not engagement, not session length.

## Positioning

**"Mirror, not blocker."** The product shows a trader facts about their own behaviour and never restricts, blocks, or advises. A competitor could copy the detectors; they could not truthfully copy the stance, because the stance costs them the intervention features that demo well.

The mechanism a neighbouring product could not copy honestly: **behaviour is attributed to money through realised P&L on the specific trades that triggered each detection**, never through a counterfactual. We say "these eleven flagged trades lost ₹18,400", never "you would have made ₹X".

## Operating Context

- Traders keep the product open in a browser tab alongside Kite during market hours.
- Data arrives from Zerodha: order postbacks in real time, positions and trades over REST, live prices over a shared WebSocket.
- Detection runs server-side per completed trade; the browser displays, it never detects.
- Reflection happens after the close, when reports and the session log are read.

## Capabilities and Constraints

**Capabilities:** 28 behavioural detectors over completed trades · live position and P&L display · alert stream with response tracking · period analytics with cost attribution · a per-instrument personal-record lookup · a self-imposed rule framework with an override ladder · an AI coach grounded in the trader's own history · generated periodic reports and a session log.

**Two hard constraints that govern every product decision:**

1. **Kite provides no trade history.** A new account is empty until the trader imports a Console CSV. Cold start is the normal first experience, not an edge case.
2. **Manual input does not happen.** Measured on real usage: 55 alerts fired, 0 outcomes recorded. Any feature requiring the trader to type or tap to work will not work.

**Money rule:** P&L is raw — `(exit − entry) × quantity × multiplier`. Never brokerage, STT or tax. A figure a trader cannot reconcile against their contract note is a figure they will not trust.

**Access constraint:** a standard Kite Connect app is bound to its owner's client ID. Multi-user access requires Zerodha compliance approval, which is not yet granted, so the product is single-user until then.

## Brand Commitments

Name: **TradeMentor AI**. Voice: an experienced trading mentor — factual, direct, evidence-first. Never a motivational coach. No praise attached to outcomes, no "great job", no encouragement in place of evidence.

**AI is invisible.** The intelligence shows in the quality of the observation, never in announcing itself. No "I noticed", no AI branding on surfaces that merely use it.

## Evidence on Hand

- Real behavioural engine with 28 detectors, running in production against live postbacks.
- Real usage evidence for the zero-manual-input constraint (55 alerts, 0 outcomes).
- Demo data (`src/lib/demoData.ts`) mirroring real API shapes, used for guest mode.

**Absences future work must not fabricate:** no testimonials, no customer count, no revenue or performance claims, no user-growth numbers. The marketing page currently carries placeholder figures that are not real and must not be treated as evidence.

## Product Principles

1. **Report, never advise.** Facts about the trader's own tape. No signals, no predictions, no verdicts on a trade not yet taken.
2. **Every behavioural claim carries a rupee figure**, drawn from the trades that triggered it.
3. **Zero manual input.** If a feature needs the trader to type for it to work, it does not ship.
4. **One screen, one story.** A metric lives on exactly one screen; others link to it.
5. **Trust is built on reconcilable numbers.** Raw P&L to the paisa, tabular alignment, sign always shown.

## Accessibility & Inclusion

No regulatory obligation applies, and accessibility is not permitted to constrain density on live screens.

One requirement is kept regardless, on product grounds rather than compliance: **profit and loss is never encoded by colour alone.** Around 8% of men have a colour-vision deficiency, and a trader misreading a loss as a gain is a product failure, not an accessibility footnote. Sign, and arrow where a trend is shown, always accompany the colour.
