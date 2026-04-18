import { useState, useEffect } from 'react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { formatCurrencyWithSign, formatCurrency } from '@/lib/formatters';

interface AttributionData {
  has_data: boolean;
  clean_pnl: number;
  clean_count: number;
  clean_wr: number;
  clean_avg_pnl: number;
  flagged_pnl: number;
  flagged_count: number;
  flagged_wr: number;
  flagged_avg_pnl: number;
  total_pnl: number;
}

export default function AttributionCard({ days }: { days: number }) {
  const [data, setData]       = useState<AttributionData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get('/api/analytics/pnl-attribution', { params: { days_back: days } })
      .then(r => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [days]);

  if (loading) return <Skeleton className="h-28 rounded-xl" />;
  if (!data?.has_data) return null;

  const { clean_pnl, clean_count, clean_wr, flagged_pnl, flagged_count, flagged_wr, total_pnl } = data;
  const totalCount = clean_count + flagged_count;
  const cleanPct   = totalCount ? Math.round((clean_count / totalCount) * 100) : 0;
  const flaggedPct = 100 - cleanPct;

  // Insight sentence
  const cleanPositive  = clean_pnl >= 0;
  const flaggedPositive = flagged_pnl >= 0;
  let insight = '';
  if (cleanPositive && !flaggedPositive) {
    const givebackPct = Math.abs(Math.round((flagged_pnl / clean_pnl) * 100));
    insight = `You're giving back ${givebackPct}% of your disciplined earnings to emotional trades.`;
  } else if (!cleanPositive && !flaggedPositive) {
    insight = 'Both disciplined and emotional trades are in the red. Focus on trade quality first.';
  } else if (cleanPositive && flaggedPositive) {
    insight = 'Both clean and flagged trades are profitable — emotional cost is lower than usual.';
  } else {
    insight = 'Your undisciplined trades are outperforming — review what drove those wins.';
  }

  return (
    <div className="tm-card overflow-hidden">
      <div className="px-5 py-4 border-b border-border">
        <p className="text-sm font-medium text-foreground">P&L Attribution</p>
        <p className="text-[11px] text-muted-foreground mt-0.5">
          Clean trades (no alert) vs flagged trades (alert ≤30 min before entry)
        </p>
      </div>
      <div className="p-5 space-y-4">
        {/* Split bar */}
        <div className="flex h-3 rounded-full overflow-hidden gap-0.5">
          <div
            className="bg-[#16A34A]/80 rounded-l-full transition-all"
            style={{ width: `${cleanPct}%` }}
          />
          <div
            className="bg-[#DC2626]/80 rounded-r-full transition-all"
            style={{ width: `${flaggedPct}%` }}
          />
        </div>

        {/* Two columns */}
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-0.5">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#16A34A]" />
              <p className="text-[11px] text-muted-foreground uppercase tracking-wide">Clean</p>
            </div>
            <p className={cn('text-xl font-mono font-semibold tabular-nums',
              clean_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
              {formatCurrencyWithSign(clean_pnl)}
            </p>
            <p className="text-[11px] text-muted-foreground">
              {clean_count} trades · {clean_wr}% WR
            </p>
          </div>
          <div className="space-y-0.5">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#DC2626]" />
              <p className="text-[11px] text-muted-foreground uppercase tracking-wide">Flagged</p>
            </div>
            <p className={cn('text-xl font-mono font-semibold tabular-nums',
              flagged_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
              {formatCurrencyWithSign(flagged_pnl)}
            </p>
            <p className="text-[11px] text-muted-foreground">
              {flagged_count} trades · {flagged_wr}% WR
            </p>
          </div>
        </div>

        {/* Insight */}
        <p className="text-[12px] text-muted-foreground border-t border-border pt-3 leading-relaxed">
          {insight}
        </p>
      </div>
    </div>
  );
}
