import { useState, useEffect } from 'react';
import { CheckCircle2, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { formatCurrency } from '@/lib/formatters';
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

function getISTHour(): number {
  const now = new Date();
  const istOffset = 5 * 60 + 30;
  const utcMs = now.getTime() + now.getTimezoneOffset() * 60000;
  return new Date(utcMs + istOffset * 60000).getHours();
}

function isWeekday(): boolean {
  const now = new Date();
  const istOffset = 5 * 60 + 30;
  const utcMs = now.getTime() + now.getTimezoneOffset() * 60000;
  const day = new Date(utcMs + istOffset * 60000).getDay();
  return day >= 1 && day <= 5;
}

function minsUntilOpen(): number {
  const now = new Date();
  const istOffset = 5 * 60 + 30;
  const utcMs = now.getTime() + now.getTimezoneOffset() * 60000;
  const ist = new Date(utcMs + istOffset * 60000);
  const openMin = 9 * 60 + 15;
  const nowMin = ist.getHours() * 60 + ist.getMinutes();
  return Math.max(0, openMin - nowMin);
}

export function MorningIntentCard({ onAcknowledged }: Props) {
  const { account } = useBroker();
  const [data, setData]               = useState<IntentData | null>(null);
  const [loading, setLoading]         = useState(true);
  const [submitting, setSubmitting]   = useState(false);
  const [showOverride, setShowOverride] = useState(false);
  const [overrideTrades, setOverrideTrades] = useState('');
  const [overrideLoss, setOverrideLoss]     = useState('');
  const [done, setDone]               = useState(false);

  useEffect(() => {
    if (!account?.id) return;
    api.get('/api/session-intent/today')
      .then(r => setData(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [account?.id]);

  // Only show on trading days, between 7:30 AM and 9:30 AM IST
  const hour = getISTHour();
  const show = isWeekday() && hour >= 7 && hour < 10;

  if (!show || loading || !data) return null;
  if (data.intent_acknowledged || done) return null;
  if (!data.planned.max_trades && !data.planned.max_loss) return null;

  const mins = minsUntilOpen();
  const timeLabel = mins > 60
    ? `${Math.ceil(mins / 60)}h ${mins % 60}m`
    : mins > 0
      ? `${mins} min`
      : 'Open now';

  async function handleCommit() {
    setSubmitting(true);
    try {
      await api.post('/api/session-intent/acknowledge', {
        max_trades: overrideTrades ? parseInt(overrideTrades, 10) : null,
        max_loss:   overrideLoss   ? parseFloat(overrideLoss)     : null,
      });
      setDone(true);
      onAcknowledged?.();
    } catch {
      // silent — user can try again
    } finally {
      setSubmitting(false);
    }
  }

  const effectiveTrades = overrideTrades ? parseInt(overrideTrades, 10) : data.planned.max_trades;
  const effectiveLoss   = overrideLoss   ? parseFloat(overrideLoss)     : data.planned.max_loss;

  return (
    <div className="tm-card overflow-hidden border-tm-brand/30 bg-tm-brand/[0.04]">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-tm-brand/20 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-foreground">Market opens in {timeLabel}</p>
          <p className="text-xs text-muted-foreground mt-0.5">Commit to your trading rules for today</p>
        </div>
        <div className="shrink-0 w-9 h-9 rounded-full bg-tm-brand/10 flex items-center justify-center">
          <span className="text-lg">🎯</span>
        </div>
      </div>

      {/* Today's rules */}
      <div className="px-5 pt-4 pb-3 grid grid-cols-2 gap-3">
        {effectiveTrades != null && (
          <div className="bg-background rounded-xl p-3 text-center border border-border">
            <p className="text-2xl font-bold font-mono text-foreground">{effectiveTrades}</p>
            <p className="text-xs text-muted-foreground mt-0.5">max trades</p>
          </div>
        )}
        {effectiveLoss != null && (
          <div className="bg-background rounded-xl p-3 text-center border border-border">
            <p className="text-2xl font-bold font-mono text-tm-loss">₹{formatCurrency(effectiveLoss)}</p>
            <p className="text-xs text-muted-foreground mt-0.5">loss limit</p>
          </div>
        )}
      </div>

      {/* Override toggle */}
      <div className="px-5 pb-2">
        <button
          onClick={() => setShowOverride(v => !v)}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors py-1"
        >
          {showOverride ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          Change today's limits
        </button>

        {showOverride && (
          <div className="mt-2 grid grid-cols-2 gap-2">
            <div>
              <label className="text-[11px] text-muted-foreground mb-1 block">Max trades</label>
              <input
                type="number"
                min={1}
                placeholder={String(data.planned.max_trades ?? '')}
                value={overrideTrades}
                onChange={e => setOverrideTrades(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-tm-brand/40"
              />
            </div>
            <div>
              <label className="text-[11px] text-muted-foreground mb-1 block">Loss limit (₹)</label>
              <input
                type="number"
                min={0}
                placeholder={String(data.planned.max_loss ?? '')}
                value={overrideLoss}
                onChange={e => setOverrideLoss(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-tm-brand/40"
              />
            </div>
          </div>
        )}
      </div>

      {/* CTA */}
      <div className="px-5 pb-5">
        <button
          onClick={handleCommit}
          disabled={submitting}
          className={cn(
            'w-full h-12 rounded-xl font-semibold text-sm text-white transition-all',
            'bg-tm-brand hover:bg-tm-brand/90 active:scale-[0.98]',
            'flex items-center justify-center gap-2',
            submitting && 'opacity-70 cursor-not-allowed'
          )}
        >
          {submitting
            ? <><Loader2 className="h-4 w-4 animate-spin" /> Committing…</>
            : <><CheckCircle2 className="h-4 w-4" /> I'll stick to my plan today</>
          }
        </button>
      </div>
    </div>
  );
}
