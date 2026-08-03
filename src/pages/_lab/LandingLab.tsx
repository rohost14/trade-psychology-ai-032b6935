import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, CaretDown } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

/**
 * DESIGN LAB — landing page. Route: /landing-lab
 *
 * Built to .claude/skills/high-end-visual-design, cross-checked against
 * redesign-existing-projects. The app's design-system doc is deliberately NOT
 * followed here: the product is Operate mode, this page is Persuade, and the
 * only inherited constraint is the font stack.
 *
 * VIBE ARCHETYPE: Soft Structuralism. Ethereal Glass is the obvious pick for a
 * fintech and is wrong here, because dark-tech reads as "trading terminal" and
 * this product explicitly is not one. Silver ground, heavy grotesk, ambient
 * diffused shadow instead of borders.
 *
 * LAYOUT ARCHETYPE: Editorial Split, with the hero surface as a Z-axis stack.
 *
 * ONE DELIBERATE DEVIATION: the skill bans Inter. The font stack is fixed by
 * the brief, so Inter body / Geist display stays and the character comes from
 * scale, weight and tracking instead of a typeface swap.
 *
 * What the audit flagged on the previous version, and what changed:
 *   generic 1px grey borders   -> ambient shadow and tinted fills; hairline rings only
 *   navbar glued edge-to-edge  -> floating glass pill, detached from the top
 *   ease-out transitions       -> cubic-bezier(0.32, 0.72, 0, 1) everywhere
 *   flat single-layer cards    -> Double-Bezel: outer shell, inner core, concentric radii
 *   plain text CTA             -> Button-in-Button, nested icon circle, hover physics
 *   py-16                      -> py-28 to py-44
 *   bare text eyebrow          -> pill badge
 *   8px radii                  -> 2rem squircles and full pills
 */

const EASE = 'cubic-bezier(0.32,0.72,0,1)';

const DETECTIONS = [
  { pattern: 'Revenge trade',   line: 'Re-entered NIFTY CE 3× in 18 minutes after a loss.',                              money: '−₹14,200', note: 'realized on those three trades' },
  { pattern: 'Size escalation', line: 'BANKNIFTY 45500 PE at 100 lots, 4× your average, 8 minutes after a ₹2,600 loss.', money: '−₹6,450',  note: 'realized on the flagged trades' },
  { pattern: 'Early exit',      line: 'Cut NIFTY CE at +₹820 after 8 minutes. It ran to +₹2,100.',                       money: '+₹820',    note: '₹1,280 left on the table' },
];

const REFUSALS: [string, string][] = [
  ['It never blocks',   'No order is cancelled, delayed or locked. You see what happened and you decide what comes next.'],
  ['It never predicts', 'No forecast, no probability, no claim about how your day will go. Only what your own record shows.'],
  ['It never guesses',  'Money attached to a behaviour is the realized P&L of those exact trades, reconcilable against your contract note.'],
];

const STEPS: [string, string][] = [
  ['Connect Zerodha',            'One OAuth redirect, read-only. The integration has no order permission, so it cannot act on your account.'],
  ['It learns your normal',      'Pace, size and re-entry timing come from your own history, so the first alert is calibrated to you rather than an average.'],
  ['It tells you, that session', 'On screen and on WhatsApp if you want it: what fired, what it cost, and your record with that pattern.'],
];

const FAQ: [string, string][] = [
  ['Can it place or cancel my trades?', 'No. The Zerodha connection is read-only and has no order permission, so it cannot act on your account even if something went wrong at our end.'],
  ['Does it restrict my trading?', 'No, and it will not. It shows you what you did and what it cost. Nothing is disabled or delayed. If you want hard limits, Zerodha already provides them.'],
  ['Is this tips or signals?', 'No. It has no view on the market and never says what to buy or sell. It reads your behaviour, not instruments. TradeMentor is not a SEBI-registered investment adviser or research analyst.'],
  ['What if I have no history yet?', 'Kite gives today’s trades only, so a new account starts empty. Import your Console tradebook as a CSV and the analysis fills in immediately.'],
  ['Where does my data go?', 'It stays in your account. Nothing is sold or shared with brokers. Export everything or delete the account outright from Settings.'],
];

/** Heavy fade-up with a blur resolve. transform and opacity only. */
function Reveal({ children, delay = 0, className }: { children: React.ReactNode; delay?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setShown(true); return; }
    // Already on screen at mount reveals immediately; waiting on a callback
    // that never fires left the hero sitting at opacity 0.
    if (el.getBoundingClientRect().top < window.innerHeight) { setShown(true); return; }
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { setShown(true); io.disconnect(); }
    }, { rootMargin: '-60px' });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      style={{ transitionDelay: `${delay}ms`, transitionTimingFunction: EASE }}
      className={cn(
        'transition-[opacity,transform,filter] duration-[850ms] motion-reduce:transition-none',
        shown ? 'opacity-100 translate-y-0 blur-0' : 'opacity-0 translate-y-12 blur-[6px]',
        className,
      )}
    >
      {children}
    </div>
  );
}

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full bg-foreground/[0.04] ring-1 ring-foreground/[0.06] px-3 py-1 text-[10px] uppercase tracking-[0.2em] font-medium text-muted-foreground">
      {children}
    </span>
  );
}

/** Button-in-Button: label, then the arrow inside its own circle, flush right. */
function Cta({ ghost = false }: { ghost?: boolean }) {
  return (
    <Link
      to="/settings"
      style={{ transitionTimingFunction: EASE }}
      className={cn(
        'group inline-flex items-center gap-3 rounded-full pl-6 pr-1.5 h-12',
        'text-[14.5px] font-medium whitespace-nowrap transition-all duration-500 active:scale-[0.98]',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        ghost
          ? 'bg-foreground/[0.04] ring-1 ring-foreground/[0.08] text-foreground hover:bg-foreground/[0.07]'
          : 'bg-primary text-primary-foreground shadow-[0_1px_2px_rgba(20,40,36,0.16),0_8px_24px_-8px_rgba(20,40,36,0.30)] hover:shadow-[0_1px_2px_rgba(20,40,36,0.18),0_14px_34px_-10px_rgba(20,40,36,0.38)]',
      )}
    >
      Connect Zerodha
      <span
        style={{ transitionTimingFunction: EASE }}
        className={cn(
          'grid place-items-center w-9 h-9 rounded-full transition-transform duration-500',
          'group-hover:translate-x-[3px] group-hover:-translate-y-[2px] group-hover:scale-105',
          ghost ? 'bg-foreground/[0.06]' : 'bg-primary-foreground/[0.16]',
        )}
      >
        <ArrowUpRight size={16} weight="light" />
      </span>
    </Link>
  );
}

/** Double-Bezel: an outer shell holding an inner core at concentric radii. */
function Bezel({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn(
      'rounded-[2rem] bg-foreground/[0.035] ring-1 ring-foreground/[0.05] p-1.5',
      'shadow-[0_2px_6px_-2px_rgba(24,28,32,0.06),0_24px_60px_-24px_rgba(24,28,32,0.16)]',
      className,
    )}>
      <div className="h-full rounded-[calc(2rem-0.375rem)] bg-card shadow-[inset_0_1px_1px_rgba(255,255,255,0.6)] dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.06)] overflow-hidden">
        {children}
      </div>
    </div>
  );
}

function FaqRow({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="px-6 sm:px-8">
      <button
        type="button" onClick={() => setOpen(v => !v)} aria-expanded={open}
        className="w-full flex items-start justify-between gap-6 py-5 text-left min-h-[44px]"
      >
        <span className="text-[16px] text-foreground leading-snug text-pretty">{q}</span>
        <span
          style={{ transitionTimingFunction: EASE }}
          className={cn('grid place-items-center w-8 h-8 rounded-full bg-foreground/[0.05] shrink-0 transition-transform duration-500', open && 'rotate-180')}
        >
          <CaretDown size={14} weight="light" />
        </span>
      </button>
      {open && <p className="text-[14.5px] text-muted-foreground leading-relaxed pb-5 max-w-[62ch] text-pretty">{a}</p>}
    </div>
  );
}

export default function LandingLab() {
  return (
    <div className="min-h-[100dvh] bg-[rgb(var(--layer-page))] antialiased">
      {/* Floating glass pill, detached from the top. */}
      <header className="sticky top-0 z-40 pt-5 px-4 pointer-events-none">
        <div className="mx-auto w-max pointer-events-auto">
          <div className="flex items-center gap-1 rounded-full bg-card/70 backdrop-blur-xl ring-1 ring-foreground/[0.07] shadow-[0_1px_2px_rgba(24,28,32,0.04),0_12px_32px_-16px_rgba(24,28,32,0.22)] pl-5 pr-1.5 py-1.5">
            <span className="text-[14px] font-semibold tracking-[-0.01em] text-foreground">TradeMentor</span>
            <span className="hidden sm:block w-px h-4 bg-foreground/10 mx-3" />
            <a href="#how" className="hidden sm:block text-[13px] text-muted-foreground hover:text-foreground transition-colors px-2.5">How it works</a>
            <a href="#price" className="hidden sm:block text-[13px] text-muted-foreground hover:text-foreground transition-colors px-2.5">Price</a>
            <Link
              to="/settings"
              style={{ transitionTimingFunction: EASE }}
              className="ml-2 rounded-full bg-foreground/[0.05] hover:bg-foreground/[0.09] px-4 py-2 text-[13px] font-medium text-foreground transition-all duration-500"
            >
              Sign in
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-[1140px] mx-auto px-5 sm:px-8">

        {/* HERO. Editorial split: type left, the product surface right. */}
        <section className="pt-20 sm:pt-28 pb-28 sm:pb-36 grid grid-cols-1 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] gap-14 lg:gap-16 items-center">
          <Reveal>
            <Eyebrow>Indian F&amp;O · intraday</Eyebrow>
            <h1 className="font-display text-[46px] sm:text-[64px] leading-[0.98] tracking-[-0.045em] font-semibold text-foreground mt-7 text-balance">
              Your worst days
              <br />
              <span className="text-muted-foreground/70">are not bad luck.</span>
            </h1>
            <p className="text-[17px] leading-[1.6] text-muted-foreground mt-7 max-w-[42ch] text-pretty">
              They have a shape. A loss, a faster re-entry, a bigger position.
              TradeMentor reads that sequence back to you while the session is
              still running.
            </p>
            <div className="flex flex-wrap items-center gap-4 mt-9">
              <Cta />
              <span className="text-[12.5px] text-muted-foreground">Read-only. It cannot place a trade.</span>
            </div>
          </Reveal>

          <Reveal delay={120} className="lg:pl-6">
            <Bezel>
              <div className="px-7 pt-7 pb-6">
                <span className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Day P&amp;L</span>
                <div className="font-display text-[44px] leading-none font-semibold tracking-[-0.04em] font-tabular text-tm-loss mt-3">
                  −₹8,455
                </div>
                <p className="text-[13px] text-muted-foreground font-tabular mt-3">
                  Booked <span className="text-tm-loss">−₹8,895</span>
                  <span className="text-muted-foreground/40"> · </span>
                  Unrealized <span className="text-tm-profit">+₹440</span>
                </p>
              </div>
              <div className="px-3 pb-3 space-y-2">
                {DETECTIONS.map(d => (
                  <div key={d.pattern} className="rounded-[1.1rem] bg-foreground/[0.028] ring-1 ring-foreground/[0.04] px-5 py-4">
                    <div className="flex items-baseline justify-between gap-4">
                      <span className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">{d.pattern}</span>
                      <span className={cn('text-[14px] font-semibold font-tabular shrink-0', d.money.startsWith('−') ? 'text-tm-loss' : 'text-tm-profit')}>{d.money}</span>
                    </div>
                    <p className="text-[13.5px] text-foreground leading-snug mt-2 text-pretty">{d.line}</p>
                    <p className="text-[11px] text-muted-foreground mt-1.5">{d.note}</p>
                  </div>
                ))}
              </div>
            </Bezel>
          </Reveal>
        </section>

        {/* Statement band. No container: the type is the block. */}
        <section className="py-28 sm:py-36">
          <Reveal>
            <p className="font-display text-[28px] sm:text-[40px] leading-[1.2] tracking-[-0.035em] font-medium text-foreground max-w-[26ch] text-balance">
              Every figure above is the realized P&amp;L of the exact trades that
              fired the alert.
              <span className="text-muted-foreground/60"> Not a guess at what a habit costs you.</span>
            </p>
          </Reveal>
        </section>

        {/* Refusals. Three bezels. */}
        <section className="py-28 sm:py-36">
          <Reveal>
            <Eyebrow>The difference</Eyebrow>
            <h2 className="font-display text-[32px] sm:text-[44px] leading-[1.05] tracking-[-0.04em] font-semibold text-foreground mt-6 max-w-[20ch] text-balance">
              Most of this category sells control. This has none.
            </h2>
          </Reveal>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mt-14">
            {REFUSALS.map(([t, d], i) => (
              <Reveal key={t} delay={i * 90} className="h-full">
                <Bezel className="h-full">
                  <div className="px-7 py-8">
                    <p className="font-display text-[19px] font-semibold tracking-[-0.02em] text-foreground">{t}</p>
                    <p className="text-[14px] text-muted-foreground leading-relaxed mt-3 text-pretty">{d}</p>
                  </div>
                </Bezel>
              </Reveal>
            ))}
          </div>
        </section>

        {/* Steps. Oversized ghost numerals, no containers. */}
        <section id="how" className="py-28 sm:py-36 scroll-mt-24">
          <Reveal><Eyebrow>How it works</Eyebrow></Reveal>
          <ol className="mt-14 space-y-14">
            {STEPS.map(([t, d], i) => (
              <Reveal key={t} delay={i * 90}>
                <li className="grid grid-cols-1 sm:grid-cols-[100px_minmax(0,1fr)] gap-x-10 gap-y-3">
                  <span className="font-display text-[40px] leading-none font-semibold tracking-[-0.04em] text-foreground/[0.13] font-tabular">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <div className="max-w-[54ch]">
                    <p className="font-display text-[22px] font-semibold tracking-[-0.025em] text-foreground">{t}</p>
                    <p className="text-[15px] text-muted-foreground leading-relaxed mt-3 text-pretty">{d}</p>
                  </div>
                </li>
              </Reveal>
            ))}
          </ol>
        </section>

        {/* Price. */}
        <section id="price" className="py-28 sm:py-36 scroll-mt-24">
          <Reveal>
            <Bezel>
              <div className="px-8 sm:px-12 py-12 grid grid-cols-1 sm:grid-cols-[auto_minmax(0,1fr)] gap-x-14 gap-y-8 items-center">
                <div className="flex items-baseline gap-2">
                  <span className="font-display text-[56px] leading-none font-semibold tracking-[-0.045em] text-foreground font-tabular">₹499</span>
                  <span className="text-[15px] text-muted-foreground">/ mo</span>
                </div>
                <div>
                  <p className="text-[15.5px] text-muted-foreground leading-relaxed max-w-[46ch] text-pretty">
                    One plan. Every detector, the full history, WhatsApp alerts,
                    data export. Cancel from Settings in a single click, with no
                    email and no retention offer.
                  </p>
                  <div className="mt-7"><Cta ghost /></div>
                </div>
              </div>
            </Bezel>
          </Reveal>
        </section>

        {/* FAQ. */}
        <section className="py-28 sm:py-36">
          <Reveal>
            <h2 className="font-display text-[30px] sm:text-[38px] leading-[1.1] tracking-[-0.035em] font-semibold text-foreground max-w-[18ch] text-balance">
              Before you connect.
            </h2>
          </Reveal>
          <Reveal delay={80} className="mt-12">
            <Bezel>
              <div className="divide-y divide-foreground/[0.055] py-2">
                {FAQ.map(([q, a]) => <FaqRow key={q} q={q} a={a} />)}
              </div>
            </Bezel>
          </Reveal>
        </section>

        {/* Close. */}
        <section className="py-32 sm:py-44 text-center">
          <Reveal>
            <h2 className="font-display text-[34px] sm:text-[52px] leading-[1.05] tracking-[-0.045em] font-semibold text-foreground max-w-[20ch] mx-auto text-balance">
              You already have the data.
              <span className="text-muted-foreground/60"> Nobody reads it back to you.</span>
            </h2>
            <div className="mt-11 flex justify-center"><Cta /></div>
          </Reveal>
        </section>
      </main>

      <footer className="max-w-[1140px] mx-auto px-5 sm:px-8 pb-16">
        <div className="rounded-[2rem] bg-foreground/[0.028] px-8 py-9">
          <div className="flex flex-col sm:flex-row sm:items-center gap-5">
            <span className="text-[13px] text-muted-foreground">© {new Date().getFullYear()} TradeMentor</span>
            <div className="flex items-center gap-7 sm:ml-auto">
              <Link to="/terms" className="text-[13px] text-muted-foreground hover:text-foreground transition-colors">Terms</Link>
              <Link to="/privacy" className="text-[13px] text-muted-foreground hover:text-foreground transition-colors">Privacy</Link>
            </div>
          </div>
          <p className="text-[12px] text-muted-foreground/80 leading-relaxed mt-7 max-w-[76ch] text-pretty">
            TradeMentor analyses your trading behaviour, not the market. It is not a
            SEBI-registered Investment Adviser or Research Analyst, and nothing here is
            advice to buy, sell or hold any security. Derivatives trading carries a risk
            of loss.
          </p>
        </div>
      </footer>
    </div>
  );
}
