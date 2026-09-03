/**
 * Trader-facing claims must have provenance.
 *
 * WHAT THIS EXISTS TO PREVENT
 *
 * On 2026-09-03 every quantitative claim that could reach a trader was
 * audited against primary sources. Twenty-six were found. NOT ONE resolved to
 * a citable source. Four were attributed to SEBI on the Dashboard's empty
 * state - the screen shown to a user who has never traded - and SEBI publishes
 * none of them; the "2.7x faster" was Odean (1998) at roughly 1.5x, from US
 * brokerage data, and pointed the OPPOSITE way to this book's own measurement,
 * which is why `holding_loser` had been retired the day before.
 *
 * Those were removed in d26c994. The next day a scan found
 * "Proven pattern disruption to stop cascade losses" still live on the landing
 * page - a banned claim, already logged as a P0, that TWO manual audit passes
 * had walked past. Both passes searched for digits. That claim has none.
 *
 * So this guard does not look for numbers. Percentages, rupees, multipliers
 * and trader-specific metrics are the product's entire job and are not
 * suspicious. It looks for CLAIM SHAPES: a statement about traders in general,
 * borrowed authority, money that was never lost, an asserted ratio, or a
 * forecast.
 *
 * THE CONTRACT
 *
 * A literal matching a marker must appear in docs/copy/claims.allowlist.json
 * with one of four categories, each of which requires a real answer to
 * "where did this come from":
 *
 *   DERIVED - computed from this trader's own data; `source` names the producer
 *   CITED   - external claim with a primary source; `source` is a citation
 *   FIXTURE - demo data mirroring a real API field; `source` names the field
 *   LEGAL   - regulatory or policy text
 *
 * There is no UNSOURCED category and no inline suppression. The only ways past
 * this test are a citation, a named producer, or deleting the claim. That is
 * deliberate: the audit found 26 claims and zero sources, so any escape hatch
 * reproduces the problem it was built to stop.
 *
 * Entries are keyed by a hash of the matched LINE, not a line number, so
 * moving code does not churn the allowlist but EDITING a claim sends it back
 * for review.
 *
 * KNOWN GAPS, stated rather than hidden:
 *   - LLM output is uncoverable. The coach generates free text at runtime and
 *     no static test reaches it. Its offline FALLBACK strings are covered.
 *   - Claims assembled across lines (f-string fragments appended to a list)
 *     are scanned per line, not as the finished sentence.
 *   - CITED cannot be verified here. A bad citation passes.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve, join } from 'node:path';

const ROOT = process.cwd();
const markers = JSON.parse(
  readFileSync(resolve(ROOT, 'docs/copy/claim_markers.json'), 'utf-8'),
);
const allowlist: AllowEntry[] = JSON.parse(
  readFileSync(resolve(ROOT, 'docs/copy/claims.allowlist.json'), 'utf-8'),
).entries;

interface AllowEntry {
  file: string;
  literal_sha256: string;
  category: 'DERIVED' | 'CITED' | 'FIXTURE' | 'LEGAL';
  source: string;
  verified: string;
  note?: string;
}

const CATEGORIES = ['DERIVED', 'CITED', 'FIXTURE', 'LEGAL'];

/** Every marker pattern, flattened, keeping its group name for the message. */
const RULES: Array<{ group: string; re: RegExp }> = Object.entries(
  markers.marker_groups as Record<string, { patterns: string[] }>,
).flatMap(([group, g]) => g.patterns.map(p => ({ group, re: new RegExp(p, 'i') })));

const sha = (s: string) => createHash('sha256').update(s).digest('hex').slice(0, 16);

/**
 * The readable text of a file, with comments removed.
 *
 * REPLACED A CHARACTER SCANNER, 2026-09-03, because that scanner had blind
 * spots. It tracked string state to pull out literals, and in TSX an apostrophe
 * in ordinary prose — `<p>Don't…</p>` — reads as an opening quote. Everything
 * up to the next apostrophe was swallowed as if it were one string, so whole
 * regions of a file were never scanned. Proved by planting the original
 * "Circuit breaker prompts" claim in Welcome.tsx: the scanner extracted 417
 * literals from that file and not one of them contained it.
 *
 * Matching whole text is strictly more sensitive and costs almost nothing in
 * precision here, because every marker is a long English phrase rather than a
 * token. Measured before switching: across 164 frontend files it produced ONE
 * hit that the literal scanner would not have, and that hit was a marker bug
 * (`% of them` matching a trader's own win rate), now fixed.
 *
 * Comments still go, and that still matters: this repo's idiom is to QUOTE a
 * removed claim in the comment that removes it, and a guard that fails on its
 * own removal notes gets switched off within a week. `//` is only treated as a
 * comment when it is not part of a `://` URL.
 */
function readableText(src: string): string {
  const noBlocks = src.replace(/\/\*[\s\S]*?\*\//g, ' ');
  return noBlocks
    .split('\n')
    .map(line => {
      let i = line.indexOf('//');
      while (i > 0 && line[i - 1] === ':') i = line.indexOf('//', i + 2);
      return i >= 0 ? line.slice(0, i) : line;
    })
    .join('\n');
}

function walk(dir: string, exts: string[], exclude: string[]): string[] {
  const files: string[] = [];
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    const posix = full.split('\\').join('/');
    if (exclude.some(x => posix.includes(x))) continue;
    if (statSync(full).isDirectory()) files.push(...walk(full, exts, exclude));
    else if (exts.some(e => name.endsWith(e))) files.push(posix);
  }
  return files;
}

const { roots, extensions, exclude_contains, marketing_surfaces } =
  markers.scope.frontend;

const sourceFiles = roots.flatMap((r: string) =>
  walk(resolve(ROOT, r), extensions, exclude_contains),
).map((f: string) => f.replace(ROOT.split('\\').join('/') + '/', ''));

describe('marker vocabulary', () => {
  it('loaded and is not empty', () => {
    // A wrong path silently disabling the guard is the failure mode that makes
    // a test like this worthless. Fail loudly instead.
    expect(RULES.length).toBeGreaterThan(20);
    expect(sourceFiles.length).toBeGreaterThan(100);
  });

  it('allowlist entries are well formed', () => {
    for (const e of allowlist) {
      expect(CATEGORIES, `${e.file}: bad category ${e.category}`).toContain(e.category);
      expect(e.source?.trim().length, `${e.file}: empty source`).toBeGreaterThan(10);
      expect(e.literal_sha256, `${e.file}: missing hash`).toMatch(/^[0-9a-f]{16}$/);
    }
  });
});

describe('trader-facing claims have provenance', () => {
  it('no unallowlisted claim shape in src/', () => {
    const violations: string[] = [];
    for (const file of sourceFiles) {
      const text = readableText(readFileSync(resolve(ROOT, file), 'utf-8'));
      text.split('\n').forEach(rawLine => {
        const line = rawLine.trim();
        if (!line) return;
        const hit = RULES.find(r => r.re.test(line));
        if (!hit) return;
        // Keyed on the matched LINE rather than a parsed literal: editing the
        // claim sends it back for review, which is what we want anyway.
        const h = sha(line);
        const allowed = allowlist.some(e => e.file === file && e.literal_sha256 === h);
        if (!allowed) {
          violations.push(
            `\n  ${file}\n    [${hit.group}] "${line.slice(0, 140)}"\n    hash: ${h}`,
          );
        }
      });
    }
    expect(
      violations,
      `Unsourced trader-facing claim(s).\n${violations.join('')}\n\n` +
        `Fix by REMOVING the claim, or - only with genuine provenance - add to\n` +
        `docs/copy/claims.allowlist.json as DERIVED / CITED / FIXTURE / LEGAL.\n` +
        `There is no UNSOURCED category. Do not source a claim to make CI green.\n`,
    ).toEqual([]);
  });

  it('marketing surfaces do not claim the product blocks or guarantees', () => {
    // A DIFFERENT CLASS from the markers above, and the one they missed.
    // "Circuit breaker prompts suggesting a cooldown period" was live on the
    // landing page: no digit, no statistic, no borrowed authority — and false,
    // because nothing here blocks a trade. Found by hand, not by this file.
    //
    // Scoped to marketing surfaces on evidence, not caution: repo-wide these
    // markers returned 6 hits and all 6 were legitimate (a real Kite API
    // circuit breaker, a "non-blocking" log line, accurate opt-in rule copy,
    // two internal comments). Here they return zero.
    const rules: RegExp[] = markers.capability_markers.patterns.map(
      (p: string) => new RegExp(p, 'i'),
    );
    const violations: string[] = [];
    for (const file of sourceFiles) {
      if (!marketing_surfaces.some((s: string) => file.startsWith(s))) continue;
      const text = readableText(readFileSync(resolve(ROOT, file), 'utf-8'));
      text.split('\n').forEach(rawLine => {
        const line = rawLine.trim();
        if (!line) return;
        const hit = rules.find(r => r.test(line));
        if (hit) violations.push(`\n  ${file}\n    "${line.slice(0, 140)}"`);
      });
    }
    expect(
      violations,
      `Marketing copy claims a capability this product does not have.${violations.join('')}\n\n` +
        `Nothing here blocks, halts or places an order — the philosophy is\n` +
        `"mirror, not blocker". Describe what it actually does.\n`,
    ).toEqual([]);
  });

  it('marketing surfaces do not sell a retired detector', () => {
    // The landing page was demonstrating `Early Exit` and `Meltdown Cascade`
    // the day after both detectors were retired.
    const labels: string[] = markers.retired_detector_labels.labels;
    const violations: string[] = [];
    for (const file of sourceFiles) {
      if (!marketing_surfaces.some((s: string) => file.startsWith(s))) continue;
      const text = readableText(readFileSync(resolve(ROOT, file), 'utf-8'));
      for (const label of labels) {
        if (text.includes(label)) violations.push(`${file}: "${label}"`);
      }
    }
    expect(
      violations,
      `Retired detector named on a marketing surface:\n  ${violations.join('\n  ')}\n\n` +
        `The detector no longer runs. Remove it rather than renaming it.\n`,
    ).toEqual([]);
  });
});

describe('the retired-label list cannot rot', () => {
  it('covers every entry in RETIRED_PATTERN_TYPES', async () => {
    const { RETIRED_PATTERN_TYPES, formatPatternName } = await import('@/contexts/AlertContext');
    const labels: string[] = markers.retired_detector_labels.labels;
    for (const t of RETIRED_PATTERN_TYPES) {
      expect(
        labels,
        `${t} is retired but its display name "${formatPatternName(t)}" is not in ` +
          `claim_markers.json retired_detector_labels - marketing could still sell it.`,
      ).toContain(formatPatternName(t));
    }
  });
});
