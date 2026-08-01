import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { formatPatternName } from '@/contexts/AlertContext';
import { formatRelativeTime } from '@/lib/formatters';
import { CardSkeleton } from '@/components/ui/skeletons';

/**
 * Which behaviours keep repeating, ranked by how often.
 *
 * Extracted from Analytics' Behaviour tab when patterns moved onto Alerts.
 * Counts and recency only — deliberately no money. Analytics owns quantified
 * cost; this page owns the loop and the repetition, so neither recomputes the
 * other's story.
 *
 * The cross-link back to response stats stays, because "how you responded"
 * lives on the same page now.
 */

interface PatternRow {
  pattern_type: string;
  count: number;
  last_detected: string;
}
interface Response {
  patterns?: PatternRow[];
  by_pattern?: PatternRow[];
}

export default function PatternFrequencyCard({ days = 30 }: { days?: number }) {
  const [rows, setRows] = useState<PatternRow[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.get<Response>('/api/analytics/risk-metrics', { params: { days } })
      .then(r => {
        if (cancelled) return;
        const d = r.data ?? {};
        setRows(d.patterns ?? d.by_pattern ?? []);
      })
      .catch(() => { if (!cancelled) setRows(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days]);

  if (loading) return <CardSkeleton lines={4} />;
  if (!rows?.length) return null;

  const maxCount = Math.max(...rows.map(r => r.count), 1);

  return (
    <section className="tm-card overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border flex items-baseline justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold text-sm">What keeps repeating</p>
          <p className="text-[11.5px] text-muted-foreground mt-0.5">
            How often each behaviour fired, and when you last saw it.
          </p>
        </div>
        <span className="text-[11px] text-muted-foreground shrink-0">last {days} days</span>
      </div>

      <div className="divide-y divide-border">
        {rows.map(p => (
          <div key={p.pattern_type} className="px-5 py-3 min-h-[44px] sm:min-h-0">
            <div className="flex items-center justify-between gap-4 mb-1.5">
              <span className="text-[13.5px] font-medium truncate">{formatPatternName(p.pattern_type)}</span>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-[11px] text-muted-foreground">last {formatRelativeTime(p.last_detected)}</span>
                <span className="text-[13px] font-semibold font-tabular">{p.count}×</span>
              </div>
            </div>
            <div className="h-1 rounded-full bg-muted/60 overflow-hidden">
              <div
                className="h-full rounded-full bg-tm-obs"
                style={{ width: `${Math.round((p.count / maxCount) * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
