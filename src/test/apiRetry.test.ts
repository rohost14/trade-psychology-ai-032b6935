/**
 * The retry rule, and the one thing it must never do.
 *
 * A single dropped request is routine on Indian mobile, and every one of them used
 * to become a visible error the user had to react to. One silent retry removes most
 * of those.
 *
 * The danger is retrying a WRITE. If a POST reached the server and succeeded but the
 * response was lost, a retry submits it twice — a second journal entry, a second
 * tradebook import, a second acknowledgement. From the client those two cases are
 * indistinguishable, so writes are never retried. A visible error on a write is far
 * cheaper than silent duplicate data.
 *
 * These test the predicate directly rather than the interceptor, because the rule is
 * the part worth pinning: the interceptor around it is four lines.
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { __isRetryableForTest as isRetryable } from '@/lib/api';

function err(opts: {
  method?: string;
  code?: string;
  status?: number;
  retried?: boolean;
}) {
  return {
    config: { method: opts.method ?? 'get', _retried: opts.retried },
    code: opts.code,
    response: opts.status ? { status: opts.status } : undefined,
  };
}

describe('api retry rule', () => {
  const realNavigator = globalThis.navigator;

  beforeEach(() => {
    Object.defineProperty(globalThis, 'navigator', {
      value: { onLine: true },
      configurable: true,
    });
  });

  afterEach(() => {
    Object.defineProperty(globalThis, 'navigator', {
      value: realNavigator,
      configurable: true,
    });
  });

  describe('never retries a write', () => {
    it.each(['post', 'put', 'patch', 'delete'])(
      'refuses %s even on a pure network failure',
      (method) => {
        expect(isRetryable(err({ method, code: 'ERR_NETWORK' }))).toBe(false);
      },
    );

    it('refuses a write that timed out — the server may have processed it', () => {
      expect(isRetryable(err({ method: 'post', code: 'ECONNABORTED' }))).toBe(false);
    });
  });

  describe('retries a transient GET', () => {
    it('retries a network failure', () => {
      expect(isRetryable(err({ code: 'ERR_NETWORK' }))).toBe(true);
    });

    it('retries a timeout', () => {
      expect(isRetryable(err({ code: 'ECONNABORTED' }))).toBe(true);
    });

    it.each([502, 503, 504])('retries a gateway-class %i', (status) => {
      expect(isRetryable(err({ status }))).toBe(true);
    });
  });

  describe('does not retry a real answer', () => {
    it.each([400, 401, 403, 404, 409, 422, 429])(
      'leaves %i alone — it is the server answering, not failing',
      (status) => {
        expect(isRetryable(err({ status }))).toBe(false);
      },
    );

    it('leaves a plain 500 alone — it would fail again identically', () => {
      expect(isRetryable(err({ status: 500 }))).toBe(false);
    });
  });

  describe('bounds', () => {
    it('retries once, never twice', () => {
      expect(isRetryable(err({ code: 'ERR_NETWORK', retried: true }))).toBe(false);
    });

    it('does not retry while offline — the banner already explains it', () => {
      Object.defineProperty(globalThis, 'navigator', {
        value: { onLine: false },
        configurable: true,
      });
      expect(isRetryable(err({ code: 'ERR_NETWORK' }))).toBe(false);
    });
  });
});
