import { useState, useEffect, useCallback } from 'react';
import { ChevronDown, ChevronUp, CheckCircle2, Loader2, Settings, Pencil } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { formatCurrency } from '@/lib/formatters';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';

interface IntentData {
  has_session: boolean;
  intent_acknowledged: boolean;
  planned: { max_trades: number | null; max_loss: number | null };
  actual: { trades: number; pnl: number };
}

interface Props {
  onAcknowledged?: () => void;
}

function getISTInfo(): { hour: number; isWeekday: boolean; minsUntilOpen: number } {
  const now = new Date();
  const ist = new Date(now.getTime() + now.getTimezoneOffset() * 60000 + (5 * 60 + 30) * 60000);
  const hour = ist.getHours();
  const day = ist.getDay();
  const openMin = 9 * 60 + 15;
  const nowMin = hour * 60 + ist.getMinutes();
  return {
    hour,
    isWeekday: day >= 1 && day <= 5,
    minsUntilOpen: Math.max(0, openMin - nowMin),
  };
}

export function MorningIntentCard({ onAcknowledged }: Props) {
  const { account } = useBroker();
  const [data, setData] = useState<IntentData | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showOverride, setShowOverride] = useState(false);
  const [overrideTrades, setOverrideTrades] = useState('');
  const [overrideLoss, setOverrideLoss] = useState('');
  const [done, setDone] = useState(false);
  const [istInfo, setIstInfo] = useState(getISTInfo);

  useEffect(() => {
    const id = setInterval(() => setIstInfo(getISTInfo()), 60_000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!account?.id) return;
    api.get('/api/session-intent/today')
      .then(r => setData(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [account?.id]);

  const { hour, isWeekday, minsUntilOpen: mins } = istInfo;
  const show = isWeekday && hour >= 7 && hour < 10;

  if (!show || loading) return null;
  if (data?.intent_acknowledged || done) return null;

  // No limits configured — show a subtle nudge to settings
  if (data && !data.planned.max_trades && !data.planned.max_loss) {
    return (
      <div className="rounded-xl border border-amber-200/60 dark:border-amber-800/30 bg-amber-50/60 dark:bg-amber-900/10 px-4 py-3 flex items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2.5">
          <Pencil className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
          <div>
            <p className="text-[12.5px] font-semibold text-amber-900 dark:text-amber-200">Set your daily trading rules</p>
            <p className="text-[11.5px] text-amber-700/70 dark:text-amber-400/70 mt-0.5">
              Define a trade limit or loss limit to use morning intent.
            </p>
          </div>
        </div>
        <Link
          to="/settings"
          className="shrink-0 flex items-center gap-1 text-[11.5px] font-medium text-amber-700 dark:text-amber-400 hover:underline"
        >
          <Settings className="h-3.5 w-3.5" />
          Settings
        </Link>
      </div>
    );
  }

  if (!data) return null;

  const timeLabel = mins > 60
    ? `${Math.ceil(mins / 60)}h ${mins % 60}m`
    : mins > 0 ? `${mins} min` : 'Open now';

  const effectiveTrades = overrideTrades ? parseInt(overrideTrades, 10) : data.planned.max_trades;
  const effectiveLoss = overrideLoss ? parseFloat(overrideLoss) : data.planned.max_loss;

  async function handleCommit() {
    setSubmitting(true);
    try {
      await api.post('/api/session-intent/acknowledge', {
        max_trades: overrideTrades ? parseInt(overrideTrades, 10) : null,
        max_loss: overrideLoss ? parseFloat(overrideLoss) : null,
      });
      setDone(true);
      onAcknowledged?.();
    } catch {
      // silent
    } finally {
      setSubmitting(false);
    }
  }

  // Build a human-readable intent summary
  const parts: string[] = [];
  if (effectiveTrades != null) parts.push(`Max ${effectiveTrades} trades`);
  if (effectiveLoss != null) parts.push(`${formatCurrency(effectiveLoss)} loss limit`);
  const intentSummary = parts.join(' · ') || 'Your rules for today';

  return (
    <div className={cn(
      'rounded-xl border mb-4 overflow-hidden',
      'bg-amber-50 dark:bg-amber-900/[0.12]',
      'border-amber-200/70 dark:border-amber-700/30',
    )}>
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="px-4 pt-3.5 pb-0 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Pencil className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
          <span className="text-[10px] font-bold text-amber-700 dark:text-amber-400 uppercase tracking-[0.1em]">
            Morning Intent
          </span>
        </div>
        <span className="text-[11px] text-amber-600/70 dark:text-amber-400/60">
          {timeLabel} to open
        </span>
      </div>

      {/* ── Plan summary ───────────────────────────────────────────────────── */}
      <div className="px-4 pt-2.5 pb-3">
        <p className="text-[15px] font-medium italic text-amber-900 dark:text-amber-100 leading-snug">
          "{intentSummary}"
        </p>
        <p className="text-[11px] text-amber-700/60 dark:text-amber-400/50 mt-1">
          Your plan for today. Tap below to commit.
        </p>
      </div>

      {/* ── Override toggle ────────────────────────────────────────────────── */}
      <div className="px-4 pb-1">
        <button
          onClick={() => setShowOverride(v => !v)}
          className="flex items-center gap-1.5 text-[11.5px] text-amber-700/70 dark:text-amber-400/60 hover:text-amber-900 dark:hover:text-amber-300 transition-colors py-0.5"
        >
          {showOverride ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          Change today's limits
        </button>

        {showOverride && (
          <div className="mt-2 grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10.5px] text-amber-700/70 dark:text-amber-400/60 mb-1 block">Max trades</label>
              <input
                type="number"
                min={1}
                placeholder={String(data.planned.max_trades ?? '')}
                value={overrideTrades}
                onChange={e => setOverrideTrades(e.target.value)}
                className={cn(
                  'w-full rounded-lg px-3 py-2 text-sm outline-none',
                  'bg-amber-100/60 dark:bg-amber-900/30',
                  'border border-amber-300/60 dark:border-amber-700/40',
                  'text-amber-900 dark:text-amber-100',
                  'placeholder:text-amber-500/50',
                  'focus:border-amber-400 dark:focus:border-amber-600',
                )}
              />
            </div>
            <div>
              <label className="text-[10.5px] text-amber-700/70 dark:text-amber-400/60 mb-1 block">Loss limit (₹)</label>
              <input
                type="number"
                min={0}
                placeholder={String(data.planned.max_loss ?? '')}
                value={overrideLoss}
                onChange={e => setOverrideLoss(e.target.value)}
                className={cn(
                  'w-full rounded-lg px-3 py-2 text-sm outline-none',
                  'bg-amber-100/60 dark:bg-amber-900/30',
                  'border border-amber-300/60 dark:border-amber-700/40',
                  'text-amber-900 dark:text-amber-100',
                  'placeholder:text-amber-500/50',
                  'focus:border-amber-400 dark:focus:border-amber-600',
                )}
              />
            </div>
          </div>
        )}
      </div>

      {/* ── Commit button ──────────────────────────────────────────────────── */}
      <div className="px-4 pb-4 pt-2">
        <button
          onClick={handleCommit}
          disabled={submitting}
          className={cn(
            'w-full h-10 rounded-xl font-semibold text-[13px] transition-all',
            'bg-amber-500 hover:bg-amber-600 text-white',
            'active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed',
            'flex items-center justify-center gap-2',
          )}
        >
          {submitting
            ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Saving…</>
            : <><CheckCircle2 className="h-3.5 w-3.5" /> I'll stick to this today</>
          }
        </button>
      </div>
    </div>
  );
}
