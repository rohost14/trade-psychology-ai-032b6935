import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { adminApi } from '@/lib/adminApi';

const STORAGE_KEY = 'tm_admin_token';

interface AdminUser { email: string; name: string; role: string; }
interface AdminAuthCtx {
  admin:      AdminUser | null;
  isLoading:  boolean;
  step:       'idle' | 'otp_sent' | 'totp_required';
  pendingEmail: string;
  login:      (email: string, password: string) => Promise<void>;
  verifyOtp:  (email: string, otp: string) => Promise<void>;
  verifyTotp: (email: string, code: string) => Promise<void>;
  logout:     () => void;
}

const Ctx = createContext<AdminAuthCtx | null>(null);

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [admin,        setAdmin]        = useState<AdminUser | null>(null);
  const [isLoading,    setIsLoading]    = useState(true);
  const [step,         setStep]         = useState<'idle' | 'otp_sent' | 'totp_required'>('idle');
  const [pendingEmail, setPendingEmail] = useState('');

  useEffect(() => {
    const token = localStorage.getItem(STORAGE_KEY);
    if (!token) { setIsLoading(false); return; }
    adminApi.me().then(data => {
      setAdmin(data);
    }).catch(() => {
      localStorage.removeItem(STORAGE_KEY);
    }).finally(() => setIsLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const res = await adminApi.login(email, password);
    setPendingEmail(email);
    if (res.status === 'ok' && res.token) {
      // Dev bypass — JWT returned directly, no 2FA step
      localStorage.setItem(STORAGE_KEY, res.token);
      setAdmin(res.admin);
      setStep('idle');
      setPendingEmail('');
    } else if (res.status === 'totp_required') {
      setStep('totp_required');
    } else {
      setStep('otp_sent');
    }
  };

  const verifyOtp = async (email: string, otp: string) => {
    const { token, admin: adminData } = await adminApi.verifyOtp(email, otp);
    localStorage.setItem(STORAGE_KEY, token);
    setAdmin(adminData);
    setStep('idle');
    setPendingEmail('');
  };

  const verifyTotp = async (email: string, code: string) => {
    const { token, admin: adminData } = await adminApi.verifyTotp(email, code);
    localStorage.setItem(STORAGE_KEY, token);
    setAdmin(adminData);
    setStep('idle');
    setPendingEmail('');
  };

  const logout = () => {
    localStorage.removeItem(STORAGE_KEY);
    setAdmin(null);
    setStep('idle');
    setPendingEmail('');
  };

  return (
    <Ctx.Provider value={{ admin, isLoading, step, pendingEmail, login, verifyOtp, verifyTotp, logout }}>
      {children}
    </Ctx.Provider>
  );
}

export const useAdminAuth = () => {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAdminAuth must be inside AdminAuthProvider');
  return ctx;
};
