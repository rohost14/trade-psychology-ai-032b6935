import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Standard data-fetch state so pages stop hand-rolling useEffect+useState+error.
 * Returns { data, loading, error, retry, setData }.
 *
 * Usage:
 *   const { data, loading, error, retry } = useFetch(
 *     () => api.get('/api/analytics/overview', { params: { days } }).then(r => r.data),
 *     [days],
 *   );
 *   if (loading) return <CardSkeleton />;
 *   if (error)   return <ErrorState error={error} onRetry={retry} />;
 *
 * `fetcher` should be an inline closure; refetching is controlled by `deps` (like
 * useEffect deps) + retry(), NOT by the fetcher's identity — so an inline closure is safe.
 */
export function useFetch<T>(fetcher: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [tick, setTick] = useState(0);

  // Keep the latest fetcher without making it a dependency (avoids refetch loops).
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetcherRef.current()
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(e); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const retry = useCallback(() => setTick((t) => t + 1), []);

  return { data, loading, error, retry, setData };
}
