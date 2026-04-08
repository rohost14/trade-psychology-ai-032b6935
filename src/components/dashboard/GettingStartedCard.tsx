/**
 * GettingStartedCard — shown to new users until they have trade data.
 * Guides them through the 4 steps needed to get value from TradeMentor.
 * Dismissible once at least 1 completed trade exists.
 */
import { useState, useEffect } from 'react';
import { CheckCircle2, Circle, RefreshCw, BarChart3, Bell, X, Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { useBroker } from '@/contexts/BrokerContext';

const DISMISS_KEY = 'tradementor_gs_dismissed';

interface GettingStartedCardProps {
  tradeCount: number;
  onboardingCompleted: boolean;
  onOpenWizard: () => void;
}

interface Step {
  id: string;
  label: string;
  description: string;
  done: boolean;
  action?: React.ReactNode;
}

export default function GettingStartedCard({
  tradeCount,
  onboardingCompleted,
  onOpenWizard,
}: GettingStartedCardProps) {
  const { account, syncTrades, syncStatus } = useBroker();
  const [dismissed, setDismissed] = useState(false);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    if (!account?.id) return;
    const key = `${DISMISS_KEY}_${account.id}`;
    if (localStorage.getItem(key)) setDismissed(true);
  }, [account?.id]);

  // Auto-hide once user has 3+ trades and completed profile
  const shouldHide = dismissed || (tradeCount >= 3 && onboardingCompleted);
  if (shouldHide) return null;

  const handleDismiss = () => {
    if (account?.id) {
      localStorage.setItem(`${DISMISS_KEY}_${account.id}`, '1');
    }
    setDismissed(true);
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      await syncTrades();
    } finally {
      setSyncing(false);
    }
  };

  const isSyncing = syncing || syncStatus === 'syncing';

  const steps: Step[] = [
    {
      id: 'connect',
      label: 'Connect Zerodha',
      description: 'Your broker account is linked and ready.',
      done: true,
    },
    {
      id: 'profile',
      label: 'Set up your profile',
      description: 'Tell us about your trading style so we can personalise alerts.',
      done: onboardingCompleted,
      action: !onboardingCompleted ? (
        <button
          onClick={onOpenWizard}
          className="text-xs font-medium text-tm-brand hover:underline"
        >
          Set up now →
        </button>
      ) : null,
    },
    {
      id: 'sync',
      label: 'Sync your first trades',
      description: tradeCount > 0
        ? `${tradeCount} trade${tradeCount > 1 ? 's' : ''} synced — behavioral analysis will appear as you trade more.`
        : 'Pull your Zerodha trade history to start behavioural analysis.',
      done: tradeCount > 0,
      action: tradeCount === 0 ? (
        <button
          onClick={handleSync}
          disabled={isSyncing}
          className="flex items-center gap-1 text-xs font-medium text-primary hover:underline disabled:opacity-60"
        >
          {isSyncing ? (
            <><Loader2 className="h-3 w-3 animate-spin" />Syncing…</>
          ) : (
            <><RefreshCw className="h-3 w-3" />Sync now</>
          )}
        </button>
      ) : null,
    },
    {
      id: 'analytics',
      label: 'Explore your Analytics',
      description: 'See patterns, timing insights, and your behavioral score.',
      done: tradeCount >= 5,
      action: tradeCount > 0 && tradeCount < 5 ? (
        <Link to="/analytics" className="text-xs font-medium text-tm-brand hover:underline">
          View Analytics →
        </Link>
      ) : tradeCount >= 5 ? null : null,
    },
  ];

  const completedCount = steps.filter(s => s.done).length;
  const progressPct = Math.round((completedCount / steps.length) * 100);

  return (
    <div className="mb-5 rounded-xl border border-tm-brand/20 bg-teal-50/50 dark:bg-teal-900/10 p-5 relative animate-fade-in-up">
      {/* Dismiss */}
      <button
        onClick={handleDismiss}
        className="absolute top-3 right-3 text-muted-foreground hover:text-foreground transition-colors"
        title="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>

      {/* Header */}
      <div className="flex items-start justify-between mb-4 pr-6">
        <div>
          <p className="text-sm font-semibold text-foreground">Getting started</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {completedCount} of {steps.length} steps complete
          </p>
        </div>
        {/* Mini progress bar */}
        <div className="flex flex-col items-end gap-1 mt-0.5">
          <span className="text-xs font-mono text-muted-foreground">{progressPct}%</span>
          <div className="w-24 h-1.5 bg-border rounded-full overflow-hidden">
            <div
              className="h-full bg-tm-brand rounded-full transition-all duration-500"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      </div>

      {/* Steps */}
      <div className="space-y-3">
        {steps.map((step) => (
          <div key={step.id} className="flex items-start gap-3">
            <div className="mt-0.5 flex-shrink-0">
              {step.done ? (
                <CheckCircle2 className="h-4 w-4 text-tm-profit" />
              ) : (
                <Circle className="h-4 w-4 text-muted-foreground/50" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline gap-2 flex-wrap">
                <p className={cn(
                  'text-sm font-medium',
                  step.done ? 'text-muted-foreground line-through' : 'text-foreground'
                )}>
                  {step.label}
                </p>
                {step.action}
              </div>
              <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
                {step.description}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Footer tip */}
      {tradeCount === 0 && (
        <p className="text-[11px] text-muted-foreground mt-4 border-t border-border/50 pt-3">
          Tip: TradeMentor needs at least 5 completed trades to detect behavioural patterns.
          Trade normally — alerts will appear automatically.
        </p>
      )}
    </div>
  );
}
