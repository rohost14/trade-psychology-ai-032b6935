import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, Circle, ArrowRight, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';
import { pushNotifications } from '@/lib/pushNotifications';

const DISMISSED_KEY = 'tradementor_setup_nudge_dismissed';

interface Step {
  id: string;
  label: string;
  done: boolean;
  cta: string;
  path: string;
}

export function SetupNudgeCard() {
  const { account, isConnected, isGuest } = useBroker();
  const navigate = useNavigate();
  const [steps, setSteps] = useState<Step[]>([]);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (localStorage.getItem(DISMISSED_KEY)) {
      setDismissed(true);
      setLoading(false);
      return;
    }

    if (!account?.id || !isConnected || isGuest) {
      setLoading(false);
      return;
    }

    checkSetup();
  }, [account?.id, isConnected, isGuest]);

  async function checkSetup() {
    try {
      const [profileRes, notifSubscribed] = await Promise.all([
        api.get('/api/profile/'),
        pushNotifications.isSubscribed(),
      ]);

      const profile = profileRes.data?.profile ?? {};
      const limitsSet = !!(profile.daily_trade_limit || profile.daily_loss_limit);

      const newSteps: Step[] = [
        {
          id: 'broker',
          label: 'Broker connected',
          done: true,
          cta: '',
          path: '',
        },
        {
          id: 'limits',
          label: 'Daily limits set',
          done: limitsSet,
          cta: 'Set limits',
          path: '/settings?tab=profile',
        },
        {
          id: 'notifications',
          label: 'Notifications enabled',
          done: notifSubscribed,
          cta: 'Enable',
          path: '/settings?tab=notifications',
        },
      ];

      setSteps(newSteps);

      // Auto-dismiss if everything is done
      if (newSteps.every(s => s.done)) {
        localStorage.setItem(DISMISSED_KEY, '1');
        setDismissed(true);
      }
    } catch {
      // Silently skip on error — setup nudge is non-critical
    } finally {
      setLoading(false);
    }
  }

  function dismiss() {
    localStorage.setItem(DISMISSED_KEY, '1');
    setDismissed(true);
  }

  const incomplete = steps.filter(s => !s.done);

  if (loading || dismissed || incomplete.length === 0 || isGuest) return null;

  const doneCount = steps.filter(s => s.done).length;
  const pct = Math.round((doneCount / steps.length) * 100);

  return (
    <div className="tm-card overflow-hidden mb-4">
      <div className="px-5 py-3.5 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground">Finish setup</span>
          <span className="text-xs text-muted-foreground">{doneCount}/{steps.length}</span>
        </div>
        <button
          onClick={dismiss}
          className="text-muted-foreground hover:text-foreground transition-colors -mr-1 p-1"
          aria-label="Dismiss"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-muted">
        <div
          className="h-full bg-tm-brand transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>

      <div className="p-5 space-y-3">
        {steps.map(step => (
          <div key={step.id} className="flex items-center gap-3">
            {step.done ? (
              <CheckCircle2 className="h-4 w-4 text-tm-profit shrink-0" />
            ) : (
              <Circle className="h-4 w-4 text-muted-foreground shrink-0" />
            )}
            <span className={cn(
              'text-sm flex-1',
              step.done ? 'text-muted-foreground line-through' : 'text-foreground'
            )}>
              {step.label}
            </span>
            {!step.done && step.path && (
              <button
                onClick={() => navigate(step.path)}
                className="flex items-center gap-1 text-xs text-tm-brand hover:text-tm-brand/80 transition-colors font-medium shrink-0"
              >
                {step.cta}
                <ArrowRight className="h-3 w-3" />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
