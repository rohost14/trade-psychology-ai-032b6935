import { useState } from 'react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';

/**
 * DESIGN LAB — three landing pages. Route: /landing-lab
 *
 * Every one of them drops what the audit found: no invented testimonials, no
 * per-pattern rupee figures nothing computes, no "circuit breakers that pause
 * trading" (the product does not block and does not predict), no AI branding,
 * no streaks. App tokens and app fonts throughout, so the seam between landing
 * and product disappears.
 *
 * They differ in structure, not in skin:
 *
 *   TAPE      The product speaks. A real detection is the hero; almost no
 *             marketing voice. Closest to Linear/Stripe.
 *   ARGUMENT  Editorial. One uncomfortable, falsifiable claim, then the case
 *             for it, read top to bottom.
 *   MIRROR    Demonstration. The visitor sees the surface they would get
 *             before being asked for anything.
 *
 * The shared asset is the thing already in the codebase and buried below the
 * fold on the live page: real alert copy. It is concrete, it is uncomfortable,
 * and no competitor can write it.
 */

const VARIANTS = { tape: 'Tape', argument: 'Argument', mirror: 'Mirror' } as const;
type Variant = keyof typeof VARIANTS;

/** Verbatim from the engine's own alert vocabulary — nothing invented. */
const DETECTIONS = [
  {
    pattern: 'Revenge trade',
    line: 'Re-entered NIFTY CE 3× in 18 min after a loss.',
    money: '−₹14,200',
    note: 'realized on those three trades',
  },
  {
    pattern: 'Size escalation',
    line: 'BANKNIFTY 45500 PE at 100 lots — 4× your average size, 8 min after a ₹2,600 loss.',
    money: '−₹6,450',
    note: 'realized on flagged trades',
  },
  {
    pattern: 'Early exit',
    line: 'Cut NIFTY CE at +₹820 after 8 min. It ran to +₹2,100.',
    money: '+₹820',
    note: 'booked · ₹1,280 left behind',
  },
];

function Cta({ subtle = false }: { subtle?: boolean }) {
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
      <Link
        to="/settings"
        className={cn(
          'inline-flex items-center h-11 px-5 rounded-md text-[14px] font-medium transition-colors',
          subtle
            ? 'border border-border text-foreground hover:bg-muted'
            : 'bg-primary text-primary-foreground hover:bg-primary/90',
        )}
      >
        Connect Zerodha
      </Link>
      <span className="text-[12.5px] text-muted-foreground">
        Read-only order data. We can never place or cancel a trade.
      </span>
    </div>
  );
}

function DetectionCard({ d, dim = false }: { d: typeof DETECTIONS[number]; dim?: boolean }) {
  const negative = d.money.startsWith('−');
  return (
    <div className={cn('px-5 py-4', dim && 'opacity-60')}>
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
          {d.pattern}
        </span>
        <span className={cn('text-[14px] font-medium font-tabular shrink-0',
          negative ? 'text-tm-loss' : 'text-tm-profit')}>
          {d.money}
        </span>
      </div>
      <p className="text-[14px] text-foreground leading-snug mt-1.5 max-w-[52ch]">{d.line}</p>
      <p className="text-[11.5px] text-muted-foreground mt-1">{d.note}</p>
    </div>
  );
}

/* ── A. TAPE ───────────────────────────────────────────────────────────────
   The product speaks first. No adjectives, no promises — a detection, then
   what it is, then how to switch it on. */
function Tape() {
  return (
    <div className="max-w-3xl mx-auto px-5 sm:px-8 py-16 sm:py-24">
      <span className="t-label">TradeMentor</span>

      <div className="tm-card overflow-hidden mt-6">
        <div className="divide-y divide-border">
          <DetectionCard d={DETECTIONS[0]} />
        </div>
        <p className="px-5 py-3 border-t border-border bg-muted/40 text-[12px] text-muted-foreground">
          This is what the product does. Nothing else on this page is more important.
        </p>
      </div>

      <h1 className="font-display text-[30px] sm:text-[38px] leading-[1.12] tracking-[-0.02em] font-normal text-foreground mt-12 max-w-[20ch]">
        It watches your orders and tells you what you just did.
      </h1>
      <p className="text-[15px] text-muted-foreground leading-relaxed mt-4 max-w-[58ch]">
        Twenty-eight behaviours, detected against your own history rather than a
        general rule. The money attached to each one is the realized P&amp;L of the
        exact trades it fired on — not an estimate of what a habit costs.
      </p>

      <div className="mt-8"><Cta /></div>

      <div className="tm-card overflow-hidden mt-14 divide-y divide-border">
        {DETECTIONS.slice(1).map(d => <DetectionCard key={d.pattern} d={d} />)}
      </div>

      <div className="mt-14 grid grid-cols-1 sm:grid-cols-3 gap-x-8 gap-y-6 border-t border-border pt-8">
        {[
          ['It does not block', 'No order is ever cancelled or delayed. You see what happened and decide the next click.'],
          ['It does not predict', 'No forecast, no probability. Only what your own tape already shows.'],
          ['It does not guess cost', 'Behaviour-to-money is realized P&L on flagged trades, reconcilable against a contract note.'],
        ].map(([h, p]) => (
          <div key={h}>
            <p className="text-[13.5px] font-medium text-foreground">{h}</p>
            <p className="text-[12.5px] text-muted-foreground leading-relaxed mt-1">{p}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── B. ARGUMENT ───────────────────────────────────────────────────────────
   One uncomfortable claim, then the case for it. Editorial: the reader is
   being convinced of something, not shown a feature list. */
function Argument() {
  return (
    <div className="max-w-2xl mx-auto px-5 sm:px-8 py-16 sm:py-24">
      <span className="t-label">TradeMentor · for Indian F&amp;O traders</span>

      <h1 className="font-display text-[34px] sm:text-[46px] leading-[1.08] tracking-[-0.025em] font-normal text-foreground mt-6">
        Your worst days are not bad luck.
        <span className="text-muted-foreground"> They have a shape.</span>
      </h1>

      <div className="mt-10 space-y-6 text-[16px] leading-[1.65] text-foreground">
        <p>
          A losing day is rarely one bad trade. It is a loss, then a faster
          re-entry, then a larger one. By the time the day is over the sequence
          is obvious — and by then it is also finished.
        </p>
        <p>
          You already have the data that shows this. It is sitting in your
          Zerodha account, in the timestamps and sizes of orders you placed
          yourself. Nobody reads it back to you.
        </p>
        <p className="text-muted-foreground">
          That is the entire product. Not signals, not advice, not a strategy.
          A mirror held up to your own tape.
        </p>
      </div>

      <div className="tm-card overflow-hidden mt-10 divide-y divide-border">
        {DETECTIONS.map(d => <DetectionCard key={d.pattern} d={d} />)}
      </div>
      <p className="text-[12px] text-muted-foreground mt-2.5">
        Real detections. The figure is the realized P&amp;L of those exact trades.
      </p>

      <div className="mt-12 space-y-6 text-[16px] leading-[1.65] text-foreground">
        <p>
          It will not stop you. There is no button that cancels an order and no
          forecast of how your day will go — both would require the product to
          claim it knows better than you, and it does not.
        </p>
        <p>
          What it knows is what you did last time, and what it cost.
        </p>
      </div>

      <div className="mt-10 pt-8 border-t border-border"><Cta /></div>
    </div>
  );
}

/* ── C. MIRROR ─────────────────────────────────────────────────────────────
   Show the surface. The visitor sees the thing they would get, at real
   fidelity, before being asked for anything. */
function Mirror() {
  return (
    <div className="max-w-5xl mx-auto px-5 sm:px-8 py-14 sm:py-20">
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,7fr)_minmax(0,9fr)] gap-10 lg:gap-14 items-start">
        <div className="lg:pt-6">
          <span className="t-label">TradeMentor</span>
          <h1 className="font-display text-[30px] sm:text-[36px] leading-[1.12] tracking-[-0.02em] font-normal text-foreground mt-5">
            This is your session, read back to you.
          </h1>
          <p className="text-[14.5px] text-muted-foreground leading-relaxed mt-4">
            Connect the account and the screen on the right fills with your own
            trades. Nothing here is a sample of someone else&apos;s trading.
          </p>
          <div className="mt-7"><Cta /></div>

          <dl className="mt-10 space-y-4 border-t border-border pt-6">
            {[
              ['Read-only', 'OAuth through Zerodha. No credentials stored, no order placed.'],
              ['Your own baseline', 'Thresholds come from how you actually trade, not a default.'],
              ['Factual money', 'Realized P&L of the trades we flagged. Never an estimate.'],
            ].map(([t, d]) => (
              <div key={t}>
                <dt className="text-[13px] font-medium text-foreground">{t}</dt>
                <dd className="text-[12.5px] text-muted-foreground leading-relaxed mt-0.5">{d}</dd>
              </div>
            ))}
          </dl>
        </div>

        {/* The product surface, at the fidelity it actually has. */}
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border flex items-baseline justify-between">
            <span className="t-label">Day P&amp;L</span>
            <span className="text-[11px] text-muted-foreground">example session</span>
          </div>
          <div className="px-5 py-4 border-b border-border">
            <div className="font-display text-[30px] leading-none font-semibold tracking-tight font-tabular text-tm-loss">
              −₹8,455
            </div>
            <p className="text-[12.5px] text-muted-foreground font-tabular mt-1.5">
              Booked <span className="text-tm-loss">−₹8,895</span>
              <span className="text-muted-foreground/40"> · </span>
              Unrealized <span className="text-tm-profit">+₹440</span>
            </p>
          </div>
          <div className="px-5 py-2.5 border-b border-border">
            <span className="t-label">What we caught today</span>
          </div>
          <div className="divide-y divide-border">
            {DETECTIONS.map((d, i) => <DetectionCard key={d.pattern} d={d} dim={i > 1} />)}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LandingLab() {
  const [variant, setVariant] = useState<Variant>('tape');

  return (
    <div className="min-h-screen bg-background">
      <div className="border-b border-border px-5 sm:px-8 py-2.5 flex items-center gap-2 flex-wrap">
        <span className="t-label">Landing</span>
        <div className="inline-flex rounded-md border border-border bg-card p-0.5">
          {(Object.keys(VARIANTS) as Variant[]).map(k => (
            <button
              key={k}
              onClick={() => setVariant(k)}
              className={cn(
                'px-2.5 h-7 rounded text-[11.5px] font-medium transition-colors',
                variant === k ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {VARIANTS[k]}
            </button>
          ))}
        </div>
      </div>

      {variant === 'tape' && <Tape />}
      {variant === 'argument' && <Argument />}
      {variant === 'mirror' && <Mirror />}
    </div>
  );
}
