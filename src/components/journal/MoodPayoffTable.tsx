import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { formatCurrencyWhole } from '@/lib/formatters';

/**
 * What each state of mind actually pays.
 *
 * The money-on-everything rule applied to psychology: a mood tag is worth
 * tapping only if it buys you something, and this is the something. Calm days
 * average X, restless days average Y — from the trader's own tape, no model.
 *
 * It also fixes the incentive. Journalling is otherwise homework with a
 * deferred payoff; this is the one answer that cannot be obtained any other
 * way, and it gets better the more days are tagged.
 *
 * Deliberately averages per DAY rather than per trade. A restless day with
 * eleven trades and a calm day with two are both one day of that state, and
 * per-trade averaging would let a single busy day dominate the row.
 */

interface Entry {
  emotion_tags: string[];
  trade_pnl: string | null;
  created_at: string;
  followed_plan: string | null;
}

const MOOD_LABEL: Record<string, string> = {
  calm: 'Calm', focused: 'Focused', neutral: 'Neutral',
  confident: 'Confident', anxious: 'Anxious', restless: 'Restless',
  fomo: 'FOMO', revenge: 'Revenge', overconfident: 'Overconfident',
  tired: 'Tired', distracted: 'Distracted',
};

interface Row {
  mood: string;
  days: number;
  avgPerDay: number;
  trades: number;
  breaks: number;
}

export function buildMoodRows(entries: Entry[]): Row[] {
  // Fold to (mood, day) first so a day counts once per mood however many
  // trades it carried.
  const byMoodDay = new Map<string, Map<string, { pnl: number; trades: number; breaks: number }>>();

  for (const e of entries) {
    const day = (e.created_at ?? '').slice(0, 10);
    if (!day) continue;
    const pnl = e.trade_pnl != null ? Number(e.trade_pnl) : 0;
    const broke = e.followed_plan === 'no' || e.followed_plan === 'partial' ? 1 : 0;

    for (const raw of e.emotion_tags ?? []) {
      const mood = raw.toLowerCase();
      if (!byMoodDay.has(mood)) byMoodDay.set(mood, new Map());
      const days = byMoodDay.get(mood)!;
      const acc = days.get(day) ?? { pnl: 0, trades: 0, breaks: 0 };
      acc.pnl += Number.isFinite(pnl) ? pnl : 0;
      acc.trades += e.trade_pnl != null ? 1 : 0;
      acc.breaks += broke;
      days.set(day, acc);
    }
  }

  const rows: Row[] = [];
  for (const [mood, days] of byMoodDay) {
    const list = [...days.values()];
    const total = list.reduce((s, d) => s + d.pnl, 0);
    rows.push({
      mood,
      days: list.length,
      avgPerDay: total / list.length,
      trades: list.reduce((s, d) => s + d.trades, 0) / list.length,
      breaks: list.reduce((s, d) => s + d.breaks, 0) / list.length,
    });
  }

  return rows.sort((a, b) => b.avgPerDay - a.avgPerDay);
}

export default function MoodPayoffTable({ entries }: { entries: Entry[] }) {
  const rows = useMemo(() => buildMoodRows(entries), [entries]);

  if (rows.length < 2) return null;   // one mood is not a comparison

  const best = rows[0];
  const worst = rows[rows.length - 1];
  const maxAbs = Math.max(...rows.map(r => Math.abs(r.avgPerDay)), 1);

  return (
    <section>
      <div className="flex items-baseline justify-between gap-3 pb-1">
        <h2 className="text-[15px] font-medium text-foreground">How your state of mind pays</h2>
      </div>
      <p className="text-[12.5px] text-muted-foreground mb-3">
        <span className="text-tm-profit font-medium">{MOOD_LABEL[best.mood] ?? best.mood}</span> days average{' '}
        <span className="font-tabular">{formatCurrencyWhole(best.avgPerDay)}</span>.{' '}
        <span className="text-tm-loss font-medium">{MOOD_LABEL[worst.mood] ?? worst.mood}</span> days average{' '}
        <span className="font-tabular">{formatCurrencyWhole(worst.avgPerDay)}</span>.
      </p>

      <div className="grid grid-cols-[minmax(88px,1fr)_minmax(0,3fr)_72px_64px_60px] gap-x-3 pb-1.5 border-b border-border">
        <span className="t-label">Mood</span>
        <span className="t-label">Avg P&amp;L per day</span>
        <span className="t-label text-right">Avg</span>
        <span className="t-label text-right">Trades</span>
        <span className="t-label text-right">Breaks</span>
      </div>

      <div className="divide-y divide-border">
        {rows.map(r => {
          const positive = r.avgPerDay >= 0;
          const width = (Math.abs(r.avgPerDay) / maxAbs) * 100;
          return (
            <div
              key={r.mood}
              className="grid grid-cols-[minmax(88px,1fr)_minmax(0,3fr)_72px_64px_60px] gap-x-3 items-center py-2.5 min-h-[44px] sm:min-h-0"
            >
              <span className="text-[13.5px] text-foreground truncate">
                {MOOD_LABEL[r.mood] ?? r.mood}
                <span className="text-[11px] text-muted-foreground font-tabular ml-1.5">{r.days}d</span>
              </span>

              {/* Diverging from a centre baseline, so a loss reads as less
                  rather than as a longer bar. */}
              <span className="h-1 flex items-center" aria-hidden>
                <span className="w-1/2 flex justify-end">
                  {!positive && <span className="h-1 rounded-l-sm bg-tm-loss/70" style={{ width: `${width}%` }} />}
                </span>
                <span className="w-1/2">
                  {positive && <span className="h-1 rounded-r-sm bg-tm-profit/70" style={{ width: `${width}%` }} />}
                </span>
              </span>

              <span className={cn('text-[13px] font-medium font-tabular text-right', positive ? 'text-tm-profit' : 'text-tm-loss')}>
                {formatCurrencyWhole(r.avgPerDay)}
              </span>
              <span className="text-[12.5px] text-muted-foreground font-tabular text-right">{r.trades.toFixed(1)}</span>
              <span className="text-[12.5px] text-muted-foreground font-tabular text-right">{r.breaks.toFixed(1)}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
