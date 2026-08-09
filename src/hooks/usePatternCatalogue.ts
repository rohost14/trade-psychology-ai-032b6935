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

/**
 * The trader's own history with one pattern.
 *
 * This slot used to hold population statistics we invented — precise, unsourced,
 * and phrased as measurement. The trader's own record is true, checkable, and
 * the one thing no competitor can show them.
 *
 * `enough` is the gate. Below it the UI must say there is not enough history
 * yet rather than render a number computed from two trades.
 */
export interface PatternRecord {
  pattern_type: string;
  window_days: number;
  times_fired: number;
  last_seen: string | null;
  /** Flagged trades that have closed. Trails times_fired while positions are open. */
  trades_measured: number;
  win_rate: number | null;
  wins: number;
  losses: number;
  pnl: number;
  avg_pnl: number;
  enough: boolean;
  min_sample: number;
}

export function usePatternRecord(patternType: string | null) {
  return useApiQuery<PatternRecord>(
    ['pattern-record', patternType ?? ''],
    `/api/risk/patterns/${patternType}/my-record`,
    { enabled: !!patternType, staleTime: 5 * 60 * 1000 },
  );
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
