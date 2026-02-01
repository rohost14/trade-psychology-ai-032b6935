// Trade Journal Sheet - View trade details and add notes
// For both open positions and closed trades

import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Calendar, Clock, FileText, Save, Trash2 } from 'lucide-react';
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
import { Position, Trade } from '@/types/api';
import { cn } from '@/lib/utils';
import { formatCurrency, formatCurrencyWithSign, formatRelativeTime } from '@/lib/formatters';
import { format, parseISO } from 'date-fns';
import { toast } from 'sonner';

// Storage key for journal entries
const JOURNAL_STORAGE_KEY = 'tradementor_trade_journal';

export interface JournalEntry {
  trade_id: string;
  notes: string;
  emotions?: string;
  lessons?: string;
  created_at: string;
  updated_at: string;
}

interface TradeJournalSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  trade: (Position & { instrument_type?: string; unrealized_pnl?: number; current_value?: number }) | Trade | null;
  type: 'position' | 'closed';
}

// Helper to check if it's a Position
function isPosition(trade: any): trade is Position {
  return 'total_quantity' in trade;
}

// Get journal entries from localStorage
function getJournalEntries(): Record<string, JournalEntry> {
  try {
    const stored = localStorage.getItem(JOURNAL_STORAGE_KEY);
    return stored ? JSON.parse(stored) : {};
  } catch {
    return {};
  }
}

// Save journal entry
function saveJournalEntry(entry: JournalEntry): void {
  const entries = getJournalEntries();
  entries[entry.trade_id] = entry;
  localStorage.setItem(JOURNAL_STORAGE_KEY, JSON.stringify(entries));
}

// Delete journal entry
function deleteJournalEntry(tradeId: string): void {
  const entries = getJournalEntries();
  delete entries[tradeId];
  localStorage.setItem(JOURNAL_STORAGE_KEY, JSON.stringify(entries));
}

export function TradeJournalSheet({ open, onOpenChange, trade, type }: TradeJournalSheetProps) {
  const [notes, setNotes] = useState('');
  const [emotions, setEmotions] = useState('');
  const [lessons, setLessons] = useState('');
  const [hasChanges, setHasChanges] = useState(false);
  const [existingEntry, setExistingEntry] = useState<JournalEntry | null>(null);

  // Load existing entry when trade changes
  useEffect(() => {
    if (trade) {
      const entries = getJournalEntries();
      const entry = entries[trade.id];
      if (entry) {
        setNotes(entry.notes || '');
        setEmotions(entry.emotions || '');
        setLessons(entry.lessons || '');
        setExistingEntry(entry);
      } else {
        setNotes('');
        setEmotions('');
        setLessons('');
        setExistingEntry(null);
      }
      setHasChanges(false);
    }
  }, [trade]);

  const handleSave = () => {
    if (!trade) return;
    
    const entry: JournalEntry = {
      trade_id: trade.id,
      notes,
      emotions,
      lessons,
      created_at: existingEntry?.created_at || new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    
    saveJournalEntry(entry);
    setExistingEntry(entry);
    setHasChanges(false);
    toast.success('Journal entry saved');
  };

  const handleDelete = () => {
    if (!trade) return;
    deleteJournalEntry(trade.id);
    setNotes('');
    setEmotions('');
    setLessons('');
    setExistingEntry(null);
    setHasChanges(false);
    toast.success('Journal entry deleted');
  };

  const handleChange = (field: 'notes' | 'emotions' | 'lessons', value: string) => {
    if (field === 'notes') setNotes(value);
    if (field === 'emotions') setEmotions(value);
    if (field === 'lessons') setLessons(value);
    setHasChanges(true);
  };

  if (!trade) return null;

  const isPos = isPosition(trade);
  const pnl = isPos ? (trade as any).unrealized_pnl || trade.realized_pnl : trade.pnl;
  const isProfit = pnl >= 0;
  const symbol = trade.tradingsymbol;
  const quantity = isPos ? trade.total_quantity : trade.quantity;
  const price = isPos ? trade.average_entry_price : trade.price;
  const tradeDate = isPos ? undefined : trade.traded_at;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Trade Journal
          </SheetTitle>
          <SheetDescription>
            Record your thoughts and learnings from this trade
          </SheetDescription>
        </SheetHeader>

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
                  {!isPos && (
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
                Emotional State
              </label>
              <Textarea
                placeholder="How were you feeling? Confident? Anxious? FOMO?"
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
              disabled={!hasChanges && !notes && !emotions && !lessons}
              className="flex-1 gap-2"
            >
              <Save className="h-4 w-4" />
              Save Entry
            </Button>
            {existingEntry && (
              <Button
                variant="outline"
                size="icon"
                onClick={handleDelete}
                className="text-destructive hover:text-destructive"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </div>

          {/* Last Updated */}
          {existingEntry && (
            <p className="text-xs text-muted-foreground text-center">
              Last updated {formatRelativeTime(existingEntry.updated_at)}
            </p>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
