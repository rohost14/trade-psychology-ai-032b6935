/**
 * Regression test for the Chat SSE parser.
 *
 * The coach streams `data: {"text": "..."}\n\n` frames. Network chunks do NOT
 * align with those frames — a single frame can arrive split across two reads.
 * The original parser called split('\n') per chunk with no carry-over, so both
 * halves of a split frame were malformed and silently dropped by its catch{},
 * producing intermittently truncated replies.
 *
 * This test replicates the exact parsing logic used in Chat.tsx and feeds it
 * deliberately hostile chunk boundaries.
 */
import { describe, it, expect } from 'vitest';

/** Mirrors the buffered reader loop in src/pages/Chat.tsx handleSend(). */
function parseSseChunks(chunks: string[]): string {
  let accumulated = '';
  let buffer = '';
  let streamDone = false;

  const handleLine = (line: string) => {
    const trimmed = line.replace(/\r$/, '');
    if (!trimmed.startsWith('data: ')) return;
    const data = trimmed.slice(6).trim();
    if (data === '[DONE]') {
      streamDone = true;
      return;
    }
    try {
      const parsed = JSON.parse(data);
      if (parsed.text) accumulated += parsed.text;
    } catch {
      /* malformed frame */
    }
  };

  for (const chunk of chunks) {
    if (streamDone) break;
    buffer += chunk;
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';
    for (const line of lines) {
      handleLine(line);
      if (streamDone) break;
    }
  }
  if (!streamDone && buffer.trim()) handleLine(buffer);
  return accumulated;
}

const frame = (text: string) => `data: ${JSON.stringify({ text })}\n\n`;

describe('Chat SSE parser', () => {
  it('reassembles a frame split mid-JSON across two chunks', () => {
    const whole = frame('Hello world');
    const cut = Math.floor(whole.length / 2);
    expect(parseSseChunks([whole.slice(0, cut), whole.slice(cut)])).toBe('Hello world');
  });

  it('reassembles a frame split immediately after "data: "', () => {
    const whole = frame('abc');
    expect(parseSseChunks([whole.slice(0, 6), whole.slice(6)])).toBe('abc');
  });

  it('handles many frames arriving in one chunk', () => {
    const joined = frame('a') + frame('b') + frame('c');
    expect(parseSseChunks([joined])).toBe('abc');
  });

  it('handles frames split at every possible byte boundary', () => {
    const whole = frame('The quick brown fox') + frame(' jumps') + 'data: [DONE]\n\n';
    for (let i = 1; i < whole.length; i++) {
      expect(parseSseChunks([whole.slice(0, i), whole.slice(i)]))
        .toBe('The quick brown fox jumps');
    }
  });

  it('stops accumulating after [DONE]', () => {
    const s = frame('kept') + 'data: [DONE]\n\n' + frame('discarded');
    expect(parseSseChunks([s])).toBe('kept');
  });

  it('tolerates CRLF line endings', () => {
    const s = `data: ${JSON.stringify({ text: 'crlf' })}\r\n\r\n`;
    expect(parseSseChunks([s])).toBe('crlf');
  });

  it('skips genuinely malformed frames without losing later ones', () => {
    const s = 'data: {not json}\n\n' + frame('recovered');
    expect(parseSseChunks([s])).toBe('recovered');
  });

  it('flushes a trailing complete frame with no terminating newline', () => {
    expect(parseSseChunks([`data: ${JSON.stringify({ text: 'tail' })}`])).toBe('tail');
  });
});
