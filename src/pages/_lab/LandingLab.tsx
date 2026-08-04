import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, CaretDown, Lightning, Eye, Prohibit, ChartLineDown, Timer, Coins } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

/**
 * DESIGN LAB — landing page. Route: /landing-lab
 *
 * Built from ui-ux-pro-max --design-system output for
 * "fintech trading behaviour analytics landing page india premium trust".
 *
 * WHAT THE TOOL RETURNED, AND WHAT IT DIAGNOSED
 *   Style      Bento Box Grid: modular cards, asymmetric grid, varied spans,
 *              negative space, hover scale 1.02, rounded-xl.
 *   Colors     Background #0F172A, primary gold #F59E0B, accent purple #8B5CF6,
 *              foreground #F8FAFC, muted #272F42, border #334155.
 *              Its own note: "Gold trust + purple tech".
 *   Effects    varied grid spans, rounded-xl, subtle shadows, hover scale,
 *              smooth transitions.
 *   AVOID      "Muted colors + Low energy".
 *
 * That last line is the diagnosis of every previous attempt on this page. They
 * were muted and low energy by construction, because they inherited the app's
 * calm operational palette. This one does not: the landing page gets its own
 * dark slate ground, gold and purple, and a bento grid.
 *
 * FONT: the tool recommends Calistoga + Inter. The font stack is fixed by the
 * brief, so Geist display + Inter body stays. Inter already matches its body
 * recommendation.
 *
 * Colours are declared locally here on purpose. The app's tokens are the
 * Operate palette; this page is Persuade and deliberately does not inherit them.
 */

const EASE = 'cubic-bezier(0.32,0.72,0,1)';

const C = {
  bg: '#0F172A',
  surface: '#161F35',
  surfaceHi: '#1B2540',
  border: '#334155',
  fg: '#F8FAFC',
  muted: '#94A3B8',
  gold: '#F59E0B',
  goldSoft: '#FBBF24',
  purple: '#8B5CF6',
  loss: '#F87171',
  profit: '#34D399',
};

const DETECTIONS = [
  { icon: Lightning,      pattern: 'Revenge trade',   line: 'Re-entered NIFTY CE 3× in 18 minutes after a loss.', money: '−₹14,200', tone: C.loss },
  { icon: ChartLineDown,  pattern: 'Size escalation', line: 'BANKNIFTY 45500 PE at 100 lots, 4× your average.',   money: '−₹6,450',  tone: C.loss },
  { icon: Timer,          pattern: 'Early exit',      line: 'Cut NIFTY CE at +₹820. It ran to +₹2,100.',          money: '+₹820',    tone: C.profit },
];

const REFUSALS = [
  { icon: Prohibit, t: 'Never blocks',   d: 'No order cancelled, delayed or locked. You decide what comes next.' },
  { icon: Eye,      t: 'Never predicts', d: 'No forecast, no probability. Only what your own record already shows.' },
  { icon: Coins,    t: 'Never guesses',  d: 'Realized P&L of those exact trades. Reconcilable against your contract note.' },
];

const STEPS: [string, string][] = [
  ['Connect Zerodha', 'One OAuth redirect, read-only. No order permission, so it cannot act on your account.'],
  ['It learns your normal', 'Pace, size and re-entry timing come from your own history, not an average trader.'],
  ['It tells you, that session', 'On screen and on WhatsApp: what fired, what it cost, your record with it.'],
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
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setShown(true); io.disconnect(); } }, { rootMargin: '-50px' });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref} style={{ transitionDelay: `${delay}ms`, transitionTimingFunction: EASE }}
      className={cn('transition-[opacity,transform] duration-700 motion-reduce:transition-none',
        shown ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6', className)}>
      {children}
    </div>
  );
}

/** Bento cell. Varied spans are set by the caller. Hover scale 1.02 per spec. */
function Cell({ children, className, span, glow }: { children: React.ReactNode; className?: string; span?: string; glow?: string }) {
  return (
    <div
      style={{ background: C.surface, borderColor: C.border, transitionTimingFunction: EASE }}
      className={cn(
        'group relative rounded-2xl border p-6 sm:p-7 overflow-hidden',
        'transition-transform duration-300 hover:scale-[1.02] cursor-default',
        span, className,
      )}
    >
      {glow && (
        <div aria-hidden className="pointer-events-none absolute -top-24 -right-20 w-64 h-64 rounded-full blur-3xl opacity-40 transition-opacity duration-500 group-hover:opacity-60"
          style={{ background: glow }} />
      )}
      <div className="relative">{children}</div>
    </div>
  );
}

function Cta({ variant = 'gold' }: { variant?: 'gold' | 'outline' }) {
  const gold = variant === 'gold';
  return (
    <Link to="/settings" style={{
      background: gold ? C.gold : 'transparent',
      color: gold ? '#0F172A' : C.fg,
      borderColor: gold ? 'transparent' : C.border,
      transitionTimingFunction: EASE,
      boxShadow: gold ? '0 8px 30px -8px rgba(245,158,11,0.55)' : 'none',
    }}
      className="group inline-flex items-center gap-3 rounded-full border pl-6 pr-1.5 h-[52px] text-[15px] font-semibold cursor-pointer transition-all duration-300 hover:scale-[1.03] active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0F172A]"
    >
      Connect Zerodha
      <span style={{ background: gold ? 'rgba(15,23,42,0.14)' : 'rgba(248,250,252,0.10)', transitionTimingFunction: EASE }}
        className="grid place-items-center w-10 h-10 rounded-full transition-transform duration-300 group-hover:translate-x-1 group-hover:-translate-y-0.5">
        <ArrowUpRight size={17} weight="bold" />
      </span>
    </Link>
  );
}

function FaqRow({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ borderColor: C.border }} className="border-b last:border-b-0">
      <button type="button" onClick={() => setOpen(v => !v)} aria-expanded={open}
        className="w-full flex items-start justify-between gap-6 py-5 text-left min-h-[44px] cursor-pointer">
        <span style={{ color: C.fg }} className="text-[16.5px] leading-snug text-pretty">{q}</span>
        <span style={{ background: C.surfaceHi, transitionTimingFunction: EASE }}
          className={cn('grid place-items-center w-8 h-8 rounded-full shrink-0 transition-transform duration-300', open && 'rotate-180')}>
          <CaretDown size={14} weight="bold" color={C.muted} />
        </span>
      </button>
      {open && <p style={{ color: C.muted }} className="text-[15px] leading-relaxed pb-5 max-w-[62ch] text-pretty">{a}</p>}
    </div>
  );
}

export default function LandingLab() {
  return (
    <div style={{ background: C.bg, color: C.fg }} className="min-h-[100dvh] antialiased overflow-x-hidden">

      {/* Nav */}
      <header className="sticky top-0 z-40 pt-5 px-4 pointer-events-none">
        <div className="mx-auto w-max pointer-events-auto">
          <div style={{ background: 'rgba(22,31,53,0.72)', borderColor: C.border }}
            className="flex items-center gap-1 rounded-full border backdrop-blur-xl pl-5 pr-1.5 py-1.5">
            <span className="text-[14px] font-semibold tracking-[-0.01em]">TradeMentor</span>
            <span style={{ background: C.border }} className="hidden sm:block w-px h-4 mx-3" />
            <a href="#how" style={{ color: C.muted }} className="hidden sm:block text-[13px] hover:text-white transition-colors px-2.5 cursor-pointer">How it works</a>
            <a href="#price" style={{ color: C.muted }} className="hidden sm:block text-[13px] hover:text-white transition-colors px-2.5 cursor-pointer">Price</a>
            <Link to="/settings" style={{ background: C.gold, color: '#0F172A' }}
              className="ml-2 rounded-full px-4 py-2 text-[13px] font-semibold cursor-pointer transition-transform duration-300 hover:scale-[1.04]">
              Sign in
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-[1200px] mx-auto px-5 sm:px-8">

        {/* HERO */}
        <section className="relative pt-16 sm:pt-24 pb-14">
          <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
            <div className="absolute -top-40 left-1/4 w-[36rem] h-[36rem] rounded-full blur-3xl opacity-25" style={{ background: C.gold }} />
            <div className="absolute -top-24 right-0 w-[30rem] h-[30rem] rounded-full blur-3xl opacity-20" style={{ background: C.purple }} />
          </div>

          <Reveal className="relative text-center">
            <span style={{ background: C.surface, borderColor: C.border, color: C.muted }}
              className="inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-[12px] font-medium">
              <span style={{ background: C.gold }} className="w-1.5 h-1.5 rounded-full" />
              For Indian F&amp;O and intraday traders
            </span>

            <h1 style={{ color: C.fg }} className="font-display text-[46px] sm:text-[72px] leading-[0.97] tracking-[-0.045em] font-bold mt-7 text-balance max-w-[16ch] mx-auto">
              Your worst days are
              <span style={{ color: C.gold }}> not bad luck.</span>
            </h1>

            <p style={{ color: C.muted }} className="text-[18px] leading-[1.6] mt-6 max-w-[54ch] mx-auto text-pretty">
              They have a shape. A loss, a faster re-entry, a bigger position.
              TradeMentor reads that sequence back to you while the session is
              still running.
            </p>

            <div className="flex flex-wrap items-center justify-center gap-4 mt-9">
              <Cta />
              <span style={{ color: C.muted }} className="text-[13px]">Read-only. It cannot place a trade.</span>
            </div>
          </Reveal>
        </section>

        {/* BENTO: asymmetric spans, the core of the recommended style. */}
        <section className="pb-24 sm:pb-32 grid grid-cols-1 md:grid-cols-6 gap-4 auto-rows-[minmax(0,auto)]">

          {/* Big cell: the live surface. */}
          <Reveal className="md:col-span-4">
            <Cell span="h-full" glow={C.gold}>
              <div className="flex items-baseline justify-between">
                <span style={{ color: C.muted }} className="text-[10px] uppercase tracking-[0.2em]">Day P&amp;L</span>
                <span style={{ color: C.muted }} className="inline-flex items-center gap-1.5 text-[11px]">
                  <span style={{ background: C.profit }} className="w-1.5 h-1.5 rounded-full animate-pulse" /> live
                </span>
              </div>
              <div style={{ color: C.loss }} className="font-display text-[52px] leading-none font-bold tracking-[-0.045em] font-tabular mt-3">
                −₹8,455
              </div>
              <p style={{ color: C.muted }} className="text-[13px] font-tabular mt-3">
                Booked <span style={{ color: C.loss }}>−₹8,895</span> · Unrealized <span style={{ color: C.profit }}>+₹440</span>
              </p>

              <div className="mt-6 space-y-2.5">
                {DETECTIONS.map(d => (
                  <div key={d.pattern} style={{ background: C.surfaceHi, borderColor: C.border }}
                    className="rounded-xl border px-4 py-3.5 flex items-start gap-3.5">
                    <span style={{ background: `${d.tone}1F` }} className="grid place-items-center w-9 h-9 rounded-lg shrink-0">
                      <d.icon size={17} weight="bold" color={d.tone} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-3">
                        <span style={{ color: C.muted }} className="text-[10px] font-semibold uppercase tracking-[0.16em]">{d.pattern}</span>
                        <span style={{ color: d.tone }} className="text-[14px] font-bold font-tabular shrink-0">{d.money}</span>
                      </div>
                      <p className="text-[13.5px] leading-snug mt-1 text-pretty">{d.line}</p>
                    </div>
                  </div>
                ))}
              </div>
            </Cell>
          </Reveal>

          {/* Tall stack: two smaller cells. */}
          <Reveal delay={80} className="md:col-span-2 flex flex-col gap-4">
            <Cell glow={C.purple} className="flex-1">
              <span style={{ color: C.purple }} className="font-display text-[44px] leading-none font-bold tracking-[-0.04em]">28</span>
              <p className="text-[15px] font-semibold mt-3">behaviours detected</p>
              <p style={{ color: C.muted }} className="text-[13.5px] leading-relaxed mt-1.5">
                Each one calibrated to your own history, not to an average trader.
              </p>
            </Cell>
            <Cell className="flex-1">
              <span style={{ color: C.goldSoft }} className="font-display text-[28px] leading-none font-bold tracking-[-0.03em]">Read-only</span>
              <p className="text-[15px] font-semibold mt-3">it cannot place a trade</p>
              <p style={{ color: C.muted }} className="text-[13.5px] leading-relaxed mt-1.5">
                The Zerodha connection has no order permission at all.
              </p>
            </Cell>
          </Reveal>

          {/* Wide statement cell. */}
          <Reveal delay={140} className="md:col-span-6">
            <Cell glow={C.gold}>
              <p className="font-display text-[24px] sm:text-[34px] leading-[1.2] tracking-[-0.035em] font-bold max-w-[30ch] text-balance">
                Every figure is the realized P&amp;L of the exact trades that fired the alert.
                <span style={{ color: C.muted }}> Not a guess at what a habit costs you.</span>
              </p>
            </Cell>
          </Reveal>

          {/* Three refusal cells. */}
          {REFUSALS.map((r, i) => (
            <Reveal key={r.t} delay={180 + i * 70} className="md:col-span-2">
              <Cell span="h-full" glow={i === 1 ? C.purple : undefined}>
                <span style={{ background: `${C.gold}1A` }} className="grid place-items-center w-11 h-11 rounded-xl">
                  <r.icon size={20} weight="bold" color={C.gold} />
                </span>
                <p className="font-display text-[19px] font-bold tracking-[-0.02em] mt-5">{r.t}</p>
                <p style={{ color: C.muted }} className="text-[14px] leading-relaxed mt-2 text-pretty">{r.d}</p>
              </Cell>
            </Reveal>
          ))}
        </section>

        {/* STEPS */}
        <section id="how" className="py-20 sm:py-28 scroll-mt-24">
          <Reveal>
            <h2 style={{ color: C.fg }} className="font-display text-[32px] sm:text-[44px] leading-[1.05] tracking-[-0.04em] font-bold max-w-[16ch] text-balance">
              Ninety seconds to
              <span style={{ color: C.gold }}> set up.</span>
            </h2>
          </Reveal>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-12">
            {STEPS.map(([t, d], i) => (
              <Reveal key={t} delay={i * 80}>
                <Cell span="h-full">
                  <span style={{ background: `${C.purple}1F`, color: C.purple }}
                    className="grid place-items-center w-11 h-11 rounded-xl font-display text-[16px] font-bold font-tabular">
                    {i + 1}
                  </span>
                  <p className="font-display text-[19px] font-bold tracking-[-0.02em] mt-5">{t}</p>
                  <p style={{ color: C.muted }} className="text-[14px] leading-relaxed mt-2 text-pretty">{d}</p>
                </Cell>
              </Reveal>
            ))}
          </div>
        </section>

        {/* PRICE */}
        <section id="price" className="py-20 sm:py-28 scroll-mt-24">
          <Reveal>
            <Cell glow={C.gold} className="!p-0">
              <div className="px-7 sm:px-12 py-12 grid grid-cols-1 sm:grid-cols-[auto_minmax(0,1fr)] gap-x-14 gap-y-8 items-center">
                <div>
                  <div className="flex items-baseline gap-2">
                    <span style={{ color: C.gold }} className="font-display text-[60px] leading-none font-bold tracking-[-0.05em] font-tabular">₹499</span>
                    <span style={{ color: C.muted }} className="text-[15px]">/ mo</span>
                  </div>
                  <p style={{ color: C.muted }} className="text-[13px] mt-3">One plan. No tiers.</p>
                </div>
                <div>
                  <p style={{ color: C.muted }} className="text-[16px] leading-relaxed max-w-[44ch] text-pretty">
                    Every detector, the full history, WhatsApp alerts and data export.
                    Cancel from Settings in one click, with no email and no retention
                    offer.
                  </p>
                  <div className="mt-8"><Cta variant="outline" /></div>
                </div>
              </div>
            </Cell>
          </Reveal>
        </section>

        {/* FAQ */}
        <section className="py-20 sm:py-28 max-w-[820px] mx-auto">
          <Reveal>
            <h2 style={{ color: C.fg }} className="font-display text-[30px] sm:text-[38px] leading-[1.08] tracking-[-0.04em] font-bold text-balance">
              Before you connect.
            </h2>
          </Reveal>
          <Reveal delay={70} className="mt-9">
            <div>{FAQ.map(([q, a]) => <FaqRow key={q} q={q} a={a} />)}</div>
          </Reveal>
        </section>

        {/* CLOSE */}
        <section className="py-24 sm:py-32 text-center">
          <Reveal>
            <h2 style={{ color: C.fg }} className="font-display text-[34px] sm:text-[52px] leading-[1.05] tracking-[-0.048em] font-bold max-w-[19ch] mx-auto text-balance">
              You already have the data.
              <span style={{ color: C.muted }}> Nobody reads it back to you.</span>
            </h2>
            <div className="mt-11 flex justify-center"><Cta /></div>
          </Reveal>
        </section>
      </main>

      <footer style={{ borderColor: C.border }} className="border-t">
        <div className="max-w-[1200px] mx-auto px-5 sm:px-8 py-12">
          <div className="flex flex-col sm:flex-row sm:items-center gap-5">
            <span style={{ color: C.muted }} className="text-[13px]">© {new Date().getFullYear()} TradeMentor</span>
            <div className="flex items-center gap-7 sm:ml-auto">
              <Link to="/terms" style={{ color: C.muted }} className="text-[13px] hover:text-white transition-colors cursor-pointer">Terms</Link>
              <Link to="/privacy" style={{ color: C.muted }} className="text-[13px] hover:text-white transition-colors cursor-pointer">Privacy</Link>
            </div>
          </div>
          <p style={{ color: C.muted }} className="text-[12px] leading-relaxed mt-8 max-w-[76ch] opacity-80 text-pretty">
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
