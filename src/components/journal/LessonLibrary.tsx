import { useMemo } from 'react';

/**
 * Every lesson you have written, collected.
 *
 * Writing a lesson into a single day's entry buries it — the entry scrolls away
 * and the lesson goes with it, so writing one has no payoff and stops happening.
 * Collecting them is what makes the field worth filling: a short list of rules
 * you arrived at yourself, in your own words, that you can actually re-read.
 *
 * Deliberately not "insights" and not generated. Every line here was typed by
 * the trader; the app only remembers them.
 */

interface Entry {
  id: string;
  lessons?: string | null;
  created_at: string;
}

interface Lesson {
  id: string;
  text: string;
  date: string;
}

export function collectLessons(entries: Entry[]): Lesson[] {
  const seen = new Set<string>();
  const out: Lesson[] = [];

  // Newest first, so a lesson repeated later keeps its most recent date.
  const sorted = [...entries].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  for (const e of sorted) {
    const text = e.lessons?.trim();
    if (!text) continue;
    const key = text.toLowerCase();
    if (seen.has(key)) continue;   // the same lesson relearned is still one lesson
    seen.add(key);
    out.push({ id: e.id, text, date: e.created_at });
  }
  return out;
}

function fmt(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' });
}

export default function LessonLibrary({ entries }: { entries: Entry[] }) {
  const lessons = useMemo(() => collectLessons(entries), [entries]);

  if (lessons.length === 0) return null;

  return (
    <section className="mb-6">
      <div className="flex items-baseline justify-between gap-3 pb-2 border-b border-border">
        <h2 className="text-[15px] font-medium text-foreground">Lessons you have written</h2>
        <span className="text-[11px] text-muted-foreground font-tabular shrink-0">{lessons.length}</span>
      </div>

      <div className="divide-y divide-border">
        {lessons.map(l => (
          <div key={l.id} className="py-3 min-h-[44px] sm:min-h-0">
            <p className="text-[13.5px] text-foreground leading-snug">{l.text}</p>
            <span className="text-[11px] text-muted-foreground uppercase tracking-wider mt-1 block">
              {fmt(l.date)}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
