/**
 * DASHBOARD VARIANTS — throwaway. Delete once a direction is chosen.
 *
 * Tab 0 reproduces today's Dashboard faithfully so the other three read as
 * deltas against it rather than as unrelated designs.
 *
 * Three defects are being fixed, in different combinations:
 *
 *   STRETCHED  Today a position row puts the symbol near x=300 and the P&L
 *              near x=1490. Kite never distributes columns across the full
 *              width; it caps content and clusters the numeric block right.
 *   FLAT       Two background levels (page, card). Linear uses four, about
 *              four luminance points apart. Depth comes from layered
 *              surfaces, not from shadow or gloss.
 *   ALL CARDS  Alerts stay cards, because an alert is a discrete event that
 *              arrives. Positions and trades are continuous data and belong
 *              in a table.
 *
 * Palette moves are declared as token overrides on each variant root, so the
 * existing semantic classes re-skin automatically and nothing leaks.
 */
import { useSearchParams } from 'react-router-dom';
import { AlertOctagon, TriangleAlert, ChevronDown } from 'lucide-react';
import Sparkline from '@/components/ui/Sparkline';
import { cn } from '@/lib/utils';

// ── Sample data, shaped like the real API ──────────────────────────────────
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
  { sym: 'NIFTY 24500 CE', dir: 'B', qty: 50, entry: 108.5, ltp: 124.2, chg: 14.47, pnl: 785 },
  { sym: 'BANKNIFTY 51000 PE', dir: 'S', qty: 25, entry: 410.2, ltp: 396.1, chg: -3.44, pnl: -352 },
  { sym: 'FINNIFTY 19800 CE', dir: 'B', qty: 40, entry: 88.0, ltp: 92.45, chg: 5.06, pnl: 178 },
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

/* ── Palette moves ─────────────────────────────────────────────────────────
   Neutrals get a warm tint rather than staying blue-grey, per the finding
   that every calm reference tints its greys and none uses pure values. Two
   extra surface levels give the depth that two levels cannot.               */
const WARM_DEPTH = {
  '--layer-page': '17 17 19',        // #111113  page, one step down
  '--layer-surface': '25 25 28',     // #19191C  panel
  '--layer-overlay': '31 31 34',     // #1F1F22  inset / table header
  '--layer-border': '46 46 51',      // #2E2E33  region edge, stronger
  '--layer-border-subtle': '33 33 37', // #212125 row divider, weaker
  '--muted-foreground': '150 148 145', // warm-shifted secondary text
} as React.CSSProperties;

/** Shared alert card. Discrete arrivals earn a surface; this never changes. */
function AlertCard({ a, inset }: { a: typeof ALERTS[number]; inset?: boolean }) {
  return (
    <article
      className={cn(
        'relative rounded-lg border overflow-hidden cursor-pointer transition-colors duration-150',
        inset ? 'bg-[rgb(var(--layer-overlay))]' : 'bg-card',
        a.sev === 'danger' ? 'border-loss/25 hover:border-loss/40' : 'border-warning/25 hover:border-warning/40',
      )}
    >
      <span aria-hidden className={cn('absolute inset-y-0 left-0 w-[3px]', a.sev === 'danger' ? 'bg-loss' : 'bg-warning')} />
      <div className="pl-4 pr-3.5 py-3">
        <div className="flex items-start gap-2.5">
          <Sev s={a.sev} c={cn('h-4 w-4 shrink-0 mt-0.5', a.sev === 'danger' ? 'text-loss' : 'text-warning')} />
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-2">
              <h3 className="text-[14px] font-semibold text-foreground">{a.name}</h3>
              {!a.seen && <span className="h-1.5 w-1.5 rounded-full bg-primary shrink-0" />}
              <span className="text-[11px] text-muted-foreground font-tabular ml-auto shrink-0">{a.at}</span>
            </div>
            <p className="text-[12.5px] text-muted-foreground leading-snug mt-1">{a.line}</p>
            <div className="flex items-center gap-2 mt-2">
              <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-muted text-muted-foreground">{a.kind}</span>
              <span className="text-[11.5px] text-muted-foreground font-tabular truncate">{a.sym}</span>
              <span className={cn('text-[15px] font-semibold font-tabular ml-auto shrink-0', tone(a.cost))}>{sgn(a.cost)}</span>
            </div>
          </div>
        </div>
      </div>
    </article>
  );
}

/**
 * Table with the numeric block CLUSTERED right rather than distributed.
 * This is the actual fix for "stretched": the instrument takes the slack,
 * the numbers stay together and the eye travels once, not five times.
 */
function DataTable({ cols, widths, rows, tintHeader }: {
  cols: string[]; widths: string; rows: React.ReactNode; tintHeader?: boolean;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13px] font-tabular min-w-[440px]">
        <thead>
          <tr className={cn('text-[11px] text-muted-foreground', tintHeader && 'bg-[rgb(var(--layer-overlay))]')}>
            {cols.map((c, i) => (
              <th key={c} className={cn('font-normal py-2 px-3 whitespace-nowrap', i === 0 ? 'text-left pl-3' : 'text-right')}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody style={{ ...({ '--w': widths } as React.CSSProperties) }}>{rows}</tbody>
      </table>
    </div>
  );
}

const Td = ({ children, className, muted }: { children: React.ReactNode; className?: string; muted?: boolean }) => (
  <td className={cn('py-2.5 px-3 text-right whitespace-nowrap', muted && 'text-muted-foreground', className)}>{children}</td>
);

const PosRows = () => (
  <>
    {POS.map(p => (
      <tr key={p.sym} className="border-t border-[rgb(var(--layer-border-subtle))] hover:bg-[rgb(var(--layer-overlay))] cursor-pointer">
        <td className="py-2.5 pl-3 pr-3 text-left w-full">
          <span className="flex items-center gap-2 min-w-0">
            <span className={cn('text-[9px] font-bold px-1 py-0.5 rounded leading-none shrink-0',
              p.dir === 'B' ? 'bg-profit/10 text-profit' : 'bg-loss/10 text-loss')}>{p.dir === 'B' ? 'BUY' : 'SELL'}</span>
            <span className="text-foreground truncate">{p.sym}</span>
          </span>
        </td>
        <Td muted>{p.qty}</Td>
        <Td muted>{p.entry.toFixed(2)}</Td>
        <Td>{p.ltp.toFixed(2)}</Td>
        <Td className={tone(p.chg)}>{p.chg > 0 ? '+' : '−'}{Math.abs(p.chg).toFixed(2)}%</Td>
        <Td className={cn('font-semibold', tone(p.pnl))}>{sgn(p.pnl)}</Td>
      </tr>
    ))}
  </>
);

const ClosedRows = () => (
  <>
    {CLOSED.map(c => (
      <tr key={c.sym} className="border-t border-[rgb(var(--layer-border-subtle))] hover:bg-[rgb(var(--layer-overlay))] cursor-pointer">
        <td className="py-2.5 pl-3 pr-3 text-left w-full text-foreground truncate">{c.sym}</td>
        <Td muted>{c.qty}</Td>
        <Td muted>{c.hold}</Td>
        <Td className={cn('font-semibold', tone(c.pnl))}>{sgn(c.pnl)}</Td>
      </tr>
    ))}
  </>
);

const SectionHead = ({ title, right }: { title: string; right?: React.ReactNode }) => (
  <div className="flex items-baseline justify-between pb-2">
    <h2 className="t-label">{title}</h2>
    {right}
  </div>
);

// ═══════════════════════════════════════════════════════════════════════════
// 0 — CURRENT   Today's Dashboard, reproduced. The control.
// ═══════════════════════════════════════════════════════════════════════════
function Current() {
  return (
    <div className="space-y-5">
      <section className="desk-card overflow-hidden">
        <div className="card-head"><span className="t-label">Day P&amp;L</span>
          <span className="text-[11px] text-muted-foreground">Session stats ▾</span></div>
        <div className="px-4 sm:px-6 py-4">
          <p className={cn('font-display text-[30px] leading-none font-semibold tracking-tight font-tabular', tone(S.pnl))}>{sgn(S.pnl)}</p>
          <p className="text-[12.5px] text-muted-foreground font-tabular mt-1">
            Booked <span className={tone(S.booked)}>{sgn(S.booked)}</span> · Unrealized <span className={tone(S.unrealized)}>{sgn(S.unrealized)}</span>
          </p>
        </div>
      </section>

      <section className="desk-card overflow-hidden">
        <div className="card-head"><span className="t-label">Live alerts</span>
          <span className="text-[11px] font-medium uppercase tracking-wider text-primary">View all →</span></div>
        <div className="divide-y divide-border">
          {ALERTS.map(a => (
            <div key={a.id} className={cn('flex items-start gap-3 px-4 sm:px-6 py-3.5 border-l-2', a.sev === 'danger' ? 'border-l-loss' : 'border-l-warning')}>
              <Sev s={a.sev} c={cn('h-4 w-4 shrink-0 mt-0.5', a.sev === 'danger' ? 'text-loss' : 'text-warning')} />
              <div className="min-w-0 flex-1">
                <p className="text-[14px] font-medium text-foreground">{a.name}</p>
                <p className="text-[12.5px] text-muted-foreground mt-0.5">{a.sym} · {a.line}</p>
              </div>
              <span className="text-[11px] text-muted-foreground shrink-0">{a.at}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="desk-card overflow-hidden">
        <div className="card-head"><span className="t-label">Open positions · {POS.length}</span>
          <span className={cn('text-[13px] font-semibold font-tabular', tone(611))}>{sgn(611)}</span></div>
        <div className="px-4 sm:px-6">
          <table className="w-full text-[13px] font-tabular">
            <thead><tr className="text-[10px] uppercase tracking-wider text-muted-foreground">
              <th className="text-left font-medium py-3">Symbol</th><th className="text-right font-medium py-3">Qty</th>
              <th className="text-right font-medium py-3">Entry</th><th className="text-right font-medium py-3">LTP</th>
              <th className="text-right font-medium py-3">Chg%</th><th className="text-right font-medium py-3">P&amp;L</th>
            </tr></thead>
            <tbody>{POS.map(p => (
              <tr key={p.sym} className="border-t border-border">
                <td className="py-3.5 text-foreground">{p.sym}</td>
                <td className="py-3.5 text-right text-muted-foreground">{p.qty}</td>
                <td className="py-3.5 text-right text-muted-foreground">{p.entry.toFixed(2)}</td>
                <td className="py-3.5 text-right text-foreground">{p.ltp.toFixed(2)}</td>
                <td className={cn('py-3.5 text-right', tone(p.chg))}>{p.chg > 0 ? '+' : '−'}{Math.abs(p.chg).toFixed(2)}%</td>
                <td className={cn('py-3.5 text-right font-semibold', tone(p.pnl))}>{sgn(p.pnl)}</td>
              </tr>))}</tbody>
          </table>
        </div>
      </section>

      <section className="desk-card overflow-hidden">
        <div className="card-head"><span className="t-label">Closed positions today</span>
          <span className={cn('text-[13px] font-semibold font-tabular', tone(680))}>{sgn(680)}</span></div>
        <div className="px-4 sm:px-6 divide-y divide-border">
          {CLOSED.map(c => (
            <div key={c.sym} className="flex items-center gap-3 py-3.5 text-[13px] font-tabular">
              <span className="text-foreground truncate flex-1">{c.sym}</span>
              <span className="text-muted-foreground">{c.hold}</span>
              <span className={cn('font-semibold w-20 text-right', tone(c.pnl))}>{sgn(c.pnl)}</span>
            </div>))}
        </div>
      </section>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 1 — TIGHT   Same single column. Content capped so nothing spans, numbers
//             clustered right, tables lose their cards, alerts keep theirs.
//             Warm neutrals and a third surface level for depth.
// ═══════════════════════════════════════════════════════════════════════════
function Tight() {
  return (
    <div style={WARM_DEPTH} className="max-w-[820px]">
      <div className="flex items-end justify-between gap-6 pb-4 border-b border-border">
        <div>
          <p className="t-label">Day P&amp;L</p>
          <p className={cn('font-display text-[32px] leading-none font-semibold tracking-tight font-tabular mt-1.5', tone(S.pnl))}>{sgn(S.pnl)}</p>
          <p className="text-[12.5px] text-muted-foreground font-tabular mt-1.5">
            <span className={tone(S.booked)}>{sgn(S.booked)}</span> booked · <span className={tone(S.unrealized)}>{sgn(S.unrealized)}</span> open · {S.trades} trades · {S.winRate}% won
          </p>
        </div>
        <Sparkline data={S.curve} width={116} height={36} className="text-profit shrink-0 hidden sm:block" />
      </div>

      <div className="pt-6">
        <SectionHead title={`Live alerts · ${ALERTS.length}`} right={<span className="text-[13px] font-semibold font-tabular text-loss">{sgn(-6120)}</span>} />
        <div className="space-y-2.5">{ALERTS.map(a => <AlertCard key={a.id} a={a} />)}</div>
      </div>

      <div className="pt-6">
        <SectionHead title={`Open · ${POS.length}`} right={<span className={cn('text-[13px] font-semibold font-tabular', tone(611))}>{sgn(611)}</span>} />
        <div className="rounded-lg border border-border overflow-hidden bg-card">
          <DataTable tintHeader cols={['Instrument', 'Qty', 'Avg', 'LTP', 'Chg', 'P&L']} widths="" rows={<PosRows />} />
        </div>
      </div>

      <div className="pt-5 pb-2">
        <SectionHead title={`Closed today · ${CLOSED.length}`} right={<span className={cn('text-[13px] font-semibold font-tabular', tone(680))}>{sgn(680)}</span>} />
        <div className="rounded-lg border border-border overflow-hidden bg-card">
          <DataTable tintHeader cols={['Instrument', 'Qty', 'Hold', 'Net']} widths="" rows={<ClosedRows />} />
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 2 — TWO-UP   Width used rather than spanned. Alerts left as cards, data
//              right as tables. Neither column is wide enough to stretch.
// ═══════════════════════════════════════════════════════════════════════════
function TwoUp() {
  return (
    <div style={WARM_DEPTH}>
      <div className="flex flex-wrap items-end justify-between gap-6 pb-4 mb-6 border-b border-border">
        <div>
          <p className="t-label">Day P&amp;L</p>
          <p className={cn('font-display text-[34px] leading-none font-semibold tracking-tight font-tabular mt-1.5', tone(S.pnl))}>{sgn(S.pnl)}</p>
        </div>
        <div className="flex items-end gap-7 font-tabular">
          {[['Booked', sgn(S.booked), tone(S.booked)], ['Open', sgn(S.unrealized), tone(S.unrealized)],
            ['Trades', `${S.trades}`, 'text-foreground'], ['Won', `${S.winRate}%`, 'text-foreground']].map(([l, v, c]) => (
            <div key={l}><p className="t-label">{l}</p><p className={cn('text-[16px] font-semibold mt-1', c)}>{v}</p></div>
          ))}
          <Sparkline data={S.curve} width={110} height={34} className="text-profit hidden lg:block" />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)] gap-x-8 gap-y-7">
        <div>
          <SectionHead title={`Live alerts · ${ALERTS.length}`} right={<span className="text-[13px] font-semibold font-tabular text-loss">{sgn(-6120)}</span>} />
          <div className="space-y-2.5">{ALERTS.map(a => <AlertCard key={a.id} a={a} />)}</div>
          <div className="mt-6 pt-5 border-t border-border grid grid-cols-2 gap-5">
            <div>
              <div className="flex items-baseline justify-between"><p className="t-label">Right now</p>
                <span className="text-[13px] font-semibold font-tabular text-foreground">{S.hour}</span></div>
              <p className="text-[11.5px] text-muted-foreground mt-1 font-tabular">Weakest hour · {sgn(S.hourPnl)}</p>
            </div>
            <div>
              <div className="flex items-baseline justify-between"><p className="t-label">Loss limit</p>
                <span className="text-[13px] font-semibold font-tabular text-foreground">{S.lossUsed}%</span></div>
              <div className="h-1 bg-muted mt-2 rounded-full overflow-hidden"><div className="h-full bg-warning" style={{ width: `${S.lossUsed}%` }} /></div>
            </div>
          </div>
        </div>

        <div className="min-w-0 space-y-6">
          <div>
            <SectionHead title={`Open · ${POS.length}`} right={<span className={cn('text-[13px] font-semibold font-tabular', tone(611))}>{sgn(611)}</span>} />
            <div className="rounded-lg border border-border overflow-hidden bg-card">
              <DataTable tintHeader cols={['Instrument', 'Qty', 'Avg', 'LTP', 'Chg', 'P&L']} widths="" rows={<PosRows />} />
            </div>
          </div>
          <div>
            <SectionHead title={`Closed today · ${CLOSED.length}`} right={<span className={cn('text-[13px] font-semibold font-tabular', tone(680))}>{sgn(680)}</span>} />
            <div className="rounded-lg border border-border overflow-hidden bg-card">
              <DataTable tintHeader cols={['Instrument', 'Qty', 'Hold', 'Net']} widths="" rows={<ClosedRows />} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 3 — PANEL   Most depth. The whole session sits on one raised panel with
//             inset regions inside it — page, panel, inset, header tint.
//             Four levels rather than two.
// ═══════════════════════════════════════════════════════════════════════════
function Panel() {
  return (
    <div style={WARM_DEPTH}>
      <div className="rounded-lg border border-border bg-card overflow-hidden max-w-[1060px]">
        {/* panel header */}
        <div className="flex flex-wrap items-end justify-between gap-6 px-5 py-4 border-b border-border">
          <div>
            <p className="t-label">Day P&amp;L</p>
            <p className={cn('font-display text-[32px] leading-none font-semibold tracking-tight font-tabular mt-1.5', tone(S.pnl))}>{sgn(S.pnl)}</p>
            <p className="text-[12.5px] text-muted-foreground font-tabular mt-1.5">
              <span className={tone(S.booked)}>{sgn(S.booked)}</span> booked · <span className={tone(S.unrealized)}>{sgn(S.unrealized)}</span> open
            </p>
          </div>
          <div className="flex items-end gap-6 font-tabular">
            {[['Trades', `${S.trades}`], ['Won', `${S.winRate}%`], ['Loss limit', `${S.lossUsed}%`]].map(([l, v]) => (
              <div key={l}><p className="t-label">{l}</p><p className="text-[16px] font-semibold text-foreground mt-1">{v}</p></div>
            ))}
            <Sparkline data={S.curve} width={104} height={32} className="text-profit hidden sm:block" />
          </div>
        </div>

        {/* inset region — one step darker than the panel */}
        <div className="bg-[rgb(var(--layer-page))] px-5 py-5 border-b border-border">
          <SectionHead title={`Live alerts · ${ALERTS.length}`} right={<span className="text-[13px] font-semibold font-tabular text-loss">{sgn(-6120)}</span>} />
          <div className="space-y-2.5">{ALERTS.map(a => <AlertCard key={a.id} a={a} inset />)}</div>
        </div>

        <div className="px-5 py-5 grid grid-cols-1 xl:grid-cols-2 gap-x-8 gap-y-6">
          <div>
            <SectionHead title={`Open · ${POS.length}`} right={<span className={cn('text-[13px] font-semibold font-tabular', tone(611))}>{sgn(611)}</span>} />
            <div className="rounded-lg border border-border overflow-hidden">
              <DataTable tintHeader cols={['Instrument', 'Qty', 'LTP', 'Chg', 'P&L']} widths=""
                rows={POS.map(p => (
                  <tr key={p.sym} className="border-t border-[rgb(var(--layer-border-subtle))] hover:bg-[rgb(var(--layer-overlay))]">
                    <td className="py-2.5 pl-3 pr-3 text-left w-full">
                      <span className="flex items-center gap-2 min-w-0">
                        <span className={cn('text-[9px] font-bold px-1 py-0.5 rounded leading-none shrink-0',
                          p.dir === 'B' ? 'bg-profit/10 text-profit' : 'bg-loss/10 text-loss')}>{p.dir === 'B' ? 'BUY' : 'SELL'}</span>
                        <span className="text-foreground truncate">{p.sym}</span>
                      </span>
                    </td>
                    <Td muted>{p.qty}</Td><Td>{p.ltp.toFixed(2)}</Td>
                    <Td className={tone(p.chg)}>{p.chg > 0 ? '+' : '−'}{Math.abs(p.chg).toFixed(2)}%</Td>
                    <Td className={cn('font-semibold', tone(p.pnl))}>{sgn(p.pnl)}</Td>
                  </tr>))} />
            </div>
          </div>
          <div>
            <SectionHead title={`Closed today · ${CLOSED.length}`} right={<span className={cn('text-[13px] font-semibold font-tabular', tone(680))}>{sgn(680)}</span>} />
            <div className="rounded-lg border border-border overflow-hidden">
              <DataTable tintHeader cols={['Instrument', 'Qty', 'Hold', 'Net']} widths="" rows={<ClosedRows />} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Shell ──────────────────────────────────────────────────────────────────
const V: Record<string, { label: string; note: string; el: JSX.Element }> = {
  current: { label: '0 · Current', note: "Today's Dashboard, reproduced. The control.", el: <Current /> },
  tight:   { label: '1 · Tight',   note: 'Content capped at 820. Numbers clustered right. Warm neutrals, third surface level.', el: <Tight /> },
  twoup:   { label: '2 · Two-up',  note: 'Width used, not spanned. Alerts left as cards, data right as tables.', el: <TwoUp /> },
  panel:   { label: '3 · Panel',   note: 'Four surface levels — page, panel, inset, header tint. Most depth.', el: <Panel /> },
};
const WIDTHS = [
  { id: 'mobile', label: 'iPhone 390', w: 390, h: 780 },
  { id: 'desktop', label: 'Desktop', w: 0, h: 0 },
] as const;

export default function DashboardVariants() {
  const [params, setParams] = useSearchParams();
  const v = params.get('v') ?? 'current';
  const bare = params.get('bare') === '1';
  const width = params.get('w') ?? 'desktop';
  const variant = V[v] ?? V.current;

  if (bare) return <div className="pb-10">{variant.el}</div>;

  const dev = WIDTHS.find(x => x.id === width) ?? WIDTHS[1];
  const set = (k: string, val: string) => {
    const n = new URLSearchParams(params); n.set(k, val); setParams(n, { replace: true });
  };

  return (
    <div className="pb-16">
      <div className="flex flex-wrap items-center gap-x-1 gap-y-2 border-b border-border">
        {Object.entries(V).map(([id, x]) => (
          <button key={id} onClick={() => set('v', id)}
            className={cn('px-3 h-9 text-[12.5px] font-medium border-b-2 -mb-px transition-colors duration-150',
              v === id ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground')}>
            {x.label}
          </button>
        ))}
      </div>
      <div className="flex items-center justify-between gap-4 flex-wrap py-3">
        <p className="text-[12.5px] text-muted-foreground">{variant.note}</p>
        <div className="flex items-center gap-1">
          {WIDTHS.map(x => (
            <button key={x.id} onClick={() => set('w', x.id)}
              className={cn('px-2.5 h-7 rounded text-[11.5px] font-medium transition-colors duration-150',
                width === x.id ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground')}>
              {x.label}
            </button>
          ))}
        </div>
      </div>
      {dev.w > 0 ? (
        <iframe key={`${v}-${dev.id}`} title={`${variant.label} at ${dev.label}`}
          src={`/dashboard-variants?bare=1&v=${v}`} style={{ width: dev.w, height: dev.h }}
          className="mx-auto block border border-border rounded-lg bg-background" />
      ) : variant.el}
    </div>
  );
}
