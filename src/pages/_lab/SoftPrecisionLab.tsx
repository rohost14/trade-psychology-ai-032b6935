/**
 * Soft Precision — design-language study at /soft-lab
 *
 * A faithful replication of the seven reference screens in demo_images/, built to
 * be LOOKED AT and judged, not shipped. Nothing here imports from the live app and
 * nothing in the live app imports from here; deleting this file removes it whole.
 *
 * WHAT THE REFERENCES ACTUALLY DO — the rules extracted, so this is a language
 * rather than seven one-off pastiches:
 *
 *   Ground is never white. A light warm grey (#F5F6F8) sits under pure-white
 *   cards, which is what makes the cards read as raised without a border.
 *   Elevation comes from one large, very faint shadow — never a stroke.
 *
 *   Radii are large and consistent: 22px cards, 14px icon tiles, full pills.
 *
 *   Every card has one hero: a large tabular number or a short verdict. Labels
 *   above it are 10-11px, uppercase, letterspaced, grey. That label/number pair
 *   is the single most repeated unit in the whole set.
 *
 *   Colour is used sparingly and always at two strengths — a 10% tint for the
 *   container, the full value for the mark or text inside it. Pills, icon tiles
 *   and status chips are all the same trick.
 *
 *   The bottom nav has five items with the middle one raised into a dark circle.
 *
 * DELIBERATE TENSION WITH THE CURRENT DESIGN SYSTEM. docs/DESIGN_SYSTEM.md says
 * containers are the exception — sections, hairlines, edge-to-edge tables. This
 * is the opposite: cards everywhere, generous padding, mobile-first. Both are
 * coherent; they are not compatible halfway. That is the decision to make from
 * looking at this, and the reason it is not applied to any real page.
 *
 * Font is loaded and scoped inside this route only. Headings carry explicit
 * colours because index.css applies `@apply text-foreground` to h1-h5 globally.
 */
import { useEffect, useState } from 'react';
import {
  Area, AreaChart, ResponsiveContainer, XAxis,
} from 'recharts';
import {
  ArrowLeft, ArrowUpRight, ArrowDownRight, Bell, BookOpen, ChevronDown, ChevronRight,
  ChevronsUpDown, Gauge, HelpCircle, History, Layers, Link2, LogOut, MessageSquare,
  Mic, Send, Settings as SettingsIcon, Shield, ShieldCheck, Sparkles, TrendingUp,
  Wallet, Zap, AlertTriangle, Brain, RefreshCw, Hourglass, LayoutGrid, BarChart3,
  Lock, Timer, Check,
} from 'lucide-react';

// ── Tokens ────────────────────────────────────────────────────────────────────
const T = {
  ground: '#F5F6F8',
  surface: '#FFFFFF',
  ink: '#2D3142',
  body: '#4B5060',
  muted: '#9AA0AE',
  faint: '#C4C8D2',
  line: '#EDEFF3',
  indigo: '#5A5BE0',
  indigoTint: '#EEEEFC',
  green: '#10B981',
  greenTint: '#E6F7F1',
  red: '#F4425F',
  redTint: '#FDE9ED',
  amber: '#F59E0B',
  amberTint: '#FEF3E2',
  orange: '#FF5A1F',
};

const CARD: React.CSSProperties = {
  background: T.surface,
  borderRadius: 22,
  boxShadow: '0 4px 24px rgba(45,49,66,0.06)',
};

const FONT = "'Poppins', 'Geist', system-ui, sans-serif";

// ── Shared atoms ──────────────────────────────────────────────────────────────

/** Uppercase, letterspaced, grey. The label half of the label/number unit. */
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

/** Tinted container + full-strength content. Used for every status chip. */
function Pill({ tone, children, solid = false }: {
  tone: 'green' | 'red' | 'amber' | 'indigo' | 'grey';
  children: React.ReactNode;
  solid?: boolean;
}) {
  const map = {
    green:  [T.greenTint, T.green],
    red:    [T.redTint, T.red],
    amber:  [T.amberTint, T.amber],
    indigo: [T.indigoTint, T.indigo],
    grey:   ['#F1F2F6', T.muted],
  }[tone];
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      background: solid ? map[1] : map[0],
      color: solid ? '#fff' : map[1],
      fontSize: 11, fontWeight: 600, padding: '5px 11px', borderRadius: 999,
      whiteSpace: 'nowrap',
    }}>
      {children}
    </span>
  );
}

/** Rounded-square tinted tile. Never a bare icon — always the tile. */
function IconTile({ tone, size = 40, children }: {
  tone: 'green' | 'red' | 'amber' | 'indigo' | 'grey';
  size?: number;
  children: React.ReactNode;
}) {
  const bg = {
    green: T.greenTint, red: T.redTint, amber: T.amberTint,
    indigo: T.indigoTint, grey: '#F1F2F6',
  }[tone];
  return (
    <span style={{
      width: size, height: size, borderRadius: size * 0.35, background: bg,
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
    }}>
      {children}
    </span>
  );
}

function Stat({ label, value, sub, valueColor }: {
  label: string; value: string; sub?: React.ReactNode; valueColor?: string;
}) {
  return (
    <div style={{ ...CARD, padding: '16px 16px 18px' }}>
      <Label>{label}</Label>
      <p style={{
        margin: '8px 0 0', fontSize: 26, fontWeight: 700, letterSpacing: '-0.02em',
        color: valueColor ?? T.ink, fontVariantNumeric: 'tabular-nums',
      }}>
        {value}
      </p>
      {sub && <p style={{ margin: '3px 0 0', fontSize: 11.5, color: T.muted }}>{sub}</p>}
    </div>
  );
}

/** Circular progress. Rounded caps, thick stroke, number in the middle. */
function Ring({ pct, size, stroke, color, children }: {
  pct: number; size: number; stroke: number; color: string; children?: React.ReactNode;
}) {
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#EBEDF1" strokeWidth={stroke} />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke}
          strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={circ * (1 - pct / 100)}
        />
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

function SectionHead({ title, action }: { title: string; action?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', margin: '0 0 12px' }}>
      <h2 style={{ margin: 0, fontSize: 19, fontWeight: 700, color: T.ink, letterSpacing: '-0.02em' }}>{title}</h2>
      {action && <span style={{ fontSize: 13, fontWeight: 600, color: T.indigo }}>{action}</span>}
    </div>
  );
}

// ── Bottom navigation ─────────────────────────────────────────────────────────

function BottomNav({ active, raised }: { active: string; raised?: boolean }) {
  const items = raised
    ? [
        { key: 'home', label: 'Home', Icon: LayoutGrid },
        { key: 'analytics', label: 'Analytics', Icon: BarChart3 },
        { key: 'shield', label: '', Icon: Shield },
        { key: 'patterns', label: 'Patterns', Icon: HelpCircle },
        { key: 'coach', label: 'Coach', Icon: MessageSquare },
      ]
    : [
        { key: 'home', label: 'Dashboard', Icon: LayoutGrid },
        { key: 'analytics', label: 'Analytics', Icon: BarChart3 },
        { key: 'patterns', label: 'Patterns', Icon: Brain },
        { key: 'settings', label: 'Settings', Icon: SettingsIcon },
      ];

  return (
    <div style={{
      display: 'flex', alignItems: 'flex-end', justifyContent: 'space-around',
      padding: '10px 8px 14px', background: T.surface, borderTop: `1px solid ${T.line}`,
    }}>
      {items.map(({ key, label, Icon }) => {
        // The middle item is lifted out of the bar into a dark circle.
        if (raised && key === 'shield') {
          return (
            <div key={key} style={{
              width: 54, height: 54, borderRadius: 999, background: T.ink,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              marginTop: -26, boxShadow: '0 8px 20px rgba(45,49,66,0.28)', flexShrink: 0,
            }}>
              <Shield size={22} color="#fff" fill="#fff" />
            </div>
          );
        }
        const on = key === active;
        return (
          <div key={key} style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5, minWidth: 56,
          }}>
            {on ? (
              <span style={{
                width: 34, height: 34, borderRadius: 999, background: T.indigoTint,
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon size={19} color={T.indigo} />
              </span>
            ) : (
              <Icon size={19} color={T.faint} style={{ marginTop: 7 }} />
            )}
            <span style={{ fontSize: 10.5, fontWeight: on ? 600 : 500, color: on ? T.indigo : T.muted }}>
              {label}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── 1. Dashboard ──────────────────────────────────────────────────────────────

function DashboardScreen() {
  const positions = [
    { sym: 'NIFTY 50', tag: 'FUT', qty: '500', pnl: '+₹4,200.50', up: true },
    { sym: 'BANKNIFTY', tag: 'OPT', qty: '250', pnl: '-₹1,240.00', up: false },
  ];
  const insights = [
    { Icon: AlertTriangle, tone: 'amber' as const, title: 'RSI Divergence on NIFTY', body: 'Momentum weakening, watch for reversal.', ago: '12m ago' },
    { Icon: Brain, tone: 'indigo' as const, title: 'Discipline Streak: 4 Days', body: 'You resisted 3 impulsive entries today.', ago: '2h ago' },
  ];

  return (
    <div style={{ padding: '20px 18px 8px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{
            width: 46, height: 46, borderRadius: 999, background: T.surface,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 2px 10px rgba(45,49,66,0.07)',
          }}>
            <Layers size={21} color={T.ink} />
          </span>
          <div>
            <h1 style={{ margin: 0, fontSize: 21, fontWeight: 700, color: T.ink, letterSpacing: '-0.02em' }}>
              Soft Precision
            </h1>
            <p style={{ margin: 0, fontSize: 12.5, color: T.muted }}>Tuesday, Oct 24</p>
          </div>
        </div>
        <span style={{
          width: 44, height: 44, borderRadius: 999, background: T.surface, position: 'relative',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 2px 10px rgba(45,49,66,0.07)',
        }}>
          <Bell size={19} color={T.ink} />
          <span style={{
            position: 'absolute', top: 11, right: 12, width: 7, height: 7,
            borderRadius: 999, background: T.red,
          }} />
        </span>
      </div>

      {/* Hero — the only gradient in the set, and it carries the state */}
      <div style={{
        borderRadius: 24, padding: '26px 20px 24px', textAlign: 'center', marginBottom: 30,
        background: `linear-gradient(160deg, ${T.greenTint} 0%, #F4FBF8 55%, #FFFFFF 100%)`,
        border: '1px solid #E4F4EE',
      }}>
        <span style={{
          width: 62, height: 62, borderRadius: 999, background: T.surface, marginBottom: 14,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 4px 14px rgba(16,185,129,0.16)',
        }}>
          <ShieldCheck size={28} color={T.green} />
        </span>
        <h2 style={{ margin: '0 0 10px', fontSize: 27, fontWeight: 700, color: T.ink, letterSpacing: '-0.03em' }}>
          State: Secure
        </h2>
        <Pill tone="green">
          <span style={{ width: 6, height: 6, borderRadius: 999, background: T.green }} />
          Risk Guardian Active
        </Pill>
        <p style={{ margin: '12px 0 0', fontSize: 12.5, color: T.muted }}>0 active emotional triggers</p>
      </div>

      <SectionHead title="Live Insights" action="View All" />
      <div style={{ display: 'grid', gap: 12, marginBottom: 30 }}>
        {insights.map(({ Icon, tone, title, body, ago }) => (
          <div key={title} style={{ ...CARD, padding: 16, display: 'flex', gap: 13, alignItems: 'flex-start' }}>
            <IconTile tone={tone}>
              <Icon size={18} color={tone === 'amber' ? T.amber : T.indigo} />
            </IconTile>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ margin: 0, fontSize: 14.5, fontWeight: 650, color: T.ink }}>{title}</p>
              <p style={{ margin: '3px 0 0', fontSize: 12.5, color: T.muted, lineHeight: 1.5 }}>{body}</p>
            </div>
            <span style={{ fontSize: 11.5, color: T.faint, whiteSpace: 'nowrap' }}>{ago}</span>
          </div>
        ))}
      </div>

      <SectionHead title="Active Risks" />
      <div style={{ ...CARD, overflow: 'hidden', marginBottom: 22 }}>
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 70px 110px', padding: '13px 18px',
          borderBottom: `1px solid ${T.line}`, background: '#FCFCFD',
        }}>
          <Label>Symbol</Label>
          <Label style={{ textAlign: 'right' }}>Qty</Label>
          <Label style={{ textAlign: 'right' }}>P&amp;L</Label>
        </div>
        {positions.map(p => (
          <div key={p.sym} style={{
            display: 'grid', gridTemplateColumns: '1fr 70px 110px', alignItems: 'center',
            padding: '16px 18px', borderBottom: `1px solid ${T.line}`,
          }}>
            <div>
              <p style={{ margin: 0, fontSize: 14.5, fontWeight: 650, color: T.ink }}>{p.sym}</p>
              <span style={{
                display: 'inline-block', marginTop: 5, fontSize: 10, fontWeight: 600,
                color: T.muted, background: '#F1F2F6', padding: '3px 8px', borderRadius: 6,
              }}>
                {p.tag}
              </span>
            </div>
            <span style={{ textAlign: 'right', fontSize: 14.5, color: T.body, fontVariantNumeric: 'tabular-nums' }}>
              {p.qty}
            </span>
            <span style={{
              textAlign: 'right', fontSize: 14.5, fontWeight: 700,
              color: p.up ? T.green : T.red, fontVariantNumeric: 'tabular-nums',
            }}>
              {p.pnl}
            </span>
          </div>
        ))}
        <div style={{
          padding: '14px', textAlign: 'center', fontSize: 13, color: T.body,
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
        }}>
          Show 1 more position <ChevronDown size={15} color={T.muted} />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div style={{ ...CARD, padding: '16px 16px 18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Label>Margin Used</Label>
            <Gauge size={15} color={T.muted} />
          </div>
          <p style={{ margin: '10px 0 12px', fontSize: 30, fontWeight: 700, color: T.ink, letterSpacing: '-0.03em' }}>
            65<span style={{ fontSize: 15, color: T.muted, marginLeft: 3 }}>%</span>
          </p>
          <div style={{ height: 6, borderRadius: 999, background: '#EDEFF3', overflow: 'hidden' }}>
            <div style={{ width: '65%', height: '100%', borderRadius: 999, background: T.ink }} />
          </div>
        </div>
        <div style={{ ...CARD, padding: '16px 16px 18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Label>Available</Label>
            <Wallet size={15} color={T.muted} />
          </div>
          <p style={{ margin: '14px 0 2px', fontSize: 12.5, color: T.muted }}>Cash Balance</p>
          <p style={{ margin: 0, fontSize: 22, fontWeight: 700, color: T.ink, fontVariantNumeric: 'tabular-nums' }}>
            ₹1,45,000
          </p>
        </div>
      </div>
    </div>
  );
}

// ── 2. Analytics ──────────────────────────────────────────────────────────────

const CURVE = [
  { d: 'May 01', v: 6 }, { d: '', v: 7 }, { d: '', v: 6.4 }, { d: '', v: 9 },
  { d: '', v: 14 }, { d: 'May 15', v: 16.5 }, { d: '', v: 17.2 }, { d: '', v: 19 },
  { d: '', v: 18.4 }, { d: '', v: 21 }, { d: 'May 30', v: 24.5 },
];

function AnalyticsScreen() {
  const tabs = ['Overview', 'Behavior', 'Perf.', 'Risk'];
  return (
    <div style={{ padding: '20px 0 8px' }}>
      <div style={{ padding: '0 18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h1 style={{ margin: 0, fontSize: 25, fontWeight: 700, color: T.ink, letterSpacing: '-0.03em' }}>
            Analytics
          </h1>
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12.5, fontWeight: 600,
            color: T.body, background: '#F1F2F6', padding: '8px 13px', borderRadius: 999,
          }}>
            Last 30 Days <ChevronDown size={14} color={T.muted} />
          </span>
        </div>

        <div style={{ display: 'flex', gap: 22, marginTop: 18, borderBottom: `1px solid ${T.line}` }}>
          {tabs.map((t, i) => (
            <span key={t} style={{
              fontSize: 13.5, fontWeight: i === 0 ? 700 : 500,
              color: i === 0 ? T.indigo : T.muted, paddingBottom: 10,
              borderBottom: i === 0 ? `2.5px solid ${T.indigo}` : '2.5px solid transparent',
            }}>
              {t}
            </span>
          ))}
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 20 }}>
          <div>
            <Label>Cumulative P&amp;L</Label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginTop: 6 }}>
              <span style={{ fontSize: 30, fontWeight: 700, color: T.ink, letterSpacing: '-0.03em', fontVariantNumeric: 'tabular-nums' }}>
                ₹24,502
              </span>
              <Pill tone="green">+12.4%</Pill>
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <Label>Discipline Score</Label>
            <p style={{ margin: '6px 0 0', fontSize: 26, fontWeight: 700, color: T.indigo, fontVariantNumeric: 'tabular-nums' }}>
              84<span style={{ fontSize: 14, color: T.muted }}>/100</span>
            </p>
          </div>
        </div>
      </div>

      <div style={{ height: 170, margin: '18px 0 6px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={CURVE} margin={{ top: 6, right: 18, left: 18, bottom: 0 }}>
            <defs>
              <linearGradient id="sp-curve" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={T.indigo} stopOpacity={0.22} />
                <stop offset="100%" stopColor={T.indigo} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="d" axisLine={false} tickLine={false}
              tick={{ fill: T.faint, fontSize: 10.5, fontWeight: 600 }} interval={0} />
            <Area type="monotone" dataKey="v" stroke={T.indigo} strokeWidth={2.6}
              fill="url(#sp-curve)" dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div style={{ padding: '0 18px' }}>
        {/* Gradient hairline down the left — the one place a stroke is allowed */}
        <div style={{
          borderRadius: 20, padding: 2, marginBottom: 28,
          background: `linear-gradient(150deg, ${T.indigo}, #C084FC 45%, #FB923C)`,
        }}>
          <div style={{ background: T.surface, borderRadius: 18, padding: 16, display: 'flex', gap: 13 }}>
            <IconTile tone="indigo"><Sparkles size={17} color={T.indigo} /></IconTile>
            <div style={{ flex: 1 }}>
              <p style={{ margin: 0, fontSize: 14.5, fontWeight: 700, color: T.ink }}>AI Coach Insight</p>
              <p style={{ margin: '4px 0 0', fontSize: 13, color: T.body, lineHeight: 1.55 }}>
                You hesitated on <strong style={{ color: T.ink }}>3 entries</strong> this week, costing approx{' '}
                <strong style={{ color: T.red }}>₹12k</strong>. However, your discipline score is up{' '}
                <strong style={{ color: T.green }}>15%</strong> from last week.
              </p>
            </div>
          </div>
        </div>

        <SectionHead title="Behavioral Patterns" action="View All" />
        {/* Second card deliberately runs off the edge — the reference does this to
            signal the row scrolls, which is why the scrollbar itself is hidden. */}
        <div className="sp-scroll" style={{ display: 'flex', gap: 12, overflowX: 'auto', paddingBottom: 6, marginBottom: 26 }}>
          {[
            { Icon: AlertTriangle, tone: 'red' as const, sev: 'HIGH SEVERITY', name: 'Hesitation', body: 'Missed entry points due to fear.', freq: '4x', cost: '-₹12,400' },
            { Icon: RefreshCw, tone: 'amber' as const, sev: 'MED SEVERITY', name: 'Over-trading', body: 'Taking trades outside plan.', freq: '2x', cost: '-₹6,100' },
          ].map(p => (
            <div key={p.name} style={{ ...CARD, padding: 16, minWidth: 232, flexShrink: 0 }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 14 }}>
                <IconTile tone={p.tone}>
                  <p.Icon size={17} color={p.tone === 'red' ? T.red : T.amber} />
                </IconTile>
                <Pill tone={p.tone}>{p.sev}</Pill>
              </div>
              <p style={{ margin: 0, fontSize: 17, fontWeight: 700, color: T.ink }}>{p.name}</p>
              <p style={{ margin: '3px 0 16px', fontSize: 12.5, color: T.muted }}>{p.body}</p>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
                <div><Label>Freq</Label><p style={{ margin: '3px 0 0', fontSize: 15, fontWeight: 650, color: T.ink }}>{p.freq}</p></div>
                <div style={{ textAlign: 'right' }}>
                  <Label>Est. Cost</Label>
                  <p style={{ margin: '3px 0 0', fontSize: 15, fontWeight: 700, color: T.red, fontVariantNumeric: 'tabular-nums' }}>{p.cost}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        <SectionHead title="Performance Stats" />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Stat label="◐ Win Rate" value="58%" sub={<span style={{ color: T.green }}>↗ +2% vs avg</span>} />
          <Stat label="⧗ Profit Factor" value="1.84" sub="Target: >2.0" />
          <Stat label="↑ Avg Winner" value="+₹4,200" valueColor={T.green} />
          <Stat label="↓ Avg Loser" value="-₹2,100" valueColor={T.red} />
        </div>
      </div>
    </div>
  );
}

// ── 3. Psychology Audit ───────────────────────────────────────────────────────

function PatternsScreen() {
  const days = [
    null, null, { n: 1, s: 'g' }, { n: 2, s: 'g' }, { n: 3, s: 'b' }, null, null,
    { n: 6, s: 'g' }, { n: 7, s: 'g' }, { n: 8, s: 'b' }, { n: 9, s: 'b' }, { n: 10, s: 'g' }, null, null,
    { n: 13, s: 'g' }, { n: 14, s: 'o' }, { n: 15, s: 'g' }, { n: 16, s: 'g' }, { n: 17, s: 'b' }, null, null,
    { n: 20, s: 'g' }, { n: 21, s: 'g' }, { n: 22, s: 'g' }, { n: 23, s: 't' }, { n: 24, s: 'x' }, null, null,
  ];

  return (
    <div style={{ padding: '18px 18px 8px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <ArrowLeft size={21} color={T.ink} />
          <h1 style={{ margin: 0, fontSize: 21, fontWeight: 700, color: T.ink, letterSpacing: '-0.02em' }}>
            Psychology Audit
          </h1>
        </div>
        <History size={19} color={T.body} />
      </div>

      <div style={{
        background: T.redTint, borderRadius: 16, padding: '13px 16px', marginBottom: 20,
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <IconTile tone="red" size={34}><AlertTriangle size={16} color={T.red} /></IconTile>
        <div style={{ flex: 1 }}>
          <p style={{ margin: 0, fontSize: 10.5, fontWeight: 700, letterSpacing: '0.08em', color: T.red }}>
            ACTIVE PATTERN DETECTED
          </p>
          <p style={{ margin: '2px 0 0', fontSize: 14, fontWeight: 600, color: T.ink }}>
            Tilt Trading • High Severity
          </p>
        </div>
        <span style={{ fontSize: 12.5, fontWeight: 600, color: T.red, textDecoration: 'underline' }}>Details</span>
      </div>

      <div style={{ ...CARD, padding: 20, marginBottom: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Wallet size={15} color={T.muted} />
          <Label>Emotional Tax Paid</Label>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '10px 0 8px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: 33, fontWeight: 700, color: T.ink, letterSpacing: '-0.03em', fontVariantNumeric: 'tabular-nums' }}>
            ₹45,200
          </span>
          <Pill tone="red">+12% vs last month</Pill>
        </div>
        <p style={{ margin: 0, fontSize: 13, color: T.muted, lineHeight: 1.55 }}>
          These are losses attributed to psychology (fear, greed, tilt), not strategy failure.
        </p>
        <div style={{ height: 1, background: T.line, margin: '18px 0' }} />
        <button style={{
          width: '100%', height: 54, borderRadius: 999, border: 'none', cursor: 'pointer',
          background: T.indigo, color: '#fff', fontSize: 15.5, fontWeight: 650, fontFamily: FONT,
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 9,
          boxShadow: '0 8px 20px rgba(90,91,224,0.28)',
        }}>
          <BookOpen size={18} /> View Journal
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 18 }}>
        <Stat label="Loss Rate" value="12%" sub={<span style={{ color: T.green }}>↓ 2%</span>} />
        <Stat label="Trades" value="42" sub="Last 30d" />
        <Stat label="Streak" value="3 Days" sub={<span style={{ color: T.green }}>Disciplined</span>} />
      </div>

      <div style={{ ...CARD, padding: 20, marginBottom: 22 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <h3 style={{ margin: 0, fontSize: 16.5, fontWeight: 700, color: T.ink }}>30-Day Consistency</h3>
          <div style={{ display: 'flex', gap: 12 }}>
            {[['Good', T.green], ['Impulsive', T.red]].map(([l, c]) => (
              <span key={l} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 10.5, fontWeight: 600, color: T.muted }}>
                <span style={{ width: 7, height: 7, borderRadius: 999, background: c as string }} /> {l}
              </span>
            ))}
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7,1fr)', gap: 8, marginBottom: 8 }}>
          {['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((d, i) => (
            <span key={i} style={{ textAlign: 'center', fontSize: 11, fontWeight: 600, color: T.faint }}>{d}</span>
          ))}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7,1fr)', gap: 8 }}>
          {days.map((d, i) => {
            if (!d) return <span key={i} style={{ aspectRatio: '1', borderRadius: 999, border: `1px solid ${T.line}` }} />;
            const style: React.CSSProperties = {
              aspectRatio: '1', borderRadius: 999, display: 'flex', alignItems: 'center',
              justifyContent: 'center', fontSize: 12.5, fontWeight: 650,
            };
            if (d.s === 'g') return <span key={i} style={{ ...style, background: T.green, color: '#fff' }}>{d.n}</span>;
            if (d.s === 'b') return <span key={i} style={{ ...style, background: T.red, color: '#fff' }}>{d.n}</span>;
            if (d.s === 't') return <span key={i} style={{ ...style, background: T.indigo, color: '#fff', boxShadow: `0 0 0 4px ${T.indigoTint}` }}>{d.n}</span>;
            if (d.s === 'x') return <span key={i} style={{ ...style, border: `1px dashed ${T.faint}`, color: T.faint }}>{d.n}</span>;
            return <span key={i} style={{ ...style, border: `1px solid ${T.line}`, color: T.faint }}>{d.n}</span>;
          })}
        </div>
      </div>

      <SectionHead title="Recurring Triggers" action="View All" />
      <div style={{ display: 'grid', gap: 12 }}>
        {[
          { Icon: Zap, tone: 'amber' as const, name: 'Revenge Trading', sev: 'MED SEVERITY', body: 'Triggered after a loss >2% within 5 mins.', freq: '3x this month', cost: '₹12,400' },
          { Icon: Hourglass, tone: 'indigo' as const, name: 'Hesitation', sev: 'LOW SEVERITY', body: 'Missed entry points due to over-analysis.', freq: '5x this month', cost: '~₹8,000 (Missed)' },
        ].map(t => (
          <div key={t.name} style={{ ...CARD, padding: 16, display: 'flex', gap: 13 }}>
            <IconTile tone={t.tone}><t.Icon size={18} color={t.tone === 'amber' ? T.amber : T.indigo} /></IconTile>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <p style={{ margin: 0, fontSize: 15, fontWeight: 700, color: T.ink }}>{t.name}</p>
                <Pill tone={t.tone === 'amber' ? 'amber' : 'grey'}>{t.sev}</Pill>
              </div>
              <p style={{ margin: '4px 0 10px', fontSize: 12.5, color: T.muted }}>{t.body}</p>
              <div style={{ display: 'flex', gap: 18, fontSize: 11.5, color: T.muted }}>
                <span>Freq: {t.freq}</span><span>Cost: {t.cost}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── 4. Blowup Shield ──────────────────────────────────────────────────────────

function ShieldScreen() {
  return (
    <div style={{ padding: '22px 18px 8px' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 26 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 25, fontWeight: 700, color: T.ink, letterSpacing: '-0.03em' }}>
            Blowup Shield
          </h1>
          <p style={{ margin: '2px 0 0', fontSize: 13.5, color: T.muted }}>Risk Intervention Protocol</p>
        </div>
        <Pill tone="red">
          <span style={{ width: 6, height: 6, borderRadius: 999, background: T.red }} /> HIGH RISK
        </Pill>
      </div>

      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 30 }}>
        <Ring pct={84} size={244} stroke={17} color={T.red}>
          <span style={{
            width: 96, height: 96, borderRadius: 999, background: T.surface, marginBottom: 8,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 4px 18px rgba(45,49,66,0.08)',
          }}>
            <Lock size={30} color={T.red} />
          </span>
          <span style={{ fontSize: 42, fontWeight: 700, color: T.ink, letterSpacing: '-0.04em', lineHeight: 1 }}>
            84<span style={{ fontSize: 20, color: T.faint }}>/100</span>
          </span>
          <Label style={{ marginTop: 6 }}>Risk Score</Label>
        </Ring>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 11, marginBottom: 26 }}>
        {[
          { l: 'Tilt', v: 75, c: T.amber },
          { l: 'Fatigue', v: 20, c: T.green },
          { l: 'Volat.', v: 90, c: T.red },
        ].map(m => (
          <div key={m.l} style={{ ...CARD, padding: '16px 8px 14px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 9 }}>
            <Ring pct={m.v} size={62} stroke={6} color={m.c}>
              <span style={{ fontSize: 13, fontWeight: 700, color: T.ink }}>{m.v}%</span>
            </Ring>
            <Label>{m.l}</Label>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 13 }}>
        <Brain size={17} color={T.ink} />
        <h3 style={{ margin: 0, fontSize: 16.5, fontWeight: 700, color: T.ink }}>Active Patterns</h3>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 9, marginBottom: 24 }}>
        <Pill tone="red" solid><AlertTriangle size={13} /> Revenge Trading</Pill>
        <Pill tone="red" solid><TrendingUp size={13} /> Over-leveraging</Pill>
        {['FOMO', 'Hesitation', 'Confirmation Bias'].map(p => (
          <span key={p} style={{
            fontSize: 12.5, fontWeight: 500, color: T.muted, padding: '7px 15px',
            borderRadius: 999, border: `1px solid ${T.line}`, background: T.surface,
          }}>
            {p}
          </span>
        ))}
      </div>

      <div style={{ ...CARD, padding: 18, display: 'flex', gap: 13, marginBottom: 26 }}>
        <IconTile tone="indigo" size={44}><Sparkles size={19} color={T.indigo} /></IconTile>
        <div style={{ flex: 1 }}>
          <p style={{ margin: 0, fontSize: 15.5, fontWeight: 700, color: T.ink }}>Coach Insight</p>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: T.muted, lineHeight: 1.6 }}>
            You&apos;ve entered 3 trades in the last 10 minutes after a significant loss. This pattern
            matches your historic &ldquo;Revenge Loop.&rdquo;
          </p>
        </div>
      </div>

      <button style={{
        width: '100%', height: 62, borderRadius: 999, border: 'none', cursor: 'pointer',
        background: `linear-gradient(100deg, ${T.red}, #E11D48)`, color: '#fff',
        fontSize: 15.5, fontWeight: 700, letterSpacing: '0.02em', fontFamily: FONT,
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
        boxShadow: '0 10px 26px rgba(244,66,95,0.34)',
      }}>
        <Timer size={20} /> TRIGGER GUARDIAN (STOP 15m)
      </button>
      <p style={{
        margin: '12px 0 0', textAlign: 'center', fontSize: 12, color: T.faint,
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
      }}>
        <Shield size={12} /> Securely locks trading API immediately
      </p>
    </div>
  );
}

// ── 5. AI Coach chat ──────────────────────────────────────────────────────────

function ChatScreen() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{
        padding: '16px 18px', background: T.surface, borderBottom: `1px solid ${T.line}`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <ArrowLeft size={21} color={T.ink} />
        <div style={{ textAlign: 'center' }}>
          <p style={{ margin: 0, fontSize: 17.5, fontWeight: 700, color: T.ink, display: 'flex', alignItems: 'center', gap: 8 }}>
            AI Coach <span style={{ width: 8, height: 8, borderRadius: 999, background: T.green }} />
          </p>
          <p style={{ margin: '1px 0 0', fontSize: 12, color: T.muted }}>Session Active • 12m</p>
        </div>
        <span style={{ fontSize: 14.5, fontWeight: 650, color: T.red }}>End</span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 16px' }}>
        <div style={{ textAlign: 'center', marginBottom: 22 }}>
          <span style={{
            fontSize: 11.5, color: T.muted, background: '#EDEFF3',
            padding: '6px 13px', borderRadius: 999,
          }}>
            Today, 10:23 AM
          </span>
        </div>

        <p style={{ margin: '0 0 7px 44px', fontSize: 11.5, color: T.muted }}>Coach</p>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 9, marginBottom: 20 }}>
          <IconTile tone="indigo" size={34}><Brain size={16} color={T.indigo} /></IconTile>
          <div style={{
            background: T.surface, borderRadius: 20, borderBottomLeftRadius: 6, padding: '15px 17px',
            boxShadow: '0 2px 14px rgba(45,49,66,0.06)', maxWidth: 300,
          }}>
            <p style={{ margin: 0, fontSize: 14.5, color: T.ink, lineHeight: 1.55 }}>
              I noticed a spike in trade frequency. You&apos;ve executed 4 trades in the last 15 minutes.
            </p>
            <p style={{ margin: '11px 0 0', fontSize: 14.5, color: T.muted, lineHeight: 1.55 }}>
              Are you feeling rushed to recover the morning&apos;s drawdown?
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 5 }}>
          <div style={{
            background: T.ink, color: '#fff', borderRadius: 20, borderBottomRightRadius: 6,
            padding: '15px 17px', maxWidth: 300,
          }}>
            <p style={{ margin: 0, fontSize: 14.5, lineHeight: 1.55 }}>
              I just need one good setup to get back to breakeven. The market is moving fast.
            </p>
          </div>
        </div>
        <p style={{ margin: '0 2px 22px 0', textAlign: 'right', fontSize: 11.5, color: T.faint }}>Read 10:25 AM</p>

        <p style={{ margin: '0 0 7px 44px', fontSize: 11.5, color: T.muted }}>Coach</p>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 9 }}>
          <IconTile tone="indigo" size={34}><Brain size={16} color={T.indigo} /></IconTile>
          <div style={{
            background: T.surface, borderRadius: 20, borderBottomLeftRadius: 6, padding: '15px 17px',
            boxShadow: '0 2px 14px rgba(45,49,66,0.06)', maxWidth: 300,
            /* Fades under the composer — the reference does this too */
            maskImage: 'linear-gradient(to bottom, #000 40%, transparent)',
            WebkitMaskImage: 'linear-gradient(to bottom, #000 40%, transparent)',
          }}>
            <p style={{ margin: 0, fontSize: 14.5, color: T.muted, lineHeight: 1.55 }}>
              That thought pattern aligns with{' '}
              <span style={{ color: T.red, fontWeight: 600 }}>Revenge Trading</span>. Chasing…
            </p>
          </div>
        </div>
      </div>

      <div style={{ padding: '12px 16px 14px', background: T.surface, borderTop: `1px solid ${T.line}` }}>
        <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
          {[
            { Icon: Brain, label: 'Start Breathing Exercise', c: T.indigo },
            { Icon: History, label: 'Review Last Loss', c: T.red },
          ].map(a => (
            <span key={a.label} style={{
              flex: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 7,
              fontSize: 12.5, fontWeight: 600, color: T.ink, padding: '11px 8px',
              borderRadius: 999, border: `1px solid ${T.line}`, whiteSpace: 'nowrap',
            }}>
              <a.Icon size={15} color={a.c} /> {a.label}
            </span>
          ))}
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, background: '#F1F2F6',
          borderRadius: 999, padding: '7px 7px 7px 16px',
        }}>
          <Mic size={19} color={T.muted} />
          <span style={{ flex: 1, fontSize: 14.5, color: T.faint }}>Type or vent…</span>
          <span style={{
            width: 44, height: 44, borderRadius: 999, background: T.indigo,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Send size={18} color="#fff" />
          </span>
        </div>
      </div>
    </div>
  );
}

// ── 6. Settings ───────────────────────────────────────────────────────────────

function Toggle({ on, tone = 'indigo' }: { on: boolean; tone?: 'indigo' | 'green' }) {
  return (
    <span style={{
      width: 50, height: 29, borderRadius: 999, padding: 3, display: 'inline-flex',
      justifyContent: on ? 'flex-end' : 'flex-start', alignItems: 'center',
      background: on ? (tone === 'green' ? T.green : T.indigo) : '#DFE2E8',
    }}>
      <span style={{ width: 23, height: 23, borderRadius: 999, background: '#fff' }} />
    </span>
  );
}

function Row({ title, sub, right, last }: {
  title: string; sub?: string; right?: React.ReactNode; last?: boolean;
}) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
      padding: '15px 17px', borderBottom: last ? 'none' : `1px solid ${T.line}`,
    }}>
      <div style={{ minWidth: 0 }}>
        <p style={{ margin: 0, fontSize: 14.5, fontWeight: 600, color: T.ink }}>{title}</p>
        {sub && <p style={{ margin: '2px 0 0', fontSize: 12, color: T.muted }}>{sub}</p>}
      </div>
      {right}
    </div>
  );
}

function SettingsScreen() {
  return (
    <div style={{ padding: '0 0 8px' }}>
      <div style={{
        padding: '17px 18px', background: T.surface, borderBottom: `1px solid ${T.line}`,
        display: 'flex', alignItems: 'center', gap: 14,
      }}>
        <ArrowLeft size={21} color={T.ink} />
        <h1 style={{ margin: '0 auto', fontSize: 19, fontWeight: 700, color: T.ink, paddingRight: 34 }}>
          Settings
        </h1>
      </div>

      <div style={{ padding: '18px 18px 0' }}>
        <div style={{ display: 'flex', background: '#F1F2F6', borderRadius: 999, padding: 4, marginBottom: 26 }}>
          {['Profile', 'Notifications'].map((t, i) => (
            <span key={t} style={{
              flex: 1, textAlign: 'center', fontSize: 14, fontWeight: 650, padding: '10px 0',
              borderRadius: 999, background: i === 0 ? T.surface : 'transparent',
              color: i === 0 ? T.ink : T.muted,
              boxShadow: i === 0 ? '0 2px 8px rgba(45,49,66,0.08)' : 'none',
            }}>
              {t}
            </span>
          ))}
        </div>

        <Label style={{ display: 'block', marginBottom: 9 }}>Account &amp; API</Label>
        <div style={{ ...CARD, overflow: 'hidden', marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 13, padding: '15px 17px', borderBottom: `1px solid ${T.line}` }}>
            <IconTile tone="amber" size={38}><Link2 size={17} color={T.orange} /></IconTile>
            <div style={{ flex: 1 }}>
              <p style={{ margin: 0, fontSize: 14.5, fontWeight: 600, color: T.ink }}>Zerodha Kite</p>
              <p style={{ margin: '2px 0 0', fontSize: 12.5, color: T.green, fontWeight: 600 }}>● Connected</p>
            </div>
            <ChevronRight size={18} color={T.faint} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 13, padding: '15px 17px' }}>
            <IconTile tone="grey" size={38}><Wallet size={17} color={T.body} /></IconTile>
            <p style={{ margin: 0, flex: 1, fontSize: 14.5, fontWeight: 600, color: T.ink }}>Total Capital</p>
            <span style={{ fontSize: 15, fontWeight: 650, color: T.ink, fontVariantNumeric: 'tabular-nums' }}>
              <span style={{ color: T.muted, marginRight: 8 }}>₹</span>5,00,000
            </span>
          </div>
        </div>

        <Label style={{ display: 'block', marginBottom: 9 }}>Risk Parameters</Label>
        <div style={{ ...CARD, overflow: 'hidden', marginBottom: 24 }}>
          <Row title="Max Daily Loss" sub="Hard stop percentage"
            right={<Pill tone="indigo">5 %</Pill>} />
          <Row title="Cooldown Period"
            right={<span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 14, color: T.body }}>
              15 Minutes <ChevronsUpDown size={15} color={T.faint} />
            </span>} />
          <Row title="Auto-Close Positions" sub="Close all if max loss hit" right={<Toggle on />} last />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 9 }}>
          <Shield size={13} color={T.red} />
          <Label style={{ color: T.red }}>Guardian Protocols</Label>
        </div>
        <div style={{
          borderRadius: 22, overflow: 'hidden', marginBottom: 24,
          background: '#FFF7F8', border: `1px solid ${T.redTint}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, padding: '16px 17px' }}>
            <div style={{ flex: 1 }}>
              <p style={{ margin: 0, fontSize: 14.5, fontWeight: 650, color: T.ink }}>WhatsApp Emergency Contact</p>
              <p style={{ margin: '4px 0 0', fontSize: 12.5, color: T.muted, lineHeight: 1.5 }}>
                Automatically message your accountability partner if daily loss exceeds 5%.
              </p>
            </div>
            <Toggle on tone="green" />
          </div>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 12, padding: '14px 17px',
            borderTop: `1px solid ${T.redTint}`, background: 'rgba(255,255,255,0.6)',
          }}>
            <IconTile tone="green" size={36}><MessageSquare size={16} color={T.green} /></IconTile>
            <p style={{ margin: 0, flex: 1, fontSize: 14, fontWeight: 600, color: T.ink }}>Partner Number</p>
            <span style={{ fontSize: 14, color: T.body, fontVariantNumeric: 'tabular-nums' }}>+91 98765 43210</span>
          </div>
        </div>

        <Label style={{ display: 'block', marginBottom: 9 }}>App Preferences</Label>
        <div style={{ ...CARD, overflow: 'hidden', marginBottom: 26 }}>
          <Row title="Appearance"
            right={<span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 14, color: T.indigo, fontWeight: 600 }}>
              Light <ChevronRight size={16} />
            </span>} />
          <Row title="FaceID Required" right={<Toggle on={false} />} last />
        </div>

        <p style={{ margin: '0 0 14px', textAlign: 'center', fontSize: 12, color: T.faint }}>
          Soft Precision v1.0.2
        </p>
        <p style={{
          margin: 0, textAlign: 'center', fontSize: 14.5, fontWeight: 650, color: T.red,
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        }}>
          <LogOut size={17} /> Log Out
        </p>
      </div>
    </div>
  );
}

// ── 7. Connect broker ─────────────────────────────────────────────────────────

function BrokerScreen() {
  return (
    <div style={{ padding: '18px 22px 8px', display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 34 }}>
        <ArrowLeft size={22} color={T.ink} />
        <div style={{ display: 'flex', gap: 7 }}>
          {[0, 1, 2].map(i => (
            <span key={i} style={{
              width: 8, height: 8, borderRadius: 999,
              background: i === 0 ? T.indigo : '#DFE2E8',
            }} />
          ))}
        </div>
        <span style={{
          width: 26, height: 26, borderRadius: 999, background: '#B9BEC9',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <HelpCircle size={18} color="#fff" />
        </span>
      </div>

      {/* Two nodes joined by a dashed link — the whole idea of the screen in one row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0, marginBottom: 12 }}>
        <div style={{ textAlign: 'center' }}>
          <span style={{
            width: 82, height: 82, borderRadius: 26, background: T.surface,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 6px 22px rgba(45,49,66,0.09)',
          }}>
            <span style={{
              width: 52, height: 52, borderRadius: 999, background: T.ink,
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Layers size={24} color="#fff" />
            </span>
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', flex: 1, maxWidth: 132 }}>
          <span style={{ flex: 1, borderTop: `2px dashed ${T.faint}` }} />
          <span style={{
            width: 38, height: 38, borderRadius: 999, background: T.surface, flexShrink: 0,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            border: `1px solid ${T.line}`,
          }}>
            <Link2 size={16} color={T.muted} />
          </span>
          <span style={{ flex: 1, borderTop: `2px dashed ${T.faint}` }} />
        </div>
        <span style={{
          width: 82, height: 82, borderRadius: 26, background: '#F1F2F6',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <span style={{ fontSize: 22, color: T.faint }}>◈</span>
        </span>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 40, padding: '0 4px' }}>
        <Label>Soft Precision</Label>
        <Label>Zerodha Kite</Label>
      </div>

      <h1 style={{ margin: '0 0 14px', textAlign: 'center', fontSize: 28, fontWeight: 700, color: T.ink, letterSpacing: '-0.03em' }}>
        Connect Broker
      </h1>
      <p style={{ margin: '0 0 32px', textAlign: 'center', fontSize: 15, color: T.body, lineHeight: 1.6 }}>
        Securely link your Kite account to enable real-time risk intervention and behavioral analysis.
      </p>

      <div style={{ background: '#F4F5F8', borderRadius: 20, padding: '20px 18px', marginBottom: 'auto' }}>
        <Label style={{ display: 'block', marginBottom: 16 }}>Security &amp; Privacy</Label>
        {[
          ['Read-only access to P&L', 'We cannot place trades without your trigger.'],
          ['No withdrawal permissions', 'Your funds remain in your broker account.'],
          ['256-bit Encryption', 'Bank-grade security standards.'],
        ].map(([t, s], i, arr) => (
          <div key={t} style={{ display: 'flex', gap: 12, marginBottom: i === arr.length - 1 ? 0 : 16 }}>
            <span style={{
              width: 22, height: 22, borderRadius: 999, background: T.greenTint, flexShrink: 0, marginTop: 2,
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Check size={13} color={T.green} strokeWidth={3} />
            </span>
            <div>
              <p style={{ margin: 0, fontSize: 14.5, fontWeight: 650, color: T.ink }}>{t}</p>
              <p style={{ margin: '2px 0 0', fontSize: 12.5, color: T.muted }}>{s}</p>
            </div>
          </div>
        ))}
      </div>

      <button style={{
        width: '100%', height: 60, borderRadius: 999, border: 'none', cursor: 'pointer',
        background: T.orange, color: '#fff', fontSize: 16.5, fontWeight: 650, fontFamily: FONT,
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12,
        boxShadow: '0 10px 26px rgba(255,90,31,0.3)', margin: '30px 0 14px',
      }}>
        <span style={{ width: 21, height: 21, borderRadius: 4, background: '#fff' }} />
        Authorize with Kite
      </button>
      <p style={{ margin: '0 0 16px', textAlign: 'center', fontSize: 12.5, color: T.muted, lineHeight: 1.6 }}>
        By connecting, you agree to our <u>Terms of Service</u> and <u>Privacy Policy</u>.
      </p>
      <p style={{
        margin: 0, textAlign: 'center', fontSize: 12.5, color: T.muted,
        borderTop: `1px solid ${T.line}`, paddingTop: 16,
      }}>
        Step 1 of 3: Broker Integration
      </p>
    </div>
  );
}

// ── Shell ─────────────────────────────────────────────────────────────────────

interface ScreenDef {
  key: string;
  label: string;
  nav: string;
  raised: boolean;
  Body: () => JSX.Element;
  /** Screens that draw their own header/footer edge to edge. */
  noNav?: boolean;
}

const SCREENS: ScreenDef[] = [
  { key: 'dashboard', label: 'Dashboard', nav: 'home',      raised: true,  Body: DashboardScreen },
  { key: 'analytics', label: 'Analytics', nav: 'analytics', raised: false, Body: AnalyticsScreen },
  { key: 'patterns',  label: 'Patterns',  nav: 'patterns',  raised: true,  Body: PatternsScreen },
  { key: 'shield',    label: 'Shield',    nav: '',          raised: false, Body: ShieldScreen, noNav: true },
  { key: 'chat',      label: 'AI Coach',  nav: 'coach',     raised: false, Body: ChatScreen },
  { key: 'settings',  label: 'Settings',  nav: 'settings',  raised: false, Body: SettingsScreen },
  { key: 'broker',    label: 'Broker',    nav: '',          raised: false, Body: BrokerScreen, noNav: true },
];

export default function SoftPrecisionLab() {
  const [active, setActive] = useState<string>('dashboard');

  // Poppins and the scrollbar rule are injected here rather than added to
  // index.css so the study cannot change the typeface — or the scrollbars — of
  // the real app just by existing. Both are removed on unmount.
  //
  // The scrollbars matter more than they sound: a phone does not render a grey
  // track down the side of its content, and leaving one visible makes the whole
  // frame read as a web page in a box rather than as the screen it is imitating.
  useEffect(() => {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap';
    document.head.appendChild(link);

    const style = document.createElement('style');
    style.textContent = `
      .sp-scroll { scrollbar-width: none; -ms-overflow-style: none; }
      .sp-scroll::-webkit-scrollbar { width: 0; height: 0; display: none; }
    `;
    document.head.appendChild(style);

    return () => {
      document.head.removeChild(link);
      document.head.removeChild(style);
    };
  }, []);

  const screen = SCREENS.find(s => s.key === active) ?? SCREENS[0];
  const { Body } = screen;

  return (
    <div style={{ minHeight: '100vh', background: '#E9EBF0', fontFamily: FONT, padding: '28px 16px 56px' }}>
      <div style={{ maxWidth: 1100, margin: '0 auto' }}>
        <p style={{ margin: '0 0 4px', fontSize: 11, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#8A90A0' }}>
          Design study · not wired to anything
        </p>
        <h1 style={{ margin: '0 0 6px', fontSize: 30, fontWeight: 700, color: T.ink, letterSpacing: '-0.03em' }}>
          Soft Precision
        </h1>
        <p style={{ margin: '0 0 22px', fontSize: 14.5, color: '#6B7183', maxWidth: 640, lineHeight: 1.6 }}>
          The seven reference screens rebuilt as one language: grey ground, white cards, 22px radii,
          one soft shadow, a label/number pair as the repeating unit, and colour only ever as a 10%
          tint plus a full-strength mark.
        </p>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 26 }}>
          {SCREENS.map(s => (
            <button
              key={s.key}
              onClick={() => setActive(s.key)}
              style={{
                fontFamily: FONT, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                padding: '9px 17px', borderRadius: 999,
                border: active === s.key ? 'none' : '1px solid #D6DAE3',
                background: active === s.key ? T.ink : 'transparent',
                color: active === s.key ? '#fff' : '#5C6273',
              }}
            >
              {s.label}
            </button>
          ))}
        </div>

        {/* 390px is the reference width — judging this at desktop width would be
            judging a layout that does not exist. */}
        <div style={{
          width: 390, maxWidth: '100%', height: 844, margin: '0 auto',
          background: T.ground, borderRadius: 42, overflow: 'hidden',
          display: 'flex', flexDirection: 'column',
          boxShadow: '0 30px 70px rgba(30,34,48,0.22), 0 0 0 10px #1E2230',
        }}>
          <div className="sp-scroll" style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
            <Body />
          </div>
          {!screen.noNav && <BottomNav active={screen.nav} raised={screen.raised} />}
        </div>
      </div>
    </div>
  );
}
