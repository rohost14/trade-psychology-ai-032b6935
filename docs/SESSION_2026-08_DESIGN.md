# Session handoff — design work, 2026-08-04 → 08

**Read this before touching any design work.** Written so the thread survives a restart
with no memory. Branch `dashboard-production-readiness`, everything committed and pushed.

---

## 1. Two numbering systems — read this first or you will get confused

There are **two unrelated "rev" sequences**:

| | What | Where | Status |
|---|---|---|---|
| **Mirror rev 1–4** | The first attempt, four revisions of one folder, each overwriting the last | `design/mirror/` (HEAD = the final one) | **all rejected** |
| **rev 4 / 5 / 6** | The current line, each its own folder | `design/rev4/`, `design/rev5/`, `design/rev6/` | rev 6 is live |

`design/rev4/` is **not** Mirror rev 4. Different thing entirely. Mirror's history lives
only in git; the recovered copies are in `design/_recovered/`.

---

## 2. Where everything is

### Design folders (all committed)

```
design/mirror/            Mirror, final state only (option-C colour). Rejected.
design/_recovered/rev2/   Mirror rev 2 recovered from bba304a — light, every block a card
design/_recovered/rev3/   Mirror rev 3 recovered from 9f14d11 — one canvas, monochrome
design/rev4/              rev2 crossed with the shipping app
design/rev5/              demo_images character, tinted neutrals, Jakarta + Plex Mono
design/rev6/              rev5 with gimmicks stripped + Sensibull discipline. CURRENT
design/stitch/            Stitch-generated dashboard + critique
design/evidence/          The first attempt. Rejected outright.
```

**`design/_recovered/rev2` and `rev3` are frozen.** The user asked explicitly that they
not be overwritten. `src/` is never to be touched by design work.

### Claude Design boards

| Board | Project ID |
|---|---|
| TradeMentor — rev6 | `cadf06e9-0cc7-4d75-b83f-3bd806c03f3e` |
| TradeMentor — rev5 | `0d6fec31-9fd9-4c25-9827-1f7bb292962f` |
| TradeMentor — rev4 | `c3662f94-ef1a-493d-807b-ddad9281d737` |
| TradeMentor — recovered rev2 + rev3 | `8902f5d6-9803-46a7-b4ff-a40a94b35273` |
| TradeMentor — Stitch round 1 | `d653ac2e-5ea0-40ba-92e7-97fc99c89b9d` |
| Mirror — TradeMentor | `c00b66b0-187a-4ef5-bbe5-2244f6997e14` |
| Evidence | `2724a73b-6bf6-401e-b3e7-bbc61f39a006` |

**Claude Design is not a generator.** It is a hosting/sync surface — `DesignSync` pushes
files authored locally. The user assumed otherwise for several rounds; correct it if it
comes up again.

### Stitch

Project `7592233293884048749`, screen `4ea0111a24e8409c9415aace20a780a6`. Generated HTML
is saved at `design/stitch/01-dashboard-stitch.html`.

### Live lab routes

```
/design-lab      3 hand-built directions on a switcher (Terminal / Market / Focused)
/dashboard-lab   restored from tag `dashboard-lab-good` (596c066, 31 Jul)
/soft-lab        Soft Precision mobile — never deleted
/soft-web-lab    Soft Precision desktop — never deleted
/landing-lab     landing page attempts
```

---

## 3. Rejection history — the important part

Do not re-propose any of these.

| Attempt | Verdict, in the user's words |
|---|---|
| Evidence | *"no i didnt like any of them… i dont see our proper full width alerts, make it realistic"* |
| Mirror rev 1 (dark) | asked for light instead |
| Mirror rev 2 (light, all cards) | *"these are good but you made every card component which i strictly said"* |
| Mirror rev 3 (one canvas) | *"very bland? grey and white thats it"* |
| Mirror rev 4 (option-C colour) | *"still looks very bad… start from scratch"* |
| `/design-lab` 3 variants | *"none look good, did claude design do this?"* |
| rev 5 | *"very gimmicky… glowing icons emojis… looks vibe coded"* |
| The shipping app itself | *"not good, very bland basic, either everything is card or none of it is"* |

**The single diagnosis that unlocked progress:** every rejection was one global containment
rule applied uniformly. rev 1 no cards → blended. rev 2 all cards → boxed. rev 3 one canvas
→ bland. The brief was always *"half in card and half other way"* — containment must vary
**by content type**.

**Root cause of five failures:** designing from taste instead of copying a named reference.
The user's own note in `AGENT_HANDOFF.md` already said *"copy references rather than
synthesise."* Ask for references first.

---

## 4. References the user named, and what each settled

**Zerodha Kite** — `zerodha.com` and `kite.zerodha.com` are **blocked by browser safety
restrictions**; never been seen directly. Spec via thedesignindex.co: blue `#387ED1`, Inter
400/500 only, radius under 8px, 8–12px internal padding, 16–24px section gaps, subtle
shadows. **Screenshots from the user would still be the highest-value missing input.**

**Tickertape** — viewed directly. Proves mixed containment on one page: left column *is* a
card, chart area is bare, tag grid below is carded. Blue UI accent, red = down at full
strength.

**Dhan** — marketing site only. Dark teal-green, orange CTA.

**Sensibull** (`web.sensibull.com/fii-dii-data`, `/option-chain`) — viewed directly, and the
most useful of the four:
- **Zero icons inside rows.** Icons only in nav, plus a small ⓘ by a column header.
- **In-cell magnitude bars** — a pale tinted bar encodes a number's size; label and quantity
  become one element. Their signature device.
- Pale tints group **sides** (calls vs puts), never mood.
- Blue for interactivity only; red/green never touch chrome.
- No shadows, no gradients, 4–6px radius, ~24px rows.

**`demo_images/`** — the user's own mockups, and the round that drew *"it has good
personality."* Character there is five devices: pastel circular icon badges, tinted pills,
one gradient per screen, a soft wide shadow, indigo accent. **Those are phone-mockup devices
and rev 5 proved they read as gimmick on a dense desktop tool.**

---

## 5. rev 6 — the current state

`design/rev6/10-page-dashboard.html` — **Dashboard only**, both themes in one file, fully
responsive. `_preview-responsive.html` renders it at 390 / 834 / 1280 in live iframes.

**Kept from rev 5** (none of it was the problem):
- Tinted neutral ramp so the page is not grey: ground `#F4F4FA`, ink `#1B1B2E` (violet-black)
- Three hues one job: accent `#4A46D6`, up `#0F9D76`, down `#D42F4E`. Severity = three
  strengths of *down*, never a fourth hue
- **Plus Jakarta Sans** for all text, **IBM Plex Mono for money figures only**

**Removed from rev 5:** icon badges, gradient card, metric icon circles, all shadows,
radius 16 → 8.

**Taken from Sensibull:** the magnitude bar, used on loss budget *only* — the one metric with
a real ceiling. A bar under every metric would be the decoration this revision removed.

**Typography rationale** (researched, sources in `design/rev5/_shared.md`): tabular lining
figures mandatory in money columns; tall x-height is what survives 11–13px; bold for emphasis
only; glyph differentiation matters where a misread digit costs money. **Poppins — the demo's
font — fails this**: geometric-round `O` barely distinct from `0`, runs wide, no source
recommends it for dense figures. Hence the pairing.

**Mono is confined to money.** Not timestamps, counts or quantities.

### Responsive behaviour

- **≤1023px** — sidebar → 56px icon rail, session strip vertical, metrics 2×2
- **≤639px** — sidebar → bottom bar of five equal targets, no FAB; tabs scroll; table folds
  Qty/Entry/LTP/Chg% into the row caption so **Symbol and P&L keep their columns**

---

## 6. Shipping-code changes made this session

Two real bug fixes in `src/` (everything else was design-only):

- **`3b8a25c`** — `DEMO_HABITS` used `pnl` where the API returns `net_pnl`. Every Habits bar
  rendered `₹NaN`, full-width, in the loss colour, so a winning hour and a losing hour were
  indistinguishable. Guest mode only. Added the missing `key`, aligned ordering, and added a
  `HabitsTab` case to `analyticsTabs.smoke.test.tsx` — it covered nine analytics surfaces but
  not that one, which is why the regression shipped.
- **`d003fd6`** — `/api/analytics/session-log` had no guest fixture, so `SessionLog` returned
  `null` and vanished entirely. `DEMO_SESSION_LOG` reconciles exactly with
  `DEMO_HABITS.by_day_of_week`.

**`App.tsx`** gained two lazy imports and two routes (`/design-lab`, `/dashboard-lab`).
`src/pages/Dashboard.tsx` and `src/components/dashboard/` verified **byte-identical**
throughout.

### Still open in shipping code (from the Fluent research, unfixed)

1. **No live-region announcements for real-time alerts.** Alerts arrive over WebSocket; a
   screen-reader user is told nothing. Spec written in `design/mirror/20-states.html`.
2. **Input border contrast.** `#D6DEE8` on white is ~1.3:1 — fails WCAG 2.1 SC 1.4.11 for
   interactive controls.
3. **Light theme leaves the sidebar dark — NOT A BUG.** Investigated at length: the DOM
   computes correct light values everywhere. Consistent with browser-level forced-dark
   rendering, which alters paint but not `getComputedStyle`. Do not "fix" this in CSS.

---

## 7. Method notes that cost real time

- **A screenshot is not ground truth for colour.** When a screenshot and `getComputedStyle`
  disagree, believe the DOM and prove the pixel with an on-page probe element of a known
  colour. Cost ~15 tool calls before this was established.
- **Media queries respond to viewport width, not element width.** Setting `body{width:390px}`
  does not test breakpoints — it just squeezes the desktop layout. **Use iframes**; the inner
  document gets a real viewport. `_preview-responsive.html` is the harness.
- **PowerShell encoding trap.** `Get-Content`/`Set-Content` round-tripping mangled every `—`
  and `₹` in five files. Always `[System.IO.File]::ReadAllText($p,[Text.Encoding]::UTF8)` and
  `WriteAllText` with `UTF8Encoding($false)`. Reversible via Windows-1252 → UTF-8 if it
  happens.
- **Double quotes inside a PowerShell here-string break git commit messages.** Bit twice.
  Write commit messages with no `"` at all.
- **`git checkout <commit> -- <path>` does not remove files added later**, so extracting an
  old revision leaks newer files into it. Verify against `git ls-tree -r <commit>`.
- **The Chrome extension goes unresponsive periodically.** Symptoms: screenshot CDP timeouts,
  `browser_batch` not responding. Recovery: `tabs_context_mcp` with `createIfEmpty:true`,
  then a fresh tab. Do not loop more than 2–3 times.
- **Stitch calls time out but keep running server-side.** Poll `list_screens`; do not retry.
  `generate_variants` failed silently and produced nothing — needs re-running.
- **`lh3.googleusercontent.com` image URLs accept a size suffix** — append `=w2200` for full
  resolution.

---

## 8. Nothing is ever lost

Every design went through git. When the user reported a lost design, all of it was
recoverable:

- **Tag `dashboard-lab-good`** → `596c066`, the approved dashboard lab, restored to
  `/dashboard-lab`
- **Mirror rev 2 / rev 3** → recovered from `bba304a` / `9f14d11` into `design/_recovered/`
- Deleted ported labs (Alerts, Analytics, Chat, Journal, MyRules, Reports) recoverable from
  `c40968b^`

---

## 9. Next step

rev 6 is **one page**. Awaiting a verdict on whether the Sensibull-disciplined direction is
right. If yes, roll the same logic across Alerts, Analytics, My Rules, Journal, My Record.

Open questions for the user:
1. Is rev 6 the direction? Warmer or colder?
2. **Kite screenshots** — still the biggest missing reference.
3. `Mirror` and `Evidence` boards are now dead weight; delete them?

## 10. Verify state after restart

```bash
git log --oneline -16                 # this session's commits
git status --short                    # expect clean
npm run typecheck && npm run test     # expect clean, 85 tests
npm run dev                           # port 8084
```

Design files are static HTML. To preview: copy into `public/` under a temp folder, open via
`localhost:8084/<folder>/<file>.html`, **then delete the temp folder** — do not leave scratch
in `public/`.
