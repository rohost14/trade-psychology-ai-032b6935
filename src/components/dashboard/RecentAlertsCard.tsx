import { useState } from 'react';
import { AlertCircle, CheckCircle2, AlertTriangle, XCircle, Check, ChevronDown, Bell, Sparkles, Lightbulb } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatRelativeTime } from '@/lib/formatters';
import { motion, AnimatePresence } from 'framer-motion';
import type { Alert } from '@/types/api';

interface RecentAlertsCardProps {
  alerts: (Alert & { pattern: string; description: string; why_it_matters?: string })[];
  onAcknowledge?: (alertId: string) => void;
}

const severityConfig = {
  critical: {
    icon: XCircle,
    badgeClass: 'bg-destructive/15 text-destructive border border-destructive/25',
    iconClass: 'text-destructive',
    bgClass: 'hover:bg-destructive/5',
    glowClass: 'hover:shadow-[inset_0_0_24px_-10px_hsl(var(--destructive)/0.25)]',
  },
  high: {
    icon: AlertCircle,
    badgeClass: 'bg-destructive/15 text-destructive border border-destructive/25',
    iconClass: 'text-destructive',
    bgClass: 'hover:bg-destructive/5',
    glowClass: 'hover:shadow-[inset_0_0_24px_-10px_hsl(var(--destructive)/0.25)]',
  },
  medium: {
    icon: AlertTriangle,
    badgeClass: 'bg-warning/15 text-warning border border-warning/25',
    iconClass: 'text-warning',
    bgClass: 'hover:bg-warning/5',
    glowClass: 'hover:shadow-[inset_0_0_24px_-10px_hsl(var(--warning)/0.25)]',
  },
  positive: {
    icon: CheckCircle2,
    badgeClass: 'bg-success/15 text-success border border-success/25',
    iconClass: 'text-success',
    bgClass: 'hover:bg-success/5',
    glowClass: 'hover:shadow-[inset_0_0_24px_-10px_hsl(var(--success)/0.25)]',
  },
};

export default function RecentAlertsCard({ alerts, onAcknowledge }: RecentAlertsCardProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [acknowledgedIds, setAcknowledgedIds] = useState<Set<string>>(new Set());

  const handleAcknowledge = (alertId: string) => {
    setAcknowledgedIds((prev) => new Set([...prev, alertId]));
    onAcknowledge?.(alertId);
  };

  const counts = {
    critical: alerts.filter(a => a.severity === 'critical').length,
    high: alerts.filter(a => a.severity === 'high').length,
    medium: alerts.filter(a => a.severity === 'medium').length,
    positive: alerts.filter(a => a.severity === 'positive').length,
  };

  const hasAlerts = alerts.length > 0;

  return (
    <div className="card-premium hover-glow-warning">
      {/* Header */}
      <div className="px-6 py-5 border-b border-border/40 bg-gradient-to-r from-warning/8 to-transparent relative overflow-hidden">
        {/* Subtle mesh */}
        <div className="absolute inset-0 bg-gradient-mesh opacity-30 pointer-events-none" />
        
        <div className="relative flex items-center justify-between">
          <div className="flex items-center gap-4">
            <motion.div 
              className="p-3 rounded-2xl bg-gradient-to-br from-warning/25 to-warning/10 border border-warning/20 shadow-lg"
              whileHover={{ scale: 1.08, rotate: 5 }}
              transition={{ type: 'spring', stiffness: 300 }}
            >
              <Bell className="h-5 w-5 text-warning" />
            </motion.div>
            <div>
              <h3 className="text-lg font-semibold text-foreground">Behavioral Alerts</h3>
              <p className="text-sm text-muted-foreground">{alerts.length} pattern{alerts.length !== 1 ? 's' : ''} detected</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {counts.high > 0 && (
              <motion.span 
                className="badge-premium bg-destructive/15 text-destructive border-destructive/25"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', delay: 0.1 }}
              >
                <AlertCircle className="h-3.5 w-3.5" />
                {counts.high}
              </motion.span>
            )}
            {counts.medium > 0 && (
              <motion.span 
                className="badge-premium bg-warning/15 text-warning border-warning/25"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', delay: 0.15 }}
              >
                <AlertTriangle className="h-3.5 w-3.5" />
                {counts.medium}
              </motion.span>
            )}
            {counts.positive > 0 && (
              <motion.span 
                className="badge-premium bg-success/15 text-success border-success/25"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', delay: 0.2 }}
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
                {counts.positive}
              </motion.span>
            )}
          </div>
        </div>
      </div>

      {/* Alerts List */}
      {hasAlerts ? (
        <div className="divide-y divide-border/40">
          {alerts.slice(0, 5).map((alert, index) => {
            const config = severityConfig[alert.severity];
            const Icon = config.icon;
            const isExpanded = expandedId === alert.id;
            const isAcknowledged = acknowledgedIds.has(alert.id);

            return (
              <motion.div
                key={alert.id}
                className={cn(
                  'transition-all duration-300 cursor-pointer',
                  config.bgClass,
                  config.glowClass,
                  isAcknowledged && 'opacity-50'
                )}
                onClick={() => setExpandedId(isExpanded ? null : alert.id)}
                initial={{ opacity: 0, x: -15 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.06, type: 'spring', stiffness: 120 }}
              >
                {/* Alert Row */}
                <div className="px-6 py-4">
                  <div className="flex items-start gap-3.5">
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ delay: 0.1 + index * 0.05, type: 'spring' }}
                      className="mt-0.5"
                    >
                      <Icon className={cn('h-5 w-5 shrink-0', config.iconClass)} />
                    </motion.div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={cn('badge-premium text-[10px] uppercase', config.badgeClass)}>
                          {alert.severity}
                        </span>
                        <span className="text-xs text-muted-foreground font-medium">
                          {formatRelativeTime(alert.timestamp)}
                        </span>
                        {isAcknowledged && (
                          <motion.div
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            transition={{ type: 'spring' }}
                            className="flex items-center gap-1 text-success"
                          >
                            <Check className="h-3.5 w-3.5" />
                          </motion.div>
                        )}
                      </div>
                      <p className="text-[15px] font-medium text-foreground mt-2">{alert.pattern}</p>
                      <p className="text-sm text-muted-foreground mt-1 line-clamp-2 leading-relaxed">{alert.description}</p>
                    </div>
                    <motion.div
                      animate={{ rotate: isExpanded ? 180 : 0 }}
                      transition={{ duration: 0.25 }}
                      className="p-1"
                    >
                      <ChevronDown className="h-5 w-5 text-muted-foreground shrink-0" />
                    </motion.div>
                  </div>
                </div>

                {/* Expanded Content */}
                <AnimatePresence>
                  {isExpanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                      className="overflow-hidden"
                    >
                      <div className="px-6 pb-5 pt-0">
                        <div className="ml-8 pl-4 border-l-2 border-border/50">
                          {/* Why it matters */}
                          <motion.div 
                            className="flex items-start gap-3 p-4 rounded-xl bg-gradient-to-r from-accent/80 to-accent/40 border border-border/50 mb-4"
                            initial={{ y: 10, opacity: 0 }}
                            animate={{ y: 0, opacity: 1 }}
                            transition={{ delay: 0.1 }}
                          >
                            <Lightbulb className="h-5 w-5 text-primary mt-0.5 shrink-0" />
                            <div>
                              <p className="text-sm font-semibold text-foreground">Why this matters</p>
                              <p className="text-sm text-muted-foreground mt-1.5 leading-relaxed">
                                {alert.why_it_matters || 'This pattern affects your trading performance.'}
                              </p>
                            </div>
                          </motion.div>

                          {/* Acknowledge Button */}
                          {!isAcknowledged && (
                            <motion.button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleAcknowledge(alert.id);
                              }}
                              className="w-full flex items-center justify-center gap-2 px-4 py-3.5 rounded-xl bg-gradient-to-r from-primary to-primary/90 text-primary-foreground text-sm font-semibold hover:opacity-90 transition-all duration-300 shadow-lg"
                              whileHover={{ scale: 1.01, y: -1 }}
                              whileTap={{ scale: 0.99 }}
                              initial={{ y: 10, opacity: 0 }}
                              animate={{ y: 0, opacity: 1 }}
                              transition={{ delay: 0.15 }}
                            >
                              <Check className="h-4 w-4" />
                              Acknowledge
                            </motion.button>
                          )}
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            );
          })}
        </div>
      ) : (
        <div className="py-16 text-center">
          <motion.div 
            className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-success/25 to-success/10 border border-success/20 mb-4 shadow-lg"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 200 }}
          >
            <CheckCircle2 className="h-8 w-8 text-success" />
          </motion.div>
          <motion.p 
            className="text-base font-semibold text-foreground"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            All clear!
          </motion.p>
          <motion.p 
            className="text-sm text-muted-foreground mt-1"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
          >
            No behavioral alerts detected
          </motion.p>
        </div>
      )}
    </div>
  );
}
