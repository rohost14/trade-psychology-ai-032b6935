import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, RotateCcw } from 'lucide-react';
import { adminApi } from '@/lib/adminApi';
import {
  AdminPage, AdminCard, SectionHeader, AreaSparkline,
  ErrorBanner, LoadingBlock, EmptyState, RefreshButton, fmtNum, type Accent,
} from './_ui';
import { cn } from '@/lib/utils';

// severity → accent token (no hex)
const SEV_ACCENT: Record<string, Accent> = { critical: 'loss', high: 'warning', medium: 'brand', low: 'profit' };
const SEV_ORDER = ['critical', 'high', 'medium', 'low'];
const ACCENT_RGB: Record<Accent, string> = {
  profit: 'rgb(var(--tm-profit))', loss: 'rgb(var(--tm-loss))',
  warning: 'rgb(var(--tm-obs))', brand: 'rgb(var(--tm-brand))', muted: 'rgb(var(--muted-foreground))',
};
const sevRgb = (sev: string) => ACCENT_RGB[SEV_ACCENT[sev] ?? 'muted'] ?? ACCENT_RGB.muted;

interface InsightsData {
  period_days: number;
  patterns:   { pattern: string; count: number }[];
  severity:   { severity: string; count: number }[];
  daily:      { date: string; count: number }[];
  engagement: { pattern: string; total: number; acknowledged: number; rate: number; avg_ack_minutes: number | null }[];
  top_users:  { account_id: string; broker_user_id: string; email: string; alert_count: number; high_severity: number; last_alert_at: string | null }[];
  recurrence: { pattern: string; base_acked: number; recurrence_count: number; rate: number }[];
}

const PatternLabel = ({ pattern }: { pattern: string }) => (
  <span className="font-mono text-[11px] text-muted-foreground">{pattern}</span>
);

function RateBar({ rate, rgb }: { rate: number; rgb: string }) {
  return (
    <div className="flex-1 h-[5px] rounded bg-muted overflow-hidden">
      <div className="h-full rounded transition-[width] duration-500" style={{ width: `${rate * 100}%`, background: rgb }} />
    </div>
  );
}

function TopPatterns({ patterns }: { patterns: InsightsData['patterns'] }) {
  const max = Math.max(...patterns.map(p => p.count), 1);
  return (
    <AdminCard title="Top Patterns" subtitle={`${patterns.length} types`}>
      {patterns.length === 0 ? <EmptyState>No data for this period</EmptyState> : (
        <div className="flex flex-col gap-2.5">
          {patterns.slice(0, 10).map(({ pattern, count }) => (
            <div key={pattern} className="grid items-center gap-2.5 [grid-template-columns:185px_1fr_36px]">
              <PatternLabel pattern={pattern} />
              <div className="h-1.5 rounded bg-muted overflow-hidden">
                <div className="h-full rounded transition-[width] duration-500" style={{ width: `${(count / max) * 100}%`, background: 'rgb(var(--tm-brand))' }} />
              </div>
              <span className="text-xs font-semibold text-foreground tabular-nums text-right">{count}</span>
            </div>
          ))}
        </div>
      )}
    </AdminCard>
  );
}

function SeverityBreakdown({ severity }: { severity: InsightsData['severity'] }) {
  const total = severity.reduce((s, r) => s + r.count, 0);
  const sorted = [...severity].sort((a, b) => SEV_ORDER.indexOf(a.severity) - SEV_ORDER.indexOf(b.severity));
  return (
    <AdminCard title="Severity Breakdown" subtitle={total ? `${fmtNum(total)} total` : undefined}>
      {sorted.length === 0 ? <EmptyState>No data</EmptyState> : (
        <>
          <div className="flex h-[7px] rounded overflow-hidden gap-px mb-4">
            {sorted.map(({ severity: sev, count }) => (
              <div key={sev} className="min-w-[2px]" style={{ flex: count, background: sevRgb(sev) }} title={`${sev}: ${count}`} />
            ))}
          </div>
          <div className="flex flex-col gap-3">
            {sorted.map(({ severity: sev, count }) => {
              const rgb = sevRgb(sev);
              const pct = total > 0 ? Math.round((count / total) * 100) : 0;
              return (
                <div key={sev}>
                  <div className="flex justify-between mb-1.5">
                    <span className="text-xs font-semibold capitalize" style={{ color: rgb }}>{sev}</span>
                    <span className="text-xs text-muted-foreground tabular-nums">{fmtNum(count)} · {pct}%</span>
                  </div>
                  <div className="h-[5px] rounded bg-muted overflow-hidden">
                    <div className="h-full rounded transition-[width] duration-500" style={{ width: `${pct}%`, background: rgb }} />
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </AdminCard>
  );
}

function EngagementTable({ rows }: { rows: InsightsData['engagement'] }) {
  const cols = '[grid-template-columns:185px_1fr_70px_80px_90px_110px]';
  return (
    <AdminCard className="lg:col-span-2" title="Alert Engagement Rate" subtitle="How often traders acknowledge each pattern type">
      {rows.length === 0 ? <EmptyState>No alert data for this period</EmptyState> : (
        <div>
          <div className={cn('grid gap-3.5 pb-2 border-b border-border', cols)}>
            {['Pattern', '', 'Fired', 'Acked', 'Rate', 'Avg Response'].map((h, i) => (
              <span key={i} className={cn('table-header', i >= 2 && 'text-right')}>{h}</span>
            ))}
          </div>
          {rows.map(row => {
            const rgb = row.rate >= 0.6 ? ACCENT_RGB.profit : row.rate >= 0.3 ? ACCENT_RGB.warning : ACCENT_RGB.loss;
            return (
              <div key={row.pattern} className={cn('grid gap-3.5 items-center py-2.5 border-b border-border', cols)}>
                <PatternLabel pattern={row.pattern} />
                <RateBar rate={row.rate} rgb={rgb} />
                <span className="text-xs text-muted-foreground text-right tabular-nums">{fmtNum(row.total)}</span>
                <span className="text-xs text-foreground text-right tabular-nums">{fmtNum(row.acknowledged)}</span>
                <span className="text-[13px] font-bold text-right tabular-nums" style={{ color: rgb }}>{(row.rate * 100).toFixed(1)}%</span>
                <span className="text-xs text-muted-foreground text-right tabular-nums">{row.avg_ack_minutes != null ? `${row.avg_ack_minutes}m` : '—'}</span>
              </div>
            );
          })}
        </div>
      )}
    </AdminCard>
  );
}

function TopUsers({ users }: { users: InsightsData['top_users'] }) {
  const navigate = useNavigate();
  return (
    <AdminCard title="Top Impacted Users" subtitle="By alert count">
      {users.length === 0 ? <EmptyState>No users yet</EmptyState> : (
        <div className="flex flex-col">
          {users.map((u, i) => {
            const lastAt = u.last_alert_at ? new Date(u.last_alert_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : '—';
            const highPct = u.alert_count > 0 ? u.high_severity / u.alert_count : 0;
            return (
              <div key={u.account_id} onClick={() => navigate(`/admin/users/${u.account_id}`)}
                className={cn('grid gap-2.5 items-center py-2.5 cursor-pointer hover:opacity-75 transition-opacity [grid-template-columns:22px_1fr_auto]',
                  i < users.length - 1 && 'border-b border-border')}>
                <span className="text-[11px] text-muted-foreground/70 tabular-nums font-semibold">{i + 1}</span>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-semibold text-foreground">{u.broker_user_id}</span>
                    <span className="text-[11px] text-muted-foreground/70">{u.email !== '—' ? u.email : ''}</span>
                  </div>
                  <div className="h-[3px] rounded-sm bg-muted overflow-hidden w-full">
                    <div className="h-full rounded-sm" style={{ width: `${highPct * 100}%`, background: highPct > 0.5 ? ACCENT_RGB.loss : ACCENT_RGB.warning }} />
                  </div>
                </div>
                <div className="text-right">
                  <div className="flex items-center gap-1.5 justify-end">
                    <span className="text-base font-bold text-foreground tabular-nums">{u.alert_count}</span>
                    {u.high_severity > 0 && (
                      <span className="text-[10px] px-1.5 py-px rounded-full font-semibold"
                        style={{ background: 'color-mix(in srgb, rgb(var(--tm-loss)) 10%, transparent)', color: 'rgb(var(--tm-loss))' }}>
                        {u.high_severity} crit/high
                      </span>
                    )}
                    <ArrowRight size={11} className="text-muted-foreground/70" />
                  </div>
                  <div className="text-[11px] text-muted-foreground/70 mt-0.5">last {lastAt}</div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </AdminCard>
  );
}

function RecurrenceTable({ rows }: { rows: InsightsData['recurrence'] }) {
  const cols = '[grid-template-columns:185px_1fr_65px_80px]';
  return (
    <AdminCard title="Pattern Re-occurrence" subtitle="Same pattern fires again after user acknowledges it">
      {rows.length === 0 ? <EmptyState>No patterns with both ack + re-occurrence yet</EmptyState> : (
        <div>
          <div className={cn('grid gap-3 pb-2 border-b border-border', cols)}>
            {['Pattern', '', 'Acked', 'Re-occurred'].map((h, i) => (
              <span key={i} className={cn('table-header', i >= 2 && 'text-right')}>{h}</span>
            ))}
          </div>
          {rows.map(row => {
            const rgb = row.rate >= 0.6 ? ACCENT_RGB.loss : row.rate >= 0.35 ? ACCENT_RGB.warning : ACCENT_RGB.warning;
            return (
              <div key={row.pattern} className={cn('grid gap-3 items-center py-2.5 border-b border-border', cols)}>
                <PatternLabel pattern={row.pattern} />
                <RateBar rate={row.rate} rgb={rgb} />
                <span className="text-xs text-muted-foreground text-right tabular-nums">{row.base_acked}</span>
                <div className="text-right">
                  <div className="text-[13px] font-bold tabular-nums" style={{ color: rgb }}>{(row.rate * 100).toFixed(0)}%</div>
                  <div className="text-[10px] text-muted-foreground/70">{row.recurrence_count} users</div>
                </div>
              </div>
            );
          })}
          <div className="mt-3.5 flex items-start gap-2 px-3 py-2.5 rounded-lg bg-muted border border-border">
            <RotateCcw size={12} className="text-muted-foreground shrink-0 mt-0.5" />
            <p className="text-[11px] text-muted-foreground m-0 leading-relaxed">
              High re-occurrence means the coaching prompt for that pattern isn't changing behavior. Consider updating the alert message or adding a follow-up nudge.
            </p>
          </div>
        </div>
      )}
    </AdminCard>
  );
}

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
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); loadingRef.current = false; }
  };

  useEffect(() => { load(); }, [days]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <AdminPage
      title="Behavioral Insights"
      subtitle="Pattern intelligence across all users"
      actions={
        <>
          <select value={days} onChange={e => setDays(Number(e.target.value))}
            className="h-9 px-2.5 rounded-lg bg-card border border-border text-foreground text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <RefreshButton onClick={load} loading={loading} />
        </>
      }
    >
      <ErrorBanner message={error} />
      {loading && !data && <LoadingBlock />}

      {data && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <TopPatterns patterns={data.patterns} />
          <SeverityBreakdown severity={data.severity} />
          <AdminCard className="lg:col-span-2" title="Daily Alert Volume" subtitle="Last 14 days">
            <AreaSparkline data={data.daily} height={72} />
          </AdminCard>
          <EngagementTable rows={data.engagement} />
          <TopUsers users={data.top_users} />
          <RecurrenceTable rows={data.recurrence} />
        </div>
      )}
    </AdminPage>
  );
}
