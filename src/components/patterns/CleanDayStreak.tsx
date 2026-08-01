import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';
import { StreakTrackerCard } from '@/components/goals/StreakTrackerCard';
import type { StreakData, DailyAdherence, StreakMilestone } from '@/types/patterns';

/**
 * Consecutive trading days without a danger or critical alert, self-contained.
 *
 * Lifted out of MyPatterns during the Alerts merge. It was ~100 lines inline in
 * that page, which meant the merged page could either duplicate it — forking
 * logic that then drifts, the exact failure the merge exists to end — or drop a
 * feature that was explicitly kept. Neither was acceptable, so it moved here and
 * both pages consume it.
 *
 * The derivation is unchanged from the original, including the two corrections
 * already baked into it:
 *  - a clean day means no `danger`/`critical` alert. An earlier version checked
 *    for 'high', a severity the backend never emits, so danger days counted as
 *    clean and the streak read high.
 *  - dates are resolved in Asia/Kolkata before taking the day-of-week, so a
 *    UTC-vs-IST offset cannot shift a session onto the wrong day.
 */

const MILESTONE_LABELS: Record<number, string> = {
  3: '3-day clean', 7: 'Week clean', 14: '2-week clean', 21: '3-week clean', 30: '30-day master',
};

const EMPTY_STREAK: StreakData = {
  current_streak_days: 0,
  longest_streak_days: 0,
  streak_start_date: null,
  daily_status: [],
  milestones_achieved: [],
};

interface RawAlert { detected_at?: string; created_at?: string; severity?: string }

/** Exported for testing: the derivation with no fetching attached. */
export function deriveStreak(rawAlerts: RawAlert[], today = new Date()): StreakData {
  const alertsByDate: Record<string, { hasDanger: boolean }> = {};
  for (const a of rawAlerts) {
    const stamp = a.detected_at || a.created_at;
    if (!stamp) continue;
    const date = new Date(stamp).toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });
    if (!alertsByDate[date]) alertsByDate[date] = { hasDanger: false };
    if (a.severity === 'danger' || a.severity === 'critical') {
      alertsByDate[date].hasDanger = true;
    }
  }

  const daily_status: DailyAdherence[] = [];
  for (let i = 0; i < 30; i++) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const dateStr = d.toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });
    const [y, mo, dy] = dateStr.split('-').map(Number);
    const dow = new Date(y, mo - 1, dy).getDay();
    if (dow === 0 || dow === 6) continue;   // NSE does not trade at the weekend
    const day = alertsByDate[dateStr];
    daily_status.push({
      date: dateStr,
      all_goals_followed: !day?.hasDanger,
      goals_broken: day?.hasDanger ? ['high_critical_alert'] : [],
      trading_day: true,
    });
  }

  let current_streak_days = 0;
  for (const day of daily_status) {
    if (!day.all_goals_followed) break;
    current_streak_days++;
  }

  let longest = 0, run = 0;
  for (const day of daily_status) {
    run = day.all_goals_followed ? run + 1 : 0;
    if (run > longest) longest = run;
  }

  const milestones_achieved: StreakMilestone[] = [3, 7, 14, 21, 30]
    .filter(d => longest >= d)
    .map(d => ({
      days: d,
      achieved_at: daily_status[d - 1]?.date ?? daily_status[daily_status.length - 1]?.date ?? '',
      label: MILESTONE_LABELS[d],
    }));

  return {
    current_streak_days,
    longest_streak_days: longest,
    streak_start_date: current_streak_days > 0
      ? (daily_status[current_streak_days - 1]?.date ?? null)
      : null,
    daily_status,
    milestones_achieved,
  };
}

export default function CleanDayStreak({ goalDays = 30 }: { goalDays?: number }) {
  const { account } = useBroker();
  const [streak, setStreak] = useState<StreakData>(EMPTY_STREAK);

  const load = useCallback(async (signal?: AbortSignal) => {
    if (!account?.id) return;
    try {
      const res = await api.get('/api/risk/alerts', { params: { hours: 720 }, signal });
      setStreak(deriveStreak(res.data?.alerts ?? []));
    } catch (err) {
      if ((err as { code?: string })?.code === 'ERR_CANCELED') return;
      // Non-fatal: the page is useful without a streak.
    }
  }, [account?.id]);

  useEffect(() => {
    const ac = new AbortController();
    load(ac.signal);
    return () => ac.abort();
  }, [load]);

  return <StreakTrackerCard streak={streak} goalDays={goalDays} />;
}
