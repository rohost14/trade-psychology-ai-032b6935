const BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/api/admin';
const STORAGE_KEY = 'tm_admin_token';

function token() { return localStorage.getItem(STORAGE_KEY); }

async function req(path: string, opts: RequestInit = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...(token() ? { Authorization: `Bearer ${token()}` } : {}),
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

export const adminApi = {
  // Auth
  login:     (email: string, password: string) =>
    req('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  verifyOtp: (email: string, otp: string) =>
    req('/auth/verify', { method: 'POST', body: JSON.stringify({ email, otp }) }),
  me:        () => req('/auth/me'),
  logout:    () => req('/auth/logout', { method: 'POST' }),

  // Overview
  overview:  () => req('/overview'),

  // Users
  users: (params?: { search?: string; status?: string; page?: number }) => {
    const q = new URLSearchParams();
    if (params?.search) q.set('search', params.search);
    if (params?.status) q.set('status', params.status);
    if (params?.page)   q.set('page', String(params.page));
    return req(`/users?${q}`);
  },
  userDetail:   (id: string) => req(`/users/${id}`),
  suspendUser:  (id: string) => req(`/users/${id}/suspend`, { method: 'PATCH' }),
  sendMessage:  (id: string, message: string) =>
    req(`/users/${id}/send-message`, { method: 'POST', body: JSON.stringify({ message }) }),

  // Export users as CSV (client-side from list response)
  exportUsersUrl: (status?: string) => {
    const q = new URLSearchParams({ limit: '1000' });
    if (status) q.set('status', status);
    return `${BASE}/users?${q}`;
  },

  // System & Tasks
  system:  () => req('/system'),
  tasks:   () => req('/tasks'),

  // Insights
  insights: (days = 30) => req(`/insights?days=${days}`),

  // Config
  getConfig:       () => req('/config'),
  setMaintenance:  (enabled: boolean, message?: string) =>
    req('/config/maintenance', { method: 'POST', body: JSON.stringify({ enabled, message }) }),
  setAnnouncement: (message: string | null) =>
    req('/config/announcement', { method: 'POST', body: JSON.stringify({ message }) }),

  // Audit log
  auditLog: (params?: { page?: number; admin_email?: string; action?: string }) => {
    const q = new URLSearchParams();
    if (params?.page)        q.set('page', String(params.page));
    if (params?.admin_email) q.set('admin_email', params.admin_email);
    if (params?.action)      q.set('action', params.action);
    return req(`/audit-log?${q}`);
  },

  // Broadcast
  broadcast: (segment: 'all_with_phone' | 'connected', message: string, dry_run = false) =>
    req('/broadcast', { method: 'POST', body: JSON.stringify({ segment, message, dry_run }) }),
};
