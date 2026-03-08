import { PieChart, RefreshCw, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCurrency } from '@/lib/formatters';
import { motion } from 'framer-motion';
import type { MarginStatus } from '@/types/api';

interface MarginStatusCardProps {
  margins: MarginStatus | null;
  isLoading?: boolean;
  onRefresh?: () => void;
}

function UtilizationBar({ percent, riskLevel }: { percent: number; riskLevel: string }) {
  const barColor =
    riskLevel === 'danger' || percent > 80
      ? 'bg-destructive'
      : riskLevel === 'warning' || percent > 60
        ? 'bg-warning'
        : 'bg-success';

  return (
    <div className="w-full h-2 rounded-full bg-muted/50 overflow-hidden">
      <motion.div
        className={cn('h-full rounded-full', barColor)}
        initial={{ width: 0 }}
        animate={{ width: `${Math.min(percent, 100)}%` }}
        transition={{ duration: 0.8, ease: 'easeOut' }}
      />
    </div>
  );
}

function SegmentCard({
  label,
  available,
  used,
  total,
  utilization,
}: {
  label: string;
  available: number;
  used: number;
  total: number;
  utilization: number;
}) {
  const riskLevel = utilization > 80 ? 'danger' : utilization > 60 ? 'warning' : 'safe';
  const textColor =
    riskLevel === 'danger'
      ? 'text-destructive'
      : riskLevel === 'warning'
        ? 'text-warning'
        : 'text-success';

  return (
    <div className="p-4 rounded-xl bg-muted/30 border border-border/50 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-foreground uppercase tracking-wide">{label}</p>
        <span className={cn('text-sm font-semibold tabular-nums', textColor)}>
          {utilization}%
        </span>
      </div>
      <UtilizationBar percent={utilization} riskLevel={riskLevel} />
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>Available: {formatCurrency(available)}</span>
        <span>Used: {formatCurrency(used)}</span>
      </div>
    </div>
  );
}

export default function MarginStatusCard({ margins, isLoading, onRefresh }: MarginStatusCardProps) {
  if (isLoading) {
    return (
      <div className="bg-card rounded-lg border border-border">
        <div className="px-6 py-5 border-b border-border">
          <div className="h-6 w-48 bg-muted animate-pulse rounded" />
        </div>
        <div className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="h-24 bg-muted animate-pulse rounded-xl" />
            <div className="h-24 bg-muted animate-pulse rounded-xl" />
          </div>
          <div className="h-12 bg-muted animate-pulse rounded" />
        </div>
      </div>
    );
  }

  if (!margins) return null;

  const { equity, commodity, overall } = margins;

  const riskBorderColor =
    overall.risk_level === 'danger'
      ? 'border-destructive/30'
      : overall.risk_level === 'warning'
        ? 'border-warning/30'
        : 'border-border';

  const RiskIcon =
    overall.risk_level === 'danger'
      ? TrendingDown
      : overall.risk_level === 'warning'
        ? Minus
        : TrendingUp;

  const riskIconColor =
    overall.risk_level === 'danger'
      ? 'text-destructive'
      : overall.risk_level === 'warning'
        ? 'text-warning'
        : 'text-success';

  return (
    <div className={cn('bg-card rounded-lg border', riskBorderColor)}>
      {/* Header */}
      <div className="px-6 py-5 border-b border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-primary/10">
              <PieChart className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-foreground">Margin Status</h3>
              <div className="flex items-center gap-1.5 mt-0.5">
                <RiskIcon className={cn('h-3.5 w-3.5', riskIconColor)} />
                <p className="text-sm text-muted-foreground">{overall.risk_message}</p>
              </div>
            </div>
          </div>
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="p-2 rounded-lg hover:bg-muted transition-colors"
              title="Refresh margins"
            >
              <RefreshCw className="h-4 w-4 text-muted-foreground" />
            </button>
          )}
        </div>
      </div>

      {/* Segments */}
      <div className="p-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <SegmentCard
            label="Equity"
            available={equity.available}
            used={equity.used}
            total={equity.total}
            utilization={equity.utilization_pct}
          />
          <SegmentCard
            label="Commodity"
            available={commodity.available}
            used={commodity.used}
            total={commodity.total}
            utilization={commodity.utilization_pct}
          />
        </div>

        {/* Breakdown */}
        <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-muted-foreground">
          <span>Cash: {formatCurrency(equity.breakdown.cash)}</span>
          <span>Collateral: {formatCurrency(equity.breakdown.collateral)}</span>
          <span>Exposure: {formatCurrency(equity.breakdown.exposure)}</span>
          {equity.breakdown.span > 0 && <span>SPAN: {formatCurrency(equity.breakdown.span)}</span>}
          {equity.breakdown.option_premium > 0 && (
            <span>Options: {formatCurrency(equity.breakdown.option_premium)}</span>
          )}
        </div>
      </div>
    </div>
  );
}
