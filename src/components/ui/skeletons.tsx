/**
 * Layout-mirroring skeletons for content loads.
 *
 * DESIGN_SYSTEM.md §14: skeleton for content, spinner for actions. A skeleton
 * must mirror the shape of what is loading — same block structure, same row
 * count, same column widths — so nothing jumps when data arrives.
 *
 *   content area loading   → one of these
 *   button / inline action → a spinner (Loader2), NOT a skeleton
 *
 * §9: a plain labelled section is the default block, so `SectionSkeleton` is the
 * one to reach for. `CardSkeleton` exists for the cases §9 actually justifies a
 * card.
 */
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

/**
 * The default block: label strip, divider, body lines. No border, no card —
 * mirrors a `.section-head` section.
 */
export function SectionSkeleton({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={className}>
      <div className="h-11 border-b border-border flex items-center justify-between">
        <Skeleton className="h-3 w-32" />
        <Skeleton className="h-3 w-16" />
      </div>
      <div className="py-4 space-y-3">
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton key={i} className={cn('h-4', i === lines - 1 ? 'w-2/3' : 'w-full')} />
        ))}
      </div>
    </div>
  );
}

/** A card with a header strip and body lines. Only where §9 justifies a card. */
export function CardSkeleton({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn('desk-card overflow-hidden', className)}>
      <div className="px-4 sm:px-6 h-11 border-b border-border flex items-center">
        <Skeleton className="h-3 w-32" />
      </div>
      <div className="px-4 sm:px-6 py-4 space-y-3">
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton key={i} className={cn('h-4', i === lines - 1 ? 'w-2/3' : 'w-full')} />
        ))}
      </div>
    </div>
  );
}

/**
 * A dense metric strip — hairline-separated cells, per the MetricStrip recipe
 * in §17. Deliberately not a grid of padded KPI cards: that shape is banned
 * (§4), so the skeleton must not promise it.
 */
export function StatRowSkeleton({ count = 4, className }: { count?: number; className?: string }) {
  return (
    <div
      className={cn('grid gap-px bg-border rounded-lg overflow-hidden border border-border', className)}
      style={{ gridTemplateColumns: `repeat(${count}, minmax(0, 1fr))` }}
    >
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="bg-card px-3 py-2.5 space-y-2">
          <Skeleton className="h-2.5 w-16" />
          <Skeleton className="h-4 w-20" />
        </div>
      ))}
    </div>
  );
}

/** A list of rows (alerts, sessions, trades). Dense rows, hairline dividers. */
export function ListSkeleton({ rows = 5, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn('divide-y divide-border', className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 py-3.5">
          <Skeleton className="h-7 w-7 rounded-md shrink-0" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-3.5 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
          <Skeleton className="h-4 w-16 shrink-0" />
        </div>
      ))}
    </div>
  );
}

/**
 * A table: column headers then rows, running edge to edge (§18). No card —
 * a table lives inside a section, not inside a container of its own.
 */
export function TableSkeleton({ rows = 6, cols = 4, className }: { rows?: number; cols?: number; className?: string }) {
  const template = { gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` };

  return (
    <div className={className}>
      <div className="grid gap-3 py-2.5 border-b border-border" style={template}>
        {Array.from({ length: cols }).map((_, i) => <Skeleton key={i} className="h-2.5 w-14" />)}
      </div>
      <div className="divide-y divide-border">
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="grid gap-3 py-3.5" style={template}>
            {Array.from({ length: cols }).map((_, c) => (
              <Skeleton key={c} className={cn('h-4', c === 0 ? 'w-3/4' : 'w-1/2')} />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/** A chart placeholder: label, then the plot area at its real height. */
export function ChartSkeleton({ height = 240, className }: { height?: number; className?: string }) {
  return (
    <div className={className}>
      <div className="h-11 border-b border-border flex items-center">
        <Skeleton className="h-3 w-32" />
      </div>
      <div className="py-4">
        <Skeleton className="w-full rounded-md" style={{ height }} />
      </div>
    </div>
  );
}
