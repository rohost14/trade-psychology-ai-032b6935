/**
 * Soft Precision — desktop, at /soft-web-lab
 *
 * The mobile study at /soft-lab put everything in a card, because at 390px a card
 * IS the layout: one column, each card a row. At 1400px that stops working —
 * twenty cards on a wide canvas reads as a scrapbook, and the gutters between
 * them eat the density a trading screen needs.
 *
 * So this keeps Soft Precision's surface language but spends it. The split is a
 * rule, not a preference:
 *
 *   CARD           a discrete object you could pick up on its own — a state, a
 *                  single metric, one insight, one alert. Something with a hero
 *                  number or a verdict. Cards earn their shadow by being separable.
 *
 *   FLAT SECTION   a collection you scan and compare across — tables, lists,
 *                  settings rows. Label, hairline dividers, edge to edge, no
 *                  container. Boxing each row here would fight the comparison the
 *                  reader came to make, and it is the exact pattern this codebase
 *                  has rejected repeatedly as card-per-row.
 *
 * That rule is a genuine merge rather than a compromise: the card half is Soft
 * Precision, the flat half is what docs/DESIGN_SYSTEM.md already says about
 * tables. The two systems disagreed about everything EXCEPT this, so this is
 * where they meet.
 *
 * Lab only. Nothing here imports from the live app and nothing in the live app
 * imports from here.
 */
import { useEffect, useState } from 'react';
import {
  Area, AreaChart, Bar, BarChart, Cell, ResponsiveContainer, XAxis, YAxis,
} from 'recharts';
import {
  AlertTriangle, ArrowRight, BarChart3, Bell, Brain, ChevronRight, Gauge,
  Hourglass, Layers, LayoutGrid, Link2, MessageSquare, RefreshCw, Search,
  Settings as SettingsIcon, Shield, ShieldCheck, Sparkles, Wallet, Zap,
} from 'lucide-react';

import { T, TONE, CARD, FONT, type Tone } from './softPrecisionTheme';

// ── Atoms ─────────────────────────────────────────────────────────────────────

function Label({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <span style={{
      fontSize: 10.5, fontWeight: 600, letterSpacing: '0.09em',
      textTransform: 'uppercase', color: T.muted, ...style,
    }}>
      {children}
    </span>
  );
}

/**
 * `solid` is what makes three severity levels readable from one hue. Without it,
 * HIGH and MED both render as a red tint and become indistinguishable — which is
 * exactly the failure that made amber feel necessary in the first place. Solid,
 * tint, neutral is three clear strengths and still only one colour.
 */
function Pill({ tone, children, solid = false }: {
  tone: Tone; children: React.ReactNode; solid?: boolean;
}) {
  const [bg, fg] = TONE[tone];
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      background: solid ? fg : bg,
      color: solid ? '#fff' : fg,
      fontSize: 11, fontWeight: 600, padding: '4px 10px', borderRadius: 999, whiteSpace: 'nowrap',
    }}>
      {children}
    </span>
  );
}

function IconTile({ tone, size = 38, children }: {
  tone: Tone; size?: number; children: React.ReactNode;
}) {
  const [bg] = TONE[tone];
  return (
    <span style={{
      width: size, height: size, borderRadius: size * 0.35, background: bg, flexShrink: 0,
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    }}>
      {children}
    </span>
  );
}

/** CARD — one metric, separable, hero number. Earns its surface. */
function MetricCard({ label, value, sub, valueColor, Icon }: {
  label: string; value: string; sub?: React.ReactNode; valueColor?: string; Icon?: React.ElementType;
}) {
  return (
    <div style={{ ...CARD, padding: '18px 20px 20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Label>{label}</Label>
        {Icon && <Icon size={15} color={T.faint} />}
      </div>
      <p style={{
        margin: '10px 0 0', fontSize: 28, fontWeight: 700, letterSpacing: '-0.03em',
        color: valueColor ?? T.ink, fontVariantNumeric: 'tabular-nums',
      }}>
        {value}
      </p>
      {sub && <p style={{ margin: '4px 0 0', fontSize: 12, color: T.muted }}>{sub}</p>}
    </div>
  );
}

/**
 * FLAT SECTION — the other half of the rule. A label, a hairline, and content
 * that runs to the edges. No box, no shadow.
 */
function Section({ title, action, children, style }: {
  title: string; action?: string; children: React.ReactNode; style?: React.CSSProperties;
}) {
  return (
    <section style={{ ...style }}>
      <div style={{
        display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
        paddingBottom: 12, borderBottom: `1px solid ${T.line}`, marginBottom: 4,
      }}>
        <h2 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: T.ink, letterSpacing: '-0.01em' }}>
          {title}
        </h2>
        {action && (
          <span style={{ fontSize: 12.5, fontWeight: 600, color: T.accent, cursor: 'pointer' }}>
            {action}
          </span>
        )}
      </div>
      {children}
    </section>
  );
}

function Ring({ pct, size, stroke, color, children }: {
  pct: number; size: number; stroke: number; color: string; children?: React.ReactNode;
}) {
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#EBEDF1" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke}
          strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={circ * (1 - pct / 100)} />
      </svg>
      <div style={{
        position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
      }}>
        {children}
      </div>
    </div>
  );
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

const NAV = [
  { key: 'dashboard', label: 'Dashboard', Icon: LayoutGrid },
  { key: 'analytics', label: 'Analytics', Icon: BarChart3 },
  { key: 'patterns',  label: 'Patterns',  Icon: Brain },
  { key: 'shield',    label: 'Shield',    Icon: Shield },
  { key: 'coach',     label: 'Coach',     Icon: MessageSquare },
  { key: 'settings',  label: 'Settings',  Icon: SettingsIcon },
];

function Sidebar({ active, onSelect }: { active: string; onSelect: (k: string) => void }) {
  return (
    <aside style={{
      width: 232, flexShrink: 0, background: T.surface, borderRight: `1px solid ${T.line}`,
      padding: '22px 14px', display: 'flex', flexDirection: 'column', gap: 26,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '0 8px' }}>
        <span style={{
          width: 38, height: 38, borderRadius: 12, background: T.ink,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Layers size={19} color="#fff" />
        </span>
        <div>
          <p style={{ margin: 0, fontSize: 14.5, fontWeight: 700, color: T.ink }}>Soft Precision</p>
          <p style={{ margin: 0, fontSize: 11, color: T.muted }}>Tuesday, Oct 24</p>
        </div>
      </div>

      <nav style={{ display: 'grid', gap: 3 }}>
        {NAV.map(({ key, label, Icon }) => {
          const on = key === active;
          return (
            <button key={key} onClick={() => onSelect(key)} style={{
              display: 'flex', alignItems: 'center', gap: 11, padding: '10px 12px',
              borderRadius: 11, border: 'none', cursor: 'pointer', textAlign: 'left',
              fontFamily: FONT, fontSize: 13.5, fontWeight: on ? 650 : 500,
              background: on ? T.accentTint : 'transparent',
              color: on ? T.accent : T.body,
            }}>
              <Icon size={17} color={on ? T.accent : T.faint} />
              {label}
            </button>
          );
        })}
      </nav>

      {/* CARD, at the bottom of a flat nav — it is a discrete status object */}
      <div style={{
        marginTop: 'auto', borderRadius: 16, padding: '14px 15px',
        background: `linear-gradient(155deg, ${T.accentTint}, #FAFAFE)`,
        border: `1px solid ${T.accentTint}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <ShieldCheck size={16} color={T.accent} />
          <span style={{ fontSize: 13, fontWeight: 650, color: T.ink }}>Guardian Active</span>
        </div>
        <p style={{ margin: 0, fontSize: 11.5, color: T.muted, lineHeight: 1.5 }}>
          0 emotional triggers in this session.
        </p>
      </div>
    </aside>
  );
}

function TopBar({ title, sub }: { title: string; sub: string }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between',
      paddingBottom: 22, marginBottom: 26, borderBottom: `1px solid ${T.line}`,
    }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 26, fontWeight: 700, color: T.ink, letterSpacing: '-0.03em' }}>
          {title}
        </h1>
        <p style={{ margin: '3px 0 0', fontSize: 13.5, color: T.muted }}>{sub}</p>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 8, height: 38, padding: '0 14px',
          borderRadius: 999, border: `1px solid ${T.line}`, background: T.surface,
          fontSize: 12.5, color: T.muted,
        }}>
          <Search size={14} /> Search
        </span>
        <span style={{
          width: 38, height: 38, borderRadius: 999, background: T.surface, position: 'relative',
          border: `1px solid ${T.line}`,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Bell size={17} color={T.body} />
          <span style={{ position: 'absolute', top: 9, right: 10, width: 6, height: 6, borderRadius: 999, background: T.down }} />
        </span>
      </div>
    </div>
  );
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

const EQUITY = [
  { d: 'Mon', v: 8 }, { d: '', v: 11 }, { d: 'Tue', v: 9.4 }, { d: '', v: 14 },
  { d: 'Wed', v: 17 }, { d: '', v: 16 }, { d: 'Thu', v: 20 }, { d: '', v: 22.5 },
  { d: 'Fri', v: 24.5 },
];

function DashboardScreen() {
  const positions = [
    { sym: 'NIFTY 50', tag: 'FUT', qty: 500, entry: '22,140.00', ltp: '22,148.40', pnl: '+₹4,200.50', up: true },
    { sym: 'BANKNIFTY', tag: 'OPT', qty: 250, entry: '486.20', ltp: '481.24', pnl: '-₹1,240.00', up: false },
    { sym: 'RELIANCE', tag: 'FUT', qty: 100, entry: '2,904.00', ltp: '2,911.60', pnl: '+₹760.00', up: true },
  ];

  return (
    <>
      <TopBar title="Dashboard" sub="Your session, as it happens" />

      {/* CARDS — four separable metrics, each with one hero number */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 30 }}>
        <MetricCard label="Session P&L" value="+₹3,720" valueColor={T.up}
          sub={<span style={{ color: T.up }}>↗ +2.1% today</span>} Icon={Wallet} />
        <MetricCard label="Open Positions" value="3" sub="2 long · 1 short" Icon={Layers} />
        <MetricCard label="Margin Used" value="65%" sub="₹3,25,000 of ₹5,00,000" Icon={Gauge} />
        <MetricCard label="Discipline" value="84/100" valueColor={T.accent}
          sub={<span style={{ color: T.up }}>↗ +6 this week</span>} Icon={ShieldCheck} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.55fr 1fr', gap: 26, marginBottom: 30 }}>
        {/* FLAT — a table is for comparing across rows. Boxing each row would
            fight exactly that, and card-per-row is the pattern already rejected
            in this codebase three times over. */}
        <Section title="Open positions" action="View all">
          <div style={{
            display: 'grid', gridTemplateColumns: '1.4fr 60px 1fr 1fr 1.1fr',
            padding: '11px 2px', borderBottom: `1px solid ${T.line}`,
          }}>
            <Label>Symbol</Label>
            <Label style={{ textAlign: 'right' }}>Qty</Label>
            <Label style={{ textAlign: 'right' }}>Entry</Label>
            <Label style={{ textAlign: 'right' }}>LTP</Label>
            <Label style={{ textAlign: 'right' }}>P&amp;L</Label>
          </div>
          {positions.map(p => (
            <div key={p.sym} style={{
              display: 'grid', gridTemplateColumns: '1.4fr 60px 1fr 1fr 1.1fr',
              alignItems: 'center', padding: '15px 2px', borderBottom: `1px solid ${T.line}`,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                <span style={{ fontSize: 13.5, fontWeight: 650, color: T.ink }}>{p.sym}</span>
                <span style={{
                  fontSize: 9.5, fontWeight: 600, color: T.muted, background: '#F1F2F6',
                  padding: '2px 7px', borderRadius: 5,
                }}>
                  {p.tag}
                </span>
              </div>
              <span style={{ textAlign: 'right', fontSize: 13, color: T.body, fontVariantNumeric: 'tabular-nums' }}>{p.qty}</span>
              <span style={{ textAlign: 'right', fontSize: 13, color: T.muted, fontVariantNumeric: 'tabular-nums' }}>{p.entry}</span>
              <span style={{ textAlign: 'right', fontSize: 13, color: T.body, fontVariantNumeric: 'tabular-nums' }}>{p.ltp}</span>
              <span style={{
                textAlign: 'right', fontSize: 13.5, fontWeight: 700,
                color: p.up ? T.up : T.down, fontVariantNumeric: 'tabular-nums',
              }}>
                {p.pnl}
              </span>
            </div>
          ))}
        </Section>

        {/* CARD — the equity curve is one object with one story */}
        <div style={{ ...CARD, padding: '18px 6px 10px 6px' }}>
          <div style={{ padding: '0 14px', marginBottom: 4 }}>
            <Label>This week</Label>
            <p style={{ margin: '7px 0 0', fontSize: 24, fontWeight: 700, color: T.ink, letterSpacing: '-0.03em', fontVariantNumeric: 'tabular-nums' }}>
              ₹24,502
            </p>
          </div>
          <div style={{ height: 168 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={EQUITY} margin={{ top: 12, right: 14, left: 14, bottom: 0 }}>
                <defs>
                  <linearGradient id="spw-eq" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={T.accent} stopOpacity={0.2} />
                    <stop offset="100%" stopColor={T.accent} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="d" axisLine={false} tickLine={false} interval={0}
                  tick={{ fill: T.faint, fontSize: 10.5, fontWeight: 600 }} />
                <Area type="monotone" dataKey="v" stroke={T.accent} strokeWidth={2.4}
                  fill="url(#spw-eq)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 26 }}>
        {/* FLAT — a list you scan down */}
        <Section title="Live insights" action="View all">
          {[
            { Icon: AlertTriangle, tone: 'down' as const, t: 'RSI Divergence on NIFTY', b: 'Momentum weakening, watch for reversal.', ago: '12m' },
            { Icon: Brain, tone: 'accent' as const, t: 'Discipline Streak: 4 Days', b: 'You resisted 3 impulsive entries today.', ago: '2h' },
            { Icon: Zap, tone: 'down' as const, t: 'Size escalation detected', b: 'Last entry was 2.4× your median size.', ago: '3h' },
          ].map(i => (
            <div key={i.t} style={{
              display: 'flex', gap: 13, alignItems: 'flex-start', padding: '14px 2px',
              borderBottom: `1px solid ${T.line}`,
            }}>
              <IconTile tone={i.tone} size={34}>
                <i.Icon size={16} color={{ down: T.down, accent: T.accent }[i.tone]} />
              </IconTile>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ margin: 0, fontSize: 13.5, fontWeight: 650, color: T.ink }}>{i.t}</p>
                <p style={{ margin: '2px 0 0', fontSize: 12.5, color: T.muted }}>{i.b}</p>
              </div>
              <span style={{ fontSize: 11.5, color: T.faint }}>{i.ago}</span>
            </div>
          ))}
        </Section>

        {/* CARD — a single insight, and the one gradient on the screen */}
        <div style={{
          borderRadius: 20, padding: 2,
          background: `linear-gradient(140deg, ${T.accent}, #C084FC 50%, #FB923C)`,
          alignSelf: 'start',
        }}>
          <div style={{ background: T.surface, borderRadius: 18, padding: 20 }}>
            <div style={{ display: 'flex', gap: 13, marginBottom: 14 }}>
              <IconTile tone="accent"><Sparkles size={17} color={T.accent} /></IconTile>
              <div>
                <p style={{ margin: 0, fontSize: 14.5, fontWeight: 700, color: T.ink }}>AI Coach Insight</p>
                <Label>Updated 4 minutes ago</Label>
              </div>
            </div>
            <p style={{ margin: 0, fontSize: 13.5, color: T.body, lineHeight: 1.65 }}>
              You hesitated on <strong style={{ color: T.ink }}>3 entries</strong> this week, costing approx{' '}
              <strong style={{ color: T.down }}>₹12k</strong>. Your discipline score is still up{' '}
              <strong style={{ color: T.up }}>15%</strong> — the hesitation is costing you upside, not
              causing losses.
            </p>
            <button style={{
              marginTop: 18, height: 44, width: '100%', borderRadius: 999, border: 'none', cursor: 'pointer',
              background: T.accent, color: '#fff', fontFamily: FONT, fontSize: 13.5, fontWeight: 650,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            }}>
              Ask the coach <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

// ── Analytics ─────────────────────────────────────────────────────────────────

const BY_DAY = [
  { d: 'Mon', v: 4200 }, { d: 'Tue', v: -1800 }, { d: 'Wed', v: 6400 },
  { d: 'Thu', v: -900 }, { d: 'Fri', v: 8100 },
];

function AnalyticsScreen() {
  return (
    <>
      <TopBar title="Analytics" sub="Last 30 days · 42 completed trades" />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 30 }}>
        <MetricCard label="Cumulative P&L" value="₹24,502" valueColor={T.up} sub="+12.4% vs previous" />
        <MetricCard label="Win Rate" value="58%" sub="+2% vs your average" />
        <MetricCard label="Profit Factor" value="1.84" sub="Target > 2.0" />
        <MetricCard label="Emotional Tax" value="₹45,200" valueColor={T.down} sub="Losses from psychology" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 26, marginBottom: 30 }}>
        {/* CARD — one chart, one story */}
        <div style={{ ...CARD, padding: '18px 8px 12px' }}>
          <div style={{ padding: '0 14px 6px' }}>
            <Label>P&amp;L by weekday</Label>
          </div>
          <div style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={BY_DAY} margin={{ top: 10, right: 12, left: 4, bottom: 0 }}>
                <XAxis dataKey="d" axisLine={false} tickLine={false}
                  tick={{ fill: T.muted, fontSize: 11.5, fontWeight: 600 }} />
                <YAxis axisLine={false} tickLine={false} width={52}
                  tick={{ fill: T.faint, fontSize: 10.5 }}
                  tickFormatter={(v: number) => `${v / 1000}k`} />
                <Bar dataKey="v" radius={[6, 6, 0, 0]}>
                  {BY_DAY.map((e, i) => <Cell key={i} fill={e.v >= 0 ? T.up : T.down} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* FLAT — instruments compared against each other */}
        <Section title="By instrument">
          <div style={{
            display: 'grid', gridTemplateColumns: '1.3fr 70px 1fr 1fr',
            padding: '11px 2px', borderBottom: `1px solid ${T.line}`,
          }}>
            <Label>Underlying</Label>
            <Label style={{ textAlign: 'right' }}>Trades</Label>
            <Label style={{ textAlign: 'right' }}>Win rate</Label>
            <Label style={{ textAlign: 'right' }}>Net P&amp;L</Label>
          </div>
          {[
            { u: 'NIFTY', n: 18, w: 61, p: '+₹14,200', up: true },
            { u: 'BANKNIFTY', n: 14, w: 50, p: '+₹6,900', up: true },
            { u: 'FINNIFTY', n: 6, w: 33, p: '-₹2,400', up: false },
            { u: 'RELIANCE', n: 4, w: 75, p: '+₹5,800', up: true },
          ].map(r => (
            <div key={r.u} style={{
              display: 'grid', gridTemplateColumns: '1.3fr 70px 1fr 1fr', alignItems: 'center',
              padding: '13px 2px', borderBottom: `1px solid ${T.line}`,
            }}>
              <span style={{ fontSize: 13.5, fontWeight: 650, color: T.ink }}>{r.u}</span>
              <span style={{ textAlign: 'right', fontSize: 13, color: T.body, fontVariantNumeric: 'tabular-nums' }}>{r.n}</span>
              <span style={{ textAlign: 'right', fontSize: 13, color: T.body, fontVariantNumeric: 'tabular-nums' }}>{r.w}%</span>
              <span style={{
                textAlign: 'right', fontSize: 13.5, fontWeight: 700,
                color: r.up ? T.up : T.down, fontVariantNumeric: 'tabular-nums',
              }}>
                {r.p}
              </span>
            </div>
          ))}
        </Section>
      </div>

      {/* CARDS — each pattern is a separable object with its own verdict */}
      <div style={{ marginBottom: 12 }}><Label>Behavioural patterns</Label></div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        {[
          { Icon: AlertTriangle, tone: 'down' as const, sev: 'HIGH', name: 'Hesitation', body: 'Missed entry points due to fear.', freq: '4×', cost: '-₹12,400' },
          { Icon: RefreshCw, tone: 'down' as const, sev: 'MED', name: 'Over-trading', body: 'Trades taken outside your plan.', freq: '2×', cost: '-₹6,100' },
          { Icon: Hourglass, tone: 'neutral' as const, sev: 'LOW', name: 'Late exits', body: 'Held winners past your target.', freq: '5×', cost: '-₹3,300' },
        ].map(p => (
          <div key={p.name} style={{ ...CARD, padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 14 }}>
              <IconTile tone={p.tone}>
                <p.Icon size={17} color={{ down: T.down, accent: T.accent }[p.tone]} />
              </IconTile>
              <Pill tone={p.tone} solid={p.sev === 'HIGH'}>{p.sev} SEVERITY</Pill>
            </div>
            <p style={{ margin: 0, fontSize: 16.5, fontWeight: 700, color: T.ink }}>{p.name}</p>
            <p style={{ margin: '3px 0 18px', fontSize: 12.5, color: T.muted }}>{p.body}</p>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
              <div><Label>Frequency</Label><p style={{ margin: '3px 0 0', fontSize: 15, fontWeight: 650, color: T.ink }}>{p.freq}</p></div>
              <div style={{ textAlign: 'right' }}>
                <Label>Cost</Label>
                <p style={{ margin: '3px 0 0', fontSize: 15, fontWeight: 700, color: T.down, fontVariantNumeric: 'tabular-nums' }}>{p.cost}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

// ── Patterns ──────────────────────────────────────────────────────────────────

function PatternsScreen() {
  const days = Array.from({ length: 35 }, (_, i) => {
    if (i % 7 >= 5) return null;
    const seed = (i * 7) % 11;
    return { n: i + 1, s: seed > 7 ? 'b' : seed > 1 ? 'g' : 'o' };
  });

  return (
    <>
      <TopBar title="Psychology Audit" sub="What your behaviour cost, and when" />

      {/* CARD — a single alarming verdict deserves its own surface */}
      <div style={{
        borderRadius: 20, padding: '18px 22px', marginBottom: 26,
        background: T.downTint, display: 'flex', alignItems: 'center', gap: 16,
      }}>
        <IconTile tone="down" size={44}><AlertTriangle size={20} color={T.down} /></IconTile>
        <div style={{ flex: 1 }}>
          <Label style={{ color: T.down }}>Active pattern detected</Label>
          <p style={{ margin: '3px 0 0', fontSize: 16, fontWeight: 700, color: T.ink }}>
            Tilt Trading · High Severity
          </p>
        </div>
        <span style={{ fontSize: 13, fontWeight: 650, color: T.down, textDecoration: 'underline', cursor: 'pointer' }}>
          Details
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.15fr', gap: 26, marginBottom: 30 }}>
        {/* CARD */}
        <div style={{ ...CARD, padding: 24 }}>
          <Label>Emotional tax paid</Label>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '10px 0 10px' }}>
            <span style={{ fontSize: 36, fontWeight: 700, color: T.ink, letterSpacing: '-0.035em', fontVariantNumeric: 'tabular-nums' }}>
              ₹45,200
            </span>
            <Pill tone="down">+12% vs last month</Pill>
          </div>
          <p style={{ margin: 0, fontSize: 13, color: T.muted, lineHeight: 1.6 }}>
            Losses attributed to psychology — fear, greed, tilt — rather than strategy failure.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginTop: 22, paddingTop: 20, borderTop: `1px solid ${T.line}` }}>
            {[['Loss rate', '12%'], ['Trades', '42'], ['Streak', '3 days']].map(([l, v]) => (
              <div key={l}>
                <Label>{l}</Label>
                <p style={{ margin: '4px 0 0', fontSize: 19, fontWeight: 700, color: T.ink }}>{v}</p>
              </div>
            ))}
          </div>
        </div>

        {/* CARD — the calendar is one object, not a table of comparisons */}
        <div style={{ ...CARD, padding: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
            <p style={{ margin: 0, fontSize: 15, fontWeight: 700, color: T.ink }}>30-day consistency</p>
            <div style={{ display: 'flex', gap: 14 }}>
              {[['Disciplined', T.accent], ['Impulsive', T.down]].map(([l, c]) => (
                <span key={l} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11, color: T.muted }}>
                  <span style={{ width: 7, height: 7, borderRadius: 999, background: c as string }} /> {l}
                </span>
              ))}
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7,1fr)', gap: 9, marginBottom: 9 }}>
            {['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((d, i) => (
              <span key={i} style={{ textAlign: 'center', fontSize: 10.5, fontWeight: 600, color: T.faint }}>{d}</span>
            ))}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7,1fr)', gap: 9 }}>
            {days.map((d, i) => {
              const base: React.CSSProperties = {
                aspectRatio: '1', borderRadius: 999, display: 'flex', alignItems: 'center',
                justifyContent: 'center', fontSize: 11.5, fontWeight: 650, maxHeight: 38,
              };
              if (!d) return <span key={i} style={{ ...base, border: `1px solid ${T.line}` }} />;
              if (d.s === 'g') return <span key={i} style={{ ...base, background: T.accent, color: '#fff' }}>{d.n}</span>;
              if (d.s === 'b') return <span key={i} style={{ ...base, background: T.down, color: '#fff' }}>{d.n}</span>;
              return <span key={i} style={{ ...base, border: `1px solid ${T.line}`, color: T.faint }}>{d.n}</span>;
            })}
          </div>
        </div>
      </div>

      {/* FLAT — triggers are a list you read down and compare */}
      <Section title="Recurring triggers" action="View all">
        {[
          { Icon: Zap, tone: 'down' as const, name: 'Revenge Trading', sev: 'MED', body: 'Triggered after a loss >2% within 5 minutes.', freq: '3× this month', cost: '₹12,400' },
          { Icon: Hourglass, tone: 'neutral' as const, name: 'Hesitation', sev: 'LOW', body: 'Missed entry points due to over-analysis.', freq: '5× this month', cost: '~₹8,000 missed' },
          { Icon: RefreshCw, tone: 'down' as const, name: 'Size escalation', sev: 'HIGH', body: 'Position size grows after consecutive losses.', freq: '2× this month', cost: '₹18,600' },
        ].map(t => (
          <div key={t.name} style={{
            display: 'grid', gridTemplateColumns: '34px 1.5fr 1fr 140px 110px', gap: 14,
            alignItems: 'center', padding: '15px 2px', borderBottom: `1px solid ${T.line}`,
          }}>
            <IconTile tone={t.tone} size={34}>
              <t.Icon size={16} color={{ down: T.down, accent: T.accent }[t.tone]} />
            </IconTile>
            <div>
              <p style={{ margin: 0, fontSize: 13.5, fontWeight: 650, color: T.ink }}>{t.name}</p>
              <p style={{ margin: '2px 0 0', fontSize: 12.5, color: T.muted }}>{t.body}</p>
            </div>
            {/* justifySelf, because a grid item stretches to fill its column by
                default — the pill was spanning the whole cell and reading as a
                progress bar rather than a label. */}
            <span style={{ justifySelf: 'start' }}>
              <Pill tone={t.tone} solid={t.sev === 'HIGH'}>{t.sev} SEVERITY</Pill>
            </span>
            <span style={{ fontSize: 12.5, color: T.muted }}>{t.freq}</span>
            <span style={{ textAlign: 'right', fontSize: 13.5, fontWeight: 700, color: T.down, fontVariantNumeric: 'tabular-nums' }}>
              {t.cost}
            </span>
          </div>
        ))}
      </Section>
    </>
  );
}

// ── Shield ────────────────────────────────────────────────────────────────────

function ShieldScreen() {
  return (
    <>
      <TopBar title="Blowup Shield" sub="Risk intervention protocol" />

      <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: 26, marginBottom: 30 }}>
        {/* CARD — the score is the single object this screen exists for */}
        <div style={{ ...CARD, padding: 28, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div style={{ alignSelf: 'stretch', display: 'flex', justifyContent: 'space-between', marginBottom: 18 }}>
            <Label>Risk score</Label>
            <Pill tone="down">● HIGH RISK</Pill>
          </div>
          <Ring pct={84} size={210} stroke={16} color={T.down}>
            <span style={{ fontSize: 44, fontWeight: 700, color: T.ink, letterSpacing: '-0.04em', lineHeight: 1 }}>
              84<span style={{ fontSize: 19, color: T.faint }}>/100</span>
            </span>
            <Label style={{ marginTop: 8 }}>Elevated</Label>
          </Ring>
          <button style={{
            marginTop: 26, width: '100%', height: 52, borderRadius: 999, border: 'none', cursor: 'pointer',
            background: `linear-gradient(100deg, ${T.down}, #E11D48)`, color: '#fff',
            fontFamily: FONT, fontSize: 14, fontWeight: 700, letterSpacing: '0.02em',
            boxShadow: '0 8px 22px rgba(244,66,95,0.3)',
          }}>
            TRIGGER GUARDIAN (STOP 15m)
          </button>
        </div>

        <div>
          {/* CARDS — three independent gauges */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 16, marginBottom: 26 }}>
            {[
              { l: 'Tilt', v: 75, c: T.down },
              { l: 'Fatigue', v: 20, c: T.accent },
              { l: 'Volatility', v: 90, c: T.down },
            ].map(m => (
              <div key={m.l} style={{ ...CARD, padding: '20px 16px', display: 'flex', alignItems: 'center', gap: 16 }}>
                <Ring pct={m.v} size={62} stroke={6} color={m.c}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: T.ink }}>{m.v}%</span>
                </Ring>
                <div>
                  <Label>{m.l}</Label>
                  <p style={{ margin: '4px 0 0', fontSize: 12.5, color: T.muted }}>
                    {m.v > 70 ? 'Above threshold' : 'Within range'}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* FLAT — active patterns are a set you scan */}
          <Section title="Active patterns" style={{ marginBottom: 26 }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 9, padding: '14px 2px' }}>
              {[
                ['Revenge Trading', true], ['Over-leveraging', true],
                ['FOMO', false], ['Hesitation', false], ['Confirmation Bias', false],
              ].map(([p, on]) => (
                <span key={p as string} style={{
                  fontSize: 12.5, fontWeight: on ? 650 : 500, padding: '8px 15px', borderRadius: 999,
                  background: on ? T.down : T.surface,
                  color: on ? '#fff' : T.muted,
                  border: on ? 'none' : `1px solid ${T.line}`,
                }}>
                  {p as string}
                </span>
              ))}
            </div>
          </Section>

          {/* CARD */}
          <div style={{ ...CARD, padding: 20, display: 'flex', gap: 14 }}>
            <IconTile tone="accent" size={42}><Sparkles size={18} color={T.accent} /></IconTile>
            <div>
              <p style={{ margin: 0, fontSize: 14.5, fontWeight: 700, color: T.ink }}>Coach Insight</p>
              <p style={{ margin: '4px 0 0', fontSize: 13, color: T.muted, lineHeight: 1.6 }}>
                You&apos;ve entered 3 trades in the last 10 minutes after a significant loss. This pattern
                matches your historic &ldquo;Revenge Loop.&rdquo;
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

// ── Settings ──────────────────────────────────────────────────────────────────

function Toggle({ on, tone = 'accent' }: { on: boolean; tone?: 'accent' }) {
  return (
    <span style={{
      width: 46, height: 27, borderRadius: 999, padding: 3, display: 'inline-flex',
      justifyContent: on ? 'flex-end' : 'flex-start', alignItems: 'center', flexShrink: 0,
      background: on ? T.accent : '#DFE2E8',
    }}>
      <span style={{ width: 21, height: 21, borderRadius: 999, background: '#fff' }} />
    </span>
  );
}

function SettingRow({ title, sub, right }: { title: string; sub?: string; right: React.ReactNode }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 20,
      padding: '16px 2px', borderBottom: `1px solid ${T.line}`,
    }}>
      <div>
        <p style={{ margin: 0, fontSize: 13.5, fontWeight: 600, color: T.ink }}>{title}</p>
        {sub && <p style={{ margin: '2px 0 0', fontSize: 12.5, color: T.muted }}>{sub}</p>}
      </div>
      {right}
    </div>
  );
}

function SettingsScreen() {
  return (
    <>
      <TopBar title="Settings" sub="Account, risk limits and guardians" />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 34, alignItems: 'start' }}>
        <div style={{ display: 'grid', gap: 30 }}>
          {/* FLAT — settings are rows you scan, the textbook case for no boxes */}
          <Section title="Risk parameters">
            <SettingRow title="Max daily loss" sub="Hard stop percentage" right={<Pill tone="accent">5 %</Pill>} />
            <SettingRow title="Cooldown period" sub="Enforced pause after a loss"
              right={<span style={{ fontSize: 13.5, color: T.body }}>15 minutes</span>} />
            <SettingRow title="Auto-close positions" sub="Close everything if the max loss is hit"
              right={<Toggle on />} />
            <SettingRow title="Max consecutive losses" sub="Stop the session after this many"
              right={<span style={{ fontSize: 13.5, color: T.body }}>3 trades</span>} />
          </Section>

          <Section title="App preferences">
            <SettingRow title="Appearance"
              right={<span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13.5, fontWeight: 600, color: T.accent }}>
                Light <ChevronRight size={15} />
              </span>} />
            <SettingRow title="Biometric unlock" sub="Require Face ID on open" right={<Toggle on={false} />} />
            <SettingRow title="Weekly report email" sub="Sunday, 20:00 IST" right={<Toggle on />} />
          </Section>
        </div>

        <div style={{ display: 'grid', gap: 20 }}>
          {/* CARD — the broker connection is a discrete object with a status */}
          <div style={{ ...CARD, padding: 20 }}>
            <Label>Account &amp; API</Label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 13, margin: '14px 0 0' }}>
              <IconTile tone="accent" size={42}><Link2 size={18} color={T.accent} /></IconTile>
              <div style={{ flex: 1 }}>
                <p style={{ margin: 0, fontSize: 14, fontWeight: 650, color: T.ink }}>Zerodha Kite</p>
                <p style={{ margin: '2px 0 0', fontSize: 12.5, fontWeight: 600, color: T.accent }}>● Connected</p>
              </div>
              <ChevronRight size={17} color={T.faint} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 18, paddingTop: 16, borderTop: `1px solid ${T.line}` }}>
              <Label>Total capital</Label>
              <span style={{ fontSize: 14, fontWeight: 700, color: T.ink, fontVariantNumeric: 'tabular-nums' }}>₹5,00,000</span>
            </div>
          </div>

          {/* CARD — tinted, because it is the one dangerous thing on the page */}
          <div style={{
            borderRadius: 20, padding: 20, background: '#FFF7F8', border: `1px solid ${T.downTint}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
              <Shield size={14} color={T.down} />
              <Label style={{ color: T.down }}>Guardian protocols</Label>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 14 }}>
              <div>
                <p style={{ margin: 0, fontSize: 13.5, fontWeight: 650, color: T.ink }}>WhatsApp emergency contact</p>
                <p style={{ margin: '4px 0 0', fontSize: 12.5, color: T.muted, lineHeight: 1.55 }}>
                  Messages your accountability partner if daily loss exceeds 5%.
                </p>
              </div>
              <Toggle on tone="accent" />
            </div>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 11, marginTop: 16, paddingTop: 14,
              borderTop: `1px solid ${T.downTint}`,
            }}>
              <IconTile tone="accent" size={34}><MessageSquare size={15} color={T.accent} /></IconTile>
              <span style={{ flex: 1, fontSize: 13, fontWeight: 600, color: T.ink }}>Partner number</span>
              <span style={{ fontSize: 13, color: T.body, fontVariantNumeric: 'tabular-nums' }}>+91 98765 43210</span>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

// ── Shell ─────────────────────────────────────────────────────────────────────

const SCREENS: Record<string, () => JSX.Element> = {
  dashboard: DashboardScreen,
  analytics: AnalyticsScreen,
  patterns: PatternsScreen,
  shield: ShieldScreen,
  coach: DashboardScreen,   // not part of this study — desktop chat is its own problem
  settings: SettingsScreen,
};

export default function SoftPrecisionWebLab() {
  const [active, setActive] = useState('dashboard');

  useEffect(() => {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap';
    document.head.appendChild(link);
    return () => { document.head.removeChild(link); };
  }, []);

  const Body = SCREENS[active] ?? DashboardScreen;

  return (
    <div style={{ minHeight: '100vh', background: T.ground, fontFamily: FONT, display: 'flex' }}>
      <Sidebar active={active} onSelect={setActive} />
      <main style={{ flex: 1, minWidth: 0, padding: '26px 34px 60px', overflowX: 'hidden' }}>
        <div style={{ maxWidth: 1240, margin: '0 auto' }}>
          {/* The rule, stated on the page, because a study nobody can read the
              intent of just becomes a screenshot. */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
            padding: '10px 14px', borderRadius: 12, background: T.accentTint, marginBottom: 22,
          }}>
            <span style={{ fontSize: 11.5, fontWeight: 700, color: T.accent, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              Design study
            </span>
            <span style={{ fontSize: 12.5, color: T.body }}>
              <strong style={{ color: T.ink }}>Card</strong> = a discrete object with one hero number ·{' '}
              <strong style={{ color: T.ink }}>Flat section</strong> = a collection you scan and compare.
              Roughly half and half by design.
            </span>
          </div>

          <Body />
        </div>
      </main>
    </div>
  );
}
