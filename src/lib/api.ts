import axios from 'axios';
import { isGuestMode, getGuestResponse } from './guestMode';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const AUTH_TOKEN_KEY = 'tradementor_auth_token';

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

    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: detect auth failures and provide better error info
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const { status, data } = error.response;

      if (status === 401) {
        // Token expired or invalid - dispatch a custom event so BrokerContext can react
        window.dispatchEvent(new CustomEvent('tradementor:token-expired', {
          detail: { message: data?.detail || 'Authentication failed' }
        }));
      }

      if (status === 503) {
        // Backend maintenance mode — redirect to maintenance page
        const msg = encodeURIComponent(apiDetailString(data?.detail, 'Service temporarily unavailable'));
        window.location.href = `/maintenance?message=${msg}`;
      }

      // Log with context for debugging
      console.error(`API Error [${status}]:`, data?.detail || data?.message || error.message);
    } else if (error.code === 'ECONNABORTED') {
      console.error('API timeout:', error.message);
    } else {
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
  const token = localStorage.getItem(AUTH_TOKEN_KEY);
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

export default api;
