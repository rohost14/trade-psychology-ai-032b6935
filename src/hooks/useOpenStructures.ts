import { useApiQuery } from '@/hooks/useApiQuery';

/**
 * Multi-leg structures among the open positions.
 *
 * The classification is served, not computed here. Recognising a spread means
 * parsing symbols, matching strikes and expiries and reading direction from the
 * sign of a quantity — a second implementation on the frontend would drift from
 * the backend's exactly as the pattern-copy maps did. The label comes from the
 * server for the same reason.
 *
 * A four-leg iron condor is one decision. Showing it as four unrelated rows is
 * the same misreading that had the engine counting it as four trades against a
 * burst threshold of five.
 */

export interface OpenStructure {
  strategy_type: string;
  label: string;
  underlying: string;
  expiry_key: string;
  symbols: string[];
  leg_count: number;
}

export function useOpenStructures(enabled = true) {
  const { data } = useApiQuery<{ structures: OpenStructure[]; count: number }>(
    ['open-structures'],
    '/api/positions/structures',
    { enabled, staleTime: 60 * 1000 },
  );

  const structures = data?.structures ?? [];

  /** symbol → the structure it belongs to, for grouping rows. */
  const bySymbol = new Map<string, OpenStructure>();
  for (const s of structures) {
    for (const symbol of s.symbols) bySymbol.set(symbol, s);
  }

  return { structures, structureFor: (symbol: string) => bySymbol.get(symbol) };
}

/**
 * Order positions so the legs of one structure sit together, each group behind
 * its caption. Positions in no structure keep their original order and follow.
 *
 * Returns a flat list with an optional `groupStart` marker, so the table stays
 * one scrollable list rather than becoming a nested tree — a trader scanning
 * P&L should not have to expand anything to see it.
 */
export function groupByStructure<T extends { tradingsymbol: string }>(
  positions: T[],
  structureFor: (symbol: string) => OpenStructure | undefined,
): { position: T; structure?: OpenStructure; groupStart?: OpenStructure }[] {
  const grouped: { position: T; structure?: OpenStructure; groupStart?: OpenStructure }[] = [];
  const singles: { position: T }[] = [];
  const seen = new Set<string>();

  for (const p of positions) {
    const structure = structureFor(p.tradingsymbol);
    if (!structure) {
      singles.push({ position: p });
      continue;
    }
    const key = `${structure.underlying}:${structure.expiry_key}:${structure.strategy_type}`;
    const first = !seen.has(key);
    seen.add(key);
    grouped.push({ position: p, structure, groupStart: first ? structure : undefined });
  }

  return [...grouped, ...singles];
}
