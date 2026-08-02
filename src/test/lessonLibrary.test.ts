import { describe, it, expect } from 'vitest';
import { collectLessons } from '@/components/journal/LessonLibrary';

const e = (id: string, created_at: string, lessons?: string | null) => ({ id, created_at, lessons });

describe('collectLessons', () => {
  it('returns newest first', () => {
    const out = collectLessons([
      e('a', '2026-07-01T10:00:00Z', 'older'),
      e('b', '2026-08-01T10:00:00Z', 'newer'),
    ]);
    expect(out.map(l => l.text)).toEqual(['newer', 'older']);
  });

  it('skips entries with no lesson', () => {
    const out = collectLessons([
      e('a', '2026-08-01T10:00:00Z', null),
      e('b', '2026-08-02T10:00:00Z', '   '),
      e('c', '2026-08-03T10:00:00Z', 'kept'),
    ]);
    expect(out).toHaveLength(1);
    expect(out[0].text).toBe('kept');
  });

  it('collapses the same lesson relearned, keeping the most recent date', () => {
    // A lesson you write twice is still one lesson; showing it twice would make
    // the library look padded and bury the others.
    const out = collectLessons([
      e('old', '2026-07-01T10:00:00Z', 'Cut size when tired'),
      e('new', '2026-08-01T10:00:00Z', 'Cut size when tired'),
    ]);
    expect(out).toHaveLength(1);
    expect(out[0].date).toBe('2026-08-01T10:00:00Z');
  });

  it('treats casing and surrounding space as the same lesson', () => {
    const out = collectLessons([
      e('a', '2026-08-02T10:00:00Z', 'Cut size when tired'),
      e('b', '2026-08-01T10:00:00Z', '  cut size when TIRED  '),
    ]);
    expect(out).toHaveLength(1);
  });

  it('trims what it stores', () => {
    const out = collectLessons([e('a', '2026-08-01T10:00:00Z', '  spaced  ')]);
    expect(out[0].text).toBe('spaced');
  });

  it('returns nothing when no entry carries a lesson', () => {
    expect(collectLessons([e('a', '2026-08-01T10:00:00Z')])).toEqual([]);
  });
});
