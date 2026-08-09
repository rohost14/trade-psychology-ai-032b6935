import { useState } from 'react';
import { Lightbulb, Check, X, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useApiQuery } from '@/hooks/useApiQuery';
import { Skeleton } from '@/components/ui/skeleton';
import ErrorState from '@/components/ErrorState';
import { cn } from '@/lib/utils';

/**
 * Rules the user's own trades argue for (G3).
 *
 * The constitution has always required typing numbers into a form, and nobody
 * types. This section computes the number instead and asks for one tap. Every
 * suggestion carries the counts it came from — a rule you cannot see the
 * evidence for is just us telling you what to do, which is the blocker posture
 * the product exists to avoid.
 *
 * Accepting posts the ordinary constitution PUT, so the change is audited and
 * change-controlled exactly as a hand-typed edit would be. Nothing here applies
 * a rule on the user's behalf.
 */

interface Suggestion {
  field: string;
  current_value: number | null;
  suggested_value: number;
  headline: string;
  evidence: { label: string; value: string }[];
  confidence: 'low' | 'medium' | 'high';
  sample: Record<string, number>;
}

interface SuggestionsResponse {
  suggestions: Suggestion[];
  status: 'ok' | 'insufficient_data' | 'no_change_needed';
  reason: string | null;
  withheld?: { field: string; reason: string }[];
  context: {
    window_days: number;
    trades: number;
    sessions: number;
    min_sessions: number;
    multi_leg_detected?: boolean;
  };
}

const DISMISSED_KEY = 'tradementor_dismissed_rule_suggestions';

function readDismissed(): string[] {
  try {
    const raw = localStorage.getItem(DISMISSED_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

/** Dismissal is keyed on field+value: change the number, and it is a new proposal. */
function keyOf(s: Suggestion) {
  return `${s.field}:${s.suggested_value}`;
}

const CONFIDENCE_LABEL: Record<string, string> = {
  low: 'Early signal',
  medium: 'Consistent',
  high: 'Strong',
};

export default function RuleSuggestions() {
  const queryClient = useQueryClient();
  const { data, isPending, error, refetch } = useApiQuery<SuggestionsResponse>(
    ['constitution', 'suggestions'],
    '/api/constitution/suggestions',
  );

  const [dismissed, setDismissed] = useState<string[]>(readDismissed);
  const [applying, setApplying] = useState<string | null>(null);

  const dismiss = (s: Suggestion) => {
    const next = [...dismissed, keyOf(s)];
    setDismissed(next);
    try {
      localStorage.setItem(DISMISSED_KEY, JSON.stringify(next));
    } catch {
      /* a full quota must not break the page */
    }
  };

  const accept = async (s: Suggestion) => {
    setApplying(s.field);
    try {
      await api.put('/api/constitution/', { [s.field]: s.suggested_value });
      toast.success('Rule updated', { description: s.headline });
      queryClient.invalidateQueries({ queryKey: ['constitution'] });
      refetch();
    } catch {
      toast.error('Could not update the rule. Try again.');
    } finally {
      setApplying(null);
    }
  };

  if (isPending) {
    return (
      <div className="tm-card overflow-hidden">
        <div className="px-5 py-3.5 border-b border-border">
          <Skeleton className="h-4 w-40" />
        </div>
        <div className="p-5 space-y-3">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      </div>
    );
  }

  // A failed request is never an empty state.
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!data) return null;

  const visible = (data.suggestions ?? []).filter(s => !dismissed.includes(keyOf(s)));
  const ctx = data.context;

  return (
    <div className="tm-card overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Lightbulb className="h-4 w-4 text-tm-brand" />
          Rules your trading suggests
        </h2>
        {ctx?.sessions > 0 && (
          <span className="text-[11px] text-muted-foreground">
            from {ctx.sessions} sessions · {ctx.window_days}d
          </span>
        )}
      </div>

      <div className="p-5">
        {/* Cold start and "nothing to change" are different answers, and saying
            the wrong one teaches the user the feature is broken. */}
        {visible.length === 0 && (
          <p className="text-sm text-muted-foreground">
            {data.status === 'insufficient_data'
              ? data.reason
              : 'Your current rules already match what your trading data supports.'}
          </p>
        )}

        {visible.length > 0 && (
          <ul className="space-y-4">
            {visible.map(s => (
              <li key={s.field} className="border-b border-border last:border-0 pb-4 last:pb-0">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground">{s.headline}</p>
                    <p className="text-[11px] text-muted-foreground mt-0.5">
                      {s.current_value == null
                        ? 'You have no rule set for this'
                        : `Currently ${s.current_value}`}
                      {' · '}
                      <span className={cn(
                        s.confidence === 'high' && 'text-tm-profit',
                        s.confidence === 'low' && 'text-tm-obs',
                      )}>
                        {CONFIDENCE_LABEL[s.confidence] ?? s.confidence}
                      </span>
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button
                      onClick={() => accept(s)}
                      disabled={applying !== null}
                      className="h-8 px-3 rounded-lg bg-tm-brand text-white text-[12px] font-medium flex items-center gap-1.5 disabled:opacity-50"
                    >
                      {applying === s.field
                        ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        : <Check className="h-3.5 w-3.5" />}
                      Set rule
                    </button>
                    <button
                      onClick={() => dismiss(s)}
                      disabled={applying !== null}
                      aria-label="Dismiss suggestion"
                      className="h-8 w-8 rounded-lg border border-border flex items-center justify-center text-muted-foreground hover:text-foreground disabled:opacity-50"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>

                {/* The evidence is the point. Without it this is an instruction. */}
                <dl className="mt-2.5 rounded-lg border border-border divide-y divide-border">
                  {s.evidence.map(e => (
                    <div key={e.label} className="flex items-center justify-between gap-3 px-3 py-2">
                      <dt className="text-[12px] text-muted-foreground">{e.label}</dt>
                      <dd className="text-[12px] font-medium text-foreground text-right">{e.value}</dd>
                    </div>
                  ))}
                </dl>
              </li>
            ))}
          </ul>
        )}

        {/* Withheld suggestions are stated, not hidden — an unexplained absence
            reads as the feature not working. */}
        {(data.withheld ?? []).map(w => (
          <p key={w.field} className="text-[11px] text-muted-foreground mt-3 leading-relaxed">
            {w.reason}
          </p>
        ))}
      </div>
    </div>
  );
}
