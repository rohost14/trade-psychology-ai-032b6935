/**
 * PredictiveContextStrip
 *
 * Thin, dismissable context rows placed between the session hero and alerts.
 * Shows pattern-based risk context (danger hour, danger day, revenge window).
 * Mental model: "here's the risk environment right now" — NOT "you just did something wrong".
 *
 * Dismissed entries survive until page reload (sessionStorage).
 */

import { useState, useEffect } from 'react';
import { Clock, AlertTriangle, Zap, TrendingDown, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { useWebSocket } from '@/contexts/WebSocketContext';

const SESSION_DISMISSED_KEY = 'tm_pred_dismissed';

interface PredictiveItem {
  id: string;
  type: 'danger_hour' | 'danger_day' | 'revenge_window' | 'problem_symbol';
  label: string;
  detail: string;
  danger: boolean;
}

const ICONS = {
  danger_hour:    Clock,
  danger_day:     AlertTriangle,
  revenge_window: Zap,
  problem_symbol: TrendingDown,
};

interface Props {
  brokerAccountId: string;
}

export function PredictiveContextStrip({ brokerAccountId }: Props) {
  const [items, setItems] = useState<PredictiveItem[]>([]);
  const { lastTradeEvent, lastAlertEvent } = useWebSocket();

  // Dismissed this session
  const [dismissed, setDismissed] = useState<Set<string>>(() => {
    try {
      const raw = sessionStorage.getItem(SESSION_DISMISSED_KEY);
      return new Set(raw ? JSON.parse(raw) : []);
    } catch {
      return new Set();
    }
  });

  function dismiss(id: string) {
    setDismissed(prev => {
      const next = new Set([...prev, id]);
      try { sessionStorage.setItem(SESSION_DISMISSED_KEY, JSON.stringify([...next])); } catch {}
      return next;
    });
  }

  useEffect(() => {
    if (!brokerAccountId) return;
    load();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [brokerAccountId, lastTradeEvent?.timestamp, lastAlertEvent?.timestamp]);

  async function load() {
    try {
      const [insRes, chkRes] = await Promise.all([
        api.get('/api/personalization/insights'),
        api.post('/api/personalization/predictive-check', {}),
      ]);
      const insights = insRes.data;
      const check    = chkRes.data;
      const next: PredictiveItem[] = [];

      const nowHour = `${new Date().getHours()}:00`;
      if (insights.danger_hours?.includes(nowHour)) {
        next.push({
          id: 'danger-hour',
          type: 'danger_hour',
          label: 'Danger hour',
          detail: `You historically lose at ${nowHour}. Trade small or wait.`,
          danger: true,
        });
      }

      const days = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
      const today = days[new Date().getDay()];
      if (insights.danger_days?.includes(today)) {
        next.push({
          id: 'danger-day',
          type: 'danger_day',
          label: `${today} — danger day`,
          detail: `Win rate below 35% historically on ${today}s.`,
          danger: true,
        });
      }

      if (insights.revenge_window_minutes && check.has_warning) {
        next.push({
          id: 'revenge-window',
          type: 'revenge_window',
          label: 'Revenge window',
          detail: `You typically trade impulsively within ${insights.revenge_window_minutes}min of a loss. Take a breath.`,
          danger: false,
        });
      }

      if (check.alert && !next.find(n => n.id === 'predictive-check')) {
        next.push({
          id: 'predictive-check',
          type: check.alert.type || 'danger_hour',
          label: check.alert.title,
          detail: check.alert.message,
          danger: check.alert.severity === 'danger',
        });
      }

      setItems(next);
    } catch {
      // non-critical — silent fail
    }
  }

  const visible = items.filter(i => !dismissed.has(i.id));
  if (visible.length === 0) return null;

  return (
    <div className="mb-3 space-y-1.5">
      {visible.map(item => {
        const Icon = ICONS[item.type] ?? Zap;
        return (
          <div
            key={item.id}
            className={cn(
              'flex items-start gap-2.5 px-4 py-2.5 rounded-lg border-l-2 text-sm',
              item.danger
                ? 'bg-red-500/[0.06] border-l-tm-loss'
                : 'bg-amber-500/[0.06] border-l-tm-obs'
            )}
          >
            <Icon className={cn('h-3.5 w-3.5 mt-0.5 shrink-0', item.danger ? 'text-tm-loss' : 'text-tm-obs')} />
            <div className="flex-1 min-w-0">
              <span className={cn('font-semibold text-xs uppercase tracking-wide mr-1.5', item.danger ? 'text-tm-loss' : 'text-tm-obs')}>
                {item.label}
              </span>
              <span className="text-xs text-muted-foreground">{item.detail}</span>
            </div>
            <button
              onClick={() => dismiss(item.id)}
              className="text-muted-foreground/50 hover:text-muted-foreground transition-colors shrink-0 mt-0.5 -mr-1"
              aria-label="Dismiss"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
