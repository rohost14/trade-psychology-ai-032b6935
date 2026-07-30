/**
 * DESIGN LAB — throwaway. Delete once a direction is chosen.
 *
 * NOT a trading terminal. TradeMentor is a reflection companion that sits
 * beside Kite: the trader executes there and comes here to understand their
 * own patterns. So these are calm, clean and subtle, not dense black cockpit.
 *
 * Mobile-first: every variant is built single-column and expands at md/lg.
 * The width switcher renders each at a real device width, because window
 * resizing does not reach the renderer in this environment.
 */
import { useState } from 'react';
import {
  ArrowRight, Clock, TrendingDown, TrendingUp, AlertOctagon,
  TriangleAlert, Info, ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ── Shared sample data ─────────────────────────────────────────────────────
const S = {
  pnl: 12480, booked: 8240, unrealized: 4240,
  trades: 14, typicalTrades: 9, lossBudget: 32, winRate: 62,
  hour: '14:00–15:00',
  hourRecord: { trades: 23, winRate: 20, pnl: -14270 },
  bestHour: '09:15–10:00',
};

const ALERTS = [
  { id: 1, name: 'Size escalation', tag: 'SIZE', sev: 'danger', cost: -2100, ago: '2h',
    line: 'BANKNIFTY 45500 PE at 100 lots, 4× your average, 8 min after a ₹2,600 loss.' },
  { id: 2, name: 'Early exit', tag: 'PACE', sev: 'caution', cost: -820, ago: '3h',
    line: 'NIFTY CE closed at +₹820 after 8 min. It continued to +₹2,100.' },
  { id: 3, name: 'No stop-loss', tag: 'RISK', sev: 'danger', cost: -3200, ago: '4h',
    line: 'FINNIFTY 19800 CE held 47 min with no stop.' },
];

const POS = [
  { sym: 'NIFTY 24500 CE', dir: 'BUY', qty: 50, entry: 108.5, ltp: 124.2, chg: 14.47, pnl: 785 },
  { sym: 'BANKNIFTY 51000 PE', dir: 'SELL', qty: 25, entry: 410.2, ltp: 396.1, chg: -3.44, pnl: -352 },
  { sym: 'FINNIFTY 19800 CE', dir: 'BUY', qty: 40, entry: 88.0, ltp: 92.45, chg: 5.06, pnl: 178 },
];

const CLOSED = [
  { sym: 'NIFTY 24400 CE', qty: 75, hold: '22m', pnl: 1455 },
  { sym: 'BANKNIFTY 50800 CE', qty: 50, hold: '1h 4m', pnl: -775 },
];

const inr = (n: number) => Math.abs(n).toLocaleString('en-IN');
const sgn = (n: number) => `${n > 0 ? '+' : n < 0 ? '−' : ''}₹${inr(n)}`;
const tone = (n: number) => (n > 0 ? 'text-profit' : n < 0 ? 'text-loss' : 'text-muted-foreground');
const SevIcon = ({ sev, className }: { sev: string; className?: string }) =>
  sev === 'danger' ? <AlertOctagon className={className} /> : <TriangleAlert className={className} />;

// ═══════════════════════════════════════════════════════════════════════════
// A — CALM
// Consumer-finance restraint: Monzo / Copilot Money. Generous line-height,
// one strong number, muted supporting text, soft dividers. Feels like an app
// that is on your side rather than an instrument panel.
// ═══════════════════════════════════════════════════════════════════════════
function Calm() {
  return (
    <div className="space-y-8">
      {/* The read — a sentence first, number second */}
      <section>
        <p className="t-label">Today, so far</p>
        <p className={cn('font-display text-[34px] sm:text-[40px] leading-none font-semibold tracking-tight font-tabular mt-2', tone(S.pnl))}>
          {sgn(S.pnl)}
        </p>
        <p className="text-[14px] text-muted-foreground leading-relaxed mt-3 max-w-[52ch]">
          <span className={tone(S.booked)}>{sgn(S.booked)}</span> booked and{' '}
          <span className={tone(S.unrealized)}>{sgn(S.unrealized)}</span> still open, over {S.trades} trades.
          That is <span className="text-foreground font-medium">{S.trades - S.typicalTrades} more than your usual day</span>,
          and you have used {S.lossBudget}% of the loss limit you set.
        </p>
      </section>

      {/* What to watch — decide, not describe */}
      <section className="rounded-lg bg-muted/40 p-5">
        <div className="flex items-start gap-3">
          <Clock className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
          <div className="min-w-0">
            <p className="text-[14px] font-medium text-foreground">
              You are in your weakest hour
            </p>
            <p className="text-[13.5px] text-muted-foreground leading-relaxed mt-1 font-tabular">
              Across {S.hourRecord.trades} trades in {S.hour}, you win {S.hourRecord.winRate}% and are down{' '}
              <span className="text-loss">{sgn(S.hourRecord.pnl)}</span>. Your {S.bestHour} hour is where the money is.
            </p>
          </div>
        </div>
      </section>

      {/* Alerts */}
      <section>
        <div className="flex items-baseline justify-between mb-3">
          <p className="t-label">What we noticed</p>
          <button className="text-[12.5px] text-primary hover:underline">All alerts</button>
        </div>
        <div className="space-y-4">
          {ALERTS.map(a => (
            <div key={a.id} className="flex gap-3">
              <SevIcon sev={a.sev} className={cn('h-4 w-4 shrink-0 mt-0.5', a.sev === 'danger' ? 'text-loss' : 'text-warning')} />
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-2 flex-wrap">
                  <span className="text-[14px] font-medium text-foreground">{a.name}</span>
                  <span className={cn('text-[13px] font-semibold font-tabular', tone(a.cost))}>{sgn(a.cost)}</span>
                  <span className="text-[12px] text-muted-foreground ml-auto">{a.ago} ago</span>
                </div>
                <p className="text-[13px] text-muted-foreground leading-relaxed mt-0.5">{a.line}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Positions */}
      <section>
        <div className="flex items-baseline justify-between mb-3">
          <p className="t-label">Still open · {POS.length}</p>
          <span className={cn('text-[13px] font-semibold font-tabular', tone(611))}>{sgn(611)}</span>
        </div>
        <div className="divide-y divide-border/70">
          {POS.map(p => (
            <div key={p.sym} className="flex items-center justify-between gap-3 py-3">
              <div className="min-w-0">
                <p className="text-[14px] text-foreground truncate">{p.sym}</p>
                <p className="text-[12px] text-muted-foreground font-tabular">
                  {p.dir === 'BUY' ? 'Bought' : 'Sold'} {p.qty} at {p.entry.toFixed(2)} · now {p.ltp.toFixed(2)}
                </p>
              </div>
              <div className="text-right shrink-0">
                <p className={cn('text-[14px] font-semibold font-tabular', tone(p.pnl))}>{sgn(p.pnl)}</p>
                <p className={cn('text-[12px] font-tabular', tone(p.chg))}>
                  {p.chg > 0 ? '+' : '−'}{Math.abs(p.chg).toFixed(2)}%
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <div className="flex items-baseline justify-between mb-3">
          <p className="t-label">Closed today · {CLOSED.length}</p>
          <span className={cn('text-[13px] font-semibold font-tabular', tone(680))}>{sgn(680)}</span>
        </div>
        <div className="divide-y divide-border/70">
          {CLOSED.map(c => (
            <div key={c.sym} className="flex items-center justify-between gap-3 py-3">
              <div className="min-w-0">
                <p className="text-[14px] text-foreground truncate">{c.sym}</p>
                <p className="text-[12px] text-muted-foreground font-tabular">{c.qty} · held {c.hold}</p>
              </div>
              <span className={cn('text-[14px] font-semibold font-tabular shrink-0', tone(c.pnl))}>{sgn(c.pnl)}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// B — BRIEFING
// The screen opens as a written read of the session, numbers inline in prose.
// Closest to what a coach would actually say. Supporting detail sits under it.
// ═══════════════════════════════════════════════════════════════════════════
function Briefing() {
  return (
    <div className="space-y-7">
      <section className="border-l-2 border-l-primary pl-5">
        <p className="t-label mb-2">Your session</p>
        <p className="text-[19px] sm:text-[21px] leading-[1.45] text-foreground max-w-[58ch]">
          You are <span className={cn('font-semibold font-tabular', tone(S.pnl))}>{sgn(S.pnl)}</span> up,
          but three behavioural patterns cost you{' '}
          <span className="font-semibold font-tabular text-loss">{sgn(-6120)}</span> along the way —
          and you have just entered the hour you lose most in.
        </p>
        <p className="text-[13.5px] text-muted-foreground font-tabular mt-3">
          {S.trades} trades · {S.winRate}% win rate · {S.lossBudget}% of loss limit used
        </p>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <section className="lg:col-span-2 space-y-4">
          <p className="t-label">The three patterns</p>
          {ALERTS.map(a => (
            <div key={a.id} className="rounded-lg border border-border p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                  <SevIcon sev={a.sev} className={cn('h-4 w-4 shrink-0', a.sev === 'danger' ? 'text-loss' : 'text-warning')} />
                  <span className="text-[14px] font-medium text-foreground truncate">{a.name}</span>
                </div>
                <span className={cn('text-[15px] font-semibold font-tabular shrink-0', tone(a.cost))}>{sgn(a.cost)}</span>
              </div>
              <p className="text-[13px] text-muted-foreground leading-relaxed mt-2">{a.line}</p>
            </div>
          ))}
        </section>

        <aside className="space-y-5">
          <div>
            <p className="t-label mb-2">Right now</p>
            <div className="rounded-lg bg-loss/5 border border-loss/20 p-4">
              <p className="text-[13px] text-foreground leading-relaxed">
                <span className="font-medium">{S.hour}</span> is your weakest window —{' '}
                <span className="font-tabular">{S.hourRecord.winRate}% win rate over {S.hourRecord.trades} trades</span>,{' '}
                <span className="text-loss font-tabular font-medium">{sgn(S.hourRecord.pnl)}</span> net.
              </p>
            </div>
          </div>
          <div>
            <p className="t-label mb-2">Open · {POS.length}</p>
            <div className="divide-y divide-border">
              {POS.map(p => (
                <div key={p.sym} className="flex items-center justify-between gap-2 py-2.5">
                  <span className="text-[13px] text-foreground truncate">{p.sym}</span>
                  <span className={cn('text-[13px] font-semibold font-tabular shrink-0', tone(p.pnl))}>{sgn(p.pnl)}</span>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// C — WORKSPACE
// Answers "the dashboard feels empty". Two columns on desktop: the session
// flow on the left, a standing context rail on the right. Single column and
// reordered on mobile. More on screen without becoming a card grid.
// ═══════════════════════════════════════════════════════════════════════════
function Workspace() {
  const Stat = ({ label, value, sub, cls }: { label: string; value: string; sub?: string; cls?: string }) => (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className={cn('text-[17px] font-semibold font-tabular mt-0.5', cls ?? 'text-foreground')}>{value}</p>
      {sub && <p className="text-[11.5px] text-muted-foreground font-tabular mt-0.5">{sub}</p>}
    </div>
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-6 lg:gap-8">
      {/* main flow */}
      <div className="space-y-6 min-w-0">
        <section>
          <div className="flex items-end justify-between gap-4 flex-wrap">
            <div>
              <p className="t-label">Day P&amp;L</p>
              <p className={cn('font-display text-[34px] leading-none font-semibold tracking-tight font-tabular mt-1.5', tone(S.pnl))}>
                {sgn(S.pnl)}
              </p>
            </div>
            <div className="grid grid-cols-3 gap-6">
              <Stat label="Booked" value={sgn(S.booked)} cls={tone(S.booked)} />
              <Stat label="Open" value={sgn(S.unrealized)} cls={tone(S.unrealized)} />
              <Stat label="Trades" value={String(S.trades)} sub={`usual ${S.typicalTrades}`} />
            </div>
          </div>
        </section>

        <section>
          <div className="flex items-baseline justify-between mb-3 pb-2 border-b border-border">
            <p className="t-label">Open positions · {POS.length}</p>
            <span className={cn('text-[13px] font-semibold font-tabular', tone(611))}>{sgn(611)}</span>
          </div>
          <div className="divide-y divide-border/70">
            {POS.map(p => (
              <div key={p.sym} className="flex items-center gap-3 py-2.5">
                <span className={cn('text-[10px] font-semibold w-9 shrink-0', p.dir === 'BUY' ? 'text-profit' : 'text-loss')}>{p.dir}</span>
                <span className="text-[13.5px] text-foreground truncate flex-1 min-w-0">{p.sym}</span>
                <span className="text-[12.5px] text-muted-foreground font-tabular hidden sm:block w-14 text-right">{p.qty}</span>
                <span className="text-[12.5px] text-muted-foreground font-tabular w-16 text-right">{p.ltp.toFixed(2)}</span>
                <span className={cn('text-[12.5px] font-tabular w-16 text-right', tone(p.chg))}>
                  {p.chg > 0 ? '+' : '−'}{Math.abs(p.chg).toFixed(2)}%
                </span>
                <span className={cn('text-[13.5px] font-semibold font-tabular w-20 text-right', tone(p.pnl))}>{sgn(p.pnl)}</span>
              </div>
            ))}
          </div>
        </section>

        <section>
          <div className="flex items-baseline justify-between mb-3 pb-2 border-b border-border">
            <p className="t-label">Closed today · {CLOSED.length}</p>
            <span className={cn('text-[13px] font-semibold font-tabular', tone(680))}>{sgn(680)}</span>
          </div>
          <div className="divide-y divide-border/70">
            {CLOSED.map(c => (
              <div key={c.sym} className="flex items-center gap-3 py-2.5">
                <span className="text-[13.5px] text-foreground truncate flex-1">{c.sym}</span>
                <span className="text-[12.5px] text-muted-foreground font-tabular">{c.hold}</span>
                <span className={cn('text-[13.5px] font-semibold font-tabular w-20 text-right', tone(c.pnl))}>{sgn(c.pnl)}</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* context rail */}
      <aside className="space-y-6 lg:border-l lg:border-border lg:pl-6">
        <div>
          <p className="t-label mb-2.5">Right now</p>
          <p className="text-[13px] text-foreground leading-relaxed">
            <span className="font-medium">{S.hour}</span> is your weakest hour.
          </p>
          <p className="text-[12.5px] text-muted-foreground font-tabular mt-1">
            {S.hourRecord.winRate}% win over {S.hourRecord.trades} trades · <span className="text-loss">{sgn(S.hourRecord.pnl)}</span>
          </p>
        </div>

        <div>
          <p className="t-label mb-2.5">Loss limit</p>
          <div className="flex items-baseline gap-2">
            <span className="text-[20px] font-semibold font-tabular text-foreground">{S.lossBudget}%</span>
            <span className="text-[12px] text-muted-foreground">used</span>
          </div>
          <div className="h-1 bg-muted mt-2 rounded-full overflow-hidden">
            <div className="h-full bg-warning rounded-full" style={{ width: `${S.lossBudget}%` }} />
          </div>
        </div>

        <div>
          <p className="t-label mb-2.5">Pace</p>
          <p className="text-[13px] text-foreground">
            <span className="font-tabular font-medium">{S.trades}</span> trades against a usual{' '}
            <span className="font-tabular">{S.typicalTrades}</span>.
          </p>
          <p className="text-[12.5px] text-warning mt-1">Faster than your rhythm.</p>
        </div>

        <div>
          <div className="flex items-baseline justify-between mb-2.5">
            <p className="t-label">Alerts · {ALERTS.length}</p>
            <span className="text-[12px] font-semibold font-tabular text-loss">{sgn(-6120)}</span>
          </div>
          <div className="space-y-2.5">
            {ALERTS.map(a => (
              <button key={a.id} className="w-full flex items-center gap-2 text-left group">
                <SevIcon sev={a.sev} className={cn('h-3.5 w-3.5 shrink-0', a.sev === 'danger' ? 'text-loss' : 'text-warning')} />
                <span className="text-[13px] text-foreground truncate flex-1 group-hover:text-primary transition-colors">{a.name}</span>
                <span className={cn('text-[12.5px] font-tabular', tone(a.cost))}>{sgn(a.cost)}</span>
              </button>
            ))}
          </div>
        </div>
      </aside>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// D — CARDS, DONE PROPERLY
// Surfaces kept, but with real hierarchy: the session card is visually
// dominant, supporting cards are quieter and smaller. Answers "empty" by
// filling the width at md+ rather than stacking four full-width blocks.
// ═══════════════════════════════════════════════════════════════════════════
function Cards() {
  return (
    <div className="space-y-4">
      {/* Dominant: the session */}
      <section className="rounded-lg border border-border bg-card p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0">
            <p className="t-label">Day P&amp;L</p>
            <p className={cn('font-display text-[36px] sm:text-[42px] leading-none font-semibold tracking-tight font-tabular mt-2', tone(S.pnl))}>
              {sgn(S.pnl)}
            </p>
            <p className="text-[13px] text-muted-foreground font-tabular mt-2">
              <span className={tone(S.booked)}>{sgn(S.booked)}</span> booked ·{' '}
              <span className={tone(S.unrealized)}>{sgn(S.unrealized)}</span> open · {S.trades} trades
            </p>
          </div>
          <div className="flex items-start gap-3 text-[13px] rounded-lg bg-loss/5 border border-loss/20 px-4 py-3 max-w-sm">
            <Clock className="h-4 w-4 text-loss shrink-0 mt-0.5" />
            <p className="text-foreground leading-relaxed">
              You are in <span className="font-medium">{S.hour}</span>, your weakest hour —{' '}
              <span className="font-tabular text-loss font-medium">{sgn(S.hourRecord.pnl)}</span> across {S.hourRecord.trades} trades.
            </p>
          </div>
        </div>
      </section>

      {/* Supporting: quieter, side by side at md+ */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <section className="rounded-lg border border-border bg-card">
          <div className="card-head">
            <span className="t-label">Patterns today · {ALERTS.length}</span>
            <span className="text-[12px] font-semibold font-tabular text-loss">{sgn(-6120)}</span>
          </div>
          <div className="px-4 sm:px-6 divide-y divide-border/70">
            {ALERTS.map(a => (
              <div key={a.id} className="flex items-center gap-2.5 py-3">
                <SevIcon sev={a.sev} className={cn('h-4 w-4 shrink-0', a.sev === 'danger' ? 'text-loss' : 'text-warning')} />
                <span className="text-[13.5px] text-foreground truncate flex-1">{a.name}</span>
                <span className={cn('text-[13px] font-semibold font-tabular', tone(a.cost))}>{sgn(a.cost)}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-border bg-card">
          <div className="card-head">
            <span className="t-label">Open · {POS.length}</span>
            <span className={cn('text-[12px] font-semibold font-tabular', tone(611))}>{sgn(611)}</span>
          </div>
          <div className="px-4 sm:px-6 divide-y divide-border/70">
            {POS.map(p => (
              <div key={p.sym} className="flex items-center gap-2.5 py-3">
                <span className="text-[13.5px] text-foreground truncate flex-1">{p.sym}</span>
                <span className={cn('text-[12px] font-tabular', tone(p.chg))}>
                  {p.chg > 0 ? '+' : '−'}{Math.abs(p.chg).toFixed(2)}%
                </span>
                <span className={cn('text-[13px] font-semibold font-tabular w-16 text-right', tone(p.pnl))}>{sgn(p.pnl)}</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="rounded-lg border border-border bg-card">
        <div className="card-head">
          <span className="t-label">Closed today · {CLOSED.length}</span>
          <span className={cn('text-[12px] font-semibold font-tabular', tone(680))}>{sgn(680)}</span>
        </div>
        <div className="px-4 sm:px-6 divide-y divide-border/70">
          {CLOSED.map(c => (
            <div key={c.sym} className="flex items-center gap-3 py-3">
              <span className="text-[13.5px] text-foreground truncate flex-1">{c.sym}</span>
              <span className="text-[12.5px] text-muted-foreground font-tabular">{c.hold}</span>
              <span className={cn('text-[13px] font-semibold font-tabular w-20 text-right', tone(c.pnl))}>{sgn(c.pnl)}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// E — TIMELINE
// The session as a chronology: what happened in order, with behaviour and
// trades on one thread. Nothing else here presents time as the spine, and
// for a reflection product that is arguably the honest structure.
// ═══════════════════════════════════════════════════════════════════════════
function Timeline() {
  const events = [
    { t: '09:18', kind: 'trade', label: 'NIFTY 24400 CE', detail: 'Bought 75 at 142.10', v: null as number | null },
    { t: '09:40', kind: 'close', label: 'NIFTY 24400 CE', detail: 'Closed after 22m', v: 1455 },
    { t: '11:02', kind: 'alert', label: 'Early exit', detail: 'Closed at +₹820. It continued to +₹2,100.', v: -820, sev: 'caution' },
    { t: '12:15', kind: 'close', label: 'BANKNIFTY 50800 CE', detail: 'Closed after 1h 4m', v: -775 },
    { t: '12:23', kind: 'alert', label: 'Size escalation', detail: '100 lots, 4× your average, 8 min after a loss.', v: -2100, sev: 'danger' },
    { t: '13:47', kind: 'alert', label: 'No stop-loss', detail: 'FINNIFTY 19800 CE held 47 min with no stop.', v: -3200, sev: 'danger' },
    { t: '14:05', kind: 'now', label: 'You are here', detail: `${S.hour} is your weakest hour — ${S.hourRecord.winRate}% win over ${S.hourRecord.trades} trades.`, v: null },
  ];

  return (
    <div className="space-y-7">
      <section>
        <p className="t-label">Today</p>
        <p className={cn('font-display text-[34px] leading-none font-semibold tracking-tight font-tabular mt-2', tone(S.pnl))}>
          {sgn(S.pnl)}
        </p>
        <p className="text-[13.5px] text-muted-foreground font-tabular mt-2">
          {S.trades} trades · {S.winRate}% win · behaviour cost{' '}
          <span className="text-loss font-medium">{sgn(-6120)}</span>
        </p>
      </section>

      <section>
        <p className="t-label mb-4">How it went</p>
        <div className="relative">
          <div className="absolute left-[52px] top-1 bottom-1 w-px bg-border" aria-hidden />
          <div className="space-y-5">
            {events.map((e, i) => (
              <div key={i} className="flex gap-4">
                <span className="text-[12px] text-muted-foreground font-tabular w-10 shrink-0 text-right pt-0.5">{e.t}</span>
                <span className="relative z-10 shrink-0 mt-1">
                  {e.kind === 'alert' ? (
                    <SevIcon sev={e.sev!} className={cn('h-4 w-4 bg-background', e.sev === 'danger' ? 'text-loss' : 'text-warning')} />
                  ) : e.kind === 'now' ? (
                    <span className="block h-4 w-4 rounded-full bg-background border-2 border-primary" />
                  ) : (
                    <span className={cn('block h-2 w-2 rounded-full mx-1 mt-1', e.kind === 'close' ? 'bg-muted-foreground' : 'bg-border')} />
                  )}
                </span>
                <div className="min-w-0 flex-1 pb-0.5">
                  <div className="flex items-baseline gap-2 flex-wrap">
                    <span className={cn('text-[14px]', e.kind === 'now' ? 'font-semibold text-primary' : 'font-medium text-foreground')}>
                      {e.label}
                    </span>
                    {e.v !== null && (
                      <span className={cn('text-[13px] font-semibold font-tabular', tone(e.v))}>{sgn(e.v)}</span>
                    )}
                  </div>
                  <p className="text-[13px] text-muted-foreground leading-relaxed mt-0.5">{e.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section>
        <div className="flex items-baseline justify-between mb-3">
          <p className="t-label">Still open · {POS.length}</p>
          <span className={cn('text-[13px] font-semibold font-tabular', tone(611))}>{sgn(611)}</span>
        </div>
        <div className="divide-y divide-border/70">
          {POS.map(p => (
            <div key={p.sym} className="flex items-center justify-between gap-3 py-2.5">
              <span className="text-[13.5px] text-foreground truncate">{p.sym}</span>
              <span className={cn('text-[13.5px] font-semibold font-tabular shrink-0', tone(p.pnl))}>{sgn(p.pnl)}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

// ── Lab shell ──────────────────────────────────────────────────────────────
const VARIANTS = [
  { id: 'calm',      label: 'A · Calm',      note: 'Consumer-finance restraint. Sentence first, number second.', el: <Calm /> },
  { id: 'briefing',  label: 'B · Briefing',  note: 'Opens as a written read of the session.',                     el: <Briefing /> },
  { id: 'workspace', label: 'C · Workspace', note: 'Two columns, standing context rail. Fills the width.',        el: <Workspace /> },
  { id: 'cards',     label: 'D · Cards',     note: 'Surfaces kept, but with real hierarchy and a 2-up row.',      el: <Cards /> },
  { id: 'timeline',  label: 'E · Timeline',  note: 'The session as a chronology. Behaviour and trades on one thread.', el: <Timeline /> },
] as const;

const WIDTHS = [
  { id: 'mobile',  label: 'Mobile 390', w: 390 },
  { id: 'tablet',  label: 'Tablet 768', w: 768 },
  { id: 'desktop', label: 'Full width', w: 0 },
] as const;

export default function DesignLab() {
  const [v, setV] = useState<string>('calm');
  const [w, setW] = useState<string>('mobile');
  const variant = VARIANTS.find(x => x.id === v) ?? VARIANTS[0];
  const width = WIDTHS.find(x => x.id === w) ?? WIDTHS[0];

  return (
    <div className="pb-20">
      <div className="flex flex-wrap items-center gap-x-1 gap-y-2 border-b border-border">
        {VARIANTS.map(x => (
          <button
            key={x.id}
            onClick={() => setV(x.id)}
            className={cn(
              'px-3 h-9 text-[12.5px] font-medium border-b-2 -mb-px transition-colors duration-150',
              v === x.id ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {x.label}
          </button>
        ))}
      </div>

      <div className="flex items-center justify-between gap-4 flex-wrap py-3">
        <p className="text-[12.5px] text-muted-foreground">{variant.note}</p>
        <div className="flex items-center gap-1">
          {WIDTHS.map(x => (
            <button
              key={x.id}
              onClick={() => setW(x.id)}
              className={cn(
                'px-2.5 h-7 rounded text-[11.5px] font-medium transition-colors duration-150',
                w === x.id ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {x.label}
            </button>
          ))}
        </div>
      </div>

      <div
        className={cn('mx-auto', width.w > 0 && 'border border-dashed border-border rounded-lg p-4')}
        style={width.w > 0 ? { width: width.w } : undefined}
      >
        {variant.el}
      </div>
    </div>
  );
}
