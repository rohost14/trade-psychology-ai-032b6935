/**
 * Journal trade-id keying.
 *
 * CompletedTrades have a unique id per round, so journaling them by `id` is safe.
 * Open positions are different: a Position row is REUSED across trading episodes
 * (the same symbol+exchange+product slot is updated in place, keeping its id), so
 * journaling by raw position id lets a future, unrelated position on the same
 * contract inherit an old journal.
 *
 * Fix: journal an open position against a synthetic, per-EPISODE id derived from
 * (position id + IST trading date). It is a valid UUID (backend stores journal
 * trade_id as UUID and validates ownership via a separate source_id), stable
 * within a day, and distinct across days — so a new episode never inherits an old
 * entry. Same-day close-and-reopen of the identical contract shares one key, which
 * is acceptable.
 */

// Deterministic, RFC-4122-shaped UUID from a string. Not cryptographic — just a
// stable id with negligible collision probability at app scale (128 bits from
// four independent FNV-1a passes).
function deterministicUuid(input: string): string {
  const fnv = (s: string): number => {
    let h = 0x811c9dc5 >>> 0;
    for (let i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    return h >>> 0;
  };
  const hex = (n: number) => (n >>> 0).toString(16).padStart(8, '0');
  const raw = (hex(fnv(input)) + hex(fnv(input + '|1')) + hex(fnv(input + '|2')) + hex(fnv(input + '|3'))).split('');
  raw[12] = '5';                                  // version nibble
  raw[16] = '89ab'[parseInt(raw[16], 16) % 4];    // variant nibble
  const j = raw.join('');
  return `${j.slice(0, 8)}-${j.slice(8, 12)}-${j.slice(12, 16)}-${j.slice(16, 20)}-${j.slice(20, 32)}`;
}

/** IST calendar date (YYYY-MM-DD) — the episode boundary for open positions. */
function istDate(): string {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });
}

/** Per-episode journal trade id for an open position. */
export function positionJournalTradeId(positionId: string): string {
  return deterministicUuid(`pos:${positionId}:${istDate()}`);
}

/**
 * The trade id to journal against:
 *   - closed trade  → its own CompletedTrade id (unique per round)
 *   - open position → the per-episode synthetic id
 */
export function journalTradeId(id: string, type: 'position' | 'closed'): string {
  return type === 'position' ? positionJournalTradeId(id) : id;
}
