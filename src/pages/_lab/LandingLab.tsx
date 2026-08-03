import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { CaretDown, ShieldCheck, Eye, Prohibit } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

/**
 * DESIGN LAB — landing page. Route: /landing-lab
 *
 * Built to .agents/skills/design-taste-frontend.
 *
 * DESIGN READ: redesign-preserve of a trust-first fintech landing for sceptical
 * Indian F&O traders, calm Linear-adjacent language, on the existing Inter +
 * Geist and pine-teal token system.
 *
 * DIALS: VARIANCE 4 · MOTION 3 · DENSITY 4. Section 1.A puts trust-first and
 * regulated products at 3-4 / 2-3 / 4-5, not the 8/6/4 baseline. This is a
 * financial product being sold to people who are pitched at constantly; a
 * high-variance page reads as a scam here.
 *
 * MODE: redesign-preserve (§11.A). Brand tokens, route slugs, nav labels and
 * the compliance copy are inherited, not reinvented.
 *
 * Checklist items that shaped this and that I had failed before:
 *  - zero em-dashes anywhere on the page (§9.G, non-negotiable)
 *  - eyebrow count capped at ceil(sections / 3): hero plus two, not one per section
 *  - no two sections share a layout family; seven sections, six families
 *  - not pure-text minimalism: the product surface renders as itself
 *  - cards omitted in favour of spacing where the content allows
 *  - motion at intensity 3: one staggered reveal, reduced-motion honoured
 *  - Phosphor icons only, no hand-rolled SVG
 *
 * Content rules from docs/LANDING_PAGE_AUDIT.md: no invented testimonials, no
 * per-pattern rupee figures nothing computes, no blocking, no prediction, no AI
 * branding, no streaks.
 */

/* Verbatim from the engine's alert vocabulary. Nothing invented. */
const DETECTIONS = [
  { pattern: 'Revenge trade',   line: 'Re-entered NIFTY CE 3× in 18 minutes after a loss.',                              money: '−₹14,200', note: 'realized on those three trades' },
  { pattern: 'Size escalation', line: 'BANKNIFTY 45500 PE at 100 lots, 4× your average, 8 minutes after a ₹2,600 loss.', money: '−₹6,450',  note: 'realized on the flagged trades' },
  { pattern: 'Early exit',      line: 'Cut NIFTY CE at +₹820 after 8 minutes. It ran to +₹2,100.',                       money: '+₹820',    note: '₹1,280 left on the table' },
];

const REFUSALS = [
  { icon: Prohibit,    t: 'It never blocks',   d: 'No order is cancelled, delayed or locked. You see what happened and you decide what comes next.' },
  { icon: Eye,         t: 'It never predicts', d: 'No forecast, no probability, no claim about how your day will go. Only what your own record shows.' },
  { icon: ShieldCheck, t: 'It never guesses',  d: 'Money attached to a behaviour is the realized P&L of those exact trades, reconcilable against your contract note.' },
];

const STEPS = [
  ['Connect Zerodha',      'One OAuth redirect, read-only. The integration has no order permission, so it cannot act on your account.'],
  ['It learns your normal', 'Pace, size and re-entry timing come from your own history, so the first alert is calibrated to you rather than an average.'],
  ['It tells you, that session', 'On screen and on WhatsApp if you want it: what fired, what it cost, and your record with that pattern.'],
];

const FAQ: [string, string][] = [
  ['Can it place or cancel my trades?',
   'No. The Zerodha connection is read-only and has no order permission, so it cannot act on your account even if something went wrong at our end.'],
  ['Does it restrict my trading?',
   'No, and it will not. It shows you what you did and what it cost. Nothing is disabled or delayed. If you want hard limits, Zerodha already provides them.'],
  ['Is this tips or signals?',
   'No. It has no view on the market and never says what to buy or sell. It reads your behaviour, not instruments. TradeMentor is not a SEBI-registered investment adviser or research analyst.'],
  ['What if I have no history yet?',
   'Kite gives today’s trades only, so a new account starts empty. Import your Console tradebook as a CSV and the analysis fills in immediately.'],
  ['Where does my data go?',
   'It stays in your account. Nothing is sold or shared with brokers. Export everything or delete the account outright from Settings.'],
];

/** One reveal, staggered. Motion intensity 3: noticed once, never again. */
function Reveal({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setShown(true); return; }
    // Anything already on screen at mount reveals immediately. Waiting for an
    // intersection callback that may never fire left the hero, and the product
    // surface beside it, sitting at opacity 0.
    if (el.getBoundingClientRect().top < window.innerHeight) { setShown(true); return; }
    const io = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setShown(true); io.disconnect(); } },
      { rootMargin: '-40px' },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      style={{ transitionDelay: `${delay}ms` }}
      className={cn('transition-all duration-500 ease-out motion-reduce:transition-none',
        shown ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-3')}
    >
      {children}
    </div>
  );
}

function Cta({ ghost = false, className }: { ghost?: boolean; className?: string }) {
  return (
    <Link
      to="/settings"
      className={cn(
        'inline-flex items-center justify-center h-11 px-5 rounded-md text-[14px] font-medium whitespace-nowrap transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        ghost ? 'border border-border text-foreground hover:bg-muted'
              : 'bg-primary text-primary-foreground hover:bg-primary/90',
        className,
      )}
    >
      Connect Zerodha
    </Link>
  );
}

function FaqRow({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-border last:border-b-0">
      <button
        type="button" onClick={() => setOpen(v => !v)} aria-expanded={open}
        className="w-full flex items-start justify-between gap-5 py-4 text-left min-h-[44px]"
      >
        <span className="text-[15px] text-foreground leading-snug">{q}</span>
        <CaretDown size={16} className={cn('mt-0.5 shrink-0 text-muted-foreground transition-transform duration-200', open && 'rotate-180')} />
      </button>
      {open && <p className="text-[14px] text-muted-foreground leading-relaxed pb-4 max-w-[66ch]">{a}</p>}
    </div>
  );
}

export default function LandingLab() {
  return (
    <div className="min-h-[100dvh] bg-background">
      {/* Nav: one line, 56px. */}
      <header className="border-b border-border">
        <div className="max-w-[1080px] mx-auto px-5 sm:px-8 h-14 flex items-center justify-between gap-4">
          <span className="text-[15px] font-semibold tracking-tight text-foreground">TradeMentor</span>
          <nav className="flex items-center gap-6">
            <a href="#how" className="hidden sm:inline text-[13px] text-muted-foreground hover:text-foreground transition-colors">How it works</a>
            <a href="#price" className="hidden sm:inline text-[13px] text-muted-foreground hover:text-foreground transition-colors">Price</a>
            <Link to="/settings" className="text-[13px] font-medium text-foreground hover:text-primary transition-colors">Sign in</Link>
          </nav>
        </div>
      </header>

      <main className="max-w-[1080px] mx-auto px-5 sm:px-8">

        {/* 1. HERO. Family: asymmetric split, text left, live surface right.
            Four text elements max, headline two lines. */}
        <section className="pt-14 sm:pt-20 pb-16 grid grid-cols-1 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] gap-10 lg:gap-14 items-center">
          <Reveal>
            <span className="t-label">For Indian F&amp;O and intraday traders</span>
            <h1 className="font-display text-[38px] sm:text-[50px] leading-[1.05] tracking-[-0.03em] font-normal text-foreground mt-4">
              Your worst days
              <br />
              are not bad luck.
            </h1>
            <p className="text-[16.5px] leading-[1.55] text-muted-foreground mt-5 max-w-[46ch]">
              They have a shape. A loss, a faster re-entry, a bigger position.
              TradeMentor reads that sequence back to you while the session is
              still running.
            </p>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-3 mt-7">
              <Cta />
              <span className="text-[12.5px] text-muted-foreground">Read-only. It cannot place a trade.</span>
            </div>
          </Reveal>

          {/* The product surface, rendered as itself rather than described. */}
          <Reveal delay={90}>
            <div className="rounded-lg border border-border bg-card overflow-hidden">
              <div className="px-5 py-3 border-b border-border flex items-baseline justify-between">
                <span className="t-label">Day P&amp;L</span>
                <span className="text-[11px] text-muted-foreground font-tabular">14:22</span>
              </div>
              <div className="px-5 py-4">
                <div className="font-display text-[32px] leading-none font-semibold tracking-tight font-tabular text-tm-loss">−₹8,455</div>
                <p className="text-[12.5px] text-muted-foreground font-tabular mt-2">
                  Booked <span className="text-tm-loss">−₹8,895</span>
                  <span className="text-muted-foreground/40"> · </span>
                  Unrealized <span className="text-tm-profit">+₹440</span>
                </p>
              </div>
              <div className="divide-y divide-border border-t border-border">
                {DETECTIONS.map(d => (
                  <div key={d.pattern} className="px-5 py-3.5">
                    <div className="flex items-baseline justify-between gap-4">
                      <span className="text-[10.5px] font-medium uppercase tracking-[0.12em] text-muted-foreground">{d.pattern}</span>
                      <span className={cn('text-[13.5px] font-medium font-tabular shrink-0', d.money.startsWith('−') ? 'text-tm-loss' : 'text-tm-profit')}>{d.money}</span>
                    </div>
                    <p className="text-[13.5px] text-foreground leading-snug mt-1.5">{d.line}</p>
                    <p className="text-[11px] text-muted-foreground mt-1">{d.note}</p>
                  </div>
                ))}
              </div>
            </div>
          </Reveal>
        </section>

        {/* 2. Family: full-bleed statement band. No eyebrow, no card. */}
        <section className="py-16 border-t border-border">
          <Reveal>
            <p className="font-display text-[24px] sm:text-[30px] leading-[1.3] tracking-[-0.015em] font-normal text-foreground max-w-[30ch]">
              Every figure above is the realized P&amp;L of the exact trades that
              fired the alert. Not a model&rsquo;s guess at what a habit costs you.
            </p>
          </Reveal>
        </section>

        {/* 3. Family: icon row, three across, no containers. */}
        <section className="py-16 border-t border-border">
          <Reveal>
            <h2 className="font-display text-[26px] sm:text-[32px] leading-[1.15] tracking-[-0.02em] font-normal text-foreground max-w-[22ch]">
              Most of this category sells you control. This one has none.
            </h2>
          </Reveal>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-10 gap-y-9 mt-10">
            {REFUSALS.map((r, i) => (
              <Reveal key={r.t} delay={i * 70}>
                <r.icon size={20} weight="regular" className="text-primary" />
                <p className="text-[15.5px] font-medium text-foreground mt-3">{r.t}</p>
                <p className="text-[14px] text-muted-foreground leading-relaxed mt-1.5">{r.d}</p>
              </Reveal>
            ))}
          </div>
        </section>

        {/* 4. Family: numbered ordered list, left rail. */}
        <section id="how" className="py-16 border-t border-border scroll-mt-16">
          <span className="t-label">How it works</span>
          <ol className="mt-8 space-y-8">
            {STEPS.map(([t, d], i) => (
              <Reveal key={t} delay={i * 70}>
                <li className="grid grid-cols-[32px_minmax(0,1fr)] gap-x-5">
                  <span className="font-display text-[15px] font-tabular text-muted-foreground pt-0.5">{String(i + 1).padStart(2, '0')}</span>
                  <div>
                    <p className="text-[16px] font-medium text-foreground">{t}</p>
                    <p className="text-[14px] text-muted-foreground leading-relaxed mt-1.5 max-w-[60ch]">{d}</p>
                  </div>
                </li>
              </Reveal>
            ))}
          </ol>
        </section>

        {/* 5. Family: single figure beside prose. */}
        <section id="price" className="py-16 border-t border-border scroll-mt-16 grid grid-cols-1 sm:grid-cols-[auto_minmax(0,1fr)] gap-x-12 gap-y-6 items-baseline">
          <Reveal>
            <div className="flex items-baseline gap-2">
              <span className="font-display text-[42px] leading-none font-semibold tracking-tight text-foreground font-tabular">₹499</span>
              <span className="text-[14px] text-muted-foreground">/ month</span>
            </div>
          </Reveal>
          <Reveal delay={70}>
            <p className="text-[15px] text-muted-foreground leading-relaxed max-w-[52ch]">
              One plan. Every detector, the full history, WhatsApp alerts, data
              export. Cancel from Settings in a single click, with no email and
              no retention offer.
            </p>
            <div className="mt-5"><Cta ghost /></div>
          </Reveal>
        </section>

        {/* 6. Family: disclosure list. */}
        <section className="py-16 border-t border-border">
          <div className="mt-5">{FAQ.map(([q, a]) => <FaqRow key={q} q={q} a={a} />)}</div>
        </section>

        {/* 7. Family: centred close. */}
        <section className="py-20 border-t border-border text-center">
          <Reveal>
            <h2 className="font-display text-[28px] sm:text-[36px] leading-[1.15] tracking-[-0.025em] font-normal text-foreground max-w-[22ch] mx-auto">
              You already have the data. Nobody reads it back to you.
            </h2>
            <div className="mt-8 flex justify-center"><Cta /></div>
          </Reveal>
        </section>
      </main>

      <footer className="border-t border-border">
        <div className="max-w-[1080px] mx-auto px-5 sm:px-8 py-8">
          <div className="flex flex-col sm:flex-row sm:items-center gap-4">
            <span className="text-[13px] text-muted-foreground">© {new Date().getFullYear()} TradeMentor</span>
            <div className="flex items-center gap-6 sm:ml-auto">
              <Link to="/terms" className="text-[13px] text-muted-foreground hover:text-foreground transition-colors">Terms</Link>
              <Link to="/privacy" className="text-[13px] text-muted-foreground hover:text-foreground transition-colors">Privacy</Link>
            </div>
          </div>
          <p className="text-[12px] text-muted-foreground leading-relaxed mt-6 max-w-[78ch]">
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
