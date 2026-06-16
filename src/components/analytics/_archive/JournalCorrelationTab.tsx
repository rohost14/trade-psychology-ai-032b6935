import { useState, useEffect } from 'react';
import { BookOpen } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { formatCurrencyWithSign } from '@/lib/formatters';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Cell,
} from 'recharts';

interface EmotionStat {
  emotion: string;
  trade_count: number;
  avg_pnl: number;
  total_pnl: number;
  win_rate: number;
}

interface EntryTypeStat {
  entry_type: string;
  trade_count: number;
  avg_pnl: number;
  win_rate: number;
}

interface CorrelationData {
  has_data: boolean;
  period_days: number;
  total_journaled: number;
  by_emotion: EmotionStat[];
  by_entry_type: EntryTypeStat[];
}

const EMOTION_LABELS: Record<string, string> = {
  calm: 'Calm',
  focused: 'Focused',
  confident: 'Confident',
  fomo: 'FOMO',
  revenge: 'Revenge',
  anxious: 'Anxious',
  greedy: 'Greedy',
  bored: 'Bored',
  frustrated: 'Frustrated',
  overconfident: 'Overconfident',
};

function EmotionTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const d: EmotionStat = payload[0]?.payload;
  return (
    <div className="bg-card border border-border rounded-md px-3 py-2 text-xs shadow-md space-y-1">
      <p className="font-semibold text-foreground">{EMOTION_LABELS[label] ?? label}</p>
      <p className="text-muted-foreground">{d.trade_count} trades</p>
      <p className={cn('font-mono', d.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
        Avg P&L: {formatCurrencyWithSign(d.avg_pnl)}
      </p>
      <p className={cn('font-mono', d.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss')}>
        Win rate: {d.win_rate}%
      </p>
    </div>
  );
}

function InsightRow({ stat, baseline }: { stat: EmotionStat; baseline: number }) {
  const delta = stat.avg_pnl - baseline;
  const label = EMOTION_LABELS[stat.emotion] ?? stat.emotion;
  return (
    <div className="px-5 py-3 flex items-center gap-4 border-b border-border last:border-0">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground capitalize">{label}</p>
        <p className="text-xs text-muted-foreground">{stat.trade_count} trades · {stat.win_rate}% win rate</p>
      </div>
      <div className="text-right shrink-0">
        <p className={cn('font-mono text-sm font-semibold', stat.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
          {formatCurrencyWithSign(stat.avg_pnl)}
        </p>
        {baseline !== 0 && (
          <p className={cn('text-[11px] font-mono', delta >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
            {delta >= 0 ? '+' : ''}{formatCurrencyWithSign(delta)} vs avg
          </p>
        )}
      </div>
    </div>
  );
}

export default function JournalCorrelationTab({ days }: { days: number }) {
  const [data, setData]       = useState<CorrelationData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get('/api/analytics/journal-correlation', { params: { days } })
      .then(r => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [days]);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-64 rounded-xl" />
        <Skeleton className="h-48 rounded-xl" />
      </div>
    );
  }

  if (!data?.has_data) {
    return (
      <div className="tm-card flex flex-col items-center justify-center py-16 text-center">
        <BookOpen className="h-10 w-10 text-muted-foreground/30 mb-3" />
        <p className="font-medium text-foreground">No journal entries yet</p>
        <p className="text-sm text-muted-foreground mt-1 max-w-sm">
          Tag trades with your pre-trade emotion in the journal (confident, anxious, FOMO...).
          Once you have {days > 30 ? '10+' : '5+'} tagged entries, this tab reveals which mindsets
          help or hurt your P&L.
        </p>
      </div>
    );
  }

  const allPnls = data.by_emotion.flatMap(e => Array(e.trade_count).fill(e.avg_pnl));
  const baseline = allPnls.length ? allPnls.reduce((a, b) => a + b, 0) / allPnls.length : 0;

  // Top insight: worst emotion by avg_pnl with ≥3 trades
  const qualified = data.by_emotion.filter(e => e.trade_count >= 3);
  const worst = qualified.length ? [...qualified].sort((a, b) => a.avg_pnl - b.avg_pnl)[0] : null;
  const best  = qualified.length ? [...qualified].sort((a, b) => b.avg_pnl - a.avg_pnl)[0] : null;

  return (
    <div className="space-y-5">
      {/* Insights banner */}
      {(worst || best) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {worst && (
            <div className="rounded-xl px-4 py-3 text-sm border bg-red-500/10 border-red-500/20 text-red-600 dark:text-red-400">
              <span className="font-semibold capitalize">{EMOTION_LABELS[worst.emotion] ?? worst.emotion}</span> trades avg{' '}
              <span className="font-mono">{formatCurrencyWithSign(worst.avg_pnl)}</span> — your worst emotional state.
            </div>
          )}
          {best && best.emotion !== worst?.emotion && (
            <div className="rounded-xl px-4 py-3 text-sm border bg-green-500/10 border-green-500/20 text-green-600 dark:text-green-400">
              <span className="font-semibold capitalize">{EMOTION_LABELS[best.emotion] ?? best.emotion}</span> trades avg{' '}
              <span className="font-mono">{formatCurrencyWithSign(best.avg_pnl)}</span> — your strongest state.
            </div>
          )}
        </div>
      )}

      {/* Bar chart: avg P&L by emotion */}
      {data.by_emotion.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <p className="text-sm font-semibold text-foreground">Avg P&L by Emotion</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {data.total_journaled} journaled trades over {days} days
            </p>
          </div>
          <div className="p-5">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={data.by_emotion} barSize={28}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis
                  dataKey="emotion"
                  tick={{ fontSize: 11 }}
                  tickFormatter={e => EMOTION_LABELS[e] ?? e}
                />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `₹${v}`} />
                <Tooltip content={<EmotionTooltip />} />
                <ReferenceLine y={0} stroke="hsl(var(--border))" />
                <Bar dataKey="avg_pnl" radius={[3, 3, 0, 0]}>
                  {data.by_emotion.map((e, i) => (
                    <Cell
                      key={i}
                      fill={e.avg_pnl >= 0 ? '#16A34A' : '#DC2626'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Ranked emotion list */}
      {data.by_emotion.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <p className="text-sm font-semibold text-foreground">Emotion Breakdown</p>
          </div>
          <div>
            {[...data.by_emotion]
              .sort((a, b) => b.trade_count - a.trade_count)
              .map(stat => (
                <InsightRow key={stat.emotion} stat={stat} baseline={baseline} />
              ))
            }
          </div>
        </div>
      )}

      {/* Entry type breakdown */}
      {data.by_entry_type?.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <p className="text-sm font-semibold text-foreground">By Journal Type</p>
          </div>
          <div className="divide-y divide-border">
            {data.by_entry_type.map(et => (
              <div key={et.entry_type} className="px-5 py-3 flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-foreground capitalize">{et.entry_type.replace('_', ' ')}</p>
                  <p className="text-xs text-muted-foreground">{et.trade_count} entries · {et.win_rate}% win</p>
                </div>
                <p className={cn('font-mono text-sm font-semibold', et.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                  {formatCurrencyWithSign(et.avg_pnl)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
