import { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';

interface VixData {
  vix: number | null;
  regime: 'low' | 'normal' | 'high' | null;
  regime_label: string | null;
  available: boolean;
  overall_win_rate: number;
  trade_count: number;
}

const REGIME_DOT: Record<string, string> = {
  low:    'bg-[#16A34A]',
  normal: 'bg-[#D97706]',
  high:   'bg-[#DC2626]',
};

const REGIME_TEXT: Record<string, string> = {
  low:    'text-tm-profit',
  normal: 'text-tm-obs',
  high:   'text-tm-loss',
};

export default function VixStrip() {
  const { accountId } = useBroker();
  const [data, setData] = useState<VixData | null>(null);

  useEffect(() => {
    if (!accountId) return;
    api.get('/api/analytics/vix-context', { params: { days_back: 90 } })
      .then(r => setData(r.data))
      .catch(() => setData(null));
  }, [accountId]);

  if (!data?.available || !data.vix || !data.regime) return null;

  const dotClass  = REGIME_DOT[data.regime]  ?? 'bg-muted-foreground';
  const textClass = REGIME_TEXT[data.regime] ?? 'text-muted-foreground';

  return (
    <div className="flex items-center gap-2 px-1 py-0.5 text-[12px] text-muted-foreground">
      <span className={cn('w-2 h-2 rounded-full shrink-0', dotClass)} />
      <span>
        VIX{' '}
        <span className={cn('font-mono font-semibold tabular-nums', textClass)}>
          {data.vix.toFixed(1)}
        </span>
        {' '}—{' '}
        <span className={textClass}>{data.regime_label}</span>
        {data.trade_count >= 10 && (
          <span className="text-muted-foreground">
            {' '}· Your {data.overall_win_rate}% WR ({data.trade_count} trades)
          </span>
        )}
      </span>
    </div>
  );
}
