import { Shield, AlertTriangle, CheckCircle2, Activity, Zap, TrendingUp, Target } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { formatCurrencyWithSign } from '@/lib/formatters';

interface RiskGuardianData {
  risk_state: 'safe' | 'caution' | 'danger';
  status_message: string;
  active_patterns: string[];
  unrealized_pnl: number;
  ai_recommendations: string[];
  last_synced: string;
}

interface RiskGuardianStats {
  trades_today?: number;
  win_rate?: number;
  max_drawdown?: number;
  risk_used?: number;
  margin_used?: number;
  margin_available?: number;
  margin_utilization?: number;
}

interface RiskGuardianCardProps {
  data: RiskGuardianData;
  stats?: RiskGuardianStats;
  onSync?: () => void;
  isLoading?: boolean;
}

const riskStateConfig = {
  safe: {
    label: 'Safe',
    icon: CheckCircle2,
    dotClass: 'bg-emerald-500',
    textClass: 'text-emerald-600 dark:text-emerald-400',
    barColor: 'bg-green-500',
  },
  caution: {
    label: 'Caution',
    icon: AlertTriangle,
    dotClass: 'bg-amber-500',
    textClass: 'text-amber-600 dark:text-amber-400',
    barColor: 'bg-amber-500',
  },
  danger: {
    label: 'Danger',
    icon: AlertTriangle,
    dotClass: 'bg-red-500',
    textClass: 'text-red-600 dark:text-red-400',
    barColor: 'bg-red-500',
  },
};

export default function RiskGuardianCard({ data, stats: propStats, onSync, isLoading }: RiskGuardianCardProps) {
  const config = riskStateConfig[data.risk_state];
  const pnlPositive = data.unrealized_pnl >= 0;
  const pnlColor = pnlPositive
    ? 'text-emerald-600 dark:text-emerald-400'
    : 'text-red-600 dark:text-red-400';

  const marginUtilization = propStats?.margin_utilization ?? propStats?.risk_used ?? 0;
  const marginBarColor =
    marginUtilization > 80 ? 'bg-red-500' :
    marginUtilization > 60 ? 'bg-amber-500' : 'bg-emerald-500';
  const marginTextColor =
    marginUtilization > 80 ? 'text-red-600 dark:text-red-400' :
    marginUtilization > 60 ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400';

  const stats = {
    trades:    propStats?.trades_today ?? 0,
    winRate:   propStats?.win_rate ?? 0,
    drawdown:  propStats?.max_drawdown ?? 0,
    marginUsed: marginUtilization,
  };

  const statItems = [
    {
      label: 'Trades Today',
      value: String(stats.trades),
      color: '',
    },
    {
      label: 'Win Rate',
      value: `${Math.round(stats.winRate)}%`,
      color: stats.winRate >= 50
        ? 'text-emerald-600 dark:text-emerald-400'
        : 'text-red-600 dark:text-red-400',
    },
    {
      label: 'Max Drawdown',
      value: formatCurrencyWithSign(stats.drawdown),
      color: 'text-red-600 dark:text-red-400',
    },
    {
      label: 'Margin Used',
      value: `${Math.round(stats.marginUsed)}%`,
      color: marginTextColor,
    },
  ];

  return (
    <div className="bg-card rounded-lg border border-border">

      {/* ── Header ── */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2.5 min-w-0">
          {/* Colored status dot */}
          <span className={cn('w-2 h-2 rounded-full shrink-0', config.dotClass)} />
          {/* State label */}
          <span className={cn('text-sm font-semibold shrink-0', config.textClass)}>
            {config.label}
          </span>
          {/* Divider */}
          <span className="text-border text-sm shrink-0">·</span>
          {/* Status message */}
          <span className="text-sm text-muted-foreground truncate">
            {data.status_message || 'Monitoring your trading behavior'}
          </span>
        </div>

        {/* Session P&L */}
        <div className="flex items-baseline gap-1.5 shrink-0 ml-4">
          <span className="text-xs text-muted-foreground">Session</span>
          <span className={cn('text-xl font-semibold tabular-nums leading-none', pnlColor)}>
            {formatCurrencyWithSign(data.unrealized_pnl)}
          </span>
        </div>
      </div>

      {/* ── Stats Grid ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 divide-x divide-y lg:divide-y-0 divide-border">
        {statItems.map((stat) => (
          <div key={stat.label} className="px-4 py-3">
            <p className="text-xs text-muted-foreground mb-0.5">{stat.label}</p>
            <p className={cn('text-lg font-semibold tabular-nums leading-tight', stat.color || 'text-foreground')}>
              {stat.value}
            </p>
          </div>
        ))}
      </div>

      {/* ── Margin Bar ── */}
      <div className="px-4 py-3 border-t border-border bg-muted/20">
        <div className="flex items-center justify-between text-xs mb-1.5">
          <span className="text-muted-foreground">Margin utilization</span>
          <span className={cn('font-medium tabular-nums', marginTextColor)}>
            {Math.round(stats.marginUsed)}% used
            {stats.marginUsed > 100
              ? <span className="text-red-600 dark:text-red-400 font-normal ml-1.5">· over-leveraged</span>
              : <span className="text-muted-foreground font-normal ml-1.5">· {Math.round(100 - stats.marginUsed)}% available</span>
            }
          </span>
        </div>
        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
          <div
            className={cn('h-full rounded-full transition-all duration-500', marginBarColor)}
            style={{ width: `${Math.min(stats.marginUsed, 100)}%` }}
          />
        </div>
      </div>
    </div>
  );
}
