/**
 * The single error surface for failed data loads. Turns any error (axios or generic) into
 * plain language — what went wrong, why, and what to do — with Retry + Contact support.
 *
 *   {error && <ErrorState error={error} onRetry={retry} />}
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
  error, onRetry, refId, compact = false, className,
}: {
  error: unknown;
  onRetry?: () => void;
  refId?: string;        // Sentry event id, if available
  compact?: boolean;     // inline (card body) vs full block
  className?: string;
}) {
  const { icon: Icon, title, message, showContact } = classify(error);

  if (compact) {
    return (
      <div className={cn('flex flex-col items-center text-center gap-2 py-6 px-4', className)}>
        <Icon className="h-5 w-5 text-muted-foreground" />
        <p className="text-[13px] font-medium text-foreground">{title}</p>
        <p className="text-xs text-muted-foreground max-w-xs">{message}</p>
        <div className="flex items-center gap-2 mt-1">
          {onRetry && (
            <Button variant="outline" size="sm" onClick={onRetry}><RefreshCw className="h-3.5 w-3.5" /> Retry</Button>
          )}
          {showContact && (
            <a href={supportMailto({ subject: 'TradeMentor — something went wrong', ref: refId })}
               className="text-xs text-primary underline">Contact support</a>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={cn('tm-card p-8 flex flex-col items-center text-center gap-3', className)}>
      <div className="w-11 h-11 rounded-full bg-muted flex items-center justify-center">
        <Icon className="h-5 w-5 text-muted-foreground" />
      </div>
      <div>
        <p className="text-base font-semibold text-foreground">{title}</p>
        <p className="text-sm text-muted-foreground mt-1 max-w-sm">{message}</p>
      </div>
      {refId && <p className="text-[11px] text-muted-foreground font-mono">Ref: {refId}</p>}
      <div className="flex items-center gap-2.5 pt-1">
        {onRetry && (
          <Button onClick={onRetry}><RefreshCw className="h-4 w-4" /> Try again</Button>
        )}
        {showContact && (
          <a href={supportMailto({ subject: 'TradeMentor — something went wrong', ref: refId })}
             className="px-4 py-2 border border-border rounded-md text-sm text-foreground hover:bg-accent/20">Contact support</a>
        )}
      </div>
      {showContact && (
        <p className="text-xs text-muted-foreground">Still stuck? Email <a href={supportMailto()} className="text-primary underline">{SUPPORT_EMAIL}</a>.</p>
      )}
    </div>
  );
}
