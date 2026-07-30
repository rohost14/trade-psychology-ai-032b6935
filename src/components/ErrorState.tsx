/**
 * The single error surface for failed data loads. Turns any error (axios or generic) into
 * plain language — what went wrong, why, and what to do — with Retry + Contact support.
 *
 *   {error && <ErrorState error={error} onRetry={retry} />}          full block
 *   {error && <ErrorState error={error} onRetry={retry} compact />}  inside a section
 *
 * DESIGN_SYSTEM.md §14: loading, empty and error are three distinct renders, and a failed
 * request is NEVER rendered as an empty state. If a fetch fails, this is what shows.
 *
 * 401 is intentionally NOT special-cased here — it's handled globally (reconnect flow) and
 * rarely reaches a component. Offline/network/timeout show no contact link (it's not our bug).
 */
import { AlertTriangle, WifiOff, Clock, Ban, SearchX, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SUPPORT_EMAIL, supportMailto } from '@/lib/support';
import { cn } from '@/lib/utils';

type Kind = 'offline' | 'timeout' | 'network' | 'forbidden' | 'notfound' | 'ratelimit' | 'server';

interface AxiosLike { code?: string; response?: { status?: number } }

function classify(error: unknown): { kind: Kind; icon: React.ElementType; title: string; message: string; showContact: boolean } {
  const e = (error ?? {}) as AxiosLike;
  const status = e.response?.status;
  const code = e.code;

  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return { kind: 'offline', icon: WifiOff, title: "You're offline", message: 'Reconnect to load this — we’ll pick up automatically.', showContact: false };
  }
  if (code === 'ECONNABORTED') {
    return { kind: 'timeout', icon: Clock, title: 'Taking too long', message: 'The server is slow to respond right now. Give it another try.', showContact: false };
  }
  if (!e.response && code) {
    return { kind: 'network', icon: WifiOff, title: "Can't reach the server", message: 'Check your connection and try again.', showContact: false };
  }
  if (status === 403) {
    return { kind: 'forbidden', icon: Ban, title: 'No access', message: "You don't have permission to view this.", showContact: false };
  }
  if (status === 404) {
    return { kind: 'notfound', icon: SearchX, title: 'Not found', message: "This isn't available (it may have moved or been removed).", showContact: false };
  }
  if (status === 429) {
    return { kind: 'ratelimit', icon: Clock, title: 'Too many requests', message: 'Please wait a moment, then try again.', showContact: false };
  }
  // 5xx / unknown
  return { kind: 'server', icon: AlertTriangle, title: 'Something went wrong', message: "We hit an error loading this and have been notified. Please try again.", showContact: true };
}

export default function ErrorState({
  error, onRetry, refId, compact = false, className, message: messageOverride,
}: {
  error: unknown;
  onRetry?: () => void;
  refId?: string;        // Sentry event id, if available
  compact?: boolean;     // inline (card body) vs full block
  className?: string;
  /**
   * Replaces the classified sentence when the caller already has a specific,
   * user-meaningful reason — e.g. a sync failure that names what failed.
   * The classified title and icon are kept, so the surface stays consistent.
   */
  message?: string;
}) {
  const { icon: Icon, title, message: classified, showContact } = classify(error);
  const message = messageOverride ?? classified;

  // Inline, inside a section or a block that failed on its own. No container —
  // the surrounding section already provides the boundary.
  if (compact) {
    return (
      <div className={cn('flex flex-col items-center text-center gap-2 py-6', className)}>
        <Icon className="h-4 w-4 text-muted-foreground" />
        <p className="text-[14px] font-medium text-foreground">{title}</p>
        <p className="text-[12.5px] text-muted-foreground max-w-xs">{message}</p>
        <div className="flex items-center gap-2 mt-1">
          {onRetry && (
            <Button variant="outline" size="sm" onClick={onRetry}><RefreshCw className="h-3.5 w-3.5" /> Retry</Button>
          )}
          {showContact && (
            <a href={supportMailto({ subject: 'TradeMentor — something went wrong', ref: refId })}
               className="text-[12.5px] text-primary underline">Contact support</a>
          )}
        </div>
      </div>
    );
  }

  // Full block — this replaces a screen's content, so it must read as separate
  // from the page flow. That is §9 justification 3, and the one case where an
  // error surface earns a card.
  return (
    <div className={cn('desk-card p-8 flex flex-col items-center text-center gap-3', className)}>
      <div className="w-11 h-11 rounded-full bg-muted flex items-center justify-center">
        <Icon className="h-5 w-5 text-muted-foreground" />
      </div>
      <div>
        <p className="text-[17px] font-semibold tracking-tight text-foreground">{title}</p>
        <p className="text-[14px] text-muted-foreground mt-1 max-w-sm">{message}</p>
      </div>
      {refId && <p className="text-[11px] text-muted-foreground font-tabular">Ref: {refId}</p>}
      <div className="flex items-center gap-2.5 pt-1">
        {onRetry && (
          <Button onClick={onRetry}><RefreshCw className="h-4 w-4" /> Try again</Button>
        )}
        {showContact && (
          <a href={supportMailto({ subject: 'TradeMentor — something went wrong', ref: refId })}
             className="inline-flex items-center h-9 px-4 border border-border rounded-md text-[14px] font-medium text-foreground transition-colors duration-150 hover:bg-muted">Contact support</a>
        )}
      </div>
      {showContact && (
        <p className="text-[12.5px] text-muted-foreground">Still stuck? Email <a href={supportMailto()} className="text-primary underline">{SUPPORT_EMAIL}</a>.</p>
      )}
    </div>
  );
}
