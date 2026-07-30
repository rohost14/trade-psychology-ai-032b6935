/**
 * DESIGN LAB — throwaway. Delete once a direction is chosen.
 *
 * Round 2. Feedback that shaped these: too much prose (especially heroes),
 * cards read as vibe-coded, C was the closest but felt plain and had no real
 * alerts section, and mobile was broken.
 *
 * So: no cards anywhere, numbers over sentences, a proper alert surface in
 * every variant, and mobile previewed in an IFRAME — Tailwind breakpoints
 * read the viewport, not a container, which is why the last preview lied.
 * The iframe gets its own viewport, so what you see is what a phone gets,
 * including the real bottom nav.
 *
 * Specs from docs/DESIGN_REFERENCES.md: Kite's 10px 12px cells, tabular
 * numerals, P&L column tint instead of zebra, four background levels, four
 * text tiers, 4px grid, radius 4 on chips and 8 max elsewhere, 44px tappable
 * rows on mobile.
 */
import { useSearchParams } from 'react-router-dom';
import { AlertOctagon, TriangleAlert, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import Sparkline from '@/components/ui/Sparkline';
import { cn } from '@/lib/utils';

// ── Shared data ────────────────────────────────────────────────────────────
const S = {
  pnl: 12480, booked: 8240, unrealized: 4240,
  trades: 14, typical: 9, lossUsed: 32, winRate: 62,
  hour: '14:00', hourWin: 20, hourPnl: -14270, hourTrades: 23,
  curve: [0, 1200, 900, 2400, 2100, 4800, 4200, 7100, 6400, 9200, 11800, 12480],
};

const ALERTS = [
  { id: 1, name: 'Size escalation', kind: 'SIZE', sev: 'danger', cost: -2100, at: '12:23',
    sym: 'BANKNIFTY 45500 PE', line: '100 lots, 4× your average, 8 min after a ₹2,600 loss', seen: false },
  { id: 2, name: 'No stop-loss', kind: 'RISK', sev: 'danger', cost: -3200, at: '13:47',
    sym: 'FINNIFTY 19800 CE', line: 'Held 47 min with no stop', seen: false },
  { id: 3, name: 'Early exit', kind: 'PACE', sev: 'caution', cost: -820, at: '11:02',
    sym: 'NIFTY 24400 CE', line: 'Closed at +₹820. It ran to +₹2,100', seen: true },
];

const POS = [
  { sym: 'NIFTY 24500 CE', dir: 'B', qty: 50, entry: 108.5, ltp: 124.2, chg: 14.47, pnl: 785, spark: [108, 110, 115, 112, 119, 121, 124] },
  { sym: 'BANKNIFTY 51000 PE', dir: 'S', qty: 25, entry: 410.2, ltp: 396.1, chg: -3.44, pnl: -352, spark: [410, 415, 408, 402, 399, 401, 396] },
  { sym: 'FINNIFTY 19800 CE', dir: 'B', qty: 40, entry: 88.0, ltp: 92.45, chg: 5.06, pnl: 178, spark: [88, 87, 89, 91, 90, 92, 92.4] },
];

const CLOSED = [
  { sym: 'NIFTY 24400 CE', qty: 75, hold: '22m', pnl: 1455 },
  { sym: 'BANKNIFTY 50800 CE', qty: 50, hold: '1h 4m', pnl: -775 },
];

const inr = (n: number) => Math.abs(n).toLocaleString('en-IN');
const sgn = (n: number) => `${n > 0 ? '+' : n < 0 ? '−' : ''}₹${inr(n)}`;
const tone = (n: number) => (n > 0 ? 'text-profit' : n < 0 ? 'text-loss' : 'text-muted-foreground');
const Sev = ({ s, c }: { s: string; c?: string }) =>
  s === 'danger' ? <AlertOctagon className={c} /> : <TriangleAlert className={c} />;

/** Kite's convention: the P&L column carries a permanent tint, not the row. */
const PNL_CELL = 'bg-muted/40';

// ═══════════════════════════════════════════════════════════════════════════
// F — RAIL   C rebuilt: real alert surface, numbers not prose, sparklines.
// ═══════════════════════════════════════════════════════════════════════════
function Rail() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-w-0 lg:border-r lg:border-border lg:pr-7">
        {/* hero: one number, one line, one shape */}
        <div className="flex items-end justify-between gap-6 pb-5 border-b border-border">
          <div>
            <p className="t-label">Day P&amp;L</p>
            <p className={cn('font-display text-[38px] leading-none font-semibold tracking-tight font-tabular mt-2', tone(S.pnl))}>
              {sgn(S.pnl)}
            </p>
            <p className="text-[12.5px] text-muted-foreground font-tabular mt-2">
              <span className={tone(S.booked)}>{sgn(S.booked)}</span> booked ·{' '}
              <span className={tone(S.unrealized)}>{sgn(S.unrealized)}</span> open
            </p>
          </div>
          <Sparkline data={S.curve} width={150} height={44} className="text-profit hidden sm:block shrink-0" />
        </div>

        {/* alerts — a real surface, dense, money-first */}
        <div className="pt-5">
          <div className="flex items-baseline justify-between pb-2">
            <p className="t-label">Behaviour today · {ALERTS.length}</p>
            <span className="text-[13px] font-semibold font-tabular text-loss">{sgn(-6120)}</span>
          </div>
          <div className="divide-y divide-border/60 border-y border-border">
            {ALERTS.map(a => (
              <button key={a.id} className="w-full flex items-center gap-3 py-3 text-left hover:bg-muted/40 transition-colors duration-150">
                <Sev s={a.sev} c={cn('h-4 w-4 shrink-0', a.sev === 'danger' ? 'text-loss' : 'text-warning')} />
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline gap-2">
                    <span className="text-[14px] font-medium text-foreground">{a.name}</span>
                    {!a.seen && <span className="h-1.5 w-1.5 rounded-full bg-primary shrink-0" />}
                    <span className="text-[11px] text-muted-foreground font-tabular ml-auto">{a.at}</span>
                  </span>
                  <span className="block text-[12.5px] text-muted-foreground truncate">{a.sym} · {a.line}</span>
                </span>
                <span className={cn('text-[14px] font-semibold font-tabular w-20 text-right shrink-0', tone(a.cost))}>{sgn(a.cost)}</span>
              </button>
            ))}
          </div>
        </div>

        {/* positions — Kite table spec */}
        <div className="pt-6">
          <div className="flex items-baseline justify-between pb-2">
            <p className="t-label">Open · {POS.length}</p>
            <span className={cn('text-[13px] font-semibold font-tabular', tone(611))}>{sgn(611)}</span>
          </div>
          <table className="w-full text-[13px] font-tabular border-t border-border">
            <thead>
              <tr className="text-[11px] text-muted-foreground">
                <th className="text-left font-normal py-2.5">Instrument</th>
                <th className="text-right font-normal py-2.5 hidden sm:table-cell">Qty</th>
                <th className="text-right font-normal py-2.5">LTP</th>
                <th className="text-right font-normal py-2.5 hidden sm:table-cell">Chg</th>
                <th className={cn('text-right font-normal py-2.5 px-3', PNL_CELL)}>P&amp;L</th>
              </tr>
            </thead>
            <tbody>
              {POS.map(p => (
                <tr key={p.sym} className="border-t border-border/60 hover:bg-muted/40">
                  <td className="py-2.5 pr-2">
                    <span className="flex items-center gap-2 min-w-0">
                      <span className={cn('text-[10px] font-semibold shrink-0', p.dir === 'B' ? 'text-profit' : 'text-loss')}>{p.dir}</span>
                      <span className="text-foreground truncate">{p.sym}</span>
                    </span>
                  </td>
                  <td className="py-2.5 text-right text-muted-foreground hidden sm:table-cell">{p.qty}</td>
                  <td className="py-2.5 text-right text-foreground">{p.ltp.toFixed(2)}</td>
                  <td className={cn('py-2.5 text-right hidden sm:table-cell', tone(p.chg))}>
                    {p.chg > 0 ? '+' : '−'}{Math.abs(p.chg).toFixed(2)}%
                  </td>
                  <td className={cn('py-2.5 px-3 text-right font-semibold', PNL_CELL, tone(p.pnl))}>{sgn(p.pnl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="pt-6 pb-2">
          <div className="flex items-baseline justify-between pb-2">
            <p className="t-label">Closed · {CLOSED.length}</p>
            <span className={cn('text-[13px] font-semibold font-tabular', tone(680))}>{sgn(680)}</span>
          </div>
          <div className="border-t border-border divide-y divide-border/60 text-[13px] font-tabular">
            {CLOSED.map(c => (
              <div key={c.sym} className="flex items-center gap-3 py-2.5">
                <span className="text-foreground truncate flex-1">{c.sym}</span>
                <span className="text-muted-foreground">{c.hold}</span>
                <span className={cn('font-semibold w-20 text-right', tone(c.pnl))}>{sgn(c.pnl)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* standing context rail */}
      <aside className="pt-6 lg:pt-0 lg:pl-7 space-y-6">
        <div>
          <p className="t-label pb-2">Right now</p>
          <p className="text-[26px] font-semibold font-tabular text-foreground leading-none">{S.hour}</p>
          <p className="text-[12.5px] text-muted-foreground mt-1.5 font-tabular">
            Your weakest hour · {S.hourWin}% win over {S.hourTrades} trades
          </p>
          <p className={cn('text-[15px] font-semibold font-tabular mt-1', tone(S.hourPnl))}>{sgn(S.hourPnl)} lifetime</p>
        </div>

        <div className="border-t border-border pt-5">
          <div className="flex items-baseline justify-between">
            <p className="t-label">Loss limit</p>
            <span className="text-[13px] font-semibold font-tabular text-foreground">{S.lossUsed}%</span>
          </div>
          <div className="h-1 bg-muted mt-2 overflow-hidden rounded-full">
            <div className="h-full bg-warning" style={{ width: `${S.lossUsed}%` }} />
          </div>
          <p className="text-[11.5px] text-muted-foreground font-tabular mt-1.5">₹8,000 of ₹25,000</p>
        </div>

        <div className="border-t border-border pt-5">
          <div className="flex items-baseline justify-between">
            <p className="t-label">Pace</p>
            <span className="text-[13px] font-semibold font-tabular text-warning">{S.trades} / {S.typical}</span>
          </div>
          <p className="text-[11.5px] text-muted-foreground mt-1.5">Faster than your usual day</p>
        </div>

        <div className="border-t border-border pt-5">
          <div className="flex items-baseline justify-between">
            <p className="t-label">Win rate</p>
            <span className="text-[13px] font-semibold font-tabular text-foreground">{S.winRate}%</span>
          </div>
          <p className="text-[11.5px] text-muted-foreground mt-1.5 font-tabular">9 of 14 closed green</p>
        </div>
      </aside>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// G — LEDGER   One chronological thread. Trades and behaviour interleaved,
//              read as a running account of the day. No prose block at all.
// ═══════════════════════════════════════════════════════════════════════════
function Ledger() {
  const rows = [
    { t: '09:18', k: 'open',  a: 'NIFTY 24400 CE', b: 'Bought 75 @ 142.10', v: null as number | null },
    { t: '09:40', k: 'close', a: 'NIFTY 24400 CE', b: 'Closed · 22m', v: 1455 },
    { t: '11:02', k: 'alert', a: 'Early exit', b: 'Closed at +₹820. It ran to +₹2,100', v: -820, sev: 'caution' },
    { t: '12:15', k: 'close', a: 'BANKNIFTY 50800 CE', b: 'Closed · 1h 4m', v: -775 },
    { t: '12:23', k: 'alert', a: 'Size escalation', b: '100 lots, 4× average, 8 min after a loss', v: -2100, sev: 'danger' },
    { t: '13:47', k: 'alert', a: 'No stop-loss', b: 'FINNIFTY 19800 CE held 47 min', v: -3200, sev: 'danger' },
    { t: '14:00', k: 'now',   a: 'Your weakest hour begins', b: `${S.hourWin}% win over ${S.hourTrades} trades · ${sgn(S.hourPnl)}`, v: null },
  ];

  return (
    <div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-border border-y border-border">
        {[
          ['Day P&L', sgn(S.pnl), tone(S.pnl)],
          ['Behaviour cost', sgn(-6120), 'text-loss'],
          ['Trades', `${S.trades}`, 'text-foreground'],
          ['Loss limit', `${S.lossUsed}%`, 'text-foreground'],
        ].map(([l, v, c]) => (
          <div key={l} className="bg-background px-3 py-3">
            <p className="t-label">{l}</p>
            <p className={cn('text-[20px] font-semibold font-tabular tracking-tight mt-1', c)}>{v}</p>
          </div>
        ))}
      </div>

      <p className="t-label pt-6 pb-1">The day, in order</p>
      <div className="border-t border-border">
        {rows.map((r, i) => (
          <div
            key={i}
            className={cn(
              'grid grid-cols-[46px_16px_minmax(0,1fr)_auto] items-baseline gap-x-3 py-3 border-b border-border/60',
              r.k === 'now' && 'bg-primary/5',
            )}
          >
            <span className="text-[12px] text-muted-foreground font-tabular">{r.t}</span>
            <span className="flex items-center h-4">
              {r.k === 'alert'
                ? <Sev s={r.sev!} c={cn('h-3.5 w-3.5', r.sev === 'danger' ? 'text-loss' : 'text-warning')} />
                : r.k === 'now'
                  ? <span className="h-2 w-2 rounded-full bg-primary" />
                  : r.k === 'close'
                    ? (r.v! > 0 ? <ArrowUpRight className="h-3.5 w-3.5 text-profit" /> : <ArrowDownRight className="h-3.5 w-3.5 text-loss" />)
                    : <span className="h-1.5 w-1.5 rounded-full bg-border" />}
            </span>
            <span className="min-w-0">
              <span className={cn('text-[14px] block truncate', r.k === 'now' ? 'font-semibold text-primary' : 'font-medium text-foreground')}>{r.a}</span>
              <span className="text-[12.5px] text-muted-foreground block truncate font-tabular">{r.b}</span>
            </span>
            <span className={cn('text-[14px] font-semibold font-tabular tabular-nums', r.v === null ? 'text-transparent' : tone(r.v))}>
              {r.v === null ? '—' : sgn(r.v)}
            </span>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 pt-6">
        <div>
          <p className="t-label pb-2">Still open · {POS.length}</p>
          <div className="border-t border-border divide-y divide-border/60 text-[13px] font-tabular">
            {POS.map(p => (
              <div key={p.sym} className="flex items-center gap-3 py-2.5">
                <span className="text-foreground truncate flex-1">{p.sym}</span>
                <Sparkline data={p.spark} width={44} height={14} className={cn('shrink-0', tone(p.pnl))} />
                <span className={cn('font-semibold w-20 text-right', tone(p.pnl))}>{sgn(p.pnl)}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="pt-6 sm:pt-0">
          <p className="t-label pb-2">Closed · {CLOSED.length}</p>
          <div className="border-t border-border divide-y divide-border/60 text-[13px] font-tabular">
            {CLOSED.map(c => (
              <div key={c.sym} className="flex items-center gap-3 py-2.5">
                <span className="text-foreground truncate flex-1">{c.sym}</span>
                <span className="text-muted-foreground">{c.hold}</span>
                <span className={cn('font-semibold w-20 text-right', tone(c.pnl))}>{sgn(c.pnl)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// H — BANDS   Full-bleed horizontal bands, hairline-separated, each a
//             different density. No container ever. Width used by the band.
// ═══════════════════════════════════════════════════════════════════════════
function Bands() {
  return (
    <div className="-mx-4 sm:-mx-6 lg:-mx-8">
      {/* band 1 — the number */}
      <div className="px-4 sm:px-6 lg:px-8 py-6 border-b border-border">
        <div className="flex flex-wrap items-end justify-between gap-x-10 gap-y-5">
          <div>
            <p className="t-label">Day P&amp;L</p>
            <p className={cn('font-display text-[42px] sm:text-[52px] leading-[0.95] font-semibold tracking-tight font-tabular mt-1.5', tone(S.pnl))}>
              {sgn(S.pnl)}
            </p>
          </div>
          <div className="flex items-end gap-8 font-tabular">
            {[
              ['Booked', sgn(S.booked), tone(S.booked)],
              ['Open', sgn(S.unrealized), tone(S.unrealized)],
              ['Trades', `${S.trades}`, 'text-foreground'],
              ['Win rate', `${S.winRate}%`, 'text-foreground'],
            ].map(([l, v, c]) => (
              <div key={l}>
                <p className="t-label">{l}</p>
                <p className={cn('text-[17px] font-semibold mt-1', c)}>{v}</p>
              </div>
            ))}
            <Sparkline data={S.curve} width={130} height={38} className="text-profit hidden md:block" />
          </div>
        </div>
      </div>

      {/* band 2 — the one thing to know, accent-tinted */}
      <div className="px-4 sm:px-6 lg:px-8 py-4 bg-loss/5 border-b border-border">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="t-label text-loss">Right now</span>
          <p className="text-[14px] text-foreground">
            {S.hour} is your weakest hour.
          </p>
          <p className="text-[13px] text-muted-foreground font-tabular">
            {S.hourWin}% win over {S.hourTrades} trades · <span className="text-loss font-medium">{sgn(S.hourPnl)}</span> lifetime
          </p>
        </div>
      </div>

      {/* band 3 — alerts */}
      <div className="px-4 sm:px-6 lg:px-8 py-5 border-b border-border">
        <div className="flex items-baseline justify-between pb-2">
          <p className="t-label">Behaviour today · {ALERTS.length}</p>
          <span className="text-[13px] font-semibold font-tabular text-loss">{sgn(-6120)}</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-border border border-border">
          {ALERTS.map(a => (
            <button key={a.id} className="bg-background px-3 py-3 text-left hover:bg-muted/40 transition-colors duration-150">
              <span className="flex items-center gap-2">
                <Sev s={a.sev} c={cn('h-3.5 w-3.5 shrink-0', a.sev === 'danger' ? 'text-loss' : 'text-warning')} />
                <span className="text-[13.5px] font-medium text-foreground truncate flex-1">{a.name}</span>
                <span className={cn('text-[13.5px] font-semibold font-tabular', tone(a.cost))}>{sgn(a.cost)}</span>
              </span>
              <span className="block text-[12px] text-muted-foreground mt-1 truncate">{a.sym} · {a.line}</span>
            </button>
          ))}
        </div>
      </div>

      {/* band 4 — positions */}
      <div className="px-4 sm:px-6 lg:px-8 py-5">
        <div className="flex items-baseline justify-between pb-2">
          <p className="t-label">Open · {POS.length}</p>
          <span className={cn('text-[13px] font-semibold font-tabular', tone(611))}>{sgn(611)}</span>
        </div>
        <table className="w-full text-[13px] font-tabular border-t border-border">
          <tbody>
            {POS.map(p => (
              <tr key={p.sym} className="border-b border-border/60 hover:bg-muted/40">
                <td className="py-2.5 pr-2">
                  <span className="flex items-center gap-2">
                    <span className={cn('text-[10px] font-semibold', p.dir === 'B' ? 'text-profit' : 'text-loss')}>{p.dir}</span>
                    <span className="text-foreground truncate">{p.sym}</span>
                  </span>
                </td>
                <td className="py-2.5 text-right text-muted-foreground hidden sm:table-cell">{p.qty}</td>
                <td className="py-2.5 text-right text-foreground">{p.ltp.toFixed(2)}</td>
                <td className={cn('py-2.5 px-3 text-right font-semibold', PNL_CELL, tone(p.pnl))}>{sgn(p.pnl)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// I — INDEX   Left column is a fixed key/label column, right is the value
//             field. Reads like a statement. Extremely quiet, no boxes.
// ═══════════════════════════════════════════════════════════════════════════
function Index() {
  const Row = ({ label, children, tall }: { label: string; children: React.ReactNode; tall?: boolean }) => (
    <div className={cn('grid grid-cols-1 sm:grid-cols-[128px_minmax(0,1fr)] gap-x-6 gap-y-1 border-t border-border', tall ? 'py-5' : 'py-3.5')}>
      <p className="t-label sm:pt-1">{label}</p>
      <div className="min-w-0">{children}</div>
    </div>
  );

  return (
    <div>
      <Row label="Day P&L" tall>
        <div className="flex items-end justify-between gap-6 flex-wrap">
          <div>
            <p className={cn('font-display text-[36px] leading-none font-semibold tracking-tight font-tabular', tone(S.pnl))}>{sgn(S.pnl)}</p>
            <p className="text-[12.5px] text-muted-foreground font-tabular mt-1.5">
              <span className={tone(S.booked)}>{sgn(S.booked)}</span> booked · <span className={tone(S.unrealized)}>{sgn(S.unrealized)}</span> open
            </p>
          </div>
          <Sparkline data={S.curve} width={140} height={40} className="text-profit shrink-0" />
        </div>
      </Row>

      <Row label="Right now">
        <p className="text-[14px] text-foreground">
          <span className="font-tabular font-semibold">{S.hour}</span> — your weakest hour
        </p>
        <p className="text-[12.5px] text-muted-foreground font-tabular mt-0.5">
          {S.hourWin}% win over {S.hourTrades} trades · <span className="text-loss">{sgn(S.hourPnl)}</span> lifetime
        </p>
      </Row>

      <Row label="Session">
        <div className="flex flex-wrap gap-x-8 gap-y-2 font-tabular text-[13px]">
          <span className="text-muted-foreground">Trades <span className="text-foreground font-semibold ml-1">{S.trades}</span> <span className="text-[11.5px]">usual {S.typical}</span></span>
          <span className="text-muted-foreground">Win rate <span className="text-foreground font-semibold ml-1">{S.winRate}%</span></span>
          <span className="text-muted-foreground">Loss limit <span className="text-warning font-semibold ml-1">{S.lossUsed}%</span></span>
        </div>
      </Row>

      <Row label={`Behaviour · ${ALERTS.length}`}>
        <div className="divide-y divide-border/60">
          {ALERTS.map(a => (
            <button key={a.id} className="w-full flex items-center gap-3 py-2.5 first:pt-0 text-left group">
              <Sev s={a.sev} c={cn('h-3.5 w-3.5 shrink-0', a.sev === 'danger' ? 'text-loss' : 'text-warning')} />
              <span className="min-w-0 flex-1">
                <span className="text-[13.5px] font-medium text-foreground group-hover:text-primary transition-colors">{a.name}</span>
                <span className="block text-[12px] text-muted-foreground truncate">{a.sym} · {a.line}</span>
              </span>
              <span className={cn('text-[13.5px] font-semibold font-tabular shrink-0', tone(a.cost))}>{sgn(a.cost)}</span>
            </button>
          ))}
        </div>
      </Row>

      <Row label={`Open · ${POS.length}`}>
        <div className="divide-y divide-border/60 text-[13px] font-tabular">
          {POS.map(p => (
            <div key={p.sym} className="flex items-center gap-3 py-2.5 first:pt-0">
              <span className={cn('text-[10px] font-semibold shrink-0', p.dir === 'B' ? 'text-profit' : 'text-loss')}>{p.dir}</span>
              <span className="text-foreground truncate flex-1">{p.sym}</span>
              <span className="text-muted-foreground hidden sm:inline">{p.ltp.toFixed(2)}</span>
              <Sparkline data={p.spark} width={40} height={14} className={cn('shrink-0 hidden sm:block', tone(p.pnl))} />
              <span className={cn('font-semibold w-20 text-right', tone(p.pnl))}>{sgn(p.pnl)}</span>
            </div>
          ))}
        </div>
      </Row>

      <Row label={`Closed · ${CLOSED.length}`}>
        <div className="divide-y divide-border/60 text-[13px] font-tabular">
          {CLOSED.map(c => (
            <div key={c.sym} className="flex items-center gap-3 py-2.5 first:pt-0">
              <span className="text-foreground truncate flex-1">{c.sym}</span>
              <span className="text-muted-foreground">{c.hold}</span>
              <span className={cn('font-semibold w-20 text-right', tone(c.pnl))}>{sgn(c.pnl)}</span>
            </div>
          ))}
        </div>
      </Row>
      <div className="border-t border-border" />
    </div>
  );
}

// ── Registry ───────────────────────────────────────────────────────────────
const VARIANTS: Record<string, { label: string; note: string; el: JSX.Element }> = {
  rail:   { label: 'F · Rail',   note: 'C rebuilt — real alert surface, sparklines, numbers over prose.', el: <Rail /> },
  ledger: { label: 'G · Ledger', note: 'One chronological thread. Trades and behaviour interleaved.',     el: <Ledger /> },
  bands:  { label: 'H · Bands',  note: 'Full-bleed horizontal bands, each a different density.',          el: <Bands /> },
  index:  { label: 'I · Index',  note: 'Label column left, values right. Reads like a statement.',        el: <Index /> },
};

const WIDTHS = [
  { id: 'mobile',  label: 'iPhone 390', w: 390, h: 780 },
  { id: 'tablet',  label: 'Tablet 834', w: 834, h: 720 },
  { id: 'desktop', label: 'Desktop',    w: 0,   h: 0 },
] as const;

export default function DesignLab() {
  const [params, setParams] = useSearchParams();
  const v = params.get('v') ?? 'rail';
  const bare = params.get('bare') === '1';
  const width = params.get('w') ?? 'mobile';
  const variant = VARIANTS[v] ?? VARIANTS.rail;

  // Rendered inside the iframe: variant only, real app chrome around it.
  if (bare) return <div className="pb-10">{variant.el}</div>;

  const dev = WIDTHS.find(x => x.id === width) ?? WIDTHS[0];
  const set = (k: string, val: string) => {
    const next = new URLSearchParams(params);
    next.set(k, val);
    setParams(next, { replace: true });
  };

  return (
    <div className="pb-16">
      <div className="flex flex-wrap items-center gap-x-1 gap-y-2 border-b border-border">
        {Object.entries(VARIANTS).map(([id, x]) => (
          <button
            key={id}
            onClick={() => set('v', id)}
            className={cn(
              'px-3 h-9 text-[12.5px] font-medium border-b-2 -mb-px transition-colors duration-150',
              v === id ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground',
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
              onClick={() => set('w', x.id)}
              className={cn(
                'px-2.5 h-7 rounded text-[11.5px] font-medium transition-colors duration-150',
                width === x.id ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {x.label}
            </button>
          ))}
        </div>
      </div>

      {dev.w > 0 ? (
        // An iframe has its own viewport, so media queries resolve at the real
        // device width. A container cannot do this, which is why the previous
        // mobile preview was wrong.
        <iframe
          key={`${v}-${dev.id}`}
          title={`${variant.label} at ${dev.label}`}
          src={`/design-lab?bare=1&v=${v}`}
          style={{ width: dev.w, height: dev.h }}
          className="mx-auto block border border-border rounded-lg bg-background"
        />
      ) : (
        variant.el
      )}
    </div>
  );
}
