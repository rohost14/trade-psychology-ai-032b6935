/**
 * Admin read-only impersonation ("view as user").
 *
 * The impersonation token lives in sessionStorage (per-tab) — NOT localStorage — so it
 * never clobbers the admin's own session in other tabs. `getAuthToken()` in api.ts (and
 * the WS/stream readers) prefer this token when present, so the whole app in THIS tab acts
 * as the impersonated user. The backend only ever issues read-only imp tokens and rejects
 * any write carrying one, so this is safe.
 */
export const IMP_TOKEN_KEY = 'tradementor_imp_token';
export const IMP_META_KEY  = 'tradementor_imp_meta';

export interface ImpersonationMeta {
  name: string;
  by: string;       // admin email
  exp: number;      // epoch seconds
}

export function getImpersonationToken(): string | null {
  try { return sessionStorage.getItem(IMP_TOKEN_KEY); } catch { return null; }
}

export function getImpersonationMeta(): ImpersonationMeta | null {
  try {
    const raw = sessionStorage.getItem(IMP_META_KEY);
    if (!raw) return null;
    const meta = JSON.parse(raw) as ImpersonationMeta;
    if (meta.exp && meta.exp * 1000 < Date.now()) { stopImpersonation(); return null; }
    return meta;
  } catch { return null; }
}

export function isImpersonating(): boolean {
  return !!getImpersonationToken();
}

export function startImpersonation(token: string, meta: ImpersonationMeta): void {
  try {
    sessionStorage.setItem(IMP_TOKEN_KEY, token);
    sessionStorage.setItem(IMP_META_KEY, JSON.stringify(meta));
  } catch { /* ignore */ }
}

export function stopImpersonation(): void {
  try {
    sessionStorage.removeItem(IMP_TOKEN_KEY);
    sessionStorage.removeItem(IMP_META_KEY);
  } catch { /* ignore */ }
}
