import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Clock, X, MessageSquare, BellOff, Bell, Hand, ArrowRight, ThumbsDown } from 'lucide-react';
import { Sheet, SheetContent } from '@/components/ui/sheet';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import { AlertNotification, useAlerts } from '@/contexts/AlertContext';
import { usePatternCatalogue, usePatternRecord } from '@/hooks/usePatternCatalogue';
import { PatternSeverity } from '@/types/patterns';
import { SEV_DOT, SEV_LABEL, SEV_LABEL_COLOR, SEV_LEFT_BORDER } from '@/lib/alertSeverity';

const OUTCOME_LABEL: Record<string, string> = {
  stopped:     'You stopped',
  took_anyway: 'Took it anyway',
  not_useful:  'Not useful',
};

const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

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
    case 'size_escalation':
      if (d.underlying)          add('Underlying', String(d.underlying));
      if (d.size_sequence && Array.isArray(d.size_sequence))
                                 add('Qty sequence', (d.size_sequence as number[]).join(' → '));
      if (d.escalation_pct != null) add('Total increase', `${fmtN(d.escalation_pct)}%`);
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
      if (d.total_loss)      add('Total loss', fmtRs(d.total_loss));
      break;
    // Engine v2 split overtrading into a 30-minute burst and a daily total.
    // This case was still keyed on the v1 name, so the most frequent alert we
    // raise showed no facts at all.
    case 'overtrading_burst':
    case 'daily_overtrading':
      if (d.daily_count != null)      add('Trades today', String(d.daily_count));
      if (d.trades_in_window != null) add('Trades in window', String(d.trades_in_window));
      // Counting is structure-aware, so a four-leg spread is one decision.
      // Show the legs too when they differ, or the numbers look wrong.
      if (d.legs_in_window != null && d.legs_in_window !== d.trades_in_window)
        add('Individual legs', String(d.legs_in_window));
      if (d.daily_legs != null && d.daily_legs !== d.daily_count)
        add('Legs today', String(d.daily_legs));
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
  const {
    alerts: allAlerts, mutedPatterns, maxMutes,
    submitAlertFeedback, mutePattern, unmutePattern,
  } = useAlerts();
  const [busy, setBusy] = useState(false);
  const [localOutcome, setLocalOutcome] = useState<string | null>(null);
  const { lookup: lookupPattern } = usePatternCatalogue();
  const { data: record } = usePatternRecord(open && alert ? alert.pattern.backend_type : null);
  if (!alert) return null;

  const sev = alert.pattern.severity;
  const backendType = alert.pattern.backend_type;
  const patternInfo = lookupPattern(backendType);
  const facts = buildFacts(backendType, alert.pattern.details ?? {});
  const confidence = alert.pattern.confidence;
  const outcome = localOutcome ?? alert.pattern.outcome ?? null;
  const isMuted = mutedPatterns.includes(backendType);

  async function handleFeedback(o: 'stopped' | 'took_anyway' | 'not_useful') {
    if (busy) return;
    setBusy(true);
    setLocalOutcome(o);
    const ok = await submitAlertFeedback(alert!.id, o);
    setBusy(false);
    if (ok) onClose();
    else { setLocalOutcome(null); toast.error('Could not save — try again'); }
  }

  async function handleToggleMute() {
    if (busy) return;
    setBusy(true);
    try {
      if (isMuted) {
        await unmutePattern(backendType);
        toast.success(`Unmuted ${alert!.pattern.name}`);
      } else {
        await mutePattern(backendType);
        toast.success(`Muted ${alert!.pattern.name} — no more live alerts (still in History)`);
      }
    } catch {
      toast.error(`Mute limit reached (${maxMutes}). Unmute another pattern first.`);
    } finally {
      setBusy(false);
    }
  }

  // Count same pattern type in last 7 days
  const weekCutoff = Date.now() - WEEK_MS;
  const weekCount = allAlerts.filter(a =>
    (a.pattern.type ?? a.pattern.backend_type) === backendType &&
    new Date(a.shown_at ?? 0).getTime() >= weekCutoff
  ).length;

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
          'flex items-start justify-between px-5 py-3.5 border-b border-border border-l-4',
          SEV_LEFT_BORDER[sev],
        )}>
          <div className="flex-1 min-w-0 pr-3">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <span className={cn('w-2 h-2 rounded-full flex-shrink-0', SEV_DOT[sev])} />
              <span className="text-[15px] font-semibold text-foreground">{alert.pattern.name}</span>
              <span className={cn('text-[10px] font-semibold uppercase tracking-wide', SEV_LABEL_COLOR[sev])}>
                {SEV_LABEL[sev]}
              </span>
              {weekCount >= 2 && (
                <span className="text-[10px] font-semibold text-tm-obs bg-amber-50 dark:bg-amber-900/20 border border-amber-300 dark:border-amber-700/50 rounded px-1.5 py-0.5">
                  {weekCount}× this week
                </span>
              )}
              {confidence != null && confidence > 0 && (
                <span
                  className="text-[10px] font-medium text-muted-foreground border border-border rounded px-1.5 py-0.5"
                  title="How certain the engine is this pattern occurred (independent of severity)"
                >
                  {Math.round(confidence)}% confidence
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
              <Clock className="h-3 w-3" />
              <span title={formatIST(alert.shown_at)}>{timeAgo(alert.shown_at)}</span>
              <span>·</span>
              <span>{formatIST(alert.shown_at)}</span>
            </div>
          </div>
          {/* 28px → 44px. This is the close button on a sheet a trader opens
              mid-session on a phone; missing it and mis-tapping something behind
              it is the worst moment for it to happen. */}
          <button
            onClick={onClose}
            className="h-11 w-11 -m-2 flex items-center justify-center rounded-lg hover:bg-muted transition-colors flex-shrink-0"
            aria-label="Close"
          >
            <X className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-4">

          {/* Evidence — real trade data from behavior_engine */}
          <p className="text-[14px] text-foreground leading-relaxed">
            {alert.pattern.description}
          </p>

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

          {/* Trades involved — shown for consecutive_loss and size_escalation */}
          {(() => {
            const d = alert.pattern.details ?? {};
            const rows: { symbol: string; qty: number; pnl: number }[] =
              Array.isArray(d.losing_trades) ? (d.losing_trades as { symbol: string; qty: number; pnl: number }[]) :
              Array.isArray(d.trade_list)    ? (d.trade_list    as { symbol: string; qty: number; pnl: number }[]) :
              [];
            if (rows.length === 0) return null;
            return (
              <div>
                <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                  Trades involved
                </p>
                <div className="rounded-lg border border-border divide-y divide-border">
                  {rows.map((r, i) => (
                    <div key={i} className="flex items-center justify-between px-3 py-2">
                      <span className="text-[12px] font-mono text-foreground">{r.symbol}</span>
                      <div className="flex items-center gap-4">
                        <span className="text-[11px] text-muted-foreground">{r.qty} qty</span>
                        <span className={cn(
                          'text-[12px] font-mono tabular-nums font-medium',
                          r.pnl < 0 ? 'text-tm-loss' : 'text-tm-profit'
                        )}>
                          {r.pnl < 0 ? '−' : '+'}₹{Math.abs(r.pnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}

          {/* Why this fired - confidence signal evidence (Engine v2, A.8).
              Rendered whenever the backend stacked signals for this alert. */}
          {(() => {
            const d = alert.pattern.details ?? {};
            const signals: { signal: string; value: unknown; importance: string }[] =
              Array.isArray(d.signals) ? (d.signals as { signal: string; value: unknown; importance: string }[]) : [];
            if (signals.length === 0) return null;
            return (
              <div>
                <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                  Why this fired
                </p>
                <ul className="space-y-1.5">
                  {signals.map((sig, i) => (
                    <li key={i} className="flex items-center gap-2 text-[12px]">
                      <span className={cn(
                        'h-1.5 w-1.5 rounded-full shrink-0',
                        sig.importance === 'critical' ? 'bg-tm-loss' :
                        sig.importance === 'high' ? 'bg-tm-loss/70' :
                        'bg-amber-500'
                      )} />
                      <span className="text-foreground">
                        {sig.signal.replace(/_/g, ' ')}
                        {typeof sig.value === 'number' && `: ${sig.value}`}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })()}

          {/* What this pattern watches, and why — from the detector registry.
              Two local Record maps used to live here, keyed on engine v1 names,
              so the most common alert we raise rendered neither of them. The
              second of those maps also carried precise unsourced statistics
              ("win rate on the 4th trade after 3 losses is typically below
              30%") presented as measurement. Both are gone: the copy has one
              home, next to the names it describes, and it states mechanism
              rather than numbers we cannot stand behind. */}
          {patternInfo && (
            <div className="border-t border-border pt-4 space-y-3">
              <div>
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                  What this watches
                </p>
                <p className="text-[12px] text-muted-foreground leading-relaxed">
                  {patternInfo.observes}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                  Why it matters
                </p>
                <p className="text-[12px] text-muted-foreground leading-relaxed">
                  {patternInfo.explanation}
                </p>
              </div>
            </div>
          )}

          {/* Your own record with this pattern.
              What sat here before was a paragraph of invented population
              statistics phrased as measurement. This is the trader's own
              realised history — true, checkable, and the one thing no
              competitor can show them. Below the sample gate it says so
              rather than presenting a number built from three trades. */}
          {record && (
            <div className="rounded-lg bg-muted/40 px-3 py-3">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                Your record with this pattern
              </p>
              {record.enough ? (
                <>
                  <p className="text-[12px] text-foreground leading-relaxed">
                    Flagged <span className="font-medium">{record.times_fired}</span> times in
                    the last {Math.round(record.window_days / 30)} months.
                    {' '}Of the {record.trades_measured} trades that have closed,
                    {' '}<span className="font-medium">{record.losses}</span> lost money
                    {record.win_rate != null && <> and you won {record.win_rate}% of them</>}.
                  </p>
                  <p className={cn(
                    'text-[12px] font-mono tabular-nums font-medium mt-1.5',
                    record.pnl < 0 ? 'text-tm-loss' : 'text-tm-profit',
                  )}>
                    {record.pnl < 0 ? '−' : '+'}₹
                    {Math.abs(record.pnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                    <span className="font-sans font-normal text-muted-foreground">
                      {' '}realised across those trades
                    </span>
                  </p>
                </>
              ) : (
                <p className="text-[12px] text-muted-foreground leading-relaxed">
                  {record.times_fired === 0
                    ? 'First time we have flagged this for you.'
                    : `Flagged ${record.times_fired} times so far. ` +
                      `We will show your record here once ${record.min_sample} of ` +
                      `those trades have closed — fewer than that is not a pattern yet.`}
                </p>
              )}
            </div>
          )}

          {/* Mute this pattern — suppresses live alerts only; still recorded in History */}
          <button
            onClick={handleToggleMute}
            disabled={busy}
            className="w-full flex items-center justify-center gap-2 py-2 rounded-lg border border-border text-[12px] text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors disabled:opacity-50"
          >
            {isMuted ? <Bell className="h-3.5 w-3.5" /> : <BellOff className="h-3.5 w-3.5" />}
            {isMuted ? `Unmute ${alert.pattern.name}` : `Mute ${alert.pattern.name} (live alerts only)`}
          </button>

        </div>

        {/* Footer — feedback loop: what did you actually do? */}
        <div className="px-5 py-4 border-t border-border space-y-2.5">
          {outcome ? (
            <div className="flex items-center justify-between">
              <span className="text-[12px] text-muted-foreground">
                You said: <span className="font-medium text-foreground">{OUTCOME_LABEL[outcome] ?? outcome}</span>
              </span>
              <button
                onClick={handleAskAI}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-border text-[12px] text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
              >
                <MessageSquare className="h-3.5 w-3.5" />
                Ask AI
              </button>
            </div>
          ) : (
            <>
              <p className="text-[11px] text-muted-foreground">What did you do?</p>
              <div className="grid grid-cols-3 gap-2">
                <button
                  onClick={() => handleFeedback('stopped')}
                  disabled={busy}
                  className="flex flex-col items-center gap-1 py-2 rounded-lg border border-border text-[11px] font-medium text-foreground hover:border-tm-brand hover:text-tm-brand transition-colors disabled:opacity-50"
                >
                  <Hand className="h-3.5 w-3.5" />
                  I stopped
                </button>
                <button
                  onClick={() => handleFeedback('took_anyway')}
                  disabled={busy}
                  className="flex flex-col items-center gap-1 py-2 rounded-lg border border-border text-[11px] font-medium text-foreground hover:border-tm-loss hover:text-tm-loss transition-colors disabled:opacity-50"
                >
                  <ArrowRight className="h-3.5 w-3.5" />
                  Took it anyway
                </button>
                <button
                  onClick={() => handleFeedback('not_useful')}
                  disabled={busy}
                  className="flex flex-col items-center gap-1 py-2 rounded-lg border border-border text-[11px] font-medium text-muted-foreground hover:border-foreground/40 hover:text-foreground transition-colors disabled:opacity-50"
                >
                  <ThumbsDown className="h-3.5 w-3.5" />
                  Not useful
                </button>
              </div>
              <div className="flex items-center justify-between pt-0.5">
                {!alert.acknowledged ? (
                  <button
                    onClick={handleAck}
                    className="text-[12px] text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Just mark reviewed
                  </button>
                ) : <span className="text-[12px] text-muted-foreground">Reviewed ✓</span>}
                <button
                  onClick={handleAskAI}
                  className="flex items-center gap-1.5 text-[12px] text-muted-foreground hover:text-foreground transition-colors"
                >
                  <MessageSquare className="h-3.5 w-3.5" />
                  Ask AI
                </button>
              </div>
            </>
          )}
        </div>

      </SheetContent>
    </Sheet>
  );
}
