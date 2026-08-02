import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '@/lib/api';
import DayEntrySheet from '@/components/journal/DayEntrySheet';

/**
 * Today's intent, on the Dashboard.
 *
 * The seam this closes: the Dashboard is where journal entries get *written*
 * (tap a trade, fill the sheet) but it never showed one back, so Journal read
 * as a separate app that happened to share a database. One line here, opening
 * the same sheet Journal uses, and the two become one surface.
 *
 * It is also the only moment an intent is worth anything. Read at 08:50 it is a
 * note; read at 14:20 with three trades already on and a loss behind you, it is
 * the thing you wrote precisely for that moment.
 *
 * Deliberately one line. `MorningIntentCard` was evicted from the Dashboard for
 * being a card that earned no space; this is not that card returning.
 */

interface DayEntry {
  id: string;
  emotion_tags: string[];
  notes: string | null;
  lessons?: string | null;
  market_condition: string | null;
  entry_type: string;
  created_at: string;
}

export function TodayIntentStrip() {
  const [entry, setEntry] = useState<DayEntry | null>(null);
  const [open, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const res = await api.get('/api/journal', { params: { limit: 20 }, signal });
      const today = new Date().toISOString().slice(0, 10);
      const list: DayEntry[] = res.data?.entries ?? [];
      setEntry(
        list.find(e => e.entry_type !== 'trade' && (e.created_at ?? '').slice(0, 10) === today) ?? null,
      );
    } catch (err) {
      if ((err as { code?: string })?.code === 'ERR_CANCELED') return;
      // Non-fatal. The Dashboard is fully useful without an intent.
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    const ac = new AbortController();
    load(ac.signal);
    return () => ac.abort();
  }, [load]);

  // Never flash the prompt before we know whether one was written.
  if (!loaded) return null;

  return (
    <>
      <div className="flex items-center justify-between gap-3 py-2.5 border-b border-border">
        {entry?.notes ? (
          <p className="text-[13px] text-foreground leading-snug min-w-0 truncate">
            <span className="text-muted-foreground">Today: </span>
            {entry.notes}
          </p>
        ) : (
          <p className="text-[13px] text-muted-foreground leading-snug min-w-0">
            No intent set for today.
          </p>
        )}

        <div className="flex items-center gap-3 shrink-0">
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="text-[12px] font-medium text-primary hover:underline"
          >
            {entry ? 'Edit' : 'Set intent'}
          </button>
          <Link to="/journal" className="text-[12px] text-muted-foreground hover:text-foreground">
            Journal
          </Link>
        </div>
      </div>

      <DayEntrySheet
        open={open}
        onOpenChange={setOpen}
        existing={entry}
        onSaved={() => load()}
      />
    </>
  );
}

export default TodayIntentStrip;
