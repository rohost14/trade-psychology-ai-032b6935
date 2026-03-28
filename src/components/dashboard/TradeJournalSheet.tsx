// Trade Journal Sheet — structured quick-capture form
// Philosophy: less friction → more entries → better analytics
// Old: 3 near-identical text areas nobody fills
// New: tap-to-select structured fields + one optional notes box

import { useState, useEffect } from 'react';
import {
  TrendingUp, TrendingDown, Calendar, Clock,
  FileText, Save, Trash2, Loader2, Star,
} from 'lucide-react';
import {
  Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Position, Trade, CompletedTrade } from '@/types/api';
import { cn } from '@/lib/utils';
import { formatCurrency, formatCurrencyWithSign, formatRelativeTime } from '@/lib/formatters';
import { format, parseISO } from 'date-fns';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';

// ── Emotion tags ──────────────────────────────────────────────────────────────
const EMOTION_TAGS = [
  { value: 'confident',  label: 'Confident',  emoji: '😎' },
  { value: 'anxious',    label: 'Anxious',    emoji: '😰' },
  { value: 'fomo',       label: 'FOMO',       emoji: '😱' },
  { value: 'greedy',     label: 'Greedy',     emoji: '🤑' },
  { value: 'fearful',    label: 'Fearful',    emoji: '😨' },
  { value: 'revenge',    label: 'Revenge',    emoji: '😤' },
  { value: 'calm',       label: 'Calm',       emoji: '😌' },
  { value: 'impatient',  label: 'Impatient',  emoji: '⏰' },
  { value: 'neutral',    label: 'Neutral',    emoji: '😐' },
];

// ── Structured option sets ────────────────────────────────────────────────────
const PLAN_OPTIONS = [
  { value: 'yes',        label: 'Yes — followed my plan' },
  { value: 'partially',  label: 'Partially' },
  { value: 'no',         label: 'No — deviated' },
];

const DEVIATION_OPTIONS = [
  { value: 'fomo',          label: 'FOMO' },
  { value: 'revenge',       label: 'Revenge' },
  { value: 'overconfident', label: 'Overconfident' },
  { value: 'bored',         label: 'Bored' },
  { value: 'impulse',       label: 'Impulse' },
  { value: 'other',         label: 'Other' },
];

const EXIT_REASONS = [
  { value: 'sl_hit',       label: 'SL Hit' },
  { value: 'target_hit',   label: 'Target Hit' },
  { value: 'trailed_stop', label: 'Trailed Stop' },
  { value: 'manual',       label: 'Manual Exit' },
  { value: 'panic',        label: 'Panic Exit' },
  { value: 'news',         label: 'News/Event' },
];

const MARKET_CONDITIONS = [
  { value: 'trending',   label: 'Trending' },
  { value: 'ranging',    label: 'Ranging' },
  { value: 'volatile',   label: 'Volatile' },
  { value: 'choppy',     label: 'Choppy' },
  { value: 'news_driven', label: 'News-driven' },
];

const REPEAT_OPTIONS = [
  { value: 'yes',   label: 'Yes' },
  { value: 'maybe', label: 'Maybe' },
  { value: 'no',    label: 'No' },
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

interface TradeJournalSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  trade: (Position & { instrument_type?: string; unrealized_pnl?: number }) | Trade | CompletedTrade | null;
  type: 'position' | 'closed';
}

// ── Type guards ───────────────────────────────────────────────────────────────
function isPosition(t: any): t is Position {
  return 'total_quantity' in t && 'average_entry_price' in t && !('direction' in t);
}
function isCompletedTrade(t: any): t is CompletedTrade {
  return 'direction' in t && 'realized_pnl' in t && 'avg_entry_price' in t;
}

// ── Reusable chip component ───────────────────────────────────────────────────
function Chip({
  label, active, onClick,
}: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'px-3 py-1.5 rounded-full text-xs font-medium transition-all border',
        active
          ? 'bg-primary text-primary-foreground border-primary'
          : 'bg-muted text-muted-foreground border-transparent hover:border-border',
      )}
    >
      {label}
    </button>
  );
}

// ── Star rating ───────────────────────────────────────────────────────────────
function StarRating({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map(n => (
        <button
          key={n}
          type="button"
          onClick={() => onChange(n === value ? 0 : n)}
          className="p-0.5 transition-transform hover:scale-110"
        >
          <Star
            className={cn(
              'h-6 w-6',
              n <= value ? 'fill-amber-400 text-amber-400' : 'text-muted-foreground/30',
            )}
          />
        </button>
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export function TradeJournalSheet({ open, onOpenChange, trade, type }: TradeJournalSheetProps) {
  const { account } = useBroker();

  const [emotionTags,     setEmotionTags]     = useState<string[]>([]);
  const [followedPlan,    setFollowedPlan]    = useState('');
  const [deviationReason, setDeviationReason] = useState('');
  const [exitReason,      setExitReason]      = useState('');
  const [setupQuality,    setSetupQuality]    = useState(0);
  const [wouldRepeat,     setWouldRepeat]     = useState('');
  const [marketCondition, setMarketCondition] = useState('');
  const [notes,           setNotes]           = useState('');

  const [hasChanges,    setHasChanges]    = useState(false);
  const [existingEntry, setExistingEntry] = useState<JournalEntry | null>(null);
  const [isLoading,     setIsLoading]     = useState(false);
  const [isSaving,      setIsSaving]      = useState(false);

  useEffect(() => {
    if (trade && open) loadEntry();
  }, [trade, open]);

  const resetForm = () => {
    setEmotionTags([]);
    setFollowedPlan('');
    setDeviationReason('');
    setExitReason('');
    setSetupQuality(0);
    setWouldRepeat('');
    setMarketCondition('');
    setNotes('');
    setExistingEntry(null);
  };

  const applyEntry = (e: JournalEntry) => {
    setEmotionTags(e.emotion_tags || []);
    setFollowedPlan(e.followed_plan || '');
    setDeviationReason(e.deviation_reason || '');
    setExitReason(e.exit_reason || '');
    setSetupQuality(e.setup_quality || 0);
    setWouldRepeat(e.would_repeat || '');
    setMarketCondition(e.market_condition || '');
    setNotes(e.notes || '');
    setExistingEntry(e);
  };

  const loadEntry = async () => {
    if (!trade || !account?.id) return;
    setIsLoading(true);
    try {
      const res = await api.get(`/api/journal/trade/${trade.id}`);
      if (res.data.entry) {
        applyEntry(res.data.entry);
      } else {
        resetForm();
      }
    } catch {
      resetForm();
    } finally {
      setIsLoading(false);
      setHasChanges(false);
    }
  };

  const mark = () => setHasChanges(true);

  const toggle = (setter: React.Dispatch<React.SetStateAction<string[]>>, val: string) => {
    setter(prev => prev.includes(val) ? prev.filter(v => v !== val) : [...prev, val]);
    mark();
  };

  const pick = (setter: React.Dispatch<React.SetStateAction<string>>, val: string, current: string) => {
    setter(val === current ? '' : val);
    mark();
  };

  const hasAnyData = () =>
    emotionTags.length > 0 || followedPlan || exitReason || setupQuality > 0 ||
    wouldRepeat || marketCondition || notes;

  const handleSave = async () => {
    if (!trade || !account?.id) return;
    setIsSaving(true);

    const payload = {
      trade_id: trade.id,
      emotion_tags: emotionTags,
      followed_plan: followedPlan || undefined,
      deviation_reason: deviationReason || undefined,
      exit_reason: exitReason || undefined,
      setup_quality: setupQuality || undefined,
      would_repeat: wouldRepeat || undefined,
      market_condition: marketCondition || undefined,
      notes: notes || undefined,
      trade_symbol: trade.tradingsymbol,
      trade_type: isPosition(trade) ? 'POSITION' : isCompletedTrade(trade)
        ? (trade as CompletedTrade).direction
        : (trade as Trade).trade_type,
      trade_pnl: String(pnl || 0),
    };

    try {
      const res = await api.post('/api/journal/', payload);
      const saved = res.data.entry;
      setExistingEntry(saved);
      setHasChanges(false);
      toast.success('Journal entry saved');
    } catch {
      toast.error('Failed to save — please try again');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!trade || !account?.id) return;
    setIsSaving(true);
    try {
      await api.delete(`/api/journal/trade/${trade.id}`);
      resetForm();
      setHasChanges(false);
      toast.success('Journal entry deleted');
    } catch {
      toast.error('Failed to delete — please try again');
    } finally {
      setIsSaving(false);
    }
  };

  if (!trade) return null;

  const isPos = isPosition(trade);
  const isCT  = isCompletedTrade(trade);
  const pnl = isPos
    ? ((trade as any).unrealized_pnl ?? 0)
    : isCT
      ? (trade as CompletedTrade).realized_pnl
      : (trade as Trade).pnl;
  const isProfit  = pnl >= 0;
  const symbol    = trade.tradingsymbol;
  const quantity  = isPos ? trade.total_quantity : isCT
    ? (trade as CompletedTrade).total_quantity
    : (trade as Trade).quantity;
  const price     = isPos ? trade.average_entry_price : isCT
    ? (trade as CompletedTrade).avg_entry_price
    : (trade as Trade).price;
  const tradeDate = isPos ? undefined : isCT
    ? (trade as CompletedTrade).exit_time
    : (trade as Trade).traded_at;
  const duration  = isCT ? (trade as CompletedTrade).duration_minutes : undefined;

  const showDeviation = followedPlan === 'no' || followedPlan === 'partially';
  const isOpen = type === 'position';

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Trade Journal
          </SheetTitle>
          <SheetDescription>
            Quick capture — most fields are one tap
          </SheetDescription>
        </SheetHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="mt-6 space-y-5">

            {/* ── Trade Summary ── */}
            <div className="p-4 rounded-lg bg-muted/50 border border-border">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="font-mono text-lg font-bold text-foreground">{symbol}</p>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    <Badge variant="secondary" className="text-xs">{trade.exchange}</Badge>
                    {isCT && (
                      <Badge
                        variant={(trade as CompletedTrade).direction === 'LONG' ? 'default' : 'destructive'}
                        className="text-xs"
                      >
                        {(trade as CompletedTrade).direction}
                      </Badge>
                    )}
                    {isOpen && <Badge variant="outline" className="text-xs border-primary text-primary">OPEN</Badge>}
                    {duration && <Badge variant="outline" className="text-xs">{duration}m hold</Badge>}
                  </div>
                </div>
                <div className="text-right">
                  <div className="flex items-center gap-2">
                    <div className={cn('p-1.5 rounded', isProfit ? 'bg-success/10' : 'bg-destructive/10')}>
                      {isProfit
                        ? <TrendingUp className="h-4 w-4 text-success" />
                        : <TrendingDown className="h-4 w-4 text-destructive" />}
                    </div>
                    <span className={cn('font-mono text-xl font-bold', isProfit ? 'text-success' : 'text-destructive')}>
                      {formatCurrencyWithSign(pnl)}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {isOpen ? 'Unrealized P&L' : 'Realized P&L'}
                  </p>
                </div>
              </div>
              <Separator className="my-3" />
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-muted-foreground">Qty</p>
                  <p className="font-mono font-medium">{quantity}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">{isPos ? 'Avg Entry' : 'Avg Entry'}</p>
                  <p className="font-mono font-medium">{formatCurrency(price)}</p>
                </div>
                {tradeDate && (
                  <>
                    <div>
                      <p className="text-muted-foreground flex items-center gap-1">
                        <Calendar className="h-3 w-3" />Date
                      </p>
                      <p className="font-medium">{format(parseISO(tradeDate), 'MMM d, yyyy')}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground flex items-center gap-1">
                        <Clock className="h-3 w-3" />Time
                      </p>
                      <p className="font-medium">{format(parseISO(tradeDate), 'h:mm a')}</p>
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* ── Emotion tags ── */}
            <div className="space-y-2">
              <p className="text-sm font-medium">How were you feeling?</p>
              <div className="flex flex-wrap gap-2">
                {EMOTION_TAGS.map(tag => (
                  <button
                    key={tag.value}
                    type="button"
                    onClick={() => toggle(setEmotionTags, tag.value)}
                    className={cn(
                      'px-3 py-1.5 rounded-full text-xs font-medium transition-all',
                      emotionTags.includes(tag.value)
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground hover:bg-muted/80',
                    )}
                  >
                    {tag.emoji} {tag.label}
                  </button>
                ))}
              </div>
            </div>

            <Separator />

            {/* ── Did you follow your plan? ── */}
            <div className="space-y-2">
              <p className="text-sm font-medium">Did you follow your plan?</p>
              <div className="flex gap-2 flex-wrap">
                {PLAN_OPTIONS.map(o => (
                  <Chip
                    key={o.value}
                    label={o.label}
                    active={followedPlan === o.value}
                    onClick={() => pick(setFollowedPlan, o.value, followedPlan)}
                  />
                ))}
              </div>
            </div>

            {/* ── Why deviated? (conditional) ── */}
            {showDeviation && (
              <div className="space-y-2">
                <p className="text-sm font-medium text-muted-foreground">Why did you deviate?</p>
                <div className="flex gap-2 flex-wrap">
                  {DEVIATION_OPTIONS.map(o => (
                    <Chip
                      key={o.value}
                      label={o.label}
                      active={deviationReason === o.value}
                      onClick={() => pick(setDeviationReason, o.value, deviationReason)}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* ── Exit reason ── */}
            {!isOpen && (
              <div className="space-y-2">
                <p className="text-sm font-medium">Why did you exit?</p>
                <div className="flex gap-2 flex-wrap">
                  {EXIT_REASONS.map(o => (
                    <Chip
                      key={o.value}
                      label={o.label}
                      active={exitReason === o.value}
                      onClick={() => pick(setExitReason, o.value, exitReason)}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* ── Setup quality + Would repeat ── */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <p className="text-sm font-medium">Setup quality</p>
                <StarRating value={setupQuality} onChange={v => { setSetupQuality(v); mark(); }} />
                <p className="text-xs text-muted-foreground">
                  {setupQuality === 0 ? 'Tap to rate' :
                   setupQuality === 1 ? 'Terrible setup' :
                   setupQuality === 2 ? 'Below average' :
                   setupQuality === 3 ? 'Average' :
                   setupQuality === 4 ? 'Good setup' : 'Textbook setup'}
                </p>
              </div>
              <div className="space-y-2">
                <p className="text-sm font-medium">Take this trade again?</p>
                <div className="flex gap-2">
                  {REPEAT_OPTIONS.map(o => (
                    <Chip
                      key={o.value}
                      label={o.label}
                      active={wouldRepeat === o.value}
                      onClick={() => pick(setWouldRepeat, o.value, wouldRepeat)}
                    />
                  ))}
                </div>
              </div>
            </div>

            {/* ── Market condition ── */}
            <div className="space-y-2">
              <p className="text-sm font-medium">Market condition</p>
              <div className="flex gap-2 flex-wrap">
                {MARKET_CONDITIONS.map(o => (
                  <Chip
                    key={o.value}
                    label={o.label}
                    active={marketCondition === o.value}
                    onClick={() => pick(setMarketCondition, o.value, marketCondition)}
                  />
                ))}
              </div>
            </div>

            {/* ── Optional notes ── */}
            <div className="space-y-2">
              <p className="text-sm font-medium text-muted-foreground">Notes <span className="font-normal">(optional)</span></p>
              <Textarea
                placeholder="Anything else worth capturing?"
                value={notes}
                onChange={e => { setNotes(e.target.value); mark(); }}
                className="min-h-[72px] resize-none text-sm"
              />
            </div>

            {/* ── Actions ── */}
            <div className="flex items-center gap-3 pt-2 border-t border-border">
              <Button
                onClick={handleSave}
                disabled={isSaving || (!hasChanges && !hasAnyData())}
                className="flex-1 gap-2"
              >
                {isSaving
                  ? <Loader2 className="h-4 w-4 animate-spin" />
                  : <Save className="h-4 w-4" />}
                {isSaving ? 'Saving…' : 'Save Entry'}
              </Button>
              {existingEntry && (
                <Button
                  variant="outline"
                  size="icon"
                  onClick={handleDelete}
                  disabled={isSaving}
                  className="text-destructive hover:text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </div>

            {/* ── Last updated ── */}
            {existingEntry && (
              <p className="text-xs text-muted-foreground text-center">Last updated {formatRelativeTime(existingEntry.updated_at)}</p>
            )}

          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
