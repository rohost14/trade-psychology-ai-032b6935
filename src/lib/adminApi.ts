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
  // ── Auth ──────────────────────────────────────────────────────────────────
  login:      (email: string, password: string) =>
    req('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  verifyOtp:  (email: string, otp: string) =>
    req('/auth/verify', { method: 'POST', body: JSON.stringify({ email, otp }) }),
  verifyTotp: (email: string, otp: string) =>
    req('/auth/totp/verify', { method: 'POST', body: JSON.stringify({ email, otp }) }),
  me:         () => req('/auth/me'),
  logout:     () => req('/auth/logout', { method: 'POST' }),

  // ── TOTP Management ───────────────────────────────────────────────────────
  totpSetupInit:    () => req('/auth/totp/setup'),
  totpSetupConfirm: (code: string) =>
    req('/auth/totp/confirm', { method: 'POST', body: JSON.stringify({ code }) }),
  totpDisable:      () => req('/auth/totp', { method: 'DELETE' }),

  // ── Overview ──────────────────────────────────────────────────────────────
  overview:  () => req('/overview'),

  // ── Users ─────────────────────────────────────────────────────────────────
  users: (params?: { search?: string; status?: string; page?: number }) => {
    const q = new URLSearchParams();
    if (params?.search) q.set('search', params.search);
    if (params?.status) q.set('status', params.status);
    if (params?.page)   q.set('page', String(params.page));
    return req(`/users?${q}`);
  },
  userDetail:     (id: string) => req(`/users/${id}`),
  suspendUser:    (id: string) => req(`/users/${id}/suspend`, { method: 'PATCH' }),
  deleteUser:     (id: string) => req(`/users/${id}`, { method: 'DELETE' }),
  eraseUser:      (id: string) => req(`/users/${id}/erase`, { method: 'DELETE' }),
  sendMessage:    (id: string, message: string) =>
    req(`/users/${id}/send-message`, { method: 'POST', body: JSON.stringify({ message }) }),
  messageHistory: (id: string) => req(`/users/${id}/messages`),

  // Phase 1 power tools
  userTimeline:      (id: string, limit = 80) => req(`/users/${id}/timeline?limit=${limit}`),
  userForceSync:     (id: string) => req(`/users/${id}/force-sync`, { method: 'POST' }),
  updateUserLimits:  (id: string, body: Record<string, number>) =>
    req(`/users/${id}/limits`, { method: 'PATCH', body: JSON.stringify(body) }),
  userPushStatus:    (id: string) => req(`/users/${id}/push-status`),
  userTestPush:      (id: string) => req(`/users/${id}/test-push`, { method: 'POST' }),
  clearUserRateLimit:(id: string) => req(`/users/${id}/rate-limit`, { method: 'DELETE' }),

  exportUsersUrl: (status?: string) => {
    const q = new URLSearchParams({ limit: '1000' });
    if (status) q.set('status', status);
    return `${BASE}/users?${q}`;
  },

  // ── System & Tasks ────────────────────────────────────────────────────────
  system:      () => req('/system'),
  tasks:       () => req('/tasks'),
  triggerTask: (taskKey: string) =>
    req(`/tasks/${taskKey}/trigger`, { method: 'POST' }),

  // ── Insights ──────────────────────────────────────────────────────────────
  insights: (days = 30) => req(`/insights?days=${days}`),

  // ── Config ────────────────────────────────────────────────────────────────
  getConfig:       () => req('/config'),
  setMaintenance:  (enabled: boolean, message?: string) =>
    req('/config/maintenance', { method: 'POST', body: JSON.stringify({ enabled, message }) }),
  setAnnouncement: (message: string | null) =>
    req('/config/announcement', { method: 'POST', body: JSON.stringify({ message }) }),

  // ── Audit log ─────────────────────────────────────────────────────────────
  auditLog: (params?: { page?: number; admin_email?: string; action?: string }) => {
    const q = new URLSearchParams();
    if (params?.page)        q.set('page', String(params.page));
    if (params?.admin_email) q.set('admin_email', params.admin_email);
    if (params?.action)      q.set('action', params.action);
    return req(`/audit-log?${q}`);
  },

  // ── Broadcast ─────────────────────────────────────────────────────────────
  broadcast: (segment: 'all_with_phone' | 'connected' | 'long_inactive' | 'high_alerts', message: string, dry_run = false) =>
    req('/broadcast', { method: 'POST', body: JSON.stringify({ segment, message, dry_run }) }),
  broadcastSegmentCounts: () => req('/broadcast/segment-counts'),
  broadcastLogs:     (limit = 20) => req(`/broadcast/logs?limit=${limit}`),
  broadcastReceipts: (id: string)  => req(`/broadcast/logs/${id}/receipts`),
};
