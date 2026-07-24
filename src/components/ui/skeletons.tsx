/**
 * Layout-mirroring skeletons for content loads. Rule of thumb:
 *   content area loading  → a skeleton that mirrors the real layout (these)
 *   button / inline action → a spinner (Loader2 / animate-spin), NOT a skeleton
 * Built on the base <Skeleton>. Use these instead of ad-hoc "Loading…" text or bare spinners.
 */
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

/** A tm-card with a header strip and body lines. */
export function CardSkeleton({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn('tm-card overflow-hidden', className)}>
      <div className="px-5 py-3.5 border-b border-border">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-3 w-56 mt-2" />
      </div>
      <div className="p-5 space-y-3">
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton key={i} className={cn('h-4', i === lines - 1 ? 'w-2/3' : 'w-full')} />
        ))}
      </div>
    </div>
  );
}

/** A row of KPI stat tiles. */
export function StatRowSkeleton({ count = 4, className }: { count?: number; className?: string }) {
  return (
    <div className={cn('grid gap-3', className)} style={{ gridTemplateColumns: `repeat(${count}, minmax(0, 1fr))` }}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="tm-card p-4 space-y-2.5">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-7 w-24" />
          <Skeleton className="h-3 w-16" />
        </div>
      ))}
    </div>
  );
}

/** A list of rows (e.g. alerts, sessions, trades). */
export function ListSkeleton({ rows = 5, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 py-2">
          <Skeleton className="h-8 w-8 rounded-lg shrink-0" />
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

/** A table with header + rows. */
export function TableSkeleton({ rows = 6, cols = 4, className }: { rows?: number; cols?: number; className?: string }) {
  return (
    <div className={cn('tm-card overflow-hidden', className)}>
      <div className="grid gap-3 px-5 py-3 border-b border-border" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
        {Array.from({ length: cols }).map((_, i) => <Skeleton key={i} className="h-3 w-16" />)}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="grid gap-3 px-5 py-3 border-b border-border last:border-0" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
          {Array.from({ length: cols }).map((_, c) => <Skeleton key={c} className={cn('h-4', c === 0 ? 'w-3/4' : 'w-1/2')} />)}
        </div>
      ))}
    </div>
  );
}

/** A chart placeholder block. */
export function ChartSkeleton({ height = 240, className }: { height?: number; className?: string }) {
  return (
    <div className={cn('tm-card p-5', className)}>
      <Skeleton className="h-4 w-40 mb-4" />
      <Skeleton className="w-full rounded-lg" style={{ height }} />
    </div>
  );
}
