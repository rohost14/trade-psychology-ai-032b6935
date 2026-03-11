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
  onSync?: () => void;  // kept for API compatibility, no longer shown (prices live via KiteTicker)
  isLoading?: boolean;
}

const riskStateConfig = {
  safe: {
    label: 'Safe',
    icon: CheckCircle2,
    badgeClass: 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400',
    barColor: 'bg-green-500',
  },
  caution: {
    label: 'Caution',
    icon: AlertTriangle,
    badgeClass: 'bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400',
    barColor: 'bg-amber-500',
  },
  danger: {
    label: 'Danger',
    icon: AlertTriangle,
    badgeClass: 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400',
    barColor: 'bg-red-500',
  },
};

export default function RiskGuardianCard({ data, stats: propStats, onSync, isLoading }: RiskGuardianCardProps) {
  const config = riskStateConfig[data.risk_state];
  const pnlColor = data.unrealized_pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400';
  const StateIcon = config.icon;

  const marginUtilization = propStats?.margin_utilization ?? propStats?.risk_used ?? 0;

  const stats = {
    trades: propStats?.trades_today ?? 0,
    winRate: propStats?.win_rate ?? 0,
    drawdown: propStats?.max_drawdown ?? 0,
    marginUsed: marginUtilization,
  };

  const statItems = [
    { label: 'Trades Today', value: stats.trades, icon: Target },
    { label: 'Win Rate', value: `${Math.round(stats.winRate)}%`, color: stats.winRate >= 50 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400', icon: TrendingUp },
    { label: 'Max Drawdown', value: formatCurrencyWithSign(stats.drawdown), color: 'text-red-600 dark:text-red-400', icon: Activity },
    { label: 'Margin Used', value: `${Math.round(stats.marginUsed)}%`, color: stats.marginUsed > 80 ? 'text-red-600' : stats.marginUsed > 60 ? 'text-amber-600' : 'text-green-600', icon: Zap },
  ];

  return (
    <div className="bg-card rounded-lg border border-border">
      {/* Header */}
      <div className="px-6 py-5 border-b border-border">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-lg bg-primary/10">
              <Shield className="h-6 w-6 text-primary" />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-lg font-semibold text-foreground">Risk Guardian</h2>
                <span className={cn('inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium', config.badgeClass)}>
                  <StateIcon className="h-3.5 w-3.5" />
                  {config.label}
                </span>
              </div>
              <p className="text-sm text-muted-foreground mt-1">
                {data.status_message || 'Monitoring your trading behavior'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-xs text-muted-foreground mb-1">Session P&L</p>
              <p className={cn('text-2xl font-semibold tabular-nums', pnlColor)}>
                {formatCurrencyWithSign(data.unrealized_pnl)}
              </p>
            </div>
            {/* Sync button removed — prices now live via KiteTicker.
                Trade sync is available in Settings if needed. */}
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 divide-x divide-y lg:divide-y-0 divide-border">
        {statItems.map((stat) => (
          <div key={stat.label} className="px-6 py-4">
            <div className="flex items-center gap-2 mb-1">
              <stat.icon className="h-4 w-4 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">{stat.label}</p>
            </div>
            <p className={cn('text-xl font-semibold tabular-nums', stat.color || 'text-foreground')}>
              {stat.value}
            </p>
          </div>
        ))}
      </div>

      {/* Margin Bar */}
      <div className="px-6 py-4 border-t border-border bg-muted/30">
        <div className="flex items-center justify-between text-sm mb-2">
          <span className="text-muted-foreground font-medium">Margin Utilization</span>
          <span className={cn(
            'font-medium',
            stats.marginUsed > 80 ? 'text-red-600' : stats.marginUsed > 60 ? 'text-amber-600' : 'text-green-600'
          )}>
            {Math.round(100 - stats.marginUsed)}% available
          </span>
        </div>
        <div className="h-2 bg-muted rounded-full overflow-hidden">
          <div
            className={cn(
              'h-full rounded-full transition-all duration-500',
              stats.marginUsed > 80 ? 'bg-red-500' : stats.marginUsed > 60 ? 'bg-amber-500' : 'bg-green-500'
            )}
            style={{ width: `${stats.marginUsed}%` }}
          />
        </div>
      </div>
    </div>
  );
}
