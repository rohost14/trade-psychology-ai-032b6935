import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * DESIGN LAB — the landing page, end to end. Route: /landing-lab
 *
 * Built against docs/DESIGN_REFERENCES.md and docs/AI_SLOP_TELLS.md rather than
 * a skill: the installed skills are dangling symlinks into a deleted .agents/
 * directory, and the research they would have supplied is already mined into
 * this repo.
 *
 * Everything docs/LANDING_PAGE_AUDIT.md found is gone: no invented
 * testimonials, no per-pattern rupee figures nothing computes, no "circuit
 * breakers that pause trading", no prediction claim, no AI branding, no
 * streaks, no second font stack, no hex literals.
 *
 * The structure is one argument, in order:
 *   1  the claim            a losing day has a shape
 *   2  the evidence         real detections, the strongest asset we own
 *   3  what it is           three plain capabilities
 *   4  what it refuses      the differentiator, stated as refusal not feature
 *   5  how it works         three steps, no screenshots of things that lie
 *   6  price                one number, no anchoring theatre
 *   7  objections           the questions a sceptical F&O trader actually has
 *
 * Craft rules taken from the reference set: one accent, semantic colour only;
 * type sizes fall from one scale and leading tightens as size rises; a single
 * boundary mechanism per level; max width 1024 with extra space becoming margin
 * rather than more columns.
 */

/** Verbatim from the engine's alert vocabulary. Nothing here is invented. */
const DETECTIONS = [
  {
    pattern: 'Revenge trade',
    line: 'Re-entered NIFTY CE 3× in 18 minutes after a loss.',
    money: '−₹14,200',
    note: 'realized P&L of those three trades',
  },
  {
    pattern: 'Size escalation',
    line: 'BANKNIFTY 45500 PE at 100 lots — 4× your average size, 8 minutes after a ₹2,600 loss.',
    money: '−₹6,450',
    note: 'realized P&L of the flagged trades',
  },
  {
    pattern: 'Early exit',
    line: 'Cut NIFTY CE at +₹820 after 8 minutes. It ran to +₹2,100.',
    money: '+₹820',
    note: 'booked · ₹1,280 left on the table',
  },
];

const CAPABILITIES = [
  {
    title: 'It reads your orders as they fill',
    body: 'Twenty-eight behaviours, evaluated against your own history rather than a general rule. Your thresholds come from how you actually trade — not a default someone picked.',
  },
  {
    title: 'It attaches money to behaviour',
    body: 'Each detection carries the realized P&L of the exact trades it fired on, traceable to individual fills. Not a model’s guess at what a habit costs you.',
  },
  {
    title: 'It remembers what you did last time',
    body: 'Before you size up after a loss, it can tell you what happened the last six times you did — from your own tape, not a study of other people.',
  },
];

const REFUSALS = [
  ['It does not block',       'No order is cancelled, delayed or blocked. You see what happened and you decide the next click.'],
  ['It does not predict',     'No forecast, no probability, no “likely to blow up today”. Only what your own record already shows.'],
  ['It does not estimate',    'Behaviour-to-money is realized P&L on flagged trades — reconcilable against your contract note.'],
  ['It does not gamify',      'No streaks, no badges, no score to protect. Nothing here is designed to keep you on the screen.'],
];

const STEPS = [
  ['Connect Zerodha', 'One OAuth redirect. Read-only order data — the integration cannot place or cancel a trade. About ninety seconds.'],
  ['It learns your baseline', 'Your normal pace, size and re-entry timing come from your own history, so the first alert is calibrated to you rather than to an average trader.'],
  ['You get told, during the session', 'On screen, and on WhatsApp if you want it. What fired, what it cost, and what your record with that pattern looks like.'],
];

const FAQ = [
  ['Can it place or cancel my trades?',
   'No. The Zerodha connection is read-only. It has no order-placement permission, so it cannot act on your account even if something went wrong.'],
  ['Does it restrict my trading?',
   'No, and it is not going to. The product shows you what you did and what it cost. Nothing is disabled, delayed or locked. If you want hard limits, Zerodha’s own tools do that.'],
  ['Is this tips or signals?',
   'No. It never says what to buy or sell, and it has no view on the market. It analyses your behaviour, not instruments. TradeMentor is not a SEBI-registered investment adviser or research analyst.'],
  ['What if I have no trading history yet?',
   'Kite provides today’s trades only, so a new account starts empty. You can import your Console tradebook as a CSV and the analysis is populated immediately.'],
  ['Where does my data go?',
   'It stays in your account. Nothing is sold, and nothing is shared with brokers or third parties. You can export everything or delete the account outright from Settings.'],
];

function Cta({ variant = 'primary' }: { variant?: 'primary' | 'ghost' }) {
  return (
    <Link
      to="/settings"
      className={cn(
        'inline-flex items-center justify-center h-11 px-5 rounded-md text-[14px] font-medium transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        variant === 'primary'
          ? 'bg-primary text-primary-foreground hover:bg-primary/90'
          : 'border border-border text-foreground hover:bg-muted',
      )}
    >
      Connect Zerodha
    </Link>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <span className="t-label">{children}</span>;
}

function FaqRow({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-border last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        aria-expanded={open}
        className="w-full flex items-start justify-between gap-4 py-4 text-left min-h-[44px] hover:text-foreground transition-colors"
      >
        <span className="text-[15px] text-foreground leading-snug">{q}</span>
        <ChevronDown className={cn('h-4 w-4 mt-0.5 shrink-0 text-muted-foreground transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <p className="text-[14px] text-muted-foreground leading-relaxed pb-4 max-w-[68ch]">{a}</p>
      )}
    </div>
  );
}

export default function LandingLab() {
  return (
    <div className="min-h-screen bg-background">
      {/* ── Nav ─────────────────────────────────────────────────────────── */}
      <header className="border-b border-border">
        <div className="max-w-[1024px] mx-auto px-5 sm:px-8 h-14 flex items-center justify-between gap-4">
          <span className="text-[15px] font-semibold tracking-tight text-foreground">TradeMentor</span>
          <div className="flex items-center gap-5">
            <a href="#how" className="hidden sm:inline text-[13px] text-muted-foreground hover:text-foreground transition-colors">How it works</a>
            <a href="#price" className="hidden sm:inline text-[13px] text-muted-foreground hover:text-foreground transition-colors">Price</a>
            <Link to="/settings" className="text-[13px] font-medium text-foreground hover:text-primary transition-colors">Sign in</Link>
          </div>
        </div>
      </header>

      <main className="max-w-[1024px] mx-auto px-5 sm:px-8">

        {/* ── 1. The claim ─────────────────────────────────────────────── */}
        <section className="pt-16 sm:pt-24 pb-14">
          <SectionLabel>For Indian F&amp;O and intraday traders</SectionLabel>
          {/* Leading tightens as size rises, per the reference set. Weight 400:
              the calm systems set headings light, never bold. */}
          <h1 className="font-display text-[36px] sm:text-[52px] leading-[1.06] tracking-[-0.03em] font-normal text-foreground mt-5 max-w-[16ch]">
            Your worst days are not bad luck.
          </h1>
          <p className="text-[17px] sm:text-[19px] leading-[1.5] text-muted-foreground mt-5 max-w-[54ch]">
            They have a shape: a loss, a faster re-entry, a bigger position. The
            sequence is obvious afterwards. TradeMentor reads it back to you
            while the day is still running.
          </p>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-3 mt-8">
            <Cta />
            <span className="text-[13px] text-muted-foreground">
              Read-only order data. It can never place or cancel a trade.
            </span>
          </div>
        </section>

        {/* ── 2. The evidence ──────────────────────────────────────────── */}
        <section className="pb-16 sm:pb-20">
          <div className="tm-card overflow-hidden">
            <div className="px-5 py-3 border-b border-border flex items-baseline justify-between gap-3">
              <SectionLabel>What it catches</SectionLabel>
              <span className="text-[11.5px] text-muted-foreground">example session</span>
            </div>
            <div className="divide-y divide-border">
              {DETECTIONS.map(d => {
                const negative = d.money.startsWith('−');
                return (
                  <div key={d.pattern} className="px-5 py-4">
                    <div className="flex items-baseline justify-between gap-4">
                      <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                        {d.pattern}
                      </span>
                      <span className={cn('text-[15px] font-medium font-tabular shrink-0',
                        negative ? 'text-tm-loss' : 'text-tm-profit')}>
                        {d.money}
                      </span>
                    </div>
                    <p className="text-[15px] text-foreground leading-snug mt-2 max-w-[56ch]">{d.line}</p>
                    <p className="text-[12px] text-muted-foreground mt-1.5">{d.note}</p>
                  </div>
                );
              })}
            </div>
          </div>
          <p className="text-[13px] text-muted-foreground mt-3 max-w-[64ch]">
            Every figure is the realized P&amp;L of the exact trades the pattern
            fired on. Nothing on this page is an estimate of what a habit costs.
          </p>
        </section>

        {/* ── 3. What it is ────────────────────────────────────────────── */}
        <section className="py-14 border-t border-border">
          <SectionLabel>What it is</SectionLabel>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-8 gap-y-9 mt-7">
            {CAPABILITIES.map(c => (
              <div key={c.title}>
                <h3 className="text-[16px] font-medium text-foreground leading-snug">{c.title}</h3>
                <p className="text-[14px] text-muted-foreground leading-relaxed mt-2">{c.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── 4. What it refuses ───────────────────────────────────────── */}
        <section className="py-14 border-t border-border">
          <SectionLabel>What it refuses to do</SectionLabel>
          <p className="text-[17px] text-foreground leading-relaxed mt-4 max-w-[56ch]">
            Most of this category sells control. This one deliberately has none,
            and that is the point rather than a limitation.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-10 gap-y-7 mt-8">
            {REFUSALS.map(([t, d]) => (
              <div key={t}>
                <p className="text-[15px] font-medium text-foreground">{t}</p>
                <p className="text-[14px] text-muted-foreground leading-relaxed mt-1.5">{d}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── 5. How it works ──────────────────────────────────────────── */}
        <section id="how" className="py-14 border-t border-border scroll-mt-16">
          <SectionLabel>How it works</SectionLabel>
          <ol className="mt-7 divide-y divide-border border-y border-border">
            {STEPS.map(([t, d], i) => (
              <li key={t} className="grid grid-cols-[28px_minmax(0,1fr)] gap-x-4 py-5">
                <span className="text-[13px] font-tabular text-muted-foreground pt-0.5">{i + 1}</span>
                <div>
                  <p className="text-[15px] font-medium text-foreground">{t}</p>
                  <p className="text-[14px] text-muted-foreground leading-relaxed mt-1.5 max-w-[62ch]">{d}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        {/* ── 6. Price ─────────────────────────────────────────────────── */}
        <section id="price" className="py-14 border-t border-border scroll-mt-16">
          <SectionLabel>Price</SectionLabel>
          <div className="mt-6 flex flex-col sm:flex-row sm:items-end gap-x-10 gap-y-6">
            <div>
              <div className="flex items-baseline gap-2">
                <span className="font-display text-[38px] leading-none font-semibold tracking-tight text-foreground font-tabular">₹499</span>
                <span className="text-[14px] text-muted-foreground">per month</span>
              </div>
              <p className="text-[14px] text-muted-foreground leading-relaxed mt-3 max-w-[46ch]">
                One plan. Every detector, the full history, WhatsApp alerts and
                data export. Cancel from Settings in one click — no email, no
                retention offer.
              </p>
            </div>
            <div className="sm:ml-auto"><Cta /></div>
          </div>
        </section>

        {/* ── 7. Objections ────────────────────────────────────────────── */}
        <section className="py-14 border-t border-border">
          <SectionLabel>Before you connect</SectionLabel>
          <div className="mt-5">
            {FAQ.map(([q, a]) => <FaqRow key={q} q={q} a={a} />)}
          </div>
        </section>

        {/* ── Close ────────────────────────────────────────────────────── */}
        <section className="py-16 border-t border-border">
          <h2 className="font-display text-[26px] sm:text-[32px] leading-[1.15] tracking-[-0.02em] font-normal text-foreground max-w-[24ch]">
            You already have the data. Nobody reads it back to you.
          </h2>
          <div className="mt-7"><Cta /></div>
        </section>
      </main>

      <footer className="border-t border-border">
        <div className="max-w-[1024px] mx-auto px-5 sm:px-8 py-8 flex flex-col sm:flex-row sm:items-center gap-4 sm:gap-6">
          <span className="text-[13px] text-muted-foreground">
            © {new Date().getFullYear()} TradeMentor
          </span>
          <div className="flex items-center gap-5 sm:ml-auto">
            <Link to="/terms" className="text-[13px] text-muted-foreground hover:text-foreground transition-colors">Terms</Link>
            <Link to="/privacy" className="text-[13px] text-muted-foreground hover:text-foreground transition-colors">Privacy</Link>
          </div>
        </div>
        <div className="max-w-[1024px] mx-auto px-5 sm:px-8 pb-8">
          <p className="text-[12px] text-muted-foreground leading-relaxed max-w-[80ch]">
            TradeMentor analyses your trading behaviour, not the market. It is
            not a SEBI-registered Investment Adviser or Research Analyst, and
            nothing here is advice to buy, sell or hold any security. Trading in
            derivatives carries a risk of loss.
          </p>
        </div>
      </footer>
    </div>
  );
}
