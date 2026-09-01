/**
 * PredictiveContextStrip
 *
 * Thin, dismissable context rows placed between the session hero and alerts.
 * Shows pattern-based risk context (revenge window, problem symbol).
 *
 * The "Danger hour" and "<day> — danger day" rows were removed 2026-09-01 with
 * the retirement of `time_of_day_bias`. They prescribed ("Trade smaller or wait
 * it out"), cited no sample, and compared IST-derived hours against
 * `new Date().getHours()` — browser-local. See
 * docs/patterns/25-27-performance-trio/.
 * Mental model: "here's the risk environment right now" — NOT "you just did something wrong".
 *
 * Dismissed entries survive until page reload (sessionStorage).
 */

import { useState, useEffect } from 'react';
import { Zap, TrendingDown, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { useWebSocket } from '@/contexts/WebSocketContext';

const SESSION_DISMISSED_KEY = 'tm_pred_dismissed';

interface PredictiveItem {
  id: string;
  type: 'revenge_window' | 'problem_symbol';
  label: string;
  detail: string;
  danger: boolean;
}

const ICONS = {
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
      try { sessionStorage.setItem(SESSION_DISMISSED_KEY, JSON.stringify([...next])); } catch { /* ignore */ }
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
      const ins  = insRes.data;   // {has_data, revenge_window_minutes: number|null}
      const chk  = chkRes.data;
      const next: PredictiveItem[] = [];

      if (!ins.has_data) {
        // No patterns learned yet — trigger background learn if stale, show nothing
        const lastUpdated = ins.last_updated ? new Date(ins.last_updated).getTime() : 0;
        const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
        if (lastUpdated < sevenDaysAgo) {
          api.post('/api/personalization/learn', {}).catch(() => {}); // fire-and-forget
        }
        setItems([]);
        return;
      }

      // revenge_window_minutes: number | null, combined with real-time check
      if (ins.revenge_window_minutes && chk.has_warning) {
        next.push({
          id: 'revenge-window',
          type: 'revenge_window',
          label: 'Revenge window',
          detail: `You typically trade impulsively within ${Math.round(ins.revenge_window_minutes)}min of a loss. Step back.`,
          danger: false,
        });
      }

      // Additional predictive alert from server-side check
      if (chk.alert && !next.find(n => n.id === 'predictive-check')) {
        next.push({
          id: 'predictive-check',
          type: chk.alert.type || 'problem_symbol',
          label: chk.alert.title,
          detail: chk.alert.message,
          danger: chk.alert.severity === 'danger',
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
            {/* Was a bare 14px icon — the smallest tap target in the app, well
                under the 24px WCAG floor. Padded to 44px with a matching negative
                margin so the row is unchanged visually. */}
            <button
              onClick={() => dismiss(item.id)}
              className="text-muted-foreground/50 hover:text-muted-foreground transition-colors shrink-0 h-11 w-11 -m-3.5 flex items-center justify-center"
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
