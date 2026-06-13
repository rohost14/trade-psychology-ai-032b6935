import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { RefreshCw, AlertTriangle, ArrowRight, RotateCcw } from 'lucide-react';
import { adminApi } from '@/lib/adminApi';

// ─── Design tokens ────────────────────────────────────────────────────────────
const T = {
  bg:       '#09090b',
  surface:  '#111115',
  raised:   '#16161d',
  border:   '#1c1c28',
  border2:  '#252536',
  text:     '#f1f0f5',
  muted:    '#6b6a82',
  dim:      '#3a3a50',
  amber:    '#f59e0b',
  amberBg:  'rgba(245,158,11,0.1)',
  green:    '#22c55e',
  greenBg:  'rgba(34,197,94,0.08)',
  red:      '#ef4444',
  redBg:    'rgba(239,68,68,0.08)',
  orange:   '#f97316',
  blue:     '#3b82f6',
  dm:       "'Inter', 'DM Sans', sans-serif",
};

const SEV_COLOR: Record<string, string> = {
  critical: T.red, high: T.orange, medium: T.amber, low: T.green,
};
const SEV_ORDER = ['critical', 'high', 'medium', 'low'];

// ─── Types ────────────────────────────────────────────────────────────────────
interface InsightsData {
  period_days: number;
  patterns:   { pattern: string; count: number }[];
  severity:   { severity: string; count: number }[];
  daily:      { date: string; count: number }[];
  engagement: {
    pattern: string; total: number; acknowledged: number;
    rate: number; avg_ack_minutes: number | null;
  }[];
  top_users: {
    account_id: string; broker_user_id: string; email: string;
    alert_count: number; high_severity: number; last_alert_at: string | null;
  }[];
  recurrence: {
    pattern: string; base_acked: number; recurrence_count: number; rate: number;
  }[];
}

// ─── Sub-components ───────────────────────────────────────────────────────────
function SectionHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 18 }}>
      <span style={{ fontSize: 13, fontWeight: 600, color: T.text, letterSpacing: '-0.01em' }}>{title}</span>
      {sub && <span style={{ fontSize: 11, color: T.dim }}>{sub}</span>}
    </div>
  );
}

function Card({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: '20px 22px', ...style }}>
      {children}
    </div>
  );
}

function Spinner() {
  return (
    <>
      <div style={{ width: 22, height: 22, border: `2px solid ${T.amber}`, borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </>
  );
}

function RateBar({ rate, color }: { rate: number; color: string }) {
  return (
    <div style={{ flex: 1, height: 5, background: T.raised, borderRadius: 3, overflow: 'hidden' }}>
      <div style={{ height: '100%', width: `${rate * 100}%`, background: color, borderRadius: 3, transition: 'width 0.5s ease' }} />
    </div>
  );
}

function PatternLabel({ pattern }: { pattern: string }) {
  return (
    <span style={{ fontFamily: "'JetBrains Mono', 'Fira Code', monospace", fontSize: 11, color: T.muted }}>
      {pattern.replace(/_/g, '_')}
    </span>
  );
}

// ─── Section: Top Patterns ────────────────────────────────────────────────────
function TopPatterns({ patterns }: { patterns: InsightsData['patterns'] }) {
  const max = Math.max(...patterns.map(p => p.count), 1);
  return (
    <Card>
      <SectionHeader title="Top Patterns" sub={`${patterns.length} types`} />
      {patterns.length === 0
        ? <p style={{ fontSize: 12, color: T.dim }}>No data for this period</p>
        : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
            {patterns.slice(0, 10).map(({ pattern, count }) => (
              <div key={pattern} style={{ display: 'grid', gridTemplateColumns: '185px 1fr 36px', gap: 10, alignItems: 'center' }}>
                <PatternLabel pattern={pattern} />
                <div style={{ height: 6, background: T.raised, borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{
                    height: '100%', width: `${(count / max) * 100}%`,
                    background: `linear-gradient(90deg, ${T.amber}cc, ${T.amber}55)`,
                    borderRadius: 3, transition: 'width 0.6s ease',
                  }} />
                </div>
                <span style={{ fontSize: 12, fontWeight: 600, color: T.text, fontVariantNumeric: 'tabular-nums', textAlign: 'right' }}>{count}</span>
              </div>
            ))}
          </div>
        )}
    </Card>
  );
}

// ─── Section: Severity Breakdown ──────────────────────────────────────────────
function SeverityBreakdown({ severity }: { severity: InsightsData['severity'] }) {
  const total = severity.reduce((s, r) => s + r.count, 0);
  const sorted = [...severity].sort((a, b) => SEV_ORDER.indexOf(a.severity) - SEV_ORDER.indexOf(b.severity));
  return (
    <Card>
      <SectionHeader title="Severity Breakdown" sub={total ? `${total.toLocaleString('en-IN')} total` : undefined} />
      {sorted.length === 0
        ? <p style={{ fontSize: 12, color: T.dim }}>No data</p>
        : (
          <>
            {/* Stacked bar */}
            <div style={{ display: 'flex', height: 7, borderRadius: 4, overflow: 'hidden', gap: 1, marginBottom: 18 }}>
              {sorted.map(({ severity: sev, count }) => (
                <div key={sev} style={{ flex: count, background: SEV_COLOR[sev] || T.muted, minWidth: 2 }}
                  title={`${sev}: ${count}`} />
              ))}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {sorted.map(({ severity: sev, count }) => {
                const color = SEV_COLOR[sev] || T.muted;
                const pct = total > 0 ? Math.round((count / total) * 100) : 0;
                return (
                  <div key={sev}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                      <span style={{ fontSize: 12, color, fontWeight: 600, textTransform: 'capitalize' }}>{sev}</span>
                      <span style={{ fontSize: 12, color: T.muted, fontVariantNumeric: 'tabular-nums' }}>{count.toLocaleString('en-IN')} · {pct}%</span>
                    </div>
                    <div style={{ height: 5, background: T.raised, borderRadius: 3, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 3, transition: 'width 0.6s ease' }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
    </Card>
  );
}

// ─── Section: Alert Volume Sparkline ─────────────────────────────────────────
function AlertVolume({ daily }: { daily: InsightsData['daily'] }) {
  if (daily.length < 2) return (
    <Card>
      <SectionHeader title="Daily Alert Volume" sub="Last 14 days" />
      <p style={{ fontSize: 12, color: T.dim }}>Not enough data</p>
    </Card>
  );
  const max = Math.max(...daily.map(d => d.count), 1);
  const W = 600, H = 72, P = 4;
  const pts = daily.map((d, i) => {
    const x = P + (i / (daily.length - 1)) * (W - P * 2);
    const y = H - P - (d.count / max) * (H - P * 2);
    return `${x},${y}`;
  });
  return (
    <Card>
      <SectionHeader title="Daily Alert Volume" sub="Last 14 days" />
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 72, display: 'block' }} preserveAspectRatio="none">
        <defs>
          <linearGradient id="ag" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={T.amber} stopOpacity="0.15" />
            <stop offset="100%" stopColor={T.amber} stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon points={`${P},${H} ${pts.join(' ')} ${W - P},${H}`} fill="url(#ag)" />
        <polyline points={pts.join(' ')} fill="none" stroke={T.amber} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
        <span style={{ fontSize: 11, color: T.dim }}>{daily[0].date}</span>
        <span style={{ fontSize: 11, color: T.dim }}>{daily[daily.length - 1].date}</span>
      </div>
    </Card>
  );
}

// ─── Section: Engagement Rate ─────────────────────────────────────────────────
function EngagementTable({ rows }: { rows: InsightsData['engagement'] }) {
  return (
    <Card style={{ gridColumn: '1 / -1' }}>
      <SectionHeader
        title="Alert Engagement Rate"
        sub="How often traders acknowledge each pattern type"
      />
      {rows.length === 0
        ? <p style={{ fontSize: 12, color: T.dim }}>No alert data for this period</p>
        : (
          <div>
            {/* Header */}
            <div style={{ display: 'grid', gridTemplateColumns: '185px 1fr 70px 80px 90px 110px', gap: 14, padding: '0 0 8px', borderBottom: `1px solid ${T.border}`, marginBottom: 2 }}>
              {['Pattern', '', 'Fired', 'Acked', 'Rate', 'Avg Response'].map((h, i) => (
                <span key={i} style={{ fontSize: 10, fontWeight: 600, color: T.dim, textTransform: 'uppercase', letterSpacing: '0.07em', textAlign: i >= 2 ? 'right' : 'left' }}>{h}</span>
              ))}
            </div>
            {rows.map(row => {
              const rateColor = row.rate >= 0.6 ? T.green : row.rate >= 0.3 ? T.amber : T.red;
              return (
                <div key={row.pattern} style={{
                  display: 'grid', gridTemplateColumns: '185px 1fr 70px 80px 90px 110px', gap: 14,
                  alignItems: 'center', padding: '10px 0', borderBottom: `1px solid ${T.border}`,
                }}>
                  <PatternLabel pattern={row.pattern} />
                  <RateBar rate={row.rate} color={rateColor} />
                  <span style={{ fontSize: 12, color: T.muted, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{row.total.toLocaleString('en-IN')}</span>
                  <span style={{ fontSize: 12, color: T.text, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{row.acknowledged.toLocaleString('en-IN')}</span>
                  <span style={{ fontSize: 13, fontWeight: 700, color: rateColor, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {(row.rate * 100).toFixed(1)}%
                  </span>
                  <span style={{ fontSize: 12, color: T.muted, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {row.avg_ack_minutes != null ? `${row.avg_ack_minutes}m` : '—'}
                  </span>
                </div>
              );
            })}
          </div>
        )}
    </Card>
  );
}

// ─── Section: Top Impacted Users ─────────────────────────────────────────────
function TopUsers({ users }: { users: InsightsData['top_users'] }) {
  const navigate = useNavigate();
  return (
    <Card>
      <SectionHeader title="Top Impacted Users" sub="By alert count" />
      {users.length === 0
        ? <p style={{ fontSize: 12, color: T.dim }}>No users yet</p>
        : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {users.map((u, i) => {
              const lastAt = u.last_alert_at
                ? new Date(u.last_alert_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
                : '—';
              const highPct = u.alert_count > 0 ? u.high_severity / u.alert_count : 0;
              return (
                <div
                  key={u.account_id}
                  onClick={() => navigate(`/admin/users/${u.account_id}`)}
                  style={{
                    display: 'grid', gridTemplateColumns: '22px 1fr auto',
                    gap: 10, alignItems: 'center',
                    padding: '10px 0',
                    borderBottom: i < users.length - 1 ? `1px solid ${T.border}` : 'none',
                    cursor: 'pointer',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.opacity = '0.75')}
                  onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
                >
                  {/* Rank */}
                  <span style={{ fontSize: 11, color: T.dim, fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
                    {i + 1}
                  </span>

                  {/* Identity + severity bar */}
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <span style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{u.broker_user_id}</span>
                      <span style={{ fontSize: 11, color: T.dim }}>{u.email !== '—' ? u.email : ''}</span>
                    </div>
                    {/* High-severity proportion bar */}
                    <div style={{ height: 3, background: T.raised, borderRadius: 2, overflow: 'hidden', width: '100%' }}>
                      <div style={{ height: '100%', width: `${highPct * 100}%`, background: highPct > 0.5 ? T.red : T.orange, borderRadius: 2 }} />
                    </div>
                  </div>

                  {/* Right side: count + last alert */}
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'flex-end' }}>
                      <span style={{ fontSize: 16, fontWeight: 700, color: T.text, fontVariantNumeric: 'tabular-nums' }}>
                        {u.alert_count}
                      </span>
                      {u.high_severity > 0 && (
                        <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 10, background: T.redBg, color: T.red, fontWeight: 600 }}>
                          {u.high_severity} crit/high
                        </span>
                      )}
                      <ArrowRight size={11} style={{ color: T.dim }} />
                    </div>
                    <div style={{ fontSize: 11, color: T.dim, marginTop: 2 }}>last {lastAt}</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
    </Card>
  );
}

// ─── Section: Re-occurrence ───────────────────────────────────────────────────
function RecurrenceTable({ rows }: { rows: InsightsData['recurrence'] }) {
  return (
    <Card>
      <SectionHeader
        title="Pattern Re-occurrence"
        sub="Same pattern fires again after user acknowledges it"
      />
      {rows.length === 0
        ? <p style={{ fontSize: 12, color: T.dim }}>No patterns with both ack + re-occurrence yet</p>
        : (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: '185px 1fr 65px 80px', gap: 12, padding: '0 0 8px', borderBottom: `1px solid ${T.border}`, marginBottom: 2 }}>
              {['Pattern', '', 'Acked', 'Re-occurred'].map((h, i) => (
                <span key={i} style={{ fontSize: 10, fontWeight: 600, color: T.dim, textTransform: 'uppercase', letterSpacing: '0.07em', textAlign: i >= 2 ? 'right' : 'left' }}>{h}</span>
              ))}
            </div>
            {rows.map(row => {
              const rateColor = row.rate >= 0.6 ? T.red : row.rate >= 0.35 ? T.orange : T.amber;
              return (
                <div key={row.pattern} style={{
                  display: 'grid', gridTemplateColumns: '185px 1fr 65px 80px', gap: 12,
                  alignItems: 'center', padding: '10px 0', borderBottom: `1px solid ${T.border}`,
                }}>
                  <PatternLabel pattern={row.pattern} />
                  <RateBar rate={row.rate} color={rateColor} />
                  <span style={{ fontSize: 12, color: T.muted, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {row.base_acked}
                  </span>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: rateColor, fontVariantNumeric: 'tabular-nums' }}>
                      {(row.rate * 100).toFixed(0)}%
                    </div>
                    <div style={{ fontSize: 10, color: T.dim }}>
                      {row.recurrence_count} users
                    </div>
                  </div>
                </div>
              );
            })}

            {/* Interpretation note */}
            <div style={{ marginTop: 14, display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px', borderRadius: 8, background: T.raised, border: `1px solid ${T.border2}` }}>
              <RotateCcw size={12} style={{ color: T.muted, flexShrink: 0, marginTop: 1 }} />
              <p style={{ fontSize: 11, color: T.dim, margin: 0, lineHeight: 1.5 }}>
                High re-occurrence means the coaching prompt for that pattern isn't changing behavior. Consider updating the alert message or adding a follow-up nudge.
              </p>
            </div>
          </div>
        )}
    </Card>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────
export default function AdminInsights() {
  const [data, setData]       = useState<InsightsData | null>(null);
  const [days, setDays]       = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const loadingRef = useRef(false);

  const load = async () => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setLoading(true); setError('');
    try { setData(await adminApi.insights(days)); }
    catch (e: any) { setError(e.message); }
    finally { setLoading(false); loadingRef.current = false; }
  };

  useEffect(() => { load(); }, [days]);

  return (
    <div style={{ padding: '28px 32px', fontFamily: T.dm, maxWidth: 1100 }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: T.text, margin: 0, letterSpacing: '-0.02em' }}>Behavioral Insights</h1>
          <p style={{ fontSize: 12, color: T.dim, marginTop: 4 }}>Pattern intelligence across all users</p>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <select
            value={days}
            onChange={e => setDays(Number(e.target.value))}
            style={{ padding: '6px 10px', borderRadius: 7, background: T.surface, border: `1px solid ${T.border}`, color: T.text, fontFamily: T.dm, fontSize: 12, outline: 'none' }}
          >
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <button
            onClick={load} disabled={loading}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px', borderRadius: 7, background: T.surface, border: `1px solid ${T.border}`, color: T.muted, fontSize: 12, cursor: loading ? 'not-allowed' : 'pointer', fontFamily: T.dm }}
          >
            <RefreshCw size={12} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
            Refresh
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderRadius: 8, background: T.redBg, border: '1px solid rgba(239,68,68,0.18)', marginBottom: 20 }}>
          <AlertTriangle size={13} style={{ color: T.red }} />
          <span style={{ fontSize: 12, color: T.red }}>{error}</span>
        </div>
      )}

      {/* Loading */}
      {loading && !data && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '56px 0' }}>
          <Spinner />
        </div>
      )}

      {data && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

          {/* Row 1: Top Patterns + Severity */}
          <TopPatterns patterns={data.patterns} />
          <SeverityBreakdown severity={data.severity} />

          {/* Row 2: Daily volume full-width */}
          <div style={{ gridColumn: '1 / -1' }}>
            <AlertVolume daily={data.daily} />
          </div>

          {/* Row 3: Engagement rate full-width table */}
          <EngagementTable rows={data.engagement} />

          {/* Row 4: Top impacted users + Re-occurrence */}
          <TopUsers users={data.top_users} />
          <RecurrenceTable rows={data.recurrence} />
        </div>
      )}
    </div>
  );
}
