/**
 * The one way to read data from the API.
 *
 * Every page used to hand-roll the same block: useState for data, useState for
 * loading, useState for error, a useEffect, an api.get, a try/catch. Around forty
 * copies of it. That repetition caused real bugs, not just noise:
 *
 *   - Loading and error were optional, because they were manual. Settings shipped
 *     with no error state at all and silently rendered hardcoded defaults as if
 *     they were saved settings.
 *   - Nothing was cached, so leaving a page and coming back re-ran every request
 *     and re-showed every skeleton.
 *   - Requests raced. Change a filter twice quickly and the FIRST response could
 *     land second, leaving stale data on screen with no error and no clue.
 *
 * This hook makes all three structural. `signal` is passed through to axios, so a
 * superseded request is cancelled rather than left to land late — that removes the
 * race class outright rather than guarding against it at each call site.
 *
 * Pair it with ErrorState, which understands the AxiosError this throws:
 *
 *     const { data, isPending, error, refetch } = useApiQuery<Rules>(
 *       ['constitution'], '/api/constitution/',
 *     );
 *     if (error) return <ErrorState error={error} onRetry={refetch} />;
 *
 * NOT for live data. Dashboard positions and Alerts are driven by the WebSocket,
 * and Chat streams over fetch. Putting a polling cache in front of a socket means
 * two sources of truth fighting over the same state.
 */
import { useQuery, type UseQueryOptions } from '@tanstack/react-query';
import { api } from '@/lib/api';

type Params = Record<string, string | number | boolean | undefined | null>;

export function useApiQuery<T>(
  key: readonly unknown[],
  url: string,
  options?: {
    params?: Params;
    enabled?: boolean;
    staleTime?: number;
    select?: (data: T) => unknown;
  },
) {
  const { params, ...queryOptions } = options ?? {};

  return useQuery<T>({
    // Params belong in the key. Without them a filter change reads the previous
    // filter's cached result and looks like the backend ignored the input.
    queryKey: params ? [...key, params] : key,
    queryFn: async ({ signal }) => {
      const res = await api.get<T>(url, { params, signal });
      return res.data;
    },
    ...(queryOptions as Partial<UseQueryOptions<T>>),
  });
}
