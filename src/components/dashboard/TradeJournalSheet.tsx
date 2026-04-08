// Trade Journal Sheet
// Philosophy: 4 taps = complete entry. Under 20 seconds.
// Fields kept: emotion, followed_plan, exit_reason, would_repeat, notes
// Fields removed: market_condition (analysis not psychology), setup_quality (redundant),
//   deviation_reason (captured by emotion), "maybe" on would_repeat (cop-out answer)

import { useState, useEffect } from 'react';
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
  created_at: string;
  updated_at: string;
}

export interface TradeJournalSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  trade: (Position & { instrument_type?: string; unrealized_pnl?: number }) | Trade | CompletedTrade | null;
  type: 'position' | 'closed';
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
export function TradeJournalSheet({ open, onOpenChange, trade, type }: TradeJournalSheetProps) {
  const { account } = useBroker();

  const [emotion,      setEmotion]      = useState('');
  const [followedPlan, setFollowedPlan] = useState('');
  const [exitReason,   setExitReason]   = useState('');
  const [wouldRepeat,  setWouldRepeat]  = useState('');
  const [notes,        setNotes]        = useState('');

  const [hasChanges,    setHasChanges]    = useState(false);
  const [existingEntry, setExistingEntry] = useState<JournalEntry | null>(null);
  const [isLoading,     setIsLoading]     = useState(false);
  const [isSaving,      setIsSaving]      = useState(false);

  useEffect(() => {
    if (trade && open) loadEntry();
  }, [trade?.id, open]); // eslint-disable-line react-hooks/exhaustive-deps

  const reset = () => {
    setEmotion(''); setFollowedPlan(''); setExitReason('');
    setWouldRepeat(''); setNotes(''); setExistingEntry(null); setHasChanges(false);
  };

  const apply = (e: JournalEntry) => {
    setEmotion((e.emotion_tags ?? [])[0] ?? '');
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
    try {
      const res = await api.get(`/api/journal/trade/${trade.id}`);
      if (res.data.entry) apply(res.data.entry);
      else reset();
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

  const handleSave = async () => {
    if (!trade || !account?.id) return;
    setIsSaving(true);
    const isPos = isPosition(trade);
    const isCT  = isCompletedTrade(trade);
    const pnl   = isPos ? ((trade as any).unrealized_pnl ?? 0)
                : isCT  ? (trade as CompletedTrade).realized_pnl
                        : (trade as Trade).pnl;
    try {
      const res = await api.post('/api/journal/', {
        trade_id:       trade.id,
        emotion_tags:   emotion ? [emotion] : [],
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
    try {
      await api.delete(`/api/journal/trade/${trade.id}`);
      reset();
      toast.success('Entry deleted');
    } catch {
      toast.error('Failed to delete');
    } finally {
      setIsSaving(false);
    }
  };

  if (!trade) return null;

  const isPos    = isPosition(trade);
  const isCT     = isCompletedTrade(trade);
  const isOpen   = type === 'position';
  const pnl      = isPos ? ((trade as any).unrealized_pnl ?? 0)
                 : isCT  ? (trade as CompletedTrade).realized_pnl
                         : (trade as Trade).pnl;
  const isProfit = (pnl ?? 0) >= 0;
  const symbol   = trade.tradingsymbol;
  const duration = isCT ? (trade as CompletedTrade).duration_minutes : undefined;
  const hasData  = emotion || followedPlan || exitReason || wouldRepeat || notes;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        className="w-full sm:max-w-md flex flex-col p-0 gap-0"
        aria-describedby="journal-desc"
      >
        {/* ── Header ── */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
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

            <div className="px-5 pb-5 mt-5 space-y-6">

              {/* ── Q1: How were you feeling? ── */}
              <div className="space-y-2.5">
                <p className="text-[13px] font-semibold text-foreground">How were you feeling?</p>
                <div className="space-y-1.5">
                  {EMOTIONS.map(e => (
                    <button
                      key={e.value}
                      type="button"
                      onClick={() => pick(emotion, e.value, setEmotion)}
                      className={cn(
                        'w-full flex items-center justify-between px-4 py-2.5 rounded-xl border text-left transition-all',
                        emotion === e.value
                          ? 'bg-teal-50 dark:bg-teal-900/20 border-tm-brand'
                          : 'bg-muted/30 border-transparent hover:border-border',
                      )}
                    >
                      <span className={cn('text-[13px] font-medium', emotion === e.value ? 'text-tm-brand' : 'text-foreground')}>
                        {e.label}
                      </span>
                      <span className="text-[11px] text-muted-foreground">{e.desc}</span>
                    </button>
                  ))}
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
