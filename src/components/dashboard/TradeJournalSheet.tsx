// Trade Journal Sheet
// Philosophy: 4 taps = complete entry. Under 20 seconds.
// Fields kept: emotion, followed_plan, exit_reason, would_repeat, notes
// Fields removed: market_condition (analysis not psychology), setup_quality (redundant),
//   deviation_reason (captured by emotion), "maybe" on would_repeat (cop-out answer)

import { useState, useEffect, useMemo } from 'react';
import { TrendingUp, TrendingDown, X, Save, Trash2 } from 'lucide-react';
import { Sheet, SheetContent } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';
import { Position, Trade, CompletedTrade } from '@/types/api';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';
import { useAlerts } from '@/contexts/AlertContext';
import { SEV_DOT, SEV_LABEL_COLOR, SEV_LABEL } from '@/lib/alertSeverity';
import { journalTradeId } from '@/lib/journalKey';

const ALERT_WINDOW_MS = 20 * 60 * 1000; // ±20 min around trade exit

// ── Emotion options — mapped 1:1 to behavioral patterns we detect ─────────────
const EMOTIONS = [
  { value: 'calm',          label: 'Calm',          desc: 'Planned & rational' },
  { value: 'fomo',          label: 'FOMO',          desc: 'Fear of missing out' },
  { value: 'revenge',       label: 'Revenge',       desc: 'Reacting to a loss' },
  { value: 'anxious',       label: 'Anxious',       desc: 'Uncertain / nervous' },
  { value: 'overconfident', label: 'Overconfident', desc: 'Too sure of outcome' },
];

const PLAN_OPTIONS = [
  { value: 'yes',       label: 'Yes',       sub: 'Followed my plan' },
  { value: 'partially', label: 'Partially', sub: 'Some deviations' },
  { value: 'no',        label: 'No',        sub: 'Deviated fully' },
];

const EXIT_REASONS = [
  { value: 'sl_hit',     label: 'SL Hit' },
  { value: 'target_hit', label: 'Target Hit' },
  { value: 'manual',     label: 'Manual Exit' },
  { value: 'panic',      label: 'Panic Exit' },
];

// ── Types ─────────────────────────────────────────────────────────────────────
export interface JournalEntry {
  id?: string;
  trade_id: string;
  emotion_tags?: string[];
  followed_plan?: string;
  deviation_reason?: string;
  exit_reason?: string;
  setup_quality?: number;
  would_repeat?: string;
  market_condition?: string;
  notes?: string;
  trade_pnl?: string;
  trade_symbol?: string;
  created_at: string;
  updated_at: string;
}

export interface TradeJournalSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  trade: (Position & { instrument_type?: string; unrealized_pnl?: number }) | Trade | CompletedTrade | null;
  type: 'position' | 'closed';
  /** Fired only after a successful save — the parent marks the trade journaled. */
  onSaved?: (tradeId: string) => void;
  /** Fired only after a successful delete — the parent clears the journaled flag. */
  onDeleted?: (tradeId: string) => void;
}

// ── Type guards ───────────────────────────────────────────────────────────────
function isPosition(t: unknown): t is Position {
  return typeof t === 'object' && t !== null && 'total_quantity' in t && 'average_entry_price' in t && !('direction' in t);
}
function isCompletedTrade(t: unknown): t is CompletedTrade {
  return typeof t === 'object' && t !== null && 'direction' in t && 'realized_pnl' in t;
}

// ── Chip ──────────────────────────────────────────────────────────────────────
function Chip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'px-3 py-1.5 rounded-lg text-[13px] font-medium transition-all border',
        active
          ? 'bg-tm-brand text-white border-tm-brand'
          : 'bg-muted/50 text-muted-foreground border-transparent hover:border-border',
      )}
    >
      {label}
    </button>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export function TradeJournalSheet({ open, onOpenChange, trade, type, onSaved, onDeleted }: TradeJournalSheetProps) {
  const { account } = useBroker();
  const { alerts } = useAlerts();

  const [emotions,     setEmotions]     = useState<string[]>([]);
  const [followedPlan, setFollowedPlan] = useState('');
  const [exitReason,   setExitReason]   = useState('');
  const [wouldRepeat,  setWouldRepeat]  = useState('');
  const [notes,        setNotes]        = useState('');

  const [hasChanges,     setHasChanges]     = useState(false);
  const [existingEntry,  setExistingEntry]  = useState<JournalEntry | null>(null);
  const [isLoading,      setIsLoading]      = useState(false);
  const [isSaving,       setIsSaving]       = useState(false);
  const [symbolHistory,  setSymbolHistory]  = useState<JournalEntry[]>([]);

  useEffect(() => {
    if (trade && open) loadEntry();
  }, [trade?.id, open]); // eslint-disable-line react-hooks/exhaustive-deps

  const reset = () => {
    setEmotions([]); setFollowedPlan(''); setExitReason('');
    setWouldRepeat(''); setNotes(''); setExistingEntry(null); setHasChanges(false);
    setSymbolHistory([]);
  };

  const apply = (e: JournalEntry) => {
    setEmotions(e.emotion_tags ?? []);
    setFollowedPlan(e.followed_plan ?? '');
    setExitReason(e.exit_reason ?? '');
    setWouldRepeat(e.would_repeat ?? '');
    setNotes(e.notes ?? '');
    setExistingEntry(e);
    setHasChanges(false);
  };

  const loadEntry = async () => {
    if (!trade || !account?.id) return;
    setIsLoading(true);
    const effId = journalTradeId(String(trade.id), type);
    try {
      const [entryRes, histRes] = await Promise.allSettled([
        api.get(`/api/journal/trade/${effId}`),
        api.get('/api/journal/', { params: { symbol: trade.tradingsymbol, limit: 4 } }),
      ]);
      if (entryRes.status === 'fulfilled' && entryRes.value.data.entry) apply(entryRes.value.data.entry);
      else reset();
      if (histRes.status === 'fulfilled') {
        const entries: JournalEntry[] = histRes.value.data.entries ?? histRes.value.data ?? [];
        setSymbolHistory(entries.filter(e => e.trade_id !== effId).slice(0, 3));
      }
    } catch {
      reset();
    } finally {
      setIsLoading(false);
    }
  };

  const pick = (current: string, val: string, setter: (v: string) => void) => {
    setter(val === current ? '' : val);
    setHasChanges(true);
  };

  const toggleEmotion = (val: string) => {
    setEmotions(prev => prev.includes(val) ? prev.filter(x => x !== val) : [...prev, val]);
    setHasChanges(true);
  };

  const handleSave = async () => {
    if (!trade || !account?.id) return;
    setIsSaving(true);
    const isPos = isPosition(trade);
    const isCT  = isCompletedTrade(trade);
    const pnl   = isPos ? ((trade as Position & { unrealized_pnl?: number }).unrealized_pnl ?? 0)
                : isCT  ? (trade as CompletedTrade).realized_pnl
                        : (trade as Trade).pnl;
    const effId = journalTradeId(String(trade.id), type);
    try {
      const res = await api.post('/api/journal/', {
        trade_id:       effId,
        // For open positions effId is a synthetic per-episode id; source_id carries
        // the real position id so the backend can verify ownership.
        source_id:      isPos ? String(trade.id) : undefined,
        emotion_tags:   emotions,
        followed_plan:  followedPlan || undefined,
        exit_reason:    exitReason   || undefined,
        would_repeat:   wouldRepeat  || undefined,
        notes:          notes        || undefined,
        trade_symbol:   trade.tradingsymbol,
        trade_type:     isPos ? 'POSITION' : isCT ? (trade as CompletedTrade).direction : (trade as Trade).trade_type,
        trade_pnl:      String(pnl ?? 0),
      });
      setExistingEntry(res.data.entry);
      setHasChanges(false);
      toast.success('Saved');
      // Mark journaled only now that the save actually succeeded.
      onSaved?.(effId);
      // Auto-close after save when triggered by auto-prompt
      onOpenChange(false);
    } catch {
      toast.error('Failed to save — please retry');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!trade || !account?.id) return;
    setIsSaving(true);
    const effId = journalTradeId(String(trade.id), type);
    try {
      await api.delete(`/api/journal/trade/${effId}`);
      reset();
      onDeleted?.(effId);
      toast.success('Entry deleted');
    } catch {
      toast.error('Failed to delete');
    } finally {
      setIsSaving(false);
    }
  };

  // Alerts that fired around the same time as this trade's exit.
  // Must be declared before the early return to satisfy rules-of-hooks.
  const linkedAlerts = useMemo(() => {
    if (!trade) return [];
    const exitTimeRaw = isCompletedTrade(trade) ? (trade as CompletedTrade).exit_time : null;
    const pivot = exitTimeRaw ? new Date(exitTimeRaw).getTime() : Date.now();
    return alerts.filter(a => {
      const alertTime = new Date(a.shown_at ?? 0).getTime();
      return Math.abs(alertTime - pivot) <= ALERT_WINDOW_MS;
    });
  }, [trade, alerts]);

  if (!trade) return null;

  const isPos    = isPosition(trade);
  const isCT     = isCompletedTrade(trade);
  const isOpen   = type === 'position';
  const pnl      = isPos ? ((trade as Position & { unrealized_pnl?: number }).unrealized_pnl ?? 0)
                 : isCT  ? (trade as CompletedTrade).realized_pnl
                         : (trade as Trade).pnl;
  const isProfit = (pnl ?? 0) >= 0;
  const symbol   = trade.tradingsymbol;
  const duration = isCT ? (trade as CompletedTrade).duration_minutes : undefined;
  const hasData  = emotions.length > 0 || followedPlan || exitReason || wouldRepeat || notes;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        className="w-full sm:max-w-md flex flex-col p-0 gap-0"
        aria-describedby="journal-desc"
      >
        {/* ── Header ── */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
          <div>
            <p className="text-[15px] font-semibold text-foreground">Trade Journal</p>
            <p id="journal-desc" className="text-[12px] text-muted-foreground mt-0.5">
              Quick capture — 4 taps, under 20 seconds
            </p>
          </div>
          <button
            onClick={() => onOpenChange(false)}
            className="p-1.5 rounded-lg hover:bg-muted/50 text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {isLoading ? (
          <div className="p-5 space-y-4">
            <Skeleton className="h-16 w-full rounded-lg" />
            <Skeleton className="h-24 w-full rounded-lg" />
            <Skeleton className="h-24 w-full rounded-lg" />
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto">

            {/* ── Trade summary ── */}
            <div className="mx-5 mt-5 rounded-xl bg-muted/40 border border-border p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-mono text-[15px] font-bold text-foreground">{symbol}</p>
                  <div className="flex items-center gap-2 mt-1 text-[12px] text-muted-foreground">
                    {isCT && <span className="font-medium text-foreground">{(trade as CompletedTrade).direction}</span>}
                    {isOpen && <span className="text-tm-brand font-medium">Open position</span>}
                    {duration && <span>· {duration}m hold</span>}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className={cn('p-1.5 rounded-lg', isProfit ? 'bg-teal-50 dark:bg-teal-900/20' : 'bg-red-50 dark:bg-red-900/20')}>
                    {isProfit
                      ? <TrendingUp className="h-4 w-4 text-tm-profit" />
                      : <TrendingDown className="h-4 w-4 text-tm-loss" />}
                  </div>
                  <p className={cn('font-mono text-[18px] font-bold tabular-nums', isProfit ? 'text-tm-profit' : 'text-tm-loss')}>
                    {formatCurrencyWithSign(pnl ?? 0)}
                  </p>
                </div>
              </div>
            </div>

            {/* ── Alerts during this trade ── */}
            {linkedAlerts.length > 0 && (
              <div className="mx-5 mt-3 rounded-xl border border-amber-200 dark:border-amber-700/40 bg-amber-50/60 dark:bg-amber-900/10 px-4 py-3 space-y-1.5">
                <p className="text-[11px] font-semibold text-tm-obs uppercase tracking-wide">
                  Pattern{linkedAlerts.length > 1 ? 's' : ''} detected during this trade
                </p>
                {linkedAlerts.map(a => (
                  <div key={a.id} className="flex items-center gap-2">
                    <span className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', SEV_DOT[a.pattern.severity])} />
                    <span className="text-[12px] font-medium text-foreground">{a.pattern.name}</span>
                    <span className={cn('text-[10px] font-semibold uppercase tracking-wide', SEV_LABEL_COLOR[a.pattern.severity])}>
                      {SEV_LABEL[a.pattern.severity]}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* ── Symbol history context ── */}
            {symbolHistory.length > 0 && (
              <div className="mx-5 mt-3 rounded-xl border border-border bg-muted/30 px-4 py-3">
                <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                  Last {symbolHistory.length}× you journaled {symbol}
                </p>
                <div className="space-y-1.5">
                  {symbolHistory.map((h, i) => {
                    const pnlNum = parseFloat(h.trade_pnl ?? '0');
                    const isWin = pnlNum >= 0;
                    const emotionStr = h.emotion_tags?.length
                      ? h.emotion_tags.map(t => t.charAt(0).toUpperCase() + t.slice(1)).join(', ')
                      : '—';
                    const planStr = h.followed_plan
                      ? h.followed_plan === 'yes' ? 'followed plan' : h.followed_plan === 'no' ? 'broke plan' : 'partial plan'
                      : null;
                    return (
                      <div key={h.id ?? i} className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className={cn(
                            'w-1.5 h-1.5 rounded-full flex-shrink-0',
                            isWin ? 'bg-tm-profit' : 'bg-tm-loss',
                          )} />
                          <span className="text-[12px] text-foreground truncate">{emotionStr}</span>
                          {planStr && <span className="text-[11px] text-muted-foreground flex-shrink-0">· {planStr}</span>}
                        </div>
                        <span className={cn(
                          'text-[12px] font-mono tabular-nums font-medium flex-shrink-0',
                          isWin ? 'text-tm-profit' : 'text-tm-loss',
                        )}>
                          {isWin ? '+' : '−'}₹{Math.abs(pnlNum).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="px-5 pb-5 mt-5 space-y-6">

              {/* ── Q1: How were you feeling? (multi-select) ── */}
              <div className="space-y-2.5">
                <div className="flex items-center justify-between">
                  <p className="text-[13px] font-semibold text-foreground">How were you feeling?</p>
                  {emotions.length > 0 && (
                    <span className="text-[11px] text-muted-foreground">{emotions.length} selected</span>
                  )}
                </div>
                <div className="space-y-1.5">
                  {EMOTIONS.map(e => {
                    const active = emotions.includes(e.value);
                    return (
                      <button
                        key={e.value}
                        type="button"
                        onClick={() => toggleEmotion(e.value)}
                        className={cn(
                          'w-full flex items-center justify-between px-4 py-2.5 rounded-xl border text-left transition-all',
                          active
                            ? 'bg-teal-50 dark:bg-teal-900/20 border-tm-brand'
                            : 'bg-muted/30 border-transparent hover:border-border',
                        )}
                      >
                        <span className={cn('text-[13px] font-medium', active ? 'text-tm-brand' : 'text-foreground')}>
                          {e.label}
                        </span>
                        <span className="text-[11px] text-muted-foreground">{e.desc}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* ── Q2: Did you follow your plan? ── */}
              <div className="space-y-2.5">
                <p className="text-[13px] font-semibold text-foreground">Did you follow your plan?</p>
                <div className="flex gap-2">
                  {PLAN_OPTIONS.map(o => (
                    <button
                      key={o.value}
                      type="button"
                      onClick={() => pick(followedPlan, o.value, setFollowedPlan)}
                      className={cn(
                        'flex-1 flex flex-col items-center gap-0.5 py-2.5 rounded-xl border text-center transition-all',
                        followedPlan === o.value
                          ? 'bg-teal-50 dark:bg-teal-900/20 border-tm-brand'
                          : 'bg-muted/30 border-transparent hover:border-border',
                      )}
                    >
                      <span className={cn('text-[13px] font-semibold', followedPlan === o.value ? 'text-tm-brand' : 'text-foreground')}>
                        {o.label}
                      </span>
                      <span className="text-[10px] text-muted-foreground">{o.sub}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* ── Q3: Why did you exit? (closed trades only) ── */}
              {!isOpen && (
                <div className="space-y-2.5">
                  <p className="text-[13px] font-semibold text-foreground">Why did you exit?</p>
                  <div className="grid grid-cols-2 gap-2">
                    {EXIT_REASONS.map(o => (
                      <Chip
                        key={o.value}
                        label={o.label}
                        active={exitReason === o.value}
                        onClick={() => pick(exitReason, o.value, setExitReason)}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* ── Q4: Take this trade again? ── */}
              <div className="space-y-2.5">
                <p className="text-[13px] font-semibold text-foreground">Take this trade again?</p>
                <div className="flex gap-2">
                  {(['yes', 'no'] as const).map(v => (
                    <button
                      key={v}
                      type="button"
                      onClick={() => pick(wouldRepeat, v, setWouldRepeat)}
                      className={cn(
                        'flex-1 py-2.5 rounded-xl border text-[13px] font-semibold transition-all',
                        wouldRepeat === v
                          ? v === 'yes'
                            ? 'bg-teal-50 dark:bg-teal-900/20 border-tm-brand text-tm-brand'
                            : 'bg-red-50 dark:bg-red-900/20 border-tm-loss text-tm-loss'
                          : 'bg-muted/30 border-transparent hover:border-border text-foreground',
                      )}
                    >
                      {v === 'yes' ? 'Yes' : 'No'}
                    </button>
                  ))}
                </div>
              </div>

              {/* ── Notes (optional) ── */}
              <div className="space-y-2">
                <p className="text-[13px] font-medium text-muted-foreground">
                  Anything to note? <span className="text-[11px]">(optional)</span>
                </p>
                <Textarea
                  placeholder="What stood out about this trade?"
                  value={notes}
                  onChange={e => { setNotes(e.target.value); setHasChanges(true); }}
                  className="min-h-[72px] resize-none text-[13px]"
                />
              </div>

            </div>
          </div>
        )}

        {/* ── Footer actions — always visible ── */}
        {!isLoading && (
          <div className="px-5 py-4 border-t border-border flex items-center gap-2 bg-card">
            <Button
              onClick={handleSave}
              disabled={isSaving || (!hasChanges && !!existingEntry)}
              className="flex-1 bg-tm-brand hover:bg-tm-brand/90 text-white gap-2"
            >
              <Save className="h-4 w-4" />
              {isSaving ? 'Saving…' : existingEntry ? 'Update' : 'Save'}
            </Button>
            {existingEntry && (
              <Button
                variant="outline"
                size="icon"
                onClick={handleDelete}
                disabled={isSaving}
                className="text-tm-loss hover:text-tm-loss border-border"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
