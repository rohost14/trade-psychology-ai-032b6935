import { useEffect, useState } from 'react';
import { RefreshCw, AlertTriangle } from 'lucide-react';
import { adminApi } from '@/lib/adminApi';

const C = {
  text:   '#e2e8f0',
  muted:  'rgba(226,232,240,0.45)',
  dim:    'rgba(226,232,240,0.25)',
  border: 'rgba(255,255,255,0.07)',
  amber:  '#f59e0b',
  green:  '#10b981',
  red:    '#ef4444',
  orange: '#f97316',
  dm:     "'DM Sans', sans-serif",
};

// Matches backend /api/admin/insights response shape
interface InsightsData {
  period_days: number;
  patterns:  { pattern: string; count: number }[];
  severity:  { severity: string; count: number }[];
  daily:     { date: string; count: number }[];
}

const SEV_COLORS: Record<string, string> = { critical: C.red, high: C.orange, medium: C.amber, low: C.green };

function BarChart({ data }: { data: { label: string; value: number }[] }) {
  const max = Math.max(...data.map(d => d.value), 1);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {data.map(({ label, value }) => (
        <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 150, fontSize: '0.73rem', color: C.muted, textAlign: 'right', flexShrink: 0, textTransform: 'capitalize' }}>
            {label.replace(/_/g, ' ')}
          </div>
          <div style={{ flex: 1, height: 18, background: 'rgba(255,255,255,0.04)', borderRadius: 4, overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${(value / max) * 100}%`, background: 'linear-gradient(90deg, rgba(245,158,11,0.7), rgba(245,158,11,0.3))', borderRadius: 4, transition: 'width 0.6s ease' }} />
          </div>
          <div style={{ width: 32, fontSize: '0.73rem', color: C.text, flexShrink: 0 }}>{value}</div>
        </div>
      ))}
    </div>
  );
}

function Sparkline({ data }: { data: { date: string; count: number }[] }) {
  if (data.length < 2) return <p style={{ fontSize: '0.78rem', color: C.dim }}>Not enough data</p>;
  const max = Math.max(...data.map(d => d.count), 1);
  const W = 500, H = 70, P = 4;
  const pts = data.map((d, i) => {
    const x = P + (i / (data.length - 1)) * (W - P * 2);
    const y = H - P - ((d.count / max) * (H - P * 2));
    return `${x},${y}`;
  });
  const area = `${P},${H} ${pts.join(' ')} ${W - P},${H}`;
  return (
    <>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 70 }} preserveAspectRatio="none">
        <polygon points={area} fill="rgba(245,158,11,0.08)" />
        <polyline points={pts.join(' ')} fill="none" stroke={C.amber} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
        <span style={{ fontSize: '0.67rem', color: C.dim }}>{data[0].date}</span>
        <span style={{ fontSize: '0.67rem', color: C.dim }}>{data[data.length - 1].date}</span>
      </div>
    </>
  );
}

export default function AdminInsights() {
  const [data, setData]       = useState<InsightsData | null>(null);
  const [days, setDays]       = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');

  const load = async () => {
    setLoading(true); setError('');
    try { setData(await adminApi.insights(days)); }
    catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [days]);

  const patternData = data?.patterns.map(p => ({ label: p.pattern, value: p.count })) ?? [];
  const totalSev = data ? data.severity.reduce((s, r) => s + r.count, 0) : 0;

  return (
    <div style={{ padding: '2rem', fontFamily: C.dm }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.3rem', fontWeight: 700, color: C.text, margin: 0 }}>Behavioral Insights</h1>
        <div style={{ display: 'flex', gap: 10 }}>
          <select value={days} onChange={e => setDays(Number(e.target.value))} style={{ padding: '0.5rem 0.75rem', borderRadius: 9, background: 'rgba(255,255,255,0.04)', border: `1px solid ${C.border}`, color: C.text, fontFamily: C.dm, fontSize: '0.8rem', outline: 'none' }}>
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <button onClick={load} disabled={loading} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0.5rem 0.75rem', borderRadius: 9, background: 'rgba(255,255,255,0.04)', border: `1px solid ${C.border}`, color: C.muted, fontSize: '0.78rem', cursor: loading ? 'not-allowed' : 'pointer', fontFamily: C.dm }}>
            <RefreshCw style={{ width: 13, height: 13, animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          </button>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0.75rem 1rem', borderRadius: 10, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', marginBottom: '1.5rem' }}>
          <AlertTriangle style={{ width: 14, height: 14, color: C.red }} />
          <span style={{ fontSize: '0.8rem', color: C.red }}>{error}</span>
        </div>
      )}

      {loading && !data && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
          <div style={{ width: 28, height: 28, border: `2px solid ${C.amber}`, borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
        </div>
      )}

      {data && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
          <div style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 14, padding: '1.25rem 1.5rem' }}>
            <h2 style={{ fontSize: '0.85rem', fontWeight: 600, color: C.text, marginBottom: '1.25rem' }}>Top Patterns</h2>
            {patternData.length === 0
              ? <p style={{ fontSize: '0.8rem', color: C.dim }}>No data for this period</p>
              : <BarChart data={patternData.slice(0, 10)} />}
          </div>

          <div style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 14, padding: '1.25rem 1.5rem' }}>
            <h2 style={{ fontSize: '0.85rem', fontWeight: 600, color: C.text, marginBottom: '1.25rem' }}>Severity Breakdown</h2>
            {data.severity.length === 0
              ? <p style={{ fontSize: '0.8rem', color: C.dim }}>No data</p>
              : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  {data.severity.map(({ severity, count }) => {
                    const color = SEV_COLORS[severity] || C.muted;
                    const pct   = totalSev > 0 ? Math.round((count / totalSev) * 100) : 0;
                    return (
                      <div key={severity}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <span style={{ fontSize: '0.78rem', color, textTransform: 'capitalize', fontWeight: 500 }}>{severity}</span>
                          <span style={{ fontSize: '0.75rem', color: C.muted }}>{count} ({pct}%)</span>
                        </div>
                        <div style={{ height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 3, transition: 'width 0.6s ease' }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
          </div>

          <div style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 14, padding: '1.25rem 1.5rem', gridColumn: '1 / -1' }}>
            <h2 style={{ fontSize: '0.85rem', fontWeight: 600, color: C.text, marginBottom: '0.75rem' }}>Daily Alert Volume (last 14 days)</h2>
            <Sparkline data={data.daily} />
          </div>
        </div>
      )}
    </div>
  );
}
