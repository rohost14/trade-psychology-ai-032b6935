import { useState, useEffect } from 'react';
import { Zap, Flame, TrendingUp } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts';

interface DisciplineData {
  has_data: boolean;
  score: number;
  max_score: number;
  week_start: string;
  danger_alerts: number;
  caution_alerts: number;
  trades_this_week: number;
  revenge_free_days: number;
  weekly_trend: number[];
  breakdown: {
    alerts_score: number;
    quality_score: number;
  };
}


function ScoreGauge({ score, max }: { score: number; max: number }) {
  const pct = Math.min(100, (score / max) * 100);
  const color = pct >= 70 ? '#16A34A' : pct >= 45 ? '#D97706' : '#DC2626';
  const circumference = 2 * Math.PI * 45;
  const dashOffset = circumference * (1 - pct / 100);

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-32 h-32">
        <svg viewBox="0 0 100 100" className="transform -rotate-90 w-full h-full">
          <circle cx="50" cy="50" r="45" stroke="var(--border)" strokeWidth="8" fill="none" />
          <circle
            cx="50" cy="50" r="45"
            stroke={color}
            strokeWidth="8"
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            strokeLinecap="round"
            className="transition-all duration-700"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <p className="text-3xl font-bold font-mono tabular-nums text-foreground">{score}</p>
          <p className="text-[10px] text-muted-foreground">/ {max}</p>
        </div>
      </div>
      <p className={cn(
        'text-sm font-semibold mt-2',
        pct >= 70 ? 'text-tm-profit' : pct >= 45 ? 'text-tm-obs' : 'text-tm-loss'
      )}>
        {pct >= 80 ? 'Excellent' : pct >= 60 ? 'Good' : pct >= 40 ? 'Needs work' : 'Struggling'}
      </p>
    </div>
  );
}

function TrendTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card border border-border rounded-md px-2 py-1.5 text-xs">
      <p className="font-mono tabular-nums">{payload[0].value} / 100</p>
    </div>
  );
}

export default function Discipline() {
  const { account } = useBroker();
  const accountId = account?.id;
  const [data, setData]       = useState<DisciplineData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!accountId) return;
    setLoading(true);
    api.get('/api/analytics/discipline-summary')
      .then(r => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [accountId]);

  if (loading) return (
    <div className="max-w-2xl mx-auto pb-12 space-y-4">
      <Skeleton className="h-8 w-40" />
      <Skeleton className="h-48 rounded-xl" />
      <Skeleton className="h-32 rounded-xl" />
      <Skeleton className="h-48 rounded-xl" />
    </div>
  );

  if (!data?.has_data) return (
    <div className="max-w-2xl mx-auto pb-12">
      <h1 className="text-lg font-semibold text-foreground mb-6">Discipline</h1>
      <div className="text-center py-16 text-muted-foreground text-sm">
        Start trading to see your discipline score.
      </div>
    </div>
  );

  const trendData = data.weekly_trend.map((s, i) => ({
    week: `W-${data.weekly_trend.length - i}`,
    score: s,
  })).reverse();

  return (
    <div className="max-w-2xl mx-auto pb-12">
      <div className="mb-6">
        <h1 className="t-heading-lg text-foreground">Discipline</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Week of {data.week_start}</p>
      </div>

      {/* Score + breakdown */}
      <div className="tm-card overflow-hidden mb-4">
        <div className="p-6 flex flex-col sm:flex-row items-center gap-6">
          <ScoreGauge score={data.score} max={data.max_score} />
          <div className="flex-1 w-full space-y-3">
            <p className="text-sm font-medium text-foreground">This Week's Score</p>

            {/* Breakdown bars */}
            <div className="space-y-2">
              <div>
                <div className="flex justify-between text-[11px] text-muted-foreground mb-1">
                  <span>Alert control</span>
                  <span className="font-mono">{data.breakdown.alerts_score} / 60</span>
                </div>
                <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full bg-tm-brand transition-all"
                    style={{ width: `${(data.breakdown.alerts_score / 60) * 100}%` }}
                  />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-[11px] text-muted-foreground mb-1">
                  <span>Trade quality</span>
                  <span className="font-mono">{data.breakdown.quality_score} / 40</span>
                </div>
                <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full bg-tm-brand transition-all"
                    style={{ width: `${(data.breakdown.quality_score / 40) * 100}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Quick stats */}
            <div className="flex gap-4 pt-1">
              <div>
                <p className="text-[10px] text-muted-foreground uppercase">Trades</p>
                <p className="text-sm font-mono font-semibold text-foreground">{data.trades_this_week}</p>
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground uppercase">Danger alerts</p>
                <p className={cn('text-sm font-mono font-semibold', data.danger_alerts > 0 ? 'text-tm-loss' : 'text-tm-profit')}>
                  {data.danger_alerts}
                </p>
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground uppercase">Caution alerts</p>
                <p className={cn('text-sm font-mono font-semibold', data.caution_alerts > 2 ? 'text-tm-obs' : 'text-foreground')}>
                  {data.caution_alerts}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 4-week trend */}
      {trendData.length > 1 && (
        <div className="tm-card overflow-hidden mb-4">
          <div className="px-5 py-4 border-b border-border flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
            <p className="text-sm font-medium text-foreground">4-Week Trend</p>
          </div>
          <div className="p-5">
            <ResponsiveContainer width="100%" height={120}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="week" tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                  axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                  axisLine={false} tickLine={false} tickFormatter={v => `${v}`} />
                <Tooltip content={<TrendTooltip />} />
                <Line
                  type="monotone" dataKey="score"
                  stroke="#0D9488" strokeWidth={2}
                  dot={{ fill: '#0D9488', r: 3 }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Streaks */}
      <div className="tm-card overflow-hidden mb-4">
        <div className="px-5 py-4 border-b border-border flex items-center gap-2">
          <Flame className="h-4 w-4 text-tm-obs" />
          <p className="text-sm font-medium text-foreground">Streaks</p>
        </div>
        <div className="divide-y divide-border">
          {/* Revenge-free streak — always shown, computed from data */}
          <div className="px-5 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xl">🧘</span>
              <div>
                <p className="text-[13px] font-medium text-foreground">Revenge-Free</p>
                <p className="text-[11px] text-muted-foreground">No revenge trades</p>
              </div>
            </div>
            <div className="text-right">
              <p className={cn(
                'text-lg font-bold font-mono tabular-nums',
                data.revenge_free_days >= 5 ? 'text-tm-profit' : data.revenge_free_days >= 2 ? 'text-tm-obs' : 'text-tm-loss'
              )}>
                {data.revenge_free_days}d
              </p>
              {data.revenge_free_days >= 5 && (
                <p className="text-[10px] text-tm-profit">On track ✓</p>
              )}
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
