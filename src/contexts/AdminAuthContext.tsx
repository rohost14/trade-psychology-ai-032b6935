import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { adminApi } from '@/lib/adminApi';

const STORAGE_KEY = 'tm_admin_token';

interface AdminUser {
  email: string;
  name: string;
  role: string;
  must_change_password?: boolean;
  totp_required?: boolean;
  has_totp?: boolean;
}
interface AdminAuthCtx {
  admin:      AdminUser | null;
  isLoading:  boolean;
  step:       'idle' | 'otp_sent' | 'totp_required';
  pendingEmail: string;
  login:      (email: string, password: string) => Promise<void>;
  verifyOtp:  (email: string, otp: string) => Promise<void>;
  verifyTotp: (email: string, code: string) => Promise<void>;
  changePassword: (newPassword: string) => Promise<void>;
  refresh:    () => Promise<void>;
  logout:     () => void;
}

const Ctx = createContext<AdminAuthCtx | null>(null);

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [admin,        setAdmin]        = useState<AdminUser | null>(null);
  const [isLoading,    setIsLoading]    = useState(true);
  const [step,         setStep]         = useState<'idle' | 'otp_sent' | 'totp_required'>('idle');
  const [pendingEmail, setPendingEmail] = useState('');

  // Load full identity (incl. IAM flags) from /auth/me after any token is set.
  const hydrate = async () => {
    const data = await adminApi.me();
    setAdmin(data);
  };

  useEffect(() => {
    const token = localStorage.getItem(STORAGE_KEY);
    if (!token) { setIsLoading(false); return; }
    hydrate()
      .catch(() => localStorage.removeItem(STORAGE_KEY))
      .finally(() => setIsLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const res = await adminApi.login(email, password);
    setPendingEmail(email);
    if (res.status === 'ok' && res.token) {
      // Dev bypass — JWT returned directly, no 2FA step
      localStorage.setItem(STORAGE_KEY, res.token);
      await hydrate();
      setStep('idle');
      setPendingEmail('');
    } else if (res.status === 'totp_required') {
      setStep('totp_required');
    } else {
      setStep('otp_sent');
    }
  };

  const verifyOtp = async (email: string, otp: string) => {
    const { token } = await adminApi.verifyOtp(email, otp);
    localStorage.setItem(STORAGE_KEY, token);
    await hydrate();
    setStep('idle');
    setPendingEmail('');
  };

  const verifyTotp = async (email: string, code: string) => {
    const { token } = await adminApi.verifyTotp(email, code);
    localStorage.setItem(STORAGE_KEY, token);
    await hydrate();
    setStep('idle');
    setPendingEmail('');
  };

  // Forced/voluntary password change. Backend returns a fresh token (bumped session
  // epoch) so THIS session survives while all others are invalidated.
  const changePassword = async (newPassword: string) => {
    const { token } = await adminApi.changePassword(newPassword);
    if (token) localStorage.setItem(STORAGE_KEY, token);
    await hydrate();
  };

  const refresh = async () => { await hydrate(); };

  const logout = () => {
    localStorage.removeItem(STORAGE_KEY);
    setAdmin(null);
    setStep('idle');
    setPendingEmail('');
  };

  return (
    <Ctx.Provider value={{ admin, isLoading, step, pendingEmail, login, verifyOtp, verifyTotp, changePassword, refresh, logout }}>
      {children}
    </Ctx.Provider>
  );
}

export const useAdminAuth = () => {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAdminAuth must be inside AdminAuthProvider');
  return ctx;
};
