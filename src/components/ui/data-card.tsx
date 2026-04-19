import { cn } from '@/lib/utils';

interface DataCardProps {
  /** Card section title */
  title?: React.ReactNode;
  /** Optional subtitle / context below the title */
  subtitle?: React.ReactNode;
  /** Optional action(s) rendered right-aligned in the header */
  action?: React.ReactNode;
  /** If true, body has no padding (table handles its own row padding) */
  noPadding?: boolean;
  /** Additional classes on the root element */
  className?: string;
  children: React.ReactNode;
}

/**
 * Standard data surface for TradeMentor AI.
 *
 * Anatomy:
 * ┌─────────────────────────────────────────┐
 * │  Title                    [action btn]  │  ← px-5 py-3.5 + border-b
 * │  subtitle                               │
 * ├─────────────────────────────────────────┤
 * │  content                                │  ← p-5 (or p-0 if noPadding)
 * └─────────────────────────────────────────┘
 *
 * Rules:
 * - Always rounded-xl (12px)
 * - Always overflow-hidden
 * - Always shadow-card via .tm-card
 * - Header border-b uses border-border
 */
export function DataCard({ title, subtitle, action, noPadding, className, children }: DataCardProps) {
  return (
    <div className={cn('tm-card', className)}>
      {(title || action) && (
        <div className="flex items-start justify-between gap-3 px-5 py-3.5 border-b border-border">
          <div className="min-w-0">
            {title && (
              <div className="t-heading-sm text-foreground truncate">
                {title}
              </div>
            )}
            {subtitle && (
              <div className="t-body-sm text-muted-foreground mt-0.5">
                {subtitle}
              </div>
            )}
          </div>
          {action && (
            <div className="shrink-0 flex items-center gap-2">
              {action}
            </div>
          )}
        </div>
      )}
      <div className={cn(!noPadding && 'p-5')}>
        {children}
      </div>
    </div>
  );
}
