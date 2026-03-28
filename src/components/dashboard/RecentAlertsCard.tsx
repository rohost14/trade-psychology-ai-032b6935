import { useState } from 'react';
import { CheckCircle2, AlertTriangle, XCircle, Check, ChevronDown, Bell, Lightbulb } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatRelativeTime } from '@/lib/formatters';
import type { Alert } from '@/types/api';

interface RecentAlertsCardProps {
  alerts: (Alert & { pattern: string; description: string; why_it_matters?: string })[];
  onAcknowledge?: (alertId: string) => void;
}

const severityConfig: Record<string, {
  icon: any;
  borderClass: string;
  textClass: string;
  dotClass: string;
}> = {
  critical: {
    icon: XCircle,
    borderClass: 'border-l-red-500',
    textClass:   'text-red-600 dark:text-red-400',
    dotClass:    'bg-red-500',
  },
  danger: {
    icon: XCircle,
    borderClass: 'border-l-red-500',
    textClass:   'text-red-600 dark:text-red-400',
    dotClass:    'bg-red-500',
  },
  high: {
    icon: AlertTriangle,
    borderClass: 'border-l-red-400',
    textClass:   'text-red-600 dark:text-red-400',
    dotClass:    'bg-red-400',
  },
  medium: {
    icon: AlertTriangle,
    borderClass: 'border-l-amber-400',
    textClass:   'text-amber-600 dark:text-amber-400',
    dotClass:    'bg-amber-400',
  },
  caution: {
    icon: AlertTriangle,
    borderClass: 'border-l-amber-400',
    textClass:   'text-amber-600 dark:text-amber-400',
    dotClass:    'bg-amber-400',
  },
  positive: {
    icon: CheckCircle2,
    borderClass: 'border-l-emerald-400',
    textClass:   'text-emerald-600 dark:text-emerald-400',
    dotClass:    'bg-emerald-400',
  },
};

export default function RecentAlertsCard({ alerts, onAcknowledge }: RecentAlertsCardProps) {
  const [expandedId, setExpandedId]   = useState<string | null>(null);
  const [localAckedIds, setLocalAckedIds] = useState<Set<string>>(new Set());

  const handleAcknowledge = (alertId: string) => {
    setLocalAckedIds((prev) => new Set([...prev, alertId]));
    onAcknowledge?.(alertId);
  };

  const counts = {
    high:     alerts.filter(a => a.severity === 'critical' || a.severity === 'high').length,
    medium:   alerts.filter(a => a.severity === 'medium').length,
    positive: alerts.filter(a => a.severity === 'positive').length,
  };

  return (
    <div className="bg-card rounded-lg border border-border">

      {/* ── Header ── */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <Bell className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-semibold text-foreground">Behavioral Alerts</span>
          <span className="text-xs text-muted-foreground">
            {alerts.length} pattern{alerts.length !== 1 ? 's' : ''}
          </span>
        </div>

        {/* Severity counts */}
        <div className="flex items-center gap-2">
          {counts.high > 0 && (
            <span className="flex items-center gap-1 text-xs font-medium text-red-600 dark:text-red-400">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
              {counts.high}
            </span>
          )}
          {counts.medium > 0 && (
            <span className="flex items-center gap-1 text-xs font-medium text-amber-600 dark:text-amber-400">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
              {counts.medium}
            </span>
          )}
          {counts.positive > 0 && (
            <span className="flex items-center gap-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              {counts.positive}
            </span>
          )}
        </div>
      </div>

      {/* ── Alert List ── */}
      {alerts.length > 0 ? (
        <div className="divide-y divide-border">
          {alerts.slice(0, 5).map((alert) => {
            const config      = severityConfig[alert.severity] ?? severityConfig['high'];
            const isExpanded  = expandedId === alert.id;
            const isAcked     = alert.acknowledged || localAckedIds.has(alert.id);

            return (
              <div
                key={alert.id}
                className={cn(
                  'border-l-2 transition-colors cursor-pointer hover:bg-muted/40',
                  config.borderClass,
                  isAcked && 'opacity-50'
                )}
                onClick={() => setExpandedId(isExpanded ? null : alert.id)}
              >
                {/* Row */}
                <div className="px-4 py-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      {/* Top line: severity label + pattern name + timestamp */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={cn(
                          'text-[10px] font-semibold uppercase tracking-wide shrink-0',
                          config.textClass
                        )}>
                          {alert.severity}
                        </span>
                        <span className="text-sm font-medium text-foreground truncate">
                          {alert.pattern}
                        </span>
                        {isAcked && <Check className="h-3 w-3 text-emerald-500 shrink-0" />}
                        <span className="text-xs text-muted-foreground ml-auto shrink-0">
                          {formatRelativeTime(alert.timestamp)}
                        </span>
                      </div>
                      {/* Description */}
                      <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
                        {alert.description}
                      </p>
                    </div>
                    <ChevronDown className={cn(
                      'h-4 w-4 text-muted-foreground shrink-0 mt-0.5 transition-transform',
                      isExpanded && 'rotate-180'
                    )} />
                  </div>
                </div>

                {/* Expanded */}
                {isExpanded && (
                  <div className="px-4 pb-3">
                    <div className="pl-0 space-y-3">
                      <div className="flex items-start gap-2 p-3 rounded-md bg-muted/50 border border-border">
                        <Lightbulb className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                        <div>
                          <p className="text-xs font-medium text-foreground">Why this matters</p>
                          <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
                            {alert.why_it_matters || 'This pattern affects your trading performance.'}
                          </p>
                        </div>
                      </div>
                      {!isAcked && (
                        <button
                          onClick={(e) => { e.stopPropagation(); handleAcknowledge(alert.id); }}
                          className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 transition-colors"
                        >
                          <Check className="h-3.5 w-3.5" />
                          Acknowledge
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="py-10 text-center">
          <CheckCircle2 className="h-8 w-8 text-emerald-500/30 mx-auto mb-2.5" />
          <p className="text-sm font-medium text-foreground">All clear</p>
          <p className="text-xs text-muted-foreground mt-0.5">No behavioral alerts detected</p>
        </div>
      )}
    </div>
  );
}
