import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, CaretDown } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

/**
 * DESIGN LAB — landing page. Route: /landing-lab
 *
 * References the user actually named: Sensibull, Stripe, Dhan. The previous
 * attempts failed on four specific things they called out: no depth, no colour,
 * no images, no hierarchy. Each is addressed by copying a concrete move from a
 * reference rather than by taste.
 *
 * WHAT EACH REFERENCE CONTRIBUTES
 *
 * Sensibull  Depth comes from ALTERNATING FULL-BLEED BANDS, not from shadows on
 *            a flat page. A two-tone headline where the key phrase carries the
 *            accent colour. A large product screenshot bleeding off the right
 *            edge instead of a tidy contained card. A stat band under the hero.
 *            A broker logo row.
 * Dhan       Light ground with a warm accent and tinted (never black) shadows.
 * Stripe     Colour arriving as a soft wash behind the hero, and section
 *            headings that are large and left-aligned rather than centred.
 *
 * ONE DELIBERATE DEPARTURE FROM SENSIBULL: it is dark. Dark was rejected earlier
 * as reading like a trading terminal, which this product is not. So the page
 * takes Sensibull's STRUCTURE on Dhan and Stripe's LIGHT ground: the depth comes
 * from banding, not from darkness.
 *
 * The "images" are the product's own surface rendered at real fidelity. There is
 * no stock photography here and there should not be: a screenshot of the actual
 * detection feed is the most persuasive asset available and it is honest.
 */

const EASE = 'cubic-bezier(0.32,0.72,0,1)';

const DETECTIONS = [
  { pattern: 'Revenge trade',   line: 'Re-entered NIFTY CE 3× in 18 minutes after a loss.',                              money: '−₹14,200', note: 'realized on those three trades', tone: 'loss' },
  { pattern: 'Size escalation', line: 'BANKNIFTY 45500 PE at 100 lots, 4× your average, 8 minutes after a ₹2,600 loss.', money: '−₹6,450',  note: 'realized on the flagged trades', tone: 'loss' },
  { pattern: 'Early exit',      line: 'Cut NIFTY CE at +₹820 after 8 minutes. It ran to +₹2,100.',                       money: '+₹820',    note: '₹1,280 left on the table',      tone: 'profit' },
];

const STATS: [string, string][] = [
  ['28', 'behaviours detected'],
  ['Read-only', 'it cannot place a trade'],
  ['Realized ₹', 'never an estimate'],
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

function Reveal({ children, delay = 0, className }: { children: React.ReactNode; delay?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setShown(true); return; }
    if (el.getBoundingClientRect().top < window.innerHeight) { setShown(true); return; }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setShown(true); io.disconnect(); } }, { rootMargin: '-60px' });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref} style={{ transitionDelay: `${delay}ms`, transitionTimingFunction: EASE }}
      className={cn('transition-[opacity,transform] duration-[800ms] motion-reduce:transition-none',
        shown ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8', className)}>
      {children}
    </div>
  );
}

function Cta({ ghost = false }: { ghost?: boolean }) {
  return (
    <Link to="/settings" style={{ transitionTimingFunction: EASE }}
      className={cn(
        'group inline-flex items-center gap-3 rounded-full pl-6 pr-1.5 h-[52px] text-[15px] font-medium whitespace-nowrap',
        'transition-all duration-500 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        ghost
          ? 'bg-white text-foreground ring-1 ring-black/[0.08] shadow-[0_1px_2px_rgba(24,28,32,0.06),0_10px_28px_-12px_rgba(24,28,32,0.20)] hover:shadow-[0_1px_2px_rgba(24,28,32,0.08),0_16px_36px_-14px_rgba(24,28,32,0.26)]'
          : 'bg-primary text-primary-foreground shadow-[0_1px_2px_rgba(20,60,54,0.20),0_12px_30px_-10px_rgba(20,60,54,0.42)] hover:shadow-[0_1px_2px_rgba(20,60,54,0.22),0_18px_42px_-12px_rgba(20,60,54,0.50)]',
      )}>
      Connect Zerodha
      <span style={{ transitionTimingFunction: EASE }}
        className={cn('grid place-items-center w-10 h-10 rounded-full transition-transform duration-500',
          'group-hover:translate-x-[3px] group-hover:-translate-y-[2px]',
          ghost ? 'bg-black/[0.05]' : 'bg-white/[0.18]')}>
        <ArrowUpRight size={17} weight="light" />
      </span>
    </Link>
  );
}

/** The product surface. Rendered at real fidelity because it IS the image. */
function ProductSurface({ className }: { className?: string }) {
  return (
    <div className={cn(
      'rounded-[1.75rem] bg-white ring-1 ring-black/[0.06] overflow-hidden',
      'shadow-[0_2px_8px_-2px_rgba(24,28,32,0.08),0_40px_80px_-32px_rgba(24,28,32,0.28)]',
      className,
    )}>
      <div className="flex items-center gap-1.5 px-5 py-3.5 border-b border-black/[0.05] bg-[rgb(var(--layer-elevated))]">
        <span className="w-2.5 h-2.5 rounded-full bg-black/[0.10]" />
        <span className="w-2.5 h-2.5 rounded-full bg-black/[0.10]" />
        <span className="w-2.5 h-2.5 rounded-full bg-black/[0.10]" />
        <span className="ml-3 text-[11px] text-muted-foreground tracking-wide">tradementor.app / dashboard</span>
      </div>

      <div className="px-6 pt-6 pb-5">
        <div className="flex items-baseline justify-between">
          <span className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Day P&amp;L</span>
          <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <span className="w-1.5 h-1.5 rounded-full bg-tm-profit animate-pulse" /> live
          </span>
        </div>
        <div className="font-display text-[42px] leading-none font-semibold tracking-[-0.04em] font-tabular text-tm-loss mt-3">−₹8,455</div>
        <p className="text-[13px] text-muted-foreground font-tabular mt-2.5">
          Booked <span className="text-tm-loss">−₹8,895</span>
          <span className="text-muted-foreground/40"> · </span>
          Unrealized <span className="text-tm-profit">+₹440</span>
        </p>
      </div>

      <div className="px-3 pb-3 space-y-2">
        {DETECTIONS.map(d => (
          <div key={d.pattern} className={cn(
            'rounded-[1.1rem] px-5 py-4 ring-1',
            d.tone === 'loss' ? 'bg-tm-loss/[0.045] ring-tm-loss/[0.10]' : 'bg-tm-profit/[0.045] ring-tm-profit/[0.10]',
          )}>
            <div className="flex items-baseline justify-between gap-4">
              <span className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">{d.pattern}</span>
              <span className={cn('text-[14px] font-semibold font-tabular shrink-0', d.tone === 'loss' ? 'text-tm-loss' : 'text-tm-profit')}>{d.money}</span>
            </div>
            <p className="text-[13.5px] text-foreground leading-snug mt-2 text-pretty">{d.line}</p>
            <p className="text-[11px] text-muted-foreground mt-1.5">{d.note}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function FaqRow({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-black/[0.06] last:border-b-0">
      <button type="button" onClick={() => setOpen(v => !v)} aria-expanded={open}
        className="w-full flex items-start justify-between gap-6 py-5 text-left min-h-[44px]">
        <span className="text-[16.5px] text-foreground leading-snug text-pretty">{q}</span>
        <span style={{ transitionTimingFunction: EASE }}
          className={cn('grid place-items-center w-8 h-8 rounded-full bg-black/[0.05] shrink-0 transition-transform duration-500', open && 'rotate-180')}>
          <CaretDown size={14} weight="light" />
        </span>
      </button>
      {open && <p className="text-[15px] text-muted-foreground leading-relaxed pb-5 max-w-[62ch] text-pretty">{a}</p>}
    </div>
  );
}

export default function LandingLab() {
  return (
    <div className="min-h-[100dvh] bg-[rgb(var(--layer-page))] antialiased overflow-x-hidden">

      {/* BAND 1: hero. Warm wash behind, Stripe-style, plus a screenshot that
          bleeds off the right edge the way Sensibull's does. */}
      <div className="relative">
        <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute -top-[22rem] -left-[14rem] w-[46rem] h-[46rem] rounded-full bg-tm-brand/[0.07] blur-3xl" />
          <div className="absolute -top-[16rem] right-[6rem] w-[38rem] h-[38rem] rounded-full bg-tm-obs/[0.06] blur-3xl" />
        </div>

        <header className="relative z-20 pt-6 px-4">
          <div className="mx-auto w-max">
            <div className="flex items-center gap-1 rounded-full bg-white/75 backdrop-blur-xl ring-1 ring-black/[0.06] shadow-[0_1px_2px_rgba(24,28,32,0.05),0_14px_34px_-18px_rgba(24,28,32,0.24)] pl-5 pr-1.5 py-1.5">
              <span className="text-[14px] font-semibold tracking-[-0.01em] text-foreground">TradeMentor</span>
              <span className="hidden sm:block w-px h-4 bg-black/[0.08] mx-3" />
              <a href="#how" className="hidden sm:block text-[13px] text-muted-foreground hover:text-foreground transition-colors px-2.5">How it works</a>
              <a href="#price" className="hidden sm:block text-[13px] text-muted-foreground hover:text-foreground transition-colors px-2.5">Price</a>
              <Link to="/settings" style={{ transitionTimingFunction: EASE }}
                className="ml-2 rounded-full bg-primary text-primary-foreground px-4 py-2 text-[13px] font-medium transition-all duration-500 hover:opacity-90">
                Sign in
              </Link>
            </div>
          </div>
        </header>

        <section className="relative z-10 max-w-[1180px] mx-auto pl-5 sm:pl-8 pr-0 pt-16 sm:pt-24 pb-24 sm:pb-32">
          <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] gap-14 lg:gap-10 items-center">
            <Reveal className="pr-5 sm:pr-8 lg:pr-0">
              <span className="inline-flex items-center gap-2 rounded-full bg-white ring-1 ring-black/[0.06] px-3.5 py-1.5 text-[11.5px] font-medium text-muted-foreground shadow-[0_1px_2px_rgba(24,28,32,0.04)]">
                <span className="w-1.5 h-1.5 rounded-full bg-tm-brand" />
                For Indian F&amp;O and intraday traders
              </span>

              {/* Two-tone headline, Sensibull's move: the accent lands on the
                  phrase that carries the argument. */}
              <h1 className="font-display text-[48px] sm:text-[62px] leading-[0.98] tracking-[-0.045em] font-semibold text-foreground mt-7 text-balance">
                Your worst days
                <br />
                <span className="text-tm-brand">are not bad luck.</span>
              </h1>

              <p className="text-[17.5px] leading-[1.6] text-muted-foreground mt-7 max-w-[40ch] text-pretty">
                They have a shape. A loss, a faster re-entry, a bigger position.
                TradeMentor reads that sequence back to you while the session is
                still running.
              </p>

              <div className="flex flex-wrap items-center gap-4 mt-9">
                <Cta />
                <span className="text-[13px] text-muted-foreground">Read-only. It cannot place a trade.</span>
              </div>
            </Reveal>

            <Reveal delay={140} className="lg:translate-x-16">
              <ProductSurface />
            </Reveal>
          </div>
        </section>
      </div>

      {/* BAND 2: stat strip on white. The first background change is the depth. */}
      <div className="bg-white border-y border-black/[0.05]">
        <div className="max-w-[1180px] mx-auto px-5 sm:px-8 py-10 grid grid-cols-1 sm:grid-cols-3 gap-8 sm:gap-6">
          {STATS.map(([v, l], i) => (
            <Reveal key={l} delay={i * 70}>
              <div className="sm:text-center">
                <div className="font-display text-[30px] leading-none font-semibold tracking-[-0.035em] text-foreground">{v}</div>
                <p className="text-[13.5px] text-muted-foreground mt-2">{l}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>

      {/* BAND 3: statement, on the page ground. */}
      <div className="max-w-[1180px] mx-auto px-5 sm:px-8 py-28 sm:py-36">
        <Reveal>
          <p className="font-display text-[30px] sm:text-[42px] leading-[1.18] tracking-[-0.04em] font-medium text-foreground max-w-[24ch] text-balance">
            Every figure above is the realized P&amp;L of the exact trades that fired the alert.
            <span className="text-muted-foreground/55"> Not a guess at what a habit costs you.</span>
          </p>
        </Reveal>
      </div>

      {/* BAND 4: refusals, inverted. The one dark band on the page, used where
          the argument is strongest. */}
      <div className="bg-[rgb(24,28,30)] text-[rgb(238,236,232)]">
        <div className="max-w-[1180px] mx-auto px-5 sm:px-8 py-28 sm:py-36">
          <Reveal>
            <h2 className="font-display text-[34px] sm:text-[46px] leading-[1.04] tracking-[-0.042em] font-semibold max-w-[19ch] text-balance">
              Most of this category sells control.
              <span className="text-tm-profit"> This has none.</span>
            </h2>
          </Reveal>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-14">
            {REFUSALS.map(([t, d], i) => (
              <Reveal key={t} delay={i * 90}>
                <div className="rounded-[1.5rem] bg-white/[0.045] ring-1 ring-white/[0.07] px-7 py-8 h-full">
                  <p className="font-display text-[19px] font-semibold tracking-[-0.02em]">{t}</p>
                  <p className="text-[14.5px] leading-relaxed mt-3 text-white/60 text-pretty">{d}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </div>

      {/* BAND 5: steps on white. */}
      <div id="how" className="bg-white scroll-mt-24">
        <div className="max-w-[1180px] mx-auto px-5 sm:px-8 py-28 sm:py-36">
          <Reveal>
            <h2 className="font-display text-[32px] sm:text-[42px] leading-[1.06] tracking-[-0.04em] font-semibold text-foreground max-w-[16ch] text-balance">
              Ninety seconds to set up.
            </h2>
          </Reveal>
          <ol className="mt-14 grid grid-cols-1 md:grid-cols-3 gap-10">
            {STEPS.map(([t, d], i) => (
              <Reveal key={t} delay={i * 90}>
                <li>
                  <span className="grid place-items-center w-11 h-11 rounded-full bg-tm-brand/[0.08] text-tm-brand font-display text-[16px] font-semibold font-tabular">
                    {i + 1}
                  </span>
                  <p className="font-display text-[20px] font-semibold tracking-[-0.025em] text-foreground mt-5">{t}</p>
                  <p className="text-[15px] text-muted-foreground leading-relaxed mt-2.5 text-pretty">{d}</p>
                </li>
              </Reveal>
            ))}
          </ol>
        </div>
      </div>

      {/* BAND 6: price, brand wash. */}
      <div className="bg-tm-brand/[0.05] border-y border-black/[0.05]" id="price">
        <div className="max-w-[1180px] mx-auto px-5 sm:px-8 py-24 sm:py-32 scroll-mt-24">
          <Reveal>
            <div className="rounded-[2rem] bg-white ring-1 ring-black/[0.06] shadow-[0_2px_8px_-2px_rgba(24,28,32,0.06),0_30px_70px_-30px_rgba(24,28,32,0.22)] px-8 sm:px-14 py-14 grid grid-cols-1 sm:grid-cols-[auto_minmax(0,1fr)] gap-x-16 gap-y-9 items-center">
              <div>
                <div className="flex items-baseline gap-2">
                  <span className="font-display text-[60px] leading-none font-semibold tracking-[-0.05em] text-foreground font-tabular">₹499</span>
                  <span className="text-[15px] text-muted-foreground">/ mo</span>
                </div>
                <p className="text-[13px] text-muted-foreground mt-3">One plan. No tiers.</p>
              </div>
              <div>
                <p className="text-[16px] text-muted-foreground leading-relaxed max-w-[44ch] text-pretty">
                  Every detector, the full history, WhatsApp alerts and data export.
                  Cancel from Settings in a single click, with no email and no
                  retention offer.
                </p>
                <div className="mt-8"><Cta ghost /></div>
              </div>
            </div>
          </Reveal>
        </div>
      </div>

      {/* BAND 7: FAQ. */}
      <div className="max-w-[820px] mx-auto px-5 sm:px-8 py-28 sm:py-36">
        <Reveal>
          <h2 className="font-display text-[32px] sm:text-[40px] leading-[1.08] tracking-[-0.04em] font-semibold text-foreground text-balance">
            Before you connect.
          </h2>
        </Reveal>
        <Reveal delay={80} className="mt-10">
          <div>{FAQ.map(([q, a]) => <FaqRow key={q} q={q} a={a} />)}</div>
        </Reveal>
      </div>

      {/* BAND 8: close, inverted to bookend the refusals band. */}
      <div className="bg-[rgb(24,28,30)] text-[rgb(238,236,232)]">
        <div className="max-w-[1180px] mx-auto px-5 sm:px-8 py-28 sm:py-40 text-center">
          <Reveal>
            <h2 className="font-display text-[36px] sm:text-[54px] leading-[1.04] tracking-[-0.048em] font-semibold max-w-[19ch] mx-auto text-balance">
              You already have the data.
              <span className="text-white/45"> Nobody reads it back to you.</span>
            </h2>
            <div className="mt-12 flex justify-center"><Cta ghost /></div>
          </Reveal>
        </div>
      </div>

      <footer className="bg-white border-t border-black/[0.05]">
        <div className="max-w-[1180px] mx-auto px-5 sm:px-8 py-12">
          <div className="flex flex-col sm:flex-row sm:items-center gap-5">
            <span className="text-[13px] text-muted-foreground">© {new Date().getFullYear()} TradeMentor</span>
            <div className="flex items-center gap-7 sm:ml-auto">
              <Link to="/terms" className="text-[13px] text-muted-foreground hover:text-foreground transition-colors">Terms</Link>
              <Link to="/privacy" className="text-[13px] text-muted-foreground hover:text-foreground transition-colors">Privacy</Link>
            </div>
          </div>
          <p className="text-[12px] text-muted-foreground/80 leading-relaxed mt-8 max-w-[76ch] text-pretty">
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
