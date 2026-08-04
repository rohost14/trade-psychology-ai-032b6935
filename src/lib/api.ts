import axios, { AxiosRequestConfig, AxiosResponse } from 'axios';
import { toast } from 'sonner';
import { isGuestMode, getGuestResponse } from './guestMode';
import { getImpersonationToken } from './impersonation';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Throttle error toasts so a page firing several failing calls at once shows ONE
// message, not a stack. 401 (reconnect flow) and 503 (maintenance page) are handled
// elsewhere and never toast here.
let _lastErrToastAt = 0;
function notifyError(message: string) {
  const now = Date.now();
  if (now - _lastErrToastAt < 4000) return;
  _lastErrToastAt = now;
  toast.error(message);
}

export const AUTH_TOKEN_KEY = 'tradementor_auth_token';

/** The active bearer token: a per-tab admin impersonation token if present,
 *  otherwise the user's own session token. Use everywhere instead of reading
 *  localStorage(AUTH_TOKEN_KEY) directly. */
export function getAuthToken(): string | null {
  return getImpersonationToken() || localStorage.getItem(AUTH_TOKEN_KEY);
}

/** Safely extract a human-readable string from a FastAPI error detail.
 *  FastAPI 422s return detail as an array of Pydantic objects {type,loc,msg,input,ctx}.
 *  Passing that array as a React child crashes with "Objects are not valid as a React child". */
export function apiDetailString(detail: unknown, fallback: string): string {
  if (!detail) return fallback;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const msg = detail.map((d: any) => d?.msg || d?.message || JSON.stringify(d)).join(', ');
    return msg || fallback;
  }
  return fallback;
}

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Request interceptor: guest mode intercept + JWT token
api.interceptors.request.use(
  (config) => {
    // Guest mode: return mock data without hitting the network
    if (isGuestMode()) {
      const url = config.url || '';
      const mockData = getGuestResponse(url, config.method);
      if (mockData !== undefined) {
        // Swap to a custom adapter that resolves immediately with mock data
        config.adapter = async () => ({
          data: mockData,
          status: 200,
          statusText: 'OK',
          headers: {},
          config,
        });
        return config;
      }
    }

    const token = getAuthToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

/**
 * Retry ONE time on a transient failure before surfacing anything to the user.
 *
 * On Indian mobile a single dropped request is routine, and today every one of them
 * becomes a visible error the user has to react to. One silent retry removes most
 * of those without the user ever knowing there was a problem.
 *
 * ONLY GET. Retrying a POST/PUT/PATCH/DELETE can double-submit — a second journal
 * entry, a second tradebook import, a second acknowledgement. The request may well
 * have reached the server and succeeded; it was the RESPONSE that was lost, and
 * from here those two cases are indistinguishable. A visible error on a write is
 * far cheaper than silent duplicate data.
 *
 * Only transient causes: no response at all (network dropped), a timeout, or a
 * gateway-class 502/503/504. A 4xx is a real answer and retrying it just wastes
 * time; a plain 500 is usually deterministic and would fail again identically.
 */
const RETRY_DELAY_MS = 600;
const RETRYABLE_STATUSES = new Set([502, 503, 504]);

function isRetryable(error: any): boolean {
  const method = (error?.config?.method || '').toLowerCase();
  if (method !== 'get') return false;
  if (error?.config?._retried) return false;

  // Offline is not transient — the OfflineBanner already explains it, and a retry
  // just burns a round trip while the user has no connection at all.
  if (typeof navigator !== 'undefined' && !navigator.onLine) return false;

  if (error?.code === 'ECONNABORTED') return true;         // timeout
  if (!error?.response) return true;                        // network / DNS / reset
  return RETRYABLE_STATUSES.has(error.response.status);     // gateway-class only
}

/** Exported for tests only — the rule is what's worth pinning, not the interceptor. */
export const __isRetryableForTest = isRetryable;

// Response interceptor: detect auth failures and provide better error info
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (isRetryable(error)) {
      error.config._retried = true;
      await new Promise(resolve => setTimeout(resolve, RETRY_DELAY_MS));
      // If this succeeds the caller never learns anything went wrong. If it fails
      // again it falls through to the normal handling below on the second pass.
      return api(error.config);
    }

    if (error.response) {
      const { status, data } = error.response;

      if (status === 401) {
        // Token expired or invalid - dispatch a custom event so BrokerContext can react
        window.dispatchEvent(new CustomEvent('tradementor:token-expired', {
          detail: { message: data?.detail || 'Authentication failed' }
        }));
      } else if (status === 503 && error.response.headers?.['x-maintenance-mode'] === '1') {
        // Real maintenance mode (marked by the backend middleware) — redirect.
        // A 503 WITHOUT this header is an incidental dependency failure, not
        // maintenance, so it falls through to the generic 5xx toast below (FE3).
        const msg = encodeURIComponent(apiDetailString(data?.detail, 'Service temporarily unavailable'));
        window.location.href = `/maintenance?message=${msg}`;
      } else if (status === 429) {
        notifyError('Too many requests — please wait a moment and try again.');
      } else if (status >= 500) {
        // Server-side failures were previously silent — the user saw a stuck loader.
        notifyError("Something went wrong on our end. We've been notified — please try again.");
      }

      // Log with context for debugging
      console.error(`API Error [${status}]:`, data?.detail || data?.message || error.message);
    } else if (error.code === 'ECONNABORTED') {
      notifyError('This is taking longer than usual. Check your connection and try again.');
      console.error('API timeout:', error.message);
    } else {
      // Network error, no response. If we're offline, the OfflineBanner already says so.
      if (typeof navigator !== 'undefined' && navigator.onLine) {
        notifyError("Can't reach the server. Check your connection and try again.");
      }
      console.error('API network error:', error.message);
    }

    return Promise.reject(error);
  }
);

/**
 * Authenticated fetch wrapper for endpoints that require native streaming (SSE).
 * Attaches the Bearer token and dispatches the same token-expired event as the
 * axios interceptor so BrokerContext can react consistently.
 */
export async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getAuthToken();
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> | undefined),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (response.status === 401) {
    window.dispatchEvent(
      new CustomEvent('tradementor:token-expired', {
        detail: { message: 'Authentication failed' },
      })
    );
  }

  return response;
}

/**
 * Deduplicated GET — if two callers request the same URL+params before the
 * first resolves, both receive the same Promise instead of two network calls.
 * Entries are removed from the map as soon as the request settles.
 */
const _pendingGets = new Map<string, Promise<AxiosResponse<any>>>();

export function dedupGet<T = any>(
  url: string,
  config?: AxiosRequestConfig,
): Promise<AxiosResponse<T>> {
  const key = `${url}::${JSON.stringify(config?.params ?? {})}`;
  const pending = _pendingGets.get(key);
  if (pending) return pending as Promise<AxiosResponse<T>>;
  const req = api.get<T>(url, config).finally(() => {
    _pendingGets.delete(key);
  });
  _pendingGets.set(key, req);
  return req;
}

export default api;
