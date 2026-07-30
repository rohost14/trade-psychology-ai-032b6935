/**
 * DESIGN LAB — throwaway. Delete once a direction is chosen.
 *
 * Three Dashboard treatments rendered from identical fixed data, so the only
 * variable is the design. Routed at /design-lab. Nothing here is imported by
 * the real app.
 *
 *   A  Terminal        zero radius, no boxes, rules + background shifts,
 *                      cockpit density, extreme type contrast, full width
 *   B  Editorial       no boxes, typography does the structural work,
 *                      generous rhythm, closer to Linear/Stripe
 *   C  Refined surface current direction, corrected: 2px radius, tighter
 *                      rows, sharper hierarchy, wider shell
 */
import { useState } from 'react';
import { cn } from '@/lib/utils';

// ── Fixed sample data — identical across all three ─────────────────────────
const DAY = { pnl: 12480, booked: 8240, unrealized: 4240, trades: 14, lossUsed: 32, winRate: 62 };

const ALERTS = [
  { id: 1, name: 'Size Escalation',  tag: 'SIZE',      sev: 'danger',  cost: -2100, ago: '2h ago',
    detail: 'BANKNIFTY 45500 PE at 100 lots, 4x your average size, 8 min after a ₹2,600 loss.' },
  { id: 2, name: 'Early Exit',       tag: 'PATTERN',   sev: 'caution', cost: -820,  ago: '3h ago',
    detail: 'NIFTY CE exited at +₹820 after 8 min. Position continued to +₹2,100.' },
  { id: 3, name: 'No Stop-Loss',     tag: 'EMOTIONAL', sev: 'danger',  cost: -3200, ago: '4h ago',
    detail: 'FINNIFTY 19800 CE open 47 min with no stop-loss.' },
];

const POSITIONS = [
  { sym: 'NIFTY24C50',   dir: 'BUY',  qty: 50, entry: 108.50, ltp: 124.20, chg:  14.47, pnl:  785 },
  { sym: 'BANKNIFTY25P', dir: 'SELL', qty: 25, entry: 410.20, ltp: 396.10, chg:  -3.44, pnl: -352 },
  { sym: 'FINNIFTY19800', dir: 'BUY', qty: 40, entry:  88.00, ltp:  92.45, chg:   5.06, pnl:  178 },
];

const CLOSED = [
  { sym: 'NIFTY24C00',  qty: 75, entry: 142.10, exit: 151.80, hold: '22m', chg:  6.82, pnl: 1455 },
  { sym: 'BANKNIFTY24', qty: 50, entry: 388.40, exit: 372.90, hold: '1h 4m', chg: -3.99, pnl: -775 },
];

const inr = (n: number) => Math.abs(n).toLocaleString('en-IN');
const signed = (n: number) => `${n > 0 ? '+' : n < 0 ? '−' : ''}₹${inr(n)}`;
const tone = (n: number) => (n > 0 ? 'text-profit' : n < 0 ? 'text-loss' : 'text-muted-foreground');
const sevTone = (s: string) => (s === 'danger' ? 'text-loss' : 'text-warning');

// ══════════════════════════════════════════════════════════════════════════
// A — TERMINAL
// Zero radius. No boxes at all: regions are marked by a background shift and
// a strong top rule. Cockpit density (28px rows). Extreme type contrast:
// 10px labels against a 48px primary. Full width, no centred column.
// ══════════════════════════════════════════════════════════════════════════
function Terminal() {
  const Rule = () => <div className="h-px bg-border" />;
  const Head = ({ label, right }: { label: string; right?: React.ReactNode }) => (
    <div className="flex items-center justify-between h-8 px-4 bg-muted/40 border-t border-border">
      <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">{label}</span>
      {right}
    </div>
  );

  return (
    <div className="font-tabular">
      {/* status strip */}
      <div className="flex items-center justify-between h-7 px-4 bg-muted/60 border-b border-border text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
        <span className="flex items-center gap-3">
          <span className="text-foreground font-semibold">TRADING DESK</span>
          <span className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-muted-foreground" />CLOSED</span>
        </span>
        <span className="flex items-center gap-4"><span>NSE F&amp;O</span><span className="text-foreground">15:30:00</span></span>
      </div>

      {/* primary metric — extreme contrast, no container */}
      <div className="px-4 py-5 flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Day P&amp;L</div>
          <div className={cn('text-[48px] leading-none font-semibold tracking-tight mt-1', tone(DAY.pnl))}>
            {signed(DAY.pnl)}
          </div>
        </div>
        <div className="flex items-stretch divide-x divide-border border-y border-border">
          {[
            ['BOOKED', signed(DAY.booked), tone(DAY.booked)],
            ['UNREALIZED', signed(DAY.unrealized), tone(DAY.unrealized)],
            ['TRADES', String(DAY.trades), 'text-foreground'],
            ['LOSS USED', `${DAY.lossUsed}%`, 'text-foreground'],
            ['WIN RATE', `${DAY.winRate}%`, 'text-foreground'],
          ].map(([l, v, t]) => (
            <div key={l} className="px-4 py-1.5">
              <div className="text-[9px] uppercase tracking-[0.16em] text-muted-foreground">{l}</div>
              <div className={cn('text-[15px] font-semibold mt-0.5', t)}>{v}</div>
            </div>
          ))}
        </div>
      </div>

      <Head label="Behavioural alerts" right={<span className="text-[10px] text-loss font-semibold">3 ACTIVE</span>} />
      <div>
        {ALERTS.map(a => (
          <div key={a.id} className="flex items-start gap-3 px-4 h-auto py-2 border-b border-border/60 hover:bg-muted/30">
            <span className={cn('mt-1.5 h-1.5 w-1.5 shrink-0', a.sev === 'danger' ? 'bg-loss' : 'bg-warning')} />
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline gap-2">
                <span className="text-[13px] font-semibold text-foreground">{a.name}</span>
                <span className={cn('text-[9px] font-semibold uppercase tracking-[0.14em]', sevTone(a.sev))}>{a.tag}</span>
                <span className="text-[10px] text-muted-foreground ml-auto">{a.ago}</span>
              </div>
              <div className="text-[12px] text-muted-foreground truncate">{a.detail}</div>
            </div>
            <span className={cn('text-[13px] font-semibold shrink-0 w-20 text-right', tone(a.cost))}>{signed(a.cost)}</span>
          </div>
        ))}
      </div>

      <Head label="Open positions · 3" right={<span className={cn('text-[11px] font-semibold', tone(611))}>{signed(611)}</span>} />
      <div className="grid grid-cols-[1.6fr_.5fr_.7fr_.7fr_.6fr_.8fr] px-4 h-6 items-center text-[9px] uppercase tracking-[0.14em] text-muted-foreground border-b border-border">
        <span>Symbol</span><span className="text-right">Qty</span><span className="text-right">Entry</span>
        <span className="text-right">LTP</span><span className="text-right">Chg%</span><span className="text-right">P&amp;L</span>
      </div>
      {POSITIONS.map(p => (
        <div key={p.sym} className="grid grid-cols-[1.6fr_.5fr_.7fr_.7fr_.6fr_.8fr] px-4 h-7 items-center text-[12px] border-b border-border/40 hover:bg-muted/30">
          <span className="flex items-center gap-2 min-w-0">
            <span className={cn('text-[9px] font-bold px-1', p.dir === 'BUY' ? 'text-profit' : 'text-loss')}>{p.dir}</span>
            <span className="text-foreground truncate">{p.sym}</span>
          </span>
          <span className="text-right text-muted-foreground">{p.qty}</span>
          <span className="text-right text-muted-foreground">{p.entry.toFixed(2)}</span>
          <span className="text-right text-foreground">{p.ltp.toFixed(2)}</span>
          <span className={cn('text-right', tone(p.chg))}>{p.chg > 0 ? '+' : '−'}{Math.abs(p.chg).toFixed(2)}%</span>
          <span className={cn('text-right font-semibold', tone(p.pnl))}>{signed(p.pnl)}</span>
        </div>
      ))}

      <Head label="Closed today · 2" right={<span className={cn('text-[11px] font-semibold', tone(680))}>{signed(680)}</span>} />
      <div className="grid grid-cols-[1.6fr_.5fr_.7fr_.7fr_.6fr_.8fr] px-4 h-6 items-center text-[9px] uppercase tracking-[0.14em] text-muted-foreground border-b border-border">
        <span>Symbol</span><span className="text-right">Qty</span><span className="text-right">Avg entry</span>
        <span className="text-right">Avg exit</span><span className="text-right">Hold</span><span className="text-right">Net</span>
      </div>
      {CLOSED.map(c => (
        <div key={c.sym} className="grid grid-cols-[1.6fr_.5fr_.7fr_.7fr_.6fr_.8fr] px-4 h-7 items-center text-[12px] border-b border-border/40 hover:bg-muted/30">
          <span className="text-foreground truncate">{c.sym}</span>
          <span className="text-right text-muted-foreground">{c.qty}</span>
          <span className="text-right text-muted-foreground">{c.entry.toFixed(2)}</span>
          <span className="text-right text-muted-foreground">{c.exit.toFixed(2)}</span>
          <span className="text-right text-muted-foreground">{c.hold}</span>
          <span className={cn('text-right font-semibold', tone(c.pnl))}>{signed(c.pnl)}</span>
        </div>
      ))}
      <Rule />
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// B — EDITORIAL
// No containers. Typography and rules carry the structure. Wide left label
// column so header and value are never 1200px apart. Moderate density.
// ══════════════════════════════════════════════════════════════════════════
function Editorial() {
  const Block = ({ label, note, right, children }: {
    label: string; note?: string; right?: React.ReactNode; children: React.ReactNode;
  }) => (
    <section className="grid grid-cols-1 lg:grid-cols-[180px_1fr] gap-x-8 gap-y-3 py-7 border-t-2 border-foreground/15">
      <div>
        <h2 className="text-[13px] font-semibold tracking-tight text-foreground">{label}</h2>
        {note && <p className="text-[11.5px] text-muted-foreground mt-0.5 leading-snug">{note}</p>}
        {right && <div className="mt-2">{right}</div>}
      </div>
      <div className="min-w-0">{children}</div>
    </section>
  );

  return (
    <div className="max-w-[1080px]">
      <div className="pb-7">
        <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Trading desk · closed</div>
        <div className={cn('font-display text-[52px] leading-none font-semibold tracking-tight font-tabular mt-2', tone(DAY.pnl))}>
          {signed(DAY.pnl)}
        </div>
        <p className="text-[14px] text-muted-foreground mt-2 font-tabular">
          {signed(DAY.booked)} booked, {signed(DAY.unrealized)} still open, across {DAY.trades} trades.
          You have used {DAY.lossUsed}% of today's loss budget.
        </p>
      </div>

      <Block label="Alerts" note="What fired this session" right={<span className="text-[12px] font-semibold text-loss font-tabular">{signed(-6120)} attached</span>}>
        <div className="space-y-4">
          {ALERTS.map(a => (
            <div key={a.id} className="flex items-baseline gap-4">
              <span className={cn('text-[13px] font-semibold shrink-0 w-24', tone(a.cost))}>{signed(a.cost)}</span>
              <div className="min-w-0">
                <span className="text-[14px] font-medium text-foreground">{a.name}</span>
                <span className="text-[11px] text-muted-foreground ml-2">{a.ago}</span>
                <p className="text-[12.5px] text-muted-foreground leading-snug mt-0.5">{a.detail}</p>
              </div>
            </div>
          ))}
        </div>
      </Block>

      <Block label="Open" note="3 positions" right={<span className={cn('text-[12px] font-semibold font-tabular', tone(611))}>{signed(611)}</span>}>
        <table className="w-full text-[13px] font-tabular">
          <tbody className="divide-y divide-border">
            {POSITIONS.map(p => (
              <tr key={p.sym}>
                <td className="py-2 text-foreground">{p.sym}</td>
                <td className="py-2 text-right text-muted-foreground">{p.qty}</td>
                <td className="py-2 text-right text-muted-foreground">{p.entry.toFixed(2)}</td>
                <td className="py-2 text-right text-foreground">{p.ltp.toFixed(2)}</td>
                <td className={cn('py-2 text-right', tone(p.chg))}>{p.chg > 0 ? '+' : '−'}{Math.abs(p.chg).toFixed(2)}%</td>
                <td className={cn('py-2 text-right font-semibold', tone(p.pnl))}>{signed(p.pnl)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Block>

      <Block label="Closed" note="2 round trips today" right={<span className={cn('text-[12px] font-semibold font-tabular', tone(680))}>{signed(680)}</span>}>
        <table className="w-full text-[13px] font-tabular">
          <tbody className="divide-y divide-border">
            {CLOSED.map(c => (
              <tr key={c.sym}>
                <td className="py-2 text-foreground">{c.sym}</td>
                <td className="py-2 text-right text-muted-foreground">{c.qty}</td>
                <td className="py-2 text-right text-muted-foreground">{c.entry.toFixed(2)} → {c.exit.toFixed(2)}</td>
                <td className="py-2 text-right text-muted-foreground">{c.hold}</td>
                <td className={cn('py-2 text-right font-semibold', tone(c.pnl))}>{signed(c.pnl)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Block>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// C — REFINED SURFACE
// The current direction, corrected: radius 2px not 10px, rows 28px not 56px,
// sharper type contrast, header row tinted so the surface reads as an
// instrument panel rather than a web card.
// ══════════════════════════════════════════════════════════════════════════
function Refined() {
  const Panel = ({ label, right, children }: { label: string; right?: React.ReactNode; children: React.ReactNode }) => (
    <section className="bg-card border border-border rounded-[2px] overflow-hidden">
      <div className="flex items-center justify-between h-8 px-3 bg-muted/50 border-b border-border">
        <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{label}</span>
        {right}
      </div>
      {children}
    </section>
  );

  return (
    <div className="space-y-3 font-tabular">
      <Panel label="Day P&amp;L" right={<span className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">closed · 15:30</span>}>
        <div className="px-3 py-3 flex items-end justify-between flex-wrap gap-4">
          <div>
            <div className={cn('text-[40px] leading-none font-semibold tracking-tight', tone(DAY.pnl))}>{signed(DAY.pnl)}</div>
            <div className="text-[11.5px] text-muted-foreground mt-1.5">
              Booked <span className={tone(DAY.booked)}>{signed(DAY.booked)}</span> · Unrealized <span className={tone(DAY.unrealized)}>{signed(DAY.unrealized)}</span>
            </div>
          </div>
          <div className="flex divide-x divide-border border border-border rounded-[2px]">
            {[['TRADES', String(DAY.trades)], ['LOSS USED', `${DAY.lossUsed}%`], ['WIN RATE', `${DAY.winRate}%`]].map(([l, v]) => (
              <div key={l} className="px-3 py-1.5">
                <div className="text-[9px] uppercase tracking-[0.16em] text-muted-foreground">{l}</div>
                <div className="text-[15px] font-semibold text-foreground mt-0.5">{v}</div>
              </div>
            ))}
          </div>
        </div>
      </Panel>

      <Panel label="Behavioural alerts · 3" right={<span className="text-[11px] font-semibold text-loss">{signed(-6120)}</span>}>
        <div className="divide-y divide-border/60">
          {ALERTS.map(a => (
            <div key={a.id} className={cn('flex items-start gap-2.5 px-3 py-2 border-l-2', a.sev === 'danger' ? 'border-l-loss' : 'border-l-warning')}>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-2">
                  <span className="text-[13px] font-semibold text-foreground">{a.name}</span>
                  <span className={cn('text-[9px] font-semibold uppercase tracking-[0.14em]', sevTone(a.sev))}>{a.tag}</span>
                  <span className="text-[10px] text-muted-foreground ml-auto">{a.ago}</span>
                </div>
                <p className="text-[12px] text-muted-foreground truncate">{a.detail}</p>
              </div>
              <span className={cn('text-[13px] font-semibold shrink-0 w-20 text-right', tone(a.cost))}>{signed(a.cost)}</span>
            </div>
          ))}
        </div>
      </Panel>

      <Panel label="Open positions · 3" right={<span className={cn('text-[11px] font-semibold', tone(611))}>{signed(611)}</span>}>
        <div className="grid grid-cols-[1.6fr_.5fr_.7fr_.7fr_.6fr_.8fr] px-3 h-6 items-center text-[9px] uppercase tracking-[0.14em] text-muted-foreground border-b border-border bg-muted/20">
          <span>Symbol</span><span className="text-right">Qty</span><span className="text-right">Entry</span>
          <span className="text-right">LTP</span><span className="text-right">Chg%</span><span className="text-right">P&amp;L</span>
        </div>
        {POSITIONS.map(p => (
          <div key={p.sym} className="grid grid-cols-[1.6fr_.5fr_.7fr_.7fr_.6fr_.8fr] px-3 h-7 items-center text-[12px] border-b border-border/40 last:border-0 hover:bg-muted/30">
            <span className="flex items-center gap-2 min-w-0">
              <span className={cn('text-[9px] font-bold', p.dir === 'BUY' ? 'text-profit' : 'text-loss')}>{p.dir}</span>
              <span className="text-foreground truncate">{p.sym}</span>
            </span>
            <span className="text-right text-muted-foreground">{p.qty}</span>
            <span className="text-right text-muted-foreground">{p.entry.toFixed(2)}</span>
            <span className="text-right text-foreground">{p.ltp.toFixed(2)}</span>
            <span className={cn('text-right', tone(p.chg))}>{p.chg > 0 ? '+' : '−'}{Math.abs(p.chg).toFixed(2)}%</span>
            <span className={cn('text-right font-semibold', tone(p.pnl))}>{signed(p.pnl)}</span>
          </div>
        ))}
      </Panel>

      <Panel label="Closed today · 2" right={<span className={cn('text-[11px] font-semibold', tone(680))}>{signed(680)}</span>}>
        {CLOSED.map(c => (
          <div key={c.sym} className="grid grid-cols-[1.6fr_.5fr_1fr_.6fr_.8fr] px-3 h-7 items-center text-[12px] border-b border-border/40 last:border-0 hover:bg-muted/30">
            <span className="text-foreground truncate">{c.sym}</span>
            <span className="text-right text-muted-foreground">{c.qty}</span>
            <span className="text-right text-muted-foreground">{c.entry.toFixed(2)} → {c.exit.toFixed(2)}</span>
            <span className="text-right text-muted-foreground">{c.hold}</span>
            <span className={cn('text-right font-semibold', tone(c.pnl))}>{signed(c.pnl)}</span>
          </div>
        ))}
      </Panel>
    </div>
  );
}

// ── Switcher ───────────────────────────────────────────────────────────────
const VARIANTS = [
  { id: 'terminal',  label: 'A · Terminal',        el: <Terminal /> },
  { id: 'editorial', label: 'B · Editorial',       el: <Editorial /> },
  { id: 'refined',   label: 'C · Refined surface', el: <Refined /> },
] as const;

export default function DesignLab() {
  const [active, setActive] = useState<string>('terminal');
  const current = VARIANTS.find(v => v.id === active) ?? VARIANTS[0];

  return (
    <div className="pb-16">
      <div className="flex items-center gap-1 mb-5 border-b border-border">
        {VARIANTS.map(v => (
          <button
            key={v.id}
            onClick={() => setActive(v.id)}
            className={cn(
              'px-3 h-9 text-[12.5px] font-medium border-b-2 -mb-px transition-colors duration-150',
              active === v.id
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {v.label}
          </button>
        ))}
      </div>
      {current.el}
    </div>
  );
}
