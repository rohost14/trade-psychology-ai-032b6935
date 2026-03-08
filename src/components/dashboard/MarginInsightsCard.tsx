import { BarChart3, CheckCircle2, AlertTriangle, XCircle, Info } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { MarginInsightsResponse, MarginSnapshot, MarginInsight } from '@/types/api';

interface MarginInsightsCardProps {
  insights: MarginInsightsResponse | null;
  isLoading?: boolean;
}

const insightIcons: Record<string, typeof Info> = {
  positive: CheckCircle2,
  warning: AlertTriangle,
  danger: XCircle,
  info: Info,
};

const insightColors: Record<string, string> = {
  positive: 'text-success bg-success/10 border-success/20',
  warning: 'text-warning bg-warning/10 border-warning/20',
  danger: 'text-destructive bg-destructive/10 border-destructive/20',
  info: 'text-primary bg-primary/10 border-primary/20',
};

function MiniChart({ snapshots }: { snapshots: MarginSnapshot[] }) {
  if (snapshots.length === 0) return null;

  const maxUtil = Math.max(...snapshots.map((s) => s.max_utilization), 100);
  const chartHeight = 64;

  return (
    <div className="flex items-end gap-[2px] h-16">
      {snapshots.slice(-14).map((snapshot, i) => {
        const height = (snapshot.max_utilization / maxUtil) * chartHeight;
        const barColor =
          snapshot.risk_level === 'danger'
            ? 'bg-destructive'
            : snapshot.risk_level === 'warning'
              ? 'bg-warning'
              : 'bg-primary/40';

        return (
          <div
            key={i}
            className={cn('flex-1 rounded-t-sm min-w-[4px]', barColor)}
            style={{ height: `${Math.max(height, 2)}px` }}
            title={`${new Date(snapshot.timestamp).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}: ${snapshot.max_utilization.toFixed(0)}% utilization`}
          />
        );
      })}
    </div>
  );
}

function InsightItem({ insight }: { insight: MarginInsight }) {
  const IconComponent = insightIcons[insight.type] || Info;
  const colorClass = insightColors[insight.type] || insightColors.info;

  return (
    <div className={cn('flex items-start gap-3 p-3 rounded-xl border', colorClass)}>
      <IconComponent className="h-4 w-4 mt-0.5 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{insight.title}</p>
        <p className="text-xs opacity-80 mt-0.5">{insight.message}</p>
      </div>
    </div>
  );
}

export default function MarginInsightsCard({ insights, isLoading }: MarginInsightsCardProps) {
  if (isLoading) {
    return (
      <div className="bg-card rounded-lg border border-border">
        <div className="px-6 py-5 border-b border-border">
          <div className="h-6 w-48 bg-muted animate-pulse rounded" />
        </div>
        <div className="p-6 space-y-4">
          <div className="h-16 bg-muted animate-pulse rounded" />
          <div className="h-12 bg-muted animate-pulse rounded" />
        </div>
      </div>
    );
  }

  if (!insights || !insights.history?.has_data) return null;

  const { history, insights: marginInsights } = insights;
  const { statistics } = history;

  return (
    <div className="bg-card rounded-lg border border-border">
      {/* Header */}
      <div className="px-6 py-5 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-primary/10">
            <BarChart3 className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-foreground">Margin Insights</h3>
            <p className="text-sm text-muted-foreground">
              Daily max margin utilization ({history.period_days} days)
            </p>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="px-6 py-5 border-b border-border">
        <MiniChart snapshots={history.snapshots} />
        <div className="flex justify-between mt-2 text-xs text-muted-foreground">
          <span>
            {history.snapshots.length > 0
              ? new Date(history.snapshots[0].timestamp).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' })
              : ''}
          </span>
          <span>Today</span>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 divide-x divide-border border-b border-border">
        <div className="px-4 py-3 text-center">
          <p className="text-xs text-muted-foreground mb-0.5">Avg</p>
          <p className="text-sm font-semibold text-foreground tabular-nums">
            {Number(statistics?.avg_utilization || 0).toFixed(0)}%
          </p>
        </div>
        <div className="px-4 py-3 text-center">
          <p className="text-xs text-muted-foreground mb-0.5">Max</p>
          <p className={cn(
            'text-sm font-semibold tabular-nums',
            (statistics?.max_utilization || 0) > 80 ? 'text-destructive' : 'text-foreground'
          )}>
            {Number(statistics?.max_utilization || 0).toFixed(0)}%
          </p>
        </div>
        <div className="px-4 py-3 text-center">
          <p className="text-xs text-muted-foreground mb-0.5">Warnings</p>
          <p className={cn(
            'text-sm font-semibold tabular-nums',
            (statistics?.danger_occurrences || 0) > 0 ? 'text-destructive' :
              (statistics?.warning_occurrences || 0) > 0 ? 'text-warning' : 'text-success'
          )}>
            {(statistics?.danger_occurrences || 0) + (statistics?.warning_occurrences || 0)}
          </p>
        </div>
      </div>

      {/* Insights */}
      {marginInsights && marginInsights.length > 0 && (
        <div className="px-6 py-5 space-y-2">
          {marginInsights.slice(0, 3).map((insight, i) => (
            <InsightItem key={i} insight={insight} />
          ))}
        </div>
      )}
    </div>
  );
}
