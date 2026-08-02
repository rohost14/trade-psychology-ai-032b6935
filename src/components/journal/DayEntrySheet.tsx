import { useState } from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

/**
 * Write a day-level journal entry.
 *
 * The gap this fills: every entry in the app is attached to a trade, written
 * from the Dashboard sheet after the fact. There has never been a way to record
 * a *day* — how you are trading, what you intend, what you learned. That is the
 * only place intent can live, and without intent "you deviated from your plan"
 * has no plan to compare against.
 *
 * Taps before typing. Mood and market are chips; intent and lesson are short
 * and optional. The rule is that the app must be fully useful with zero input,
 * not that input is unwelcome — so nothing here is required, and a mood tap
 * alone is a valid entry.
 */

const MOODS = ['calm', 'focused', 'neutral', 'anxious', 'restless', 'tired'] as const;
const MOOD_LABEL: Record<string, string> = {
  calm: 'Calm', focused: 'Focused', neutral: 'Neutral',
  anxious: 'Anxious', restless: 'Restless', tired: 'Tired',
};

const MARKETS = ['trending', 'choppy', 'volatile', 'quiet'] as const;
const MARKET_LABEL: Record<string, string> = {
  trending: 'Trending', choppy: 'Choppy', volatile: 'Volatile', quiet: 'Quiet',
};

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  existing?: { id: string; emotion_tags: string[]; notes: string | null; market_condition: string | null } | null;
  onSaved?: () => void;
}

function ChipRow({ options, labels, value, onChange }: {
  options: readonly string[];
  labels: Record<string, string>;
  value: string | null;
  onChange: (v: string | null) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map(o => (
        <button
          key={o}
          type="button"
          onClick={() => onChange(value === o ? null : o)}
          className={cn(
            'h-9 px-3 rounded-md border text-[13px] font-medium transition-colors',
            value === o
              ? 'bg-muted text-foreground border-border'
              : 'text-muted-foreground border-border hover:text-foreground',
          )}
        >
          {labels[o] ?? o}
        </button>
      ))}
    </div>
  );
}

export default function DayEntrySheet({ open, onOpenChange, existing, onSaved }: Props) {
  const [mood, setMood] = useState<string | null>(existing?.emotion_tags?.[0] ?? null);
  const [market, setMarket] = useState<string | null>(existing?.market_condition ?? null);
  const [notes, setNotes] = useState(existing?.notes ?? '');
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      const body = {
        entry_type: 'day',
        emotion_tags: mood ? [mood] : [],
        market_condition: market,
        notes: notes.trim() || null,
      };
      if (existing?.id) {
        await api.put(`/api/journal/${existing.id}`, body);
      } else {
        await api.post('/api/journal', body);
      }
      toast.success('Saved');
      onSaved?.();
      onOpenChange(false);
    } catch {
      toast.error('Could not save — try again');
    } finally {
      setSaving(false);
    }
  };

  const today = new Date().toLocaleDateString('en-IN', {
    weekday: 'short', day: 'numeric', month: 'short',
  });

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-md overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="text-left">{today}</SheetTitle>
        </SheetHeader>

        <div className="mt-5 space-y-6">
          <div>
            <span className="t-label">How are you trading today?</span>
            <div className="mt-2">
              <ChipRow options={MOODS} labels={MOOD_LABEL} value={mood} onChange={setMood} />
            </div>
          </div>

          <div>
            <span className="t-label">Market</span>
            <div className="mt-2">
              <ChipRow options={MARKETS} labels={MARKET_LABEL} value={market} onChange={setMarket} />
            </div>
          </div>

          <div>
            <span className="t-label">Anything worth remembering</span>
            <p className="text-[12px] text-muted-foreground mt-1 mb-2">
              Optional. A mood on its own is a complete entry.
            </p>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              rows={5}
              placeholder="Your plan, or what you noticed…"
              className="w-full rounded-md border border-border bg-card px-3 py-2 text-[13.5px] text-foreground placeholder:text-muted-foreground resize-y focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>

          <div className="flex items-center gap-2 pt-1">
            <Button onClick={save} disabled={saving || (!mood && !market && !notes.trim())}>
              {saving ? 'Saving…' : 'Save'}
            </Button>
            <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
