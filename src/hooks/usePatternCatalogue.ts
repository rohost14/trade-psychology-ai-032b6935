import { useApiQuery } from '@/hooks/useApiQuery';

/**
 * What every behaviour pattern observes, and why it matters.
 *
 * This used to be three `Record<string, string>` maps inside AlertDetailSheet,
 * keyed on pattern name with no normalisation. Engine v2 renamed the detectors,
 * the maps kept the v1 keys, and the lookups silently returned undefined — so
 * an overtrading alert, our most common, opened a detail panel with no facts,
 * no explanation and no context. There was no error, because a missing key is
 * not a failure in TypeScript any more than it is in Python.
 *
 * The copy now comes from the detector registry, which is the only place that
 * knows what patterns exist. A rename cannot orphan it, and a backend contract
 * test fails if a pattern has no copy or copy has no pattern.
 *
 * Identical for every user and effectively immutable between deploys, so it is
 * fetched once and never refetched.
 */

export interface PatternInfo {
  pattern_type: string;
  label: string;
  observes: string;
  explanation: string;
  nature: string | null;
  disposition: string;
  trigger: string;
  guardian_eligible: boolean;
  version: string | null;
}

interface CatalogueResponse {
  patterns: PatternInfo[];
  count: number;
  severity_order: string[];
}

export function usePatternCatalogue() {
  const { data, isPending, error } = useApiQuery<CatalogueResponse>(
    ['pattern-catalogue'],
    '/api/risk/patterns',
    { staleTime: Infinity },
  );

  const byType = new Map<string, PatternInfo>(
    (data?.patterns ?? []).map(p => [p.pattern_type, p]),
  );

  return {
    patterns: data?.patterns ?? [],
    /** Copy for one pattern, or undefined if the catalogue has not loaded. */
    lookup: (patternType: string) => byType.get(patternType),
    isPending,
    error,
  };
}
