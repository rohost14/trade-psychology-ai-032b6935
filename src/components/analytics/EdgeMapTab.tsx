import { useState, useEffect } from 'react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { formatCurrencyWithSign } from '@/lib/formatters';
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, ZAxis, Cell,
} from 'recharts';

interface Instrument {
  underlying: string;
  trade_count: number;
  trade_pct: number;
  win_rate: number;
  avg_pnl: number;
  total_pnl: number;
}

interface EdgeMapData {
  has_data: boolean;
  instruments: Instrument[];
  overall_win_rate: number;
  total_trades: number;
  proportional_benchmark: number;
}

// Custom tooltip for the scatter
function EdgeTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload as Instrument;
  return (
    <div className="bg-card border border-border rounded-md px-3 py-2 text-xs shadow-md">
      <p className="font-semibold text-foreground mb-1">{d.underlying}</p>
      <p className="text-muted-foreground">{d.trade_count} trades ({d.trade_pct}% of all)</p>
      <p className={cn('font-mono', d.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss')}>
        Win rate: {d.win_rate}%
      </p>
      <p className={cn('font-mono', d.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
        Avg P&L: {formatCurrencyWithSign(d.avg_pnl)}
      </p>
      <p className={cn('font-mono text-[10px] mt-1', d.total_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
        Total: {formatCurrencyWithSign(d.total_pnl)}
      </p>
    </div>
  );
}

export default function EdgeMapTab({ days }: { days: number }) {
  const [data, setData]       = useState<EdgeMapData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get('/api/analytics/edge-map', { params: { days_back: days } })
      .then(r => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [days]);

  if (loading) return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        {[1,2].map(i => <Skeleton key={i} className="h-20 rounded-xl" />)}
      </div>
      <Skeleton className="h-72 rounded-xl" />
      <Skeleton className="h-48 rounded-xl" />
    </div>
  );

  if (!data?.has_data) return (
    <div className="text-center py-16 text-muted-foreground text-sm">
      Need at least 4 trades per instrument to build your edge map.
    </div>
  );

  const { instruments, overall_win_rate, proportional_benchmark } = data;

  // Scatter data: x=trade_pct, y=win_rate, z=trade_count
  const scatterData = instruments.map(i => ({ ...i, x: i.trade_pct, y: i.win_rate, z: i.trade_count }));

  // Identify misaligned instruments
  const overallocated = instruments.filter(i => i.trade_pct > proportional_benchmark && i.win_rate < overall_win_rate);
  const underallocated = instruments.filter(i => i.trade_pct < proportional_benchmark && i.win_rate > overall_win_rate);

  return (
    <div className="space-y-6">
      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <div className="tm-card p-4">
          <p className="text-[11px] text-muted-foreground uppercase tracking-wide">Instruments tracked</p>
          <p className="text-2xl font-mono font-semibold text-foreground tabular-nums mt-1">
            {instruments.length}
          </p>
        </div>
        <div className="tm-card p-4">
          <p className="text-[11px] text-muted-foreground uppercase tracking-wide">Overall win rate</p>
          <p className={cn('text-2xl font-mono font-semibold tabular-nums mt-1',
            overall_win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss')}>
            {overall_win_rate}%
          </p>
        </div>
        <div className="tm-card p-4 col-span-2 sm:col-span-1">
          <p className="text-[11px] text-muted-foreground uppercase tracking-wide">Best instrument</p>
          {instruments[0] ? (
            <>
              <p className="text-xl font-semibold text-foreground mt-1">{instruments[0].underlying}</p>
              <p className="text-[11px] text-muted-foreground">{instruments[0].win_rate}% WR</p>
            </>
          ) : <p className="text-lg text-muted-foreground">—</p>}
        </div>
      </div>

      {/* Scatter chart */}
      <div className="tm-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <p className="text-sm font-medium text-foreground">Capital Allocation vs Edge</p>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Each bubble = one instrument. Size = trade count. Top-left = underallocated edge.
          </p>
        </div>
        <div className="p-5">
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                type="number" dataKey="x" name="% of trades"
                domain={[0, 'auto']}
                tickFormatter={v => `${v}%`}
                tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                axisLine={false} tickLine={false}
                label={{ value: '% of your trades', position: 'insideBottom', offset: -8,
                         style: { fontSize: 11, fill: 'var(--muted-foreground)' } }}
              />
              <YAxis
                type="number" dataKey="y" name="Win rate"
                domain={[0, 100]}
                tickFormatter={v => `${v}%`}
                tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                axisLine={false} tickLine={false}
              />
              <ZAxis type="number" dataKey="z" range={[40, 200]} />
              <Tooltip content={<EdgeTooltip />} />
              {/* Horizontal: overall win rate */}
              <ReferenceLine y={overall_win_rate} stroke="var(--muted-foreground)"
                strokeDasharray="4 2" label={{ value: 'Avg WR', position: 'insideTopRight',
                  style: { fontSize: 10, fill: 'var(--muted-foreground)' } }} />
              {/* Vertical: proportional allocation */}
              <ReferenceLine x={proportional_benchmark} stroke="var(--muted-foreground)"
                strokeDasharray="4 2" label={{ value: 'Equal alloc', position: 'insideTopLeft',
                  style: { fontSize: 10, fill: 'var(--muted-foreground)' } }} />
              <Scatter
                data={scatterData}
                shape={(props: any) => {
                  const { cx, cy, r, payload } = props;
                  const color = payload.win_rate >= overall_win_rate ? '#16A34A' : '#DC2626';
                  return (
                    <g>
                      <circle cx={cx} cy={cy} r={r} fill={color} fillOpacity={0.7} stroke={color} strokeWidth={1} />
                      <text x={cx} y={cy - r - 3} textAnchor="middle" fontSize={10}
                        fill="var(--muted-foreground)">{payload.underlying}</text>
                    </g>
                  );
                }}
              />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Misalignment callouts */}
      {(overallocated.length > 0 || underallocated.length > 0) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {overallocated.length > 0 && (
            <div className="tm-card p-4 border-l-4 border-l-tm-loss">
              <p className="text-[11px] text-muted-foreground uppercase tracking-wide mb-2">Over-allocated, low edge</p>
              <div className="space-y-2">
                {overallocated.map(i => (
                  <div key={i.underlying} className="flex items-center justify-between">
                    <p className="text-sm font-medium text-foreground">{i.underlying}</p>
                    <div className="text-right">
                      <p className="text-[11px] font-mono text-tm-loss">{i.trade_pct}% of trades</p>
                      <p className="text-[11px] text-muted-foreground">{i.win_rate}% WR</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {underallocated.length > 0 && (
            <div className="tm-card p-4 border-l-4 border-l-tm-profit">
              <p className="text-[11px] text-muted-foreground uppercase tracking-wide mb-2">Under-allocated, strong edge</p>
              <div className="space-y-2">
                {underallocated.map(i => (
                  <div key={i.underlying} className="flex items-center justify-between">
                    <p className="text-sm font-medium text-foreground">{i.underlying}</p>
                    <div className="text-right">
                      <p className="text-[11px] font-mono text-tm-profit">{i.trade_pct}% of trades</p>
                      <p className="text-[11px] text-muted-foreground">{i.win_rate}% WR</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Ranked table */}
      <div className="tm-card overflow-hidden">
        <div className="px-5 py-3 border-b border-border">
          <p className="text-sm font-medium text-foreground">All Instruments</p>
        </div>
        <div className="divide-y divide-border">
          {instruments.map(i => (
            <div key={i.underlying} className="px-5 py-3 flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="text-[13px] font-medium text-foreground">{i.underlying}</p>
                <p className="text-[11px] text-muted-foreground">{i.trade_count} trades · {i.trade_pct}% of total</p>
              </div>
              <div className="shrink-0 flex items-center gap-4">
                <div className="text-right">
                  <p className={cn('text-[13px] font-mono font-semibold tabular-nums',
                    i.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss')}>
                    {i.win_rate}% WR
                  </p>
                  <p className={cn('text-[11px] font-mono tabular-nums',
                    i.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                    {formatCurrencyWithSign(i.avg_pnl)}/trade
                  </p>
                </div>
                <div className={cn(
                  'w-1.5 h-8 rounded-full',
                  i.win_rate >= overall_win_rate + 5 ? 'bg-[#16A34A]' :
                  i.win_rate <= overall_win_rate - 5 ? 'bg-[#DC2626]' : 'bg-muted'
                )} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
