import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Scale, Clock } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Cell,
  ScatterChart, Scatter, ZAxis,
} from 'recharts';

// ─── Types ────────────────────────────────────────────────────────────────────

interface HoldBucket {
  bucket: string;
  avg_pct: number;
  count: number;
  avg_win_pct: number;
  avg_loss_pct: number;
}

interface TradePoint {
  tradingsymbol: string;
  instrument_type: string | null;
  direction: string | null;
  pnl_pct: number;
  realized_pnl: number;
  duration_minutes: number;
  exit_time: string | null;
}

interface PnlPercentData {
  has_data: boolean;
  avg_win_pct: number;
  avg_loss_pct: number;
  rr_ratio: number | null;
  win_count: number;
  loss_count: number;
  by_hold_time: HoldBucket[];
  trades: TradePoint[];
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const fmt = (n: number, sign = false) =>
  `${sign && n > 0 ? '+' : ''}${n.toFixed(1)}%`;

function StatCard({
  label, value, sub, color,
}: { label: string; value: string; sub?: string; color: string }) {
  return (
    <div className="tm-card p-4 flex flex-col gap-1">
      <p className="text-[11px] text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className={cn('text-2xl font-mono font-semibold tabular-nums', color)}>{value}</p>
      {sub && <p className="text-[11px] text-muted-foreground">{sub}</p>}
    </div>
  );
}

// Custom tooltip for hold-time bar chart
function HoldTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload as HoldBucket;
  return (
    <div className="bg-card border border-border rounded-md px-3 py-2 text-xs shadow-md">
      <p className="font-medium text-foreground mb-1">{label}</p>
      <p className="text-muted-foreground">{d.count} trade{d.count !== 1 ? 's' : ''}</p>
      {d.avg_win_pct !== 0  && <p className="text-tm-profit">Avg win: {fmt(d.avg_win_pct, true)}</p>}
      {d.avg_loss_pct !== 0 && <p className="text-tm-loss">Avg loss: {fmt(d.avg_loss_pct)}</p>}
      <p className={cn('font-semibold mt-1', d.avg_pct >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
        Net avg: {fmt(d.avg_pct, true)}
      </p>
    </div>
  );
}

// Custom tooltip for scatter
function ScatterTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload as TradePoint;
  const hrs = d.duration_minutes >= 60
    ? `${(d.duration_minutes / 60).toFixed(1)}h`
    : `${d.duration_minutes}m`;
  return (
    <div className="bg-card border border-border rounded-md px-3 py-2 text-xs shadow-md">
      <p className="font-medium text-foreground">{d.tradingsymbol}</p>
      <p className={cn('font-mono tabular-nums', d.pnl_pct >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
        {fmt(d.pnl_pct, true)}
      </p>
      <p className="text-muted-foreground">₹{d.realized_pnl.toLocaleString('en-IN')}</p>
      <p className="text-muted-foreground">Hold: {hrs}</p>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function PnlPercentTab({ days }: { days: number }) {
  const { accountId } = useBroker();
  const [data, setData]       = useState<PnlPercentData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    if (!accountId) return;
    setLoading(true);
    setError(null);
    api.get('/api/analytics/pnl-percent', { params: { days_back: days } })
      .then(r => setData(r.data))
      .catch(e => setError(e.message || 'Failed to load'))
      .finally(() => setLoading(false));
  }, [accountId, days]);

  if (loading) return <PnlPercentSkeleton />;
  if (error)   return <p className="text-sm text-tm-loss p-4">{error}</p>;
  if (!data?.has_data) return (
    <div className="text-center py-16 text-muted-foreground text-sm">
      No closed trades with price data in the last {days} days.
    </div>
  );

  const { avg_win_pct, avg_loss_pct, rr_ratio, win_count, loss_count, by_hold_time, trades } = data;

  // Scatter: x = duration_minutes, y = pnl_pct
  const scatterData = trades.map(t => ({ ...t, x: t.duration_minutes, y: t.pnl_pct }));

  return (
    <div className="space-y-6">

      {/* ── Stat cards ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard
          label="Avg win %"
          value={fmt(avg_win_pct, true)}
          sub={`${win_count} winning trade${win_count !== 1 ? 's' : ''}`}
          color="text-tm-profit"
        />
        <StatCard
          label="Avg loss %"
          value={fmt(avg_loss_pct)}
          sub={`${loss_count} losing trade${loss_count !== 1 ? 's' : ''}`}
          color="text-tm-loss"
        />
        <StatCard
          label="R:R ratio"
          value={rr_ratio !== null ? rr_ratio.toFixed(2) : '—'}
          sub={rr_ratio !== null
            ? rr_ratio >= 1
              ? 'Avg win > avg loss'
              : 'Avg win < avg loss'
            : 'Not enough data'}
          color={rr_ratio !== null && rr_ratio >= 1 ? 'text-tm-profit' : 'text-tm-obs'}
        />
        <StatCard
          label="Win rate"
          value={win_count + loss_count > 0
            ? `${((win_count / (win_count + loss_count)) * 100).toFixed(0)}%`
            : '—'}
          sub={`${win_count + loss_count} total trades`}
          color="text-foreground"
        />
      </div>

      {/* ── Hold time vs % P&L ── */}
      <div className="tm-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center gap-2">
          <Clock className="h-4 w-4 text-muted-foreground" />
          <p className="text-sm font-medium text-foreground">Hold Time vs % Return</p>
        </div>
        <div className="p-5">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={by_hold_time} barSize={40}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis
                dataKey="bucket"
                tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                axisLine={false} tickLine={false}
              />
              <YAxis
                tickFormatter={v => `${v}%`}
                tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                axisLine={false} tickLine={false}
              />
              <Tooltip content={<HoldTooltip />} />
              <ReferenceLine y={0} stroke="var(--border)" />
              <Bar dataKey="avg_pct" radius={[4, 4, 0, 0]}>
                {by_hold_time.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={entry.avg_pct >= 0 ? '#16A34A' : '#DC2626'}
                    fillOpacity={0.85}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="text-[11px] text-muted-foreground text-center mt-1">
            Average % return per trade, grouped by how long you held
          </p>
        </div>
      </div>

      {/* ── Trade scatter: hold time × % P&L ── */}
      <div className="tm-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <p className="text-sm font-medium text-foreground">Every Trade — Hold Time × % Return</p>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Each dot is one closed trade. Green = profit, red = loss.
          </p>
        </div>
        <div className="p-5">
          <ResponsiveContainer width="100%" height={260}>
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                type="number" dataKey="x"
                name="Hold (min)"
                tickFormatter={v => v >= 60 ? `${(v / 60).toFixed(0)}h` : `${v}m`}
                tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                axisLine={false} tickLine={false}
                label={{ value: 'Hold time', position: 'insideBottom', offset: -4,
                         style: { fontSize: 11, fill: 'var(--muted-foreground)' } }}
              />
              <YAxis
                type="number" dataKey="y"
                name="% return"
                tickFormatter={v => `${v}%`}
                tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                axisLine={false} tickLine={false}
              />
              <ZAxis range={[40, 40]} />
              <Tooltip content={<ScatterTooltip />} />
              <ReferenceLine y={0} stroke="var(--border)" strokeDasharray="4 2" />
              <Scatter
                data={scatterData}
                fill="#888"
                shape={(props: any) => {
                  const { cx, cy, payload } = props;
                  return (
                    <circle
                      cx={cx} cy={cy} r={5}
                      fill={payload.pnl_pct >= 0 ? '#16A34A' : '#DC2626'}
                      fillOpacity={0.75}
                      stroke="none"
                    />
                  );
                }}
              />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Trade list ── */}
      <div className="tm-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <p className="text-sm font-medium text-foreground">All Trades ({trades.length})</p>
        </div>
        <div className="divide-y divide-border">
          {[...trades].sort((a, b) => a.pnl_pct - b.pnl_pct).map((t, i) => {
            const isWin = t.pnl_pct >= 0;
            const hrs = t.duration_minutes >= 60
              ? `${(t.duration_minutes / 60).toFixed(1)}h`
              : `${t.duration_minutes}m`;
            return (
              <div key={i} className="flex items-center justify-between px-5 py-2.5">
                <div>
                  <p className="text-[13px] font-medium text-foreground">{t.tradingsymbol}</p>
                  <p className="text-[11px] text-muted-foreground">{hrs} hold</p>
                </div>
                <div className="text-right">
                  <p className={cn(
                    'text-[13px] font-mono tabular-nums font-semibold',
                    isWin ? 'text-tm-profit' : 'text-tm-loss',
                  )}>
                    {fmt(t.pnl_pct, true)}
                  </p>
                  <p className={cn(
                    'text-[11px] font-mono tabular-nums',
                    isWin ? 'text-tm-profit' : 'text-tm-loss',
                  )}>
                    ₹{Math.abs(t.realized_pnl).toLocaleString('en-IN')}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

    </div>
  );
}

function PnlPercentSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[1,2,3,4].map(i => <Skeleton key={i} className="h-20 rounded-xl" />)}
      </div>
      <Skeleton className="h-56 rounded-xl" />
      <Skeleton className="h-72 rounded-xl" />
    </div>
  );
}
