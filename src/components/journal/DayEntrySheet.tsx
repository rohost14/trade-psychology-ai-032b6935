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
  existing?: {
    id: string; emotion_tags: string[]; notes: string | null;
    market_condition: string | null; lessons?: string | null;
  } | null;
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
  // Field mapping, deliberate and worth stating: the backend schema has
  // `notes` and `lessons` but no `intent`, so intent rides on `notes` for a day
  // entry rather than adding a column for one string. Lesson uses `lessons`.
  const [intent, setIntent] = useState(existing?.notes ?? '');
  const [lesson, setLesson] = useState(existing?.lessons ?? '');
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      const body = {
        entry_type: 'day',
        emotion_tags: mood ? [mood] : [],
        market_condition: market,
        notes: intent.trim() || null,
        lessons: lesson.trim() || null,
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

          {/* The two fields that make a day entry worth having. Intent is the
              only place a plan exists before the session, and without it
              "you deviated from your plan" has nothing to compare against.
              Lesson is what you would tell yourself tomorrow. */}
          <div>
            <span className="t-label">Intent</span>
            <p className="text-[12px] text-muted-foreground mt-1 mb-2">
              What you will and will not trade today.
            </p>
            <textarea
              value={intent}
              onChange={e => setIntent(e.target.value)}
              rows={3}
              placeholder="e.g. Only A+ setups. Skip the first 15 minutes."
              className="w-full rounded-md border border-border bg-card px-3 py-2 text-[13.5px] text-foreground placeholder:text-muted-foreground resize-y focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>

          <div>
            <span className="t-label">Lesson</span>
            <p className="text-[12px] text-muted-foreground mt-1 mb-2">
              Optional. A mood on its own is still a complete entry.
            </p>
            <textarea
              value={lesson}
              onChange={e => setLesson(e.target.value)}
              rows={3}
              placeholder="e.g. One loss ends the day when I am tired."
              className="w-full rounded-md border border-border bg-card px-3 py-2 text-[13.5px] text-foreground placeholder:text-muted-foreground resize-y focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>

          <div className="flex items-center gap-2 pt-1">
            <Button onClick={save} disabled={saving || (!mood && !market && !intent.trim() && !lesson.trim())}>
              {saving ? 'Saving…' : 'Save'}
            </Button>
            <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
