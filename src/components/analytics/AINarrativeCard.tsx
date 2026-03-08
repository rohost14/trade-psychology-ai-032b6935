import { useState, useEffect } from 'react';
import { Loader2, Brain, RefreshCw, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';

interface AINarrativeCardProps {
  tab: 'overview' | 'behavior' | 'performance' | 'risk';
  days: number;
}

interface NarrativeData {
  narrative: string | null;
  key_insight: string | null;
  action_item: string | null;
  cached: boolean;
  generated_at: string | null;
}

export default function AINarrativeCard({ tab, days }: AINarrativeCardProps) {
  const [data, setData] = useState<NarrativeData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [error, setError] = useState(false);

  const fetchNarrative = async (force = false) => {
    try {
      if (force) setIsRegenerating(true);
      else setIsLoading(true);
      setError(false);

      const res = await api.get('/api/analytics/ai-summary', {
        params: { tab, days, force },
      });
      setData(res.data);
    } catch {
      setError(true);
    } finally {
      setIsLoading(false);
      setIsRegenerating(false);
    }
  };

  useEffect(() => {
    fetchNarrative();
  }, [tab, days]);

  if (isLoading) {
    return (
      <div className="bg-gradient-to-r from-indigo-500/5 to-purple-500/5 border border-indigo-500/20 rounded-lg p-4 animate-pulse">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Generating AI analysis...
        </div>
      </div>
    );
  }

  if (error || !data?.narrative) {
    return null; // Graceful degradation — don't show card if AI fails
  }

  return (
    <div className="bg-gradient-to-r from-indigo-500/5 to-purple-500/5 border border-indigo-500/20 rounded-lg p-4">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-indigo-500" />
          <span className="text-xs font-medium text-indigo-600 dark:text-indigo-400 uppercase tracking-wide">
            AI Analysis
          </span>
          {data.cached && (
            <span className="text-[10px] bg-muted text-muted-foreground px-1.5 py-0.5 rounded">
              cached
            </span>
          )}
        </div>
        <button
          onClick={() => fetchNarrative(true)}
          disabled={isRegenerating}
          className="text-muted-foreground hover:text-foreground transition-colors"
          title="Regenerate"
        >
          <RefreshCw className={cn('h-3.5 w-3.5', isRegenerating && 'animate-spin')} />
        </button>
      </div>

      <p className="text-sm text-foreground leading-relaxed">{data.narrative}</p>

      {data.key_insight && (
        <p className="text-sm text-indigo-600 dark:text-indigo-400 font-medium mt-2">
          {data.key_insight}
        </p>
      )}

      {data.action_item && (
        <p className="text-xs text-muted-foreground mt-1.5 italic">
          {data.action_item}
        </p>
      )}
    </div>
  );
}
