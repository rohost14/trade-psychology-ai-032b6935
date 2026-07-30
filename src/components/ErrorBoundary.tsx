import { Component, ErrorInfo, ReactNode } from 'react';
import * as Sentry from '@sentry/react';
import { SUPPORT_EMAIL, supportMailto } from '@/lib/support';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  eventId: string | null;
  error?: Error;
  componentStack?: string;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, eventId: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, eventId: null, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    const eventId = Sentry.captureException(error, {
      extra: { componentStack: info.componentStack },
    });
    this.setState({ eventId, error, componentStack: info.componentStack ?? undefined });
    // Also log locally so devs see it without Sentry configured
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      const isDev = import.meta.env.DEV;
      return (
        <div className="min-h-screen flex items-center justify-center bg-background p-8">
          <div className="max-w-lg text-center space-y-4">
            <h1 className="text-[22px] font-semibold tracking-tight text-foreground">Something went wrong</h1>
            <p className="text-[14px] text-muted-foreground">
              An unexpected error occurred. Our team has been notified.
            </p>
            {isDev && this.state.error && (
              // Dev-only stack trace. `text-loss` rather than a raw palette red.
              // Monospace is correct here — it's code, not data.
              <pre className="text-left text-[12.5px] bg-muted p-4 rounded-md overflow-auto max-h-60 text-loss whitespace-pre-wrap font-mono">
                {String(this.state.error)}
                {'\n\n'}
                {this.state.componentStack}
              </pre>
            )}
            {this.state.eventId && (
              <p className="text-[11px] text-muted-foreground font-tabular">
                Ref: {this.state.eventId}
              </p>
            )}
            <div className="flex items-center justify-center gap-3 pt-1">
              <button
                onClick={() => window.location.reload()}
                className="inline-flex items-center h-9 px-4 bg-primary text-primary-foreground rounded-md text-[14px] font-medium transition-colors duration-150 hover:bg-primary/90"
              >
                Reload page
              </button>
              <a
                href={supportMailto({ subject: 'TradeMentor — something went wrong', ref: this.state.eventId ?? undefined })}
                className="inline-flex items-center h-9 px-4 border border-border rounded-md text-[14px] font-medium text-foreground transition-colors duration-150 hover:bg-muted"
              >
                Contact support
              </a>
            </div>
            <p className="text-[12.5px] text-muted-foreground">
              Still stuck? Email us at{' '}
              <a href={supportMailto()} className="text-primary underline">{SUPPORT_EMAIL}</a>.
            </p>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
