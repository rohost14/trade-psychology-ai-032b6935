// Trade Journal Sheet - View trade details and add notes
// Connects to backend API with localStorage fallback

import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Calendar, Clock, FileText, Save, Trash2, Loader2, Cloud, CloudOff } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
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

// Emotion tags for quick selection
const EMOTION_TAGS = [
  { value: 'confident', label: 'Confident', emoji: '😎' },
  { value: 'anxious', label: 'Anxious', emoji: '😰' },
  { value: 'fomo', label: 'FOMO', emoji: '😱' },
  { value: 'greedy', label: 'Greedy', emoji: '🤑' },
  { value: 'fearful', label: 'Fearful', emoji: '😨' },
  { value: 'revenge', label: 'Revenge', emoji: '😤' },
  { value: 'calm', label: 'Calm', emoji: '😌' },
  { value: 'impatient', label: 'Impatient', emoji: '⏰' },
  { value: 'neutral', label: 'Neutral', emoji: '😐' },
];

export interface JournalEntry {
  id?: string;
  trade_id: string;
  notes: string;
  emotions?: string;
  lessons?: string;
  emotion_tags?: string[];
  created_at: string;
  updated_at: string;
}

interface TradeJournalSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  trade: (Position & { instrument_type?: string; unrealized_pnl?: number; current_value?: number }) | Trade | CompletedTrade | null;
  type: 'position' | 'closed';
}

// Helper to check if it's a Position (open)
function isPosition(trade: any): trade is Position {
  return 'total_quantity' in trade && 'average_entry_price' in trade && !('direction' in trade);
}

// Helper to check if it's a CompletedTrade (flat-to-flat round)
function isCompletedTrade(trade: any): trade is CompletedTrade {
  return 'direction' in trade && 'realized_pnl' in trade && 'avg_entry_price' in trade;
}

// localStorage fallback
const JOURNAL_STORAGE_KEY = 'tradementor_trade_journal';

function getLocalEntry(tradeId: string): JournalEntry | null {
  try {
    const stored = localStorage.getItem(JOURNAL_STORAGE_KEY);
    const entries = stored ? JSON.parse(stored) : {};
    return entries[tradeId] || null;
  } catch {
    return null;
  }
}

function saveLocalEntry(entry: JournalEntry): void {
  try {
    const stored = localStorage.getItem(JOURNAL_STORAGE_KEY);
    const entries = stored ? JSON.parse(stored) : {};
    entries[entry.trade_id] = entry;
    localStorage.setItem(JOURNAL_STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // Ignore localStorage errors
  }
}

function deleteLocalEntry(tradeId: string): void {
  try {
    const stored = localStorage.getItem(JOURNAL_STORAGE_KEY);
    const entries = stored ? JSON.parse(stored) : {};
    delete entries[tradeId];
    localStorage.setItem(JOURNAL_STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // Ignore localStorage errors
  }
}

export function TradeJournalSheet({ open, onOpenChange, trade, type }: TradeJournalSheetProps) {
  const { account } = useBroker();
  const [notes, setNotes] = useState('');
  const [emotions, setEmotions] = useState('');
  const [lessons, setLessons] = useState('');
  const [emotionTags, setEmotionTags] = useState<string[]>([]);
  const [hasChanges, setHasChanges] = useState(false);
  const [existingEntry, setExistingEntry] = useState<JournalEntry | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isOnline, setIsOnline] = useState(true);

  // Load existing entry when trade changes
  useEffect(() => {
    if (trade && open) {
      loadEntry();
    }
  }, [trade, open]);

  const loadEntry = async () => {
    if (!trade || !account?.id) return;

    setIsLoading(true);

    try {
      // Try API first
      const response = await api.get(`/api/journal/trade/${trade.id}`);

      const entry = response.data.entry;
      if (entry) {
        setNotes(entry.notes || '');
        setEmotions(entry.emotions || '');
        setLessons(entry.lessons || '');
        setEmotionTags(entry.emotion_tags || []);
        setExistingEntry(entry);
        setIsOnline(true);
      } else {
        // Check localStorage fallback
        const localEntry = getLocalEntry(trade.id);
        if (localEntry) {
          setNotes(localEntry.notes || '');
          setEmotions(localEntry.emotions || '');
          setLessons(localEntry.lessons || '');
          setEmotionTags(localEntry.emotion_tags || []);
          setExistingEntry(localEntry);
        } else {
          resetForm();
        }
        setIsOnline(true);
      }
    } catch (error) {
      console.error('Failed to load journal entry:', error);
      // Fall back to localStorage
      const localEntry = getLocalEntry(trade.id);
      if (localEntry) {
        setNotes(localEntry.notes || '');
        setEmotions(localEntry.emotions || '');
        setLessons(localEntry.lessons || '');
        setEmotionTags(localEntry.emotion_tags || []);
        setExistingEntry(localEntry);
      } else {
        resetForm();
      }
      setIsOnline(false);
    } finally {
      setIsLoading(false);
      setHasChanges(false);
    }
  };

  const resetForm = () => {
    setNotes('');
    setEmotions('');
    setLessons('');
    setEmotionTags([]);
    setExistingEntry(null);
  };

  const handleSave = async () => {
    if (!trade || !account?.id) return;

    setIsSaving(true);

    const entryData = {
      trade_id: trade.id,
      notes,
      emotions,
      lessons,
      emotion_tags: emotionTags,
      trade_symbol: trade.tradingsymbol,
      trade_type: isPosition(trade) ? 'POSITION' : isCompletedTrade(trade) ? (trade as CompletedTrade).direction : (trade as Trade).trade_type,
      trade_pnl: String(pnl || 0),
      entry_type: 'trade'
    };

    try {
      // Try API first
      const response = await api.post('/api/journal/', entryData);

      setExistingEntry(response.data.entry);
      setHasChanges(false);
      setIsOnline(true);

      // Also save to localStorage as backup
      saveLocalEntry({
        ...entryData,
        id: response.data.entry.id,
        created_at: response.data.entry.created_at,
        updated_at: response.data.entry.updated_at
      });

      toast.success('Journal entry saved');
    } catch (error) {
      console.error('Failed to save journal entry:', error);

      // Fall back to localStorage
      const localEntry: JournalEntry = {
        ...entryData,
        created_at: existingEntry?.created_at || new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      saveLocalEntry(localEntry);
      setExistingEntry(localEntry);
      setHasChanges(false);
      setIsOnline(false);

      toast.success('Journal entry saved locally', {
        description: 'Will sync when connection is restored'
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!trade || !account?.id) return;

    setIsSaving(true);

    try {
      // Try API first
      await api.delete(`/api/journal/trade/${trade.id}`);

      // Also delete from localStorage
      deleteLocalEntry(trade.id);

      resetForm();
      setHasChanges(false);
      toast.success('Journal entry deleted');
    } catch (error) {
      console.error('Failed to delete journal entry:', error);

      // Fall back to localStorage only delete
      deleteLocalEntry(trade.id);
      resetForm();
      setHasChanges(false);

      toast.success('Journal entry deleted locally');
    } finally {
      setIsSaving(false);
    }
  };

  const handleChange = (field: 'notes' | 'emotions' | 'lessons', value: string) => {
    if (field === 'notes') setNotes(value);
    if (field === 'emotions') setEmotions(value);
    if (field === 'lessons') setLessons(value);
    setHasChanges(true);
  };

  const toggleEmotionTag = (tag: string) => {
    setEmotionTags(prev =>
      prev.includes(tag)
        ? prev.filter(t => t !== tag)
        : [...prev, tag]
    );
    setHasChanges(true);
  };

  if (!trade) return null;

  const isPos = isPosition(trade);
  const isCT = isCompletedTrade(trade);
  const pnl = isPos
    ? ((trade as any).unrealized_pnl ?? 0)
    : isCT
      ? (trade as CompletedTrade).realized_pnl
      : (trade as Trade).pnl;
  const isProfit = pnl >= 0;
  const symbol = trade.tradingsymbol;
  const quantity = isPos
    ? trade.total_quantity
    : isCT
      ? (trade as CompletedTrade).total_quantity
      : (trade as Trade).quantity;
  const price = isPos
    ? trade.average_entry_price
    : isCT
      ? (trade as CompletedTrade).avg_entry_price
      : (trade as Trade).price;
  const tradeDate = isPos
    ? undefined
    : isCT
      ? (trade as CompletedTrade).exit_time
      : (trade as Trade).traded_at;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Trade Journal
            {!isOnline && (
              <Badge variant="outline" className="ml-2 text-xs">
                <CloudOff className="h-3 w-3 mr-1" />
                Offline
              </Badge>
            )}
          </SheetTitle>
          <SheetDescription>
            Record your thoughts and learnings from this trade
          </SheetDescription>
        </SheetHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="mt-6 space-y-6">
            {/* Trade Summary */}
            <div className="p-4 rounded-lg bg-muted/50 border border-border">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="font-mono text-lg font-bold text-foreground">{symbol}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <Badge variant="secondary" className="text-xs">
                      {trade.exchange}
                    </Badge>
                    {!isPos && isCT && (
                      <Badge
                        variant={(trade as CompletedTrade).direction === 'LONG' ? 'default' : 'destructive'}
                        className="text-xs"
                      >
                        {(trade as CompletedTrade).direction}
                      </Badge>
                    )}
                    {!isPos && !isCT && (
                      <Badge
                        variant={(trade as Trade).trade_type === 'BUY' ? 'default' : 'destructive'}
                        className="text-xs"
                      >
                        {(trade as Trade).trade_type}
                      </Badge>
                    )}
                    {type === 'position' && (
                      <Badge variant="outline" className="text-xs border-primary text-primary">
                        OPEN
                      </Badge>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <div className="flex items-center gap-2">
                    <div className={cn(
                      'p-1.5 rounded',
                      isProfit ? 'bg-success/10' : 'bg-destructive/10'
                    )}>
                      {isProfit ? (
                        <TrendingUp className="h-4 w-4 text-success" />
                      ) : (
                        <TrendingDown className="h-4 w-4 text-destructive" />
                      )}
                    </div>
                    <span className={cn(
                      'font-mono text-xl font-bold',
                      isProfit ? 'text-success' : 'text-destructive'
                    )}>
                      {formatCurrencyWithSign(pnl)}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {type === 'position' ? 'Unrealized P&L' : 'Realized P&L'}
                  </p>
                </div>
              </div>

              <Separator className="my-3" />

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">Quantity</p>
                  <p className="font-mono font-medium">{quantity}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">{isPos ? 'Avg Entry' : 'Price'}</p>
                  <p className="font-mono font-medium">{formatCurrency(price)}</p>
                </div>
                {tradeDate && (
                  <>
                    <div>
                      <p className="text-muted-foreground flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        Date
                      </p>
                      <p className="font-medium">{format(parseISO(tradeDate), 'MMM d, yyyy')}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        Time
                      </p>
                      <p className="font-medium">{format(parseISO(tradeDate), 'h:mm a')}</p>
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Quick Emotion Tags */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                How were you feeling? (tap to select)
              </label>
              <div className="flex flex-wrap gap-2">
                {EMOTION_TAGS.map(tag => (
                  <button
                    key={tag.value}
                    type="button"
                    onClick={() => toggleEmotionTag(tag.value)}
                    className={cn(
                      'px-3 py-1.5 rounded-full text-xs font-medium transition-all',
                      emotionTags.includes(tag.value)
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground hover:bg-muted/80'
                    )}
                  >
                    {tag.emoji} {tag.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Journal Entries */}
            <div className="space-y-4">
              {/* Notes */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Trade Notes
                </label>
                <Textarea
                  placeholder="Why did you take this trade? What was your thesis?"
                  value={notes}
                  onChange={(e) => handleChange('notes', e.target.value)}
                  className="min-h-[100px] resize-none"
                />
              </div>

              {/* Emotions */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Detailed Thoughts
                </label>
                <Textarea
                  placeholder="Any additional context about your emotional state or market conditions..."
                  value={emotions}
                  onChange={(e) => handleChange('emotions', e.target.value)}
                  className="min-h-[80px] resize-none"
                />
              </div>

              {/* Lessons */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Key Lessons
                </label>
                <Textarea
                  placeholder="What did you learn? What would you do differently?"
                  value={lessons}
                  onChange={(e) => handleChange('lessons', e.target.value)}
                  className="min-h-[80px] resize-none"
                />
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3 pt-4 border-t border-border">
              <Button
                onClick={handleSave}
                disabled={isSaving || (!hasChanges && !notes && !emotions && !lessons && emotionTags.length === 0)}
                className="flex-1 gap-2"
              >
                {isSaving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                {isSaving ? 'Saving...' : 'Save Entry'}
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

            {/* Last Updated */}
            {existingEntry && (
              <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
                {isOnline ? (
                  <Cloud className="h-3 w-3" />
                ) : (
                  <CloudOff className="h-3 w-3" />
                )}
                <span>Last updated {formatRelativeTime(existingEntry.updated_at)}</span>
              </div>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
