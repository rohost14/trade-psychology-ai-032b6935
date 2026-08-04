import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, CaretDown } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

/**
 * DESIGN LAB — landing page. Route: /landing-lab
 *
 * This one does not invent a structure. It copies the Lovable TradeMentor
 * landing page section for section, because that is what was asked for and
 * because five attempts at synthesising one failed.
 *
 * WHAT WAS READ OFF THE REFERENCE (measured, not guessed):
 *   ground        white, with alternating tinted bands
 *   font          Inter
 *   hero h1       50px
 *   section h2    34px
 *   section order nav · hero · "EVER DONE THIS?" · how it works · what you get ·
 *                 rules · journal-vs-alarm · pricing · FAQ · close
 *
 * THE MOVE I HAD MISSED: "EVER DONE THIS?" is a numbered list of six specific,
 * uncomfortable behaviours. It makes the reader identify themselves before
 * anything is sold, and it is the strongest section on their page. Nothing I
 * built had an equivalent.
 *
 * SECOND THING COPIED: every section heading is a sentence with a point of
 * view, not a label. "A journal is a post-mortem. This is a smoke alarm." My
 * versions used category names.
 *
 * Uppercase eyebrows are used per section here, which the taste skill caps.
 * The reference uses them and the reference is the brief.
 *
 * Content is ours and stays truthful: no invented testimonials, no per-pattern
 * costs nothing computes, no blocking, no prediction.
 */

const EASE = 'cubic-bezier(0.32,0.72,0,1)';

const EVER_DONE: string[] = [
  'Added to a trade that was already losing.',
  'Took five trades to win back one loss.',
  'Doubled the quantity right after a bad trade.',
  'Moved the stop-loss instead of taking the stop.',
  'Kept trading after you had already hit your limit for the day.',
  'Felt like the next trade had to be the one that fixed it.',
];

const HOW: [string, string][] = [
  ['It learns how you trade', 'Your last 90 days of orders, read once. Average size, usual pace, how you behave after a stop-out. Your normal, not an average trader’s.'],
  ['It watches the fills', 'Every order that completes is checked against that baseline, in the session, not at the end of the month.'],
  ['It tells you what just happened', 'On screen and on WhatsApp: the behaviour, the money it has already cost you, and your record with it.'],
];

const GET: [string, string][] = [
  ['Live behaviour alerts', 'Size spikes, fast re-entries, missing stops, loss streaks. Each alert carries the rupee figure that habit has already charged you.'],
  ['Cost leaks', 'Your P&L split by behaviour instead of by scrip. The line most traders have never seen.'],
  ['Your own record', 'Before you size up after a loss, what happened the last six times you did.'],
  ['Your rules, enforced honestly', 'Set a limit and the app tells you when your own trading is already tighter than it.'],
  ['A journal that fills itself', 'Every trade already logged. Add a mood in one tap, or nothing at all.'],
  ['Session reports', 'Morning brief, end of day, weekly. On WhatsApp if you want them.'],
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
        shown ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-5', className)}>
      {children}
    </div>
  );
}

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <span className="block text-[11px] font-semibold uppercase tracking-[0.18em] text-neutral-400">{children}</span>;
}

/** h2 at 34px, sentence with a point of view. Colour set explicitly because
 *  index.css applies text-foreground to headings globally. */
function H2({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <h2 style={{ color: '#141618' }}
      className={cn('font-display text-[27px] sm:text-[34px] leading-[1.12] tracking-[-0.03em] font-semibold mt-4 max-w-[24ch] text-balance', className)}>
      {children}
    </h2>
  );
}

function Cta({ light = false }: { light?: boolean }) {
  return (
    <Link to="/settings" style={{ transitionTimingFunction: EASE }}
      className={cn('group inline-flex items-center gap-2.5 rounded-lg px-6 h-[52px] text-[15px] font-semibold cursor-pointer transition-all duration-300',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
        light ? 'bg-white text-[#141618] hover:bg-neutral-100' : 'bg-[#155B56] text-white hover:bg-[#11463F]')}>
      See it on my trades
      <ArrowRight size={17} weight="bold" className="transition-transform duration-300 group-hover:translate-x-1" />
    </Link>
  );
}

function FaqRow({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-neutral-200 last:border-b-0">
      <button type="button" onClick={() => setOpen(v => !v)} aria-expanded={open}
        className="w-full flex items-start justify-between gap-6 py-5 text-left min-h-[44px] cursor-pointer">
        <span style={{ color: '#141618' }} className="text-[16.5px] font-medium leading-snug text-pretty">{q}</span>
        <CaretDown size={16} weight="bold"
          style={{ transitionTimingFunction: EASE }}
          className={cn('mt-1 shrink-0 text-neutral-400 transition-transform duration-300', open && 'rotate-180')} />
      </button>
      {open && <p className="text-[15px] text-neutral-600 leading-relaxed pb-5 max-w-[64ch] text-pretty">{a}</p>}
    </div>
  );
}

export default function LandingLab() {
  return (
    <div style={{ background: '#FFFFFF', color: '#141618' }} className="min-h-[100dvh] antialiased overflow-x-hidden">

      {/* NAV */}
      <header className="border-b border-neutral-200">
        <div className="max-w-[1140px] mx-auto px-5 sm:px-8 h-16 flex items-center gap-8">
          <span className="text-[15px] font-bold tracking-[-0.01em]">TradeMentor</span>
          <nav className="hidden md:flex items-center gap-7">
            {[['#ever', 'What it catches'], ['#how', 'How it works'], ['#get', 'Features'], ['#price', 'Pricing']].map(([h, l]) => (
              <a key={l} href={h} className="text-[13.5px] text-neutral-600 hover:text-[#141618] transition-colors cursor-pointer">{l}</a>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-4">
            <Link to="/settings" className="hidden sm:block text-[13.5px] font-medium text-neutral-600 hover:text-[#141618] transition-colors cursor-pointer">Log in</Link>
            <Link to="/settings" className="rounded-lg bg-[#155B56] text-white px-4 py-2.5 text-[13.5px] font-semibold hover:bg-[#11463F] transition-colors cursor-pointer">
              See it on my trades
            </Link>
          </div>
        </div>
      </header>

      {/* 1. HERO — 50px claim, product surface on the right */}
      <section className="max-w-[1140px] mx-auto px-5 sm:px-8 py-16 sm:py-24 grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] gap-12 lg:gap-14 items-center">
        <Reveal>
          <span className="inline-flex items-center gap-2 rounded-full border border-neutral-200 px-3 py-1 text-[12px] font-medium text-neutral-600">
            <span className="w-1.5 h-1.5 rounded-full bg-[#155B56]" />
            For Indian F&amp;O and intraday traders
          </span>
          <h1 style={{ color: '#141618' }}
            className="font-display text-[38px] sm:text-[50px] leading-[1.04] tracking-[-0.035em] font-bold mt-6 text-balance">
            Most losing days are made of
            <span className="text-[#155B56]"> 3 bad trades.</span>
          </h1>
          <p className="text-[17px] leading-[1.6] text-neutral-600 mt-6 max-w-[46ch] text-pretty">
            TradeMentor watches your live orders and tells you the moment you start
            repeating the habit that usually wrecks your day, while the day can
            still be saved.
          </p>
          <div className="flex flex-wrap items-center gap-4 mt-8">
            <Cta />
            <a href="#ever" className="text-[14px] font-medium text-neutral-600 hover:text-[#141618] transition-colors cursor-pointer">
              First, show me what it catches
            </a>
          </div>
          <p className="text-[12.5px] text-neutral-500 mt-5">Read-only order data. We can never place or cancel a trade.</p>
        </Reveal>

        <Reveal delay={120}>
          <div className="rounded-2xl border border-neutral-200 bg-white shadow-[0_2px_8px_-2px_rgba(20,22,24,0.06),0_28px_60px_-28px_rgba(20,22,24,0.22)] overflow-hidden">
            <div className="px-5 py-3 border-b border-neutral-200 bg-neutral-50 flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-neutral-300" />
              <span className="w-2.5 h-2.5 rounded-full bg-neutral-300" />
              <span className="w-2.5 h-2.5 rounded-full bg-neutral-300" />
              <span className="ml-2 text-[11px] text-neutral-500">TRADEMENTOR.APP / DASHBOARD</span>
            </div>
            <div className="p-5">
              <div className="rounded-xl border border-neutral-200 p-5">
                <div className="flex items-center justify-between">
                  <span className="text-[10.5px] font-semibold uppercase tracking-[0.16em] text-neutral-500">Intraday P&amp;L</span>
                  <span className="inline-flex items-center gap-1.5 text-[11px] text-neutral-500">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#2E7D32]" /> LIVE
                  </span>
                </div>
                <div className="font-display text-[34px] leading-none font-bold tracking-[-0.035em] font-tabular text-[#C0392B] mt-3">−₹3,247</div>
                <p className="text-[12.5px] text-neutral-500 mt-2">today · 3 open</p>
                <div className="grid grid-cols-3 gap-3 mt-5">
                  {[['TILT', '62'], ['PACE', '1.8×'], ['BUDGET', '₹6.8k']].map(([l, v]) => (
                    <div key={l}>
                      <div className="flex items-baseline justify-between">
                        <span className="text-[9.5px] font-semibold uppercase tracking-[0.14em] text-neutral-500">{l}</span>
                        <span className="text-[12.5px] font-bold font-tabular">{v}</span>
                      </div>
                      <div className="h-1 rounded-full bg-neutral-200 mt-1.5 overflow-hidden">
                        <div className="h-full rounded-full bg-neutral-400" style={{ width: l === 'TILT' ? '62%' : l === 'PACE' ? '80%' : '45%' }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-xl border border-[#C0392B]/20 bg-[#C0392B]/[0.04] p-5 mt-4">
                <div className="flex items-center gap-2">
                  <span className="text-[14px] font-bold text-[#C0392B]">Overtrading pace</span>
                  <span className="rounded bg-[#C0392B]/10 px-1.5 py-0.5 text-[9.5px] font-bold uppercase tracking-wider text-[#C0392B]">Pace</span>
                </div>
                <p className="text-[13px] text-neutral-700 mt-2">7 trades in 22 min · 2.1× your normal pace.</p>
                <p className="text-[13px] text-[#C0392B] mt-1.5">This pattern has cost you −₹9,200 across 8 trades.</p>
              </div>

              <p className="text-[10.5px] font-semibold uppercase tracking-[0.14em] text-neutral-500 mt-5">
                Observation only · you decide the next click
              </p>
            </div>
          </div>
        </Reveal>
      </section>

      {/* 2. EVER DONE THIS — the self-recognition list */}
      <section id="ever" className="bg-neutral-50 border-y border-neutral-200 scroll-mt-16">
        <div className="max-w-[1140px] mx-auto px-5 sm:px-8 py-20 sm:py-28">
          <Reveal><Eyebrow>Ever done this?</Eyebrow></Reveal>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-14 gap-y-0 mt-8">
            {EVER_DONE.map((t, i) => (
              <Reveal key={t} delay={i * 60}>
                <div className="flex items-baseline gap-5 py-5 border-b border-neutral-200">
                  <span className="font-display text-[13px] font-bold font-tabular text-neutral-400 shrink-0">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span className="text-[17px] leading-snug text-pretty">{t}</span>
                </div>
              </Reveal>
            ))}
          </div>
          <Reveal delay={120}>
            <p className="text-[17px] text-neutral-600 mt-10 max-w-[52ch] text-pretty">
              None of these are strategy problems. They happen in the twenty minutes
              after something goes wrong, and they are visible in your order log
              long before they are visible to you.
            </p>
          </Reveal>
        </div>
      </section>

      {/* 3. HOW IT WORKS */}
      <section id="how" className="scroll-mt-16">
        <div className="max-w-[1140px] mx-auto px-5 sm:px-8 py-20 sm:py-28">
          <Reveal>
            <Eyebrow>How it works</Eyebrow>
            <H2>We don&rsquo;t predict your trades. We recognise your habits.</H2>
            <p className="text-[17px] text-neutral-600 mt-5 max-w-[58ch] text-pretty">
              The alert lands after the order fills, early enough that the next
              three do not follow it.
            </p>
          </Reveal>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-10 mt-14">
            {HOW.map(([t, d], i) => (
              <Reveal key={t} delay={i * 80}>
                <span className="font-display text-[13px] font-bold font-tabular text-neutral-400">{String(i + 1).padStart(2, '0')}</span>
                <p className="text-[18px] font-semibold mt-3">{t}</p>
                <p className="text-[15px] text-neutral-600 leading-relaxed mt-2.5 text-pretty">{d}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* 4. WHAT YOU GET */}
      <section id="get" className="bg-neutral-50 border-y border-neutral-200 scroll-mt-16">
        <div className="max-w-[1140px] mx-auto px-5 sm:px-8 py-20 sm:py-28">
          <Reveal>
            <Eyebrow>What you get</Eyebrow>
            <H2>Six things, all pointed at the same problem.</H2>
          </Reveal>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mt-14">
            {GET.map(([t, d], i) => (
              <Reveal key={t} delay={i * 60}>
                <div className="h-full rounded-xl border border-neutral-200 bg-white p-6">
                  <p className="text-[16.5px] font-semibold">{t}</p>
                  <p className="text-[14.5px] text-neutral-600 leading-relaxed mt-2.5 text-pretty">{d}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* 5. JOURNAL VS ALARM */}
      <section>
        <div className="max-w-[1140px] mx-auto px-5 sm:px-8 py-20 sm:py-28 grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-20 items-center">
          <Reveal>
            <Eyebrow>Versus a journal</Eyebrow>
            <H2>A journal is a post-mortem. This is a smoke alarm.</H2>
            <p className="text-[17px] text-neutral-600 mt-5 max-w-[46ch] text-pretty">
              A journal tells you on Sunday what went wrong on Tuesday. Useful, and
              too late to change Tuesday. This one speaks while the session is
              still open.
            </p>
          </Reveal>
          <Reveal delay={90}>
            <div className="rounded-xl border border-neutral-200 overflow-hidden">
              {[
                ['Journal', 'You write it, afterwards', 'Sunday evening'],
                ['TradeMentor', 'It writes itself, from your orders', 'Twenty seconds after the fill'],
              ].map(([a, b, c], i) => (
                <div key={a} className={cn('px-6 py-5', i === 0 ? 'bg-neutral-50 border-b border-neutral-200' : 'bg-white')}>
                  <p className={cn('text-[15px] font-semibold', i === 1 && 'text-[#155B56]')}>{a}</p>
                  <p className="text-[14px] text-neutral-600 mt-1.5">{b}</p>
                  <p className="text-[12.5px] text-neutral-500 mt-1">{c}</p>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* 6. PRICING */}
      <section id="price" className="bg-neutral-50 border-y border-neutral-200 scroll-mt-16">
        <div className="max-w-[1140px] mx-auto px-5 sm:px-8 py-20 sm:py-28">
          <Reveal>
            <Eyebrow>Pricing</Eyebrow>
            <H2>Cheaper than one revenge trade.</H2>
          </Reveal>
          <Reveal delay={80}>
            <div className="rounded-2xl border border-neutral-200 bg-white p-8 sm:p-12 mt-12 grid grid-cols-1 sm:grid-cols-[auto_minmax(0,1fr)] gap-x-14 gap-y-8 items-center">
              <div>
                <div className="flex items-baseline gap-2">
                  <span className="font-display text-[52px] leading-none font-bold tracking-[-0.045em] font-tabular">₹499</span>
                  <span className="text-[15px] text-neutral-500">/ month</span>
                </div>
                <p className="text-[13px] text-neutral-500 mt-3">One plan. No tiers.</p>
              </div>
              <div>
                <p className="text-[16px] text-neutral-600 leading-relaxed max-w-[46ch] text-pretty">
                  Every detector, the full history, WhatsApp alerts and data export.
                  Cancel from Settings in one click, with no email and no retention
                  offer.
                </p>
                <div className="mt-7"><Cta /></div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* 7. FAQ */}
      <section>
        <div className="max-w-[820px] mx-auto px-5 sm:px-8 py-20 sm:py-28">
          <Reveal>
            <Eyebrow>Questions</Eyebrow>
            <H2>The ones traders actually ask.</H2>
          </Reveal>
          <Reveal delay={70} className="mt-10">
            <div>{FAQ.map(([q, a]) => <FaqRow key={q} q={q} a={a} />)}</div>
          </Reveal>
        </div>
      </section>

      {/* 8. CLOSE */}
      <section style={{ background: '#141618' }}>
        <div className="max-w-[1140px] mx-auto px-5 sm:px-8 py-24 sm:py-32 text-center">
          <Reveal>
            <h2 style={{ color: '#FFFFFF' }} className="font-display text-[30px] sm:text-[44px] leading-[1.1] tracking-[-0.035em] font-bold max-w-[22ch] mx-auto text-balance">
              Tomorrow morning, something will go wrong.
              <span className="text-white/50"> Be the first to know.</span>
            </h2>
            <div className="mt-10 flex justify-center"><Cta light /></div>
            <p className="text-[12.5px] text-white/40 mt-6">Read-only. We can never place or cancel a trade.</p>
          </Reveal>
        </div>
      </section>

      <footer className="border-t border-neutral-200">
        <div className="max-w-[1140px] mx-auto px-5 sm:px-8 py-12">
          <div className="flex flex-col sm:flex-row sm:items-center gap-5">
            <span className="text-[13px] text-neutral-500">© {new Date().getFullYear()} TradeMentor</span>
            <div className="flex items-center gap-7 sm:ml-auto">
              <Link to="/terms" className="text-[13px] text-neutral-500 hover:text-[#141618] transition-colors cursor-pointer">Terms</Link>
              <Link to="/privacy" className="text-[13px] text-neutral-500 hover:text-[#141618] transition-colors cursor-pointer">Privacy</Link>
            </div>
          </div>
          <p className="text-[12px] text-neutral-500 leading-relaxed mt-8 max-w-[78ch] text-pretty">
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
