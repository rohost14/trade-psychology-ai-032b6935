import { useState } from 'react';
import { AlertCircle, CheckCircle2, AlertTriangle, XCircle, Check, ChevronDown, Bell, Lightbulb } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatRelativeTime } from '@/lib/formatters';
import type { Alert } from '@/types/api';

interface RecentAlertsCardProps {
  alerts: (Alert & { pattern: string; description: string; why_it_matters?: string })[];
  onAcknowledge?: (alertId: string) => void;
}

const severityConfig = {
  critical: {
    icon: XCircle,
    badgeClass: 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400',
    iconClass: 'text-red-600 dark:text-red-400',
  },
  high: {
    icon: AlertCircle,
    badgeClass: 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400',
    iconClass: 'text-red-600 dark:text-red-400',
  },
  medium: {
    icon: AlertTriangle,
    badgeClass: 'bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400',
    iconClass: 'text-amber-600 dark:text-amber-400',
  },
  positive: {
    icon: CheckCircle2,
    badgeClass: 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400',
    iconClass: 'text-green-600 dark:text-green-400',
  },
};

export default function RecentAlertsCard({ alerts, onAcknowledge }: RecentAlertsCardProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  // Track locally acknowledged IDs (for immediate UI feedback before backend confirms)
  const [localAckedIds, setLocalAckedIds] = useState<Set<string>>(new Set());

  const handleAcknowledge = (alertId: string) => {
    setLocalAckedIds((prev) => new Set([...prev, alertId]));
    onAcknowledge?.(alertId);
  };

  const counts = {
    high: alerts.filter(a => a.severity === 'critical' || a.severity === 'high').length,
    medium: alerts.filter(a => a.severity === 'medium').length,
    positive: alerts.filter(a => a.severity === 'positive').length,
  };

  return (
    <div className="bg-card rounded-lg border border-border">
      {/* Header */}
      <div className="px-6 py-5 border-b border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-amber-100 dark:bg-amber-900/30">
              <Bell className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-foreground">Behavioral Alerts</h3>
              <p className="text-sm text-muted-foreground">{alerts.length} pattern{alerts.length !== 1 ? 's' : ''} detected</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {counts.high > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400">
                <AlertCircle className="h-3.5 w-3.5" />
                {counts.high}
              </span>
            )}
            {counts.medium > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400">
                <AlertTriangle className="h-3.5 w-3.5" />
                {counts.medium}
              </span>
            )}
            {counts.positive > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400">
                <CheckCircle2 className="h-3.5 w-3.5" />
                {counts.positive}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Alerts List */}
      {alerts.length > 0 ? (
        <div className="divide-y divide-border">
          {alerts.slice(0, 5).map((alert) => {
            const config = severityConfig[alert.severity];
            const Icon = config.icon;
            const isExpanded = expandedId === alert.id;
            const isAcknowledged = alert.acknowledged || localAckedIds.has(alert.id);

            return (
              <div
                key={alert.id}
                className={cn(
                  'transition-colors cursor-pointer hover:bg-muted/50',
                  isAcknowledged && 'opacity-50'
                )}
                onClick={() => setExpandedId(isExpanded ? null : alert.id)}
              >
                {/* Alert Row */}
                <div className="px-6 py-4">
                  <div className="flex items-start gap-3">
                    <Icon className={cn('h-5 w-5 shrink-0 mt-0.5', config.iconClass)} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={cn('inline-flex items-center px-2 py-0.5 rounded text-xs font-medium uppercase', config.badgeClass)}>
                          {alert.severity}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {formatRelativeTime(alert.timestamp)}
                        </span>
                        {isAcknowledged && (
                          <Check className="h-3.5 w-3.5 text-green-600" />
                        )}
                      </div>
                      <p className="text-sm font-medium text-foreground mt-2">{alert.pattern}</p>
                      <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{alert.description}</p>
                    </div>
                    <ChevronDown className={cn(
                      'h-5 w-5 text-muted-foreground transition-transform',
                      isExpanded && 'rotate-180'
                    )} />
                  </div>
                </div>

                {/* Expanded Content */}
                {isExpanded && (
                  <div className="px-6 pb-4">
                    <div className="ml-8 pl-4 border-l-2 border-border">
                      {/* Why it matters */}
                      <div className="flex items-start gap-3 p-4 rounded-lg bg-muted/50 border border-border mb-4">
                        <Lightbulb className="h-5 w-5 text-primary mt-0.5 shrink-0" />
                        <div>
                          <p className="text-sm font-medium text-foreground">Why this matters</p>
                          <p className="text-sm text-muted-foreground mt-1">
                            {alert.why_it_matters || 'This pattern affects your trading performance.'}
                          </p>
                        </div>
                      </div>

                      {/* Acknowledge Button */}
                      {!isAcknowledged && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleAcknowledge(alert.id);
                          }}
                          className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
                        >
                          <Check className="h-4 w-4" />
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
        <div className="py-12 text-center">
          <CheckCircle2 className="h-10 w-10 text-green-500/40 mx-auto mb-3" />
          <p className="font-medium text-foreground">All clear!</p>
          <p className="text-sm text-muted-foreground mt-1">No behavioral alerts detected</p>
        </div>
      )}
    </div>
  );
}
