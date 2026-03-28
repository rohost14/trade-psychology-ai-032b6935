import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { adminApi } from '@/lib/adminApi';

const STORAGE_KEY = 'tm_admin_token';

interface AdminUser { email: string; name: string; }
interface AdminAuthCtx {
  admin: AdminUser | null;
  isLoading: boolean;
  step: 'idle' | 'otp_sent';
  login: (email: string, password: string) => Promise<void>;
  verifyOtp: (email: string, otp: string) => Promise<void>;
  logout: () => void;
}

const Ctx = createContext<AdminAuthCtx | null>(null);

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [admin,     setAdmin]     = useState<AdminUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [step,      setStep]      = useState<'idle' | 'otp_sent'>('idle');

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
    await adminApi.login(email, password);
    setStep('otp_sent');
  };

  const verifyOtp = async (email: string, otp: string) => {
    const { token, admin: adminData } = await adminApi.verifyOtp(email, otp);
    localStorage.setItem(STORAGE_KEY, token);
    setAdmin(adminData);
    setStep('idle');
  };

  const logout = () => {
    localStorage.removeItem(STORAGE_KEY);
    setAdmin(null);
    setStep('idle');
  };

  return (
    <Ctx.Provider value={{ admin, isLoading, step, login, verifyOtp, logout }}>
      {children}
    </Ctx.Provider>
  );
}

export const useAdminAuth = () => {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAdminAuth must be inside AdminAuthProvider');
  return ctx;
};
