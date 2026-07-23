import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { adminApi } from '@/lib/adminApi';

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

  // Identity (incl. IAM flags) comes from /auth/me. Auth rides the httpOnly cookie,
  // so there is no client-side token to store — a successful me() means we're signed in.
  const hydrate = async () => {
    const data = await adminApi.me();
    setAdmin(data);
  };

  useEffect(() => {
    // Cookie may already be set (returning visitor) — try to hydrate; 401 just means "not logged in".
    hydrate().catch(() => {}).finally(() => setIsLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const res = await adminApi.login(email, password);
    setPendingEmail(email);
    if (res.status === 'ok') {
      // Dev bypass — cookie already set by the server, no 2FA step.
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
    await adminApi.verifyOtp(email, otp);   // sets the httpOnly cookie
    await hydrate();
    setStep('idle');
    setPendingEmail('');
  };

  const verifyTotp = async (email: string, code: string) => {
    await adminApi.verifyTotp(email, code); // sets the httpOnly cookie
    await hydrate();
    setStep('idle');
    setPendingEmail('');
  };

  // Forced/voluntary password change. Backend rotates the cookie (bumped session epoch)
  // so THIS session survives while all others are invalidated.
  const changePassword = async (newPassword: string) => {
    await adminApi.changePassword(newPassword);
    await hydrate();
  };

  const refresh = async () => { await hydrate(); };

  const logout = () => {
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
