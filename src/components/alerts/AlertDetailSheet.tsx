import { useNavigate } from 'react-router-dom';
import { Clock, X, MessageSquare } from 'lucide-react';
import { Sheet, SheetContent } from '@/components/ui/sheet';
import { cn } from '@/lib/utils';
import { AlertNotification } from '@/contexts/AlertContext';
import { PatternSeverity } from '@/types/patterns';

// ─── Severity config ──────────────────────────────────────────────────────────
const SEV_DOT: Record<PatternSeverity, string> = {
  critical: 'bg-tm-loss',
  high:     'bg-tm-loss/70',
  medium:   'bg-tm-obs',
  low:      'bg-slate-400',
};
const SEV_LABEL: Record<PatternSeverity, string> = {
  critical: 'Critical',
  high:     'High',
  medium:   'Caution',
  low:      'Info',
};
const SEV_LABEL_COLOR: Record<PatternSeverity, string> = {
  critical: 'text-tm-loss',
  high:     'text-tm-loss',
  medium:   'text-tm-obs',
  low:      'text-muted-foreground',
};
const SEV_LEFT_BORDER: Record<PatternSeverity, string> = {
  critical: 'border-l-tm-loss',
  high:     'border-l-tm-loss',
  medium:   'border-l-tm-obs',
  low:      'border-l-slate-300 dark:border-l-slate-600',
};

// ─── Pattern explanations (keyed by backend pattern_type) ────────────────────
const PATTERN_EXPLANATIONS: Record<string, string> = {
  revenge_trade:            'Entering immediately after a loss while the emotional response is still active. The next trade placed under stress tends to be larger, faster, and less disciplined than planned.',
  rapid_reentry:            'Re-entering the same instrument shortly after a losing exit. The setup has not changed — the same conditions that caused the first loss are still in play.',
  panic_exit:               'A fast manual exit at a loss with no stop-loss order on record. May be a rational decision or an impulsive reaction — worth reviewing against your pre-trade plan.',
  martingale_behaviour:     'Increasing position size after consecutive losses on the same instrument. Each escalation increases the total risk in the session, not just the cost of this trade.',
  post_loss_recovery_bet:   'Taking a significantly larger position on the same underlying after losing. If this trade also loses, the combined loss will exceed all prior losses combined.',
  consecutive_loss_streak:  'Multiple consecutive losses in the same session. After the third loss, the probability of the next trade being a loss is statistically higher due to emotional state, not randomness.',
  overtrading:              'Trade frequency has exceeded your normal session pace. More trades per hour rarely means more profit — it usually means smaller gaps between decisions.',
  profit_giveaway:          'You had reached a session high, then a subsequent trade gave back a large portion of those gains. Common pattern: taking one more trade after a good session.',
  no_stoploss:              'The position was exited manually without a stop-loss order triggering. Pre-defined exits reduce the emotional cost of holding through a drawdown.',
  opening_5min_trap:        'Entry in the first 8 minutes of market open. Bid-ask spreads are widest and option premiums are most distorted during this window as the market finds its opening level.',
  end_of_session_mis_panic: 'MIS position opened after 15:10 IST with forced auto-square-off within minutes. Very little time to manage the trade once entered.',
  fomo_entry:               'Entry spread across multiple unrelated instruments in a short window. Often a signal of chasing multiple moves simultaneously rather than a focused view.',
};

// ─── Formatters ───────────────────────────────────────────────────────────────
function fmtRs(val: unknown) {
  const n = Number(val);
  return isNaN(n) ? '—' : `₹${Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}
function fmtN(val: unknown, suffix = '') {
  const n = Number(val);
  return isNaN(n) ? '—' : `${n.toLocaleString('en-IN', { maximumFractionDigits: 1 })}${suffix}`;
}

// ─── Build data facts from details dict (keyed by backend pattern_type) ──────
function buildFacts(patternType: string, d: Record<string, unknown>): { label: string; value: string }[] {
  const facts: { label: string; value: string }[] = [];
  const add = (label: string, value: string) => facts.push({ label, value });

  switch (patternType) {
    case 'revenge_trade':
      if (d.prior_symbol)        add('Prior trade', String(d.prior_symbol));
      if (d.prior_loss)          add('Prior loss', fmtRs(d.prior_loss));
      if (d.gap_minutes != null) add('Gap to re-entry', `${fmtN(d.gap_minutes)} min`);
      break;
    case 'rapid_reentry':
      if (d.symbol)              add('Instrument', String(d.symbol));
      if (d.prior_pnl)           add('Prior exit P&L', fmtRs(d.prior_pnl));
      if (d.gap_minutes != null) add('Gap', `${fmtN(d.gap_minutes)} min`);
      break;
    case 'panic_exit':
      if (d.hold_minutes != null) add('Hold time', `${fmtN(d.hold_minutes)} min`);
      if (d.realized_pnl)        add('Loss', fmtRs(d.realized_pnl));
      break;
    case 'martingale_behaviour':
      if (d.underlying)          add('Underlying', String(d.underlying));
      if (d.size_sequence && Array.isArray(d.size_sequence))
                                 add('Size sequence', (d.size_sequence as number[]).join(' → '));
      if (d.max_ratio)           add('Largest step-up', `${fmtN(d.max_ratio)}×`);
      if (d.consecutive_losses != null) add('Consecutive losses', String(d.consecutive_losses));
      break;
    case 'post_loss_recovery_bet':
      if (d.underlying)          add('Underlying', String(d.underlying));
      if (d.prior_total_loss)    add('Prior losses', fmtRs(d.prior_total_loss));
      if (d.size_ratio)          add('Size vs recent avg', `${fmtN(d.size_ratio)}×`);
      if (d.current_qty != null)    add('This trade qty', String(d.current_qty));
      if (d.avg_recent_qty != null) add('Recent avg qty', fmtN(d.avg_recent_qty));
      break;
    case 'consecutive_loss_streak':
      if (d.streak != null)  add('Loss streak', `${d.streak} in a row`);
      if (d.total_loss)      add('Total session loss', fmtRs(d.total_loss));
      break;
    case 'overtrading':
      if (d.daily_count != null)      add('Trades today', String(d.daily_count));
      if (d.trades_in_window != null) add('Trades in window', String(d.trades_in_window));
      break;
    case 'profit_giveaway':
      if (d.peak_pnl != null)   add('Session peak P&L', fmtRs(d.peak_pnl));
      if (d.erosion != null)    add('Gave back', fmtRs(d.erosion));
      if (d.erosion_pct != null) add('% of peak given back', `${fmtN(d.erosion_pct)}%`);
      break;
    case 'no_stoploss':
      if (d.duration_minutes != null) add('Hold time', `${d.duration_minutes} min`);
      if (d.loss_pct != null)    add('Loss vs capital at risk', `${fmtN(d.loss_pct)}%`);
      if (d.capital_at_risk)     add('Capital at risk', fmtRs(d.capital_at_risk));
      break;
    default:
      for (const [k, v] of Object.entries(d)) {
        if (['exchange', 'trigger_symbol', 'underlying', 'insight', 'historical_insight',
             'caution_window', 'danger_window', 'window_min', 'exit_order_types'].includes(k)) continue;
        if (typeof v === 'number' || (typeof v === 'string' && v.length < 40)) {
          const label = k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
          const value = k.endsWith('_pnl') || k.endsWith('_loss') ? fmtRs(v)
            : k.endsWith('_pct') ? `${fmtN(v)}%`
            : k.endsWith('_minutes') ? `${v} min`
            : String(v);
          add(label, value);
          if (facts.length >= 4) break;
        }
      }
  }
  return facts;
}

function timeAgo(dateStr: string | undefined): string {
  if (!dateStr) return '—';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  const hrs = Math.floor(mins / 60);
  const days = Math.floor(hrs / 24);
  if (mins < 1)  return 'just now';
  if (mins < 60) return `${mins}m ago`;
  if (hrs < 24)  return `${hrs}h ago`;
  return `${days}d ago`;
}

function formatIST(dateStr: string | undefined): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

// ─── Component ────────────────────────────────────────────────────────────────
interface AlertDetailSheetProps {
  alert: AlertNotification | null;
  open: boolean;
  onClose: () => void;
  onAcknowledge: (id: string) => void;
}

export default function AlertDetailSheet({ alert, open, onClose, onAcknowledge }: AlertDetailSheetProps) {
  const navigate = useNavigate();
  if (!alert) return null;

  const sev = alert.pattern.severity;
  const backendType = alert.pattern.backend_type;
  const facts = buildFacts(backendType, alert.pattern.details ?? {});

  function handleAck() {
    onAcknowledge(alert!.id);
    onClose();
  }

  function handleAskAI() {
    const q = encodeURIComponent(
      `I got a "${alert!.pattern.name}" alert — ${alert!.pattern.description} Can you explain what this means for my trading?`
    );
    navigate(`/chat?q=${q}`);
  }

  return (
    <Sheet open={open} onOpenChange={v => !v && onClose()}>
      <SheetContent side="right" className="w-full sm:w-[420px] p-0 flex flex-col overflow-hidden">

        {/* Header */}
        <div className={cn(
          'flex items-start justify-between px-5 py-4 border-b border-border border-l-4',
          SEV_LEFT_BORDER[sev],
        )}>
          <div className="flex-1 min-w-0 pr-3">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <span className={cn('w-2 h-2 rounded-full flex-shrink-0', SEV_DOT[sev])} />
              <span className="text-[15px] font-semibold text-foreground">{alert.pattern.name}</span>
              <span className={cn('text-[10px] font-semibold uppercase tracking-wide', SEV_LABEL_COLOR[sev])}>
                {SEV_LABEL[sev]}
              </span>
            </div>
            <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
              <Clock className="h-3 w-3" />
              <span title={formatIST(alert.shown_at)}>{timeAgo(alert.shown_at)}</span>
              <span>·</span>
              <span>{formatIST(alert.shown_at)}</span>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-muted transition-colors flex-shrink-0">
            <X className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-4">

          {/* Evidence — real trade data from behavior_engine */}
          <p className="text-[14px] text-foreground leading-relaxed">
            {alert.pattern.description}
          </p>

          {(alert.pattern.estimated_cost ?? 0) > 0 && (
            <p className="text-[12px] text-tm-loss font-mono tabular-nums -mt-2">
              Est. cost: ₹{(alert.pattern.estimated_cost as number).toLocaleString('en-IN')}
            </p>
          )}

          {/* Data table */}
          {facts.length > 0 && (
            <div className="rounded-lg border border-border divide-y divide-border">
              {facts.map(({ label, value }) => (
                <div key={label} className="flex items-center justify-between px-3 py-2.5">
                  <span className="text-[12px] text-muted-foreground">{label}</span>
                  <span className="text-[12px] font-mono tabular-nums font-medium text-foreground">{value}</span>
                </div>
              ))}
            </div>
          )}

          {/* Pattern explanation */}
          {PATTERN_EXPLANATIONS[backendType] && (
            <p className="text-[12px] text-muted-foreground leading-relaxed border-t border-border pt-4">
              {PATTERN_EXPLANATIONS[backendType]}
            </p>
          )}

        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-border flex items-center gap-3">
          {!alert.acknowledged ? (
            <button
              onClick={handleAck}
              className="flex-1 py-2.5 rounded-lg bg-tm-brand text-white text-[13px] font-semibold hover:bg-tm-brand/90 transition-colors"
            >
              Mark as reviewed
            </button>
          ) : (
            <div className="flex-1 py-2.5 text-center text-[13px] text-muted-foreground">
              Reviewed ✓
            </div>
          )}
          <button
            onClick={handleAskAI}
            className="flex items-center gap-1.5 px-4 py-2.5 rounded-lg border border-border text-[13px] text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
          >
            <MessageSquare className="h-3.5 w-3.5" />
            Ask AI
          </button>
        </div>

      </SheetContent>
    </Sheet>
  );
}
