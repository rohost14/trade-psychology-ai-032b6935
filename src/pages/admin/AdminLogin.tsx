import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Mail, Lock, KeyRound, Eye, EyeOff, Smartphone } from 'lucide-react';
import { useAdminAuth } from '@/contexts/AdminAuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export default function AdminLogin() {
  const { step, pendingEmail, admin, login, verifyOtp, verifyTotp } = useAdminAuth();
  const navigate = useNavigate();
  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [code,     setCode]     = useState('');
  const [showPwd,  setShowPwd]  = useState(false);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState('');

  useEffect(() => {
    if (admin) navigate('/admin/overview', { replace: true });
  }, [admin, navigate]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(''); setLoading(true);
    try { await login(email, password); }
    catch (err: unknown) { setError(err instanceof Error ? err.message : 'Invalid credentials'); }
    finally { setLoading(false); }
  };

  const handleOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(''); setLoading(true);
    try { await verifyOtp(pendingEmail || email, code); }
    catch (err: unknown) { setError(err instanceof Error ? err.message : 'Invalid code'); }
    finally { setLoading(false); }
  };

  const handleTotp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(''); setLoading(true);
    try { await verifyTotp(pendingEmail || email, code); }
    catch (err: unknown) { setError(err instanceof Error ? err.message : 'Invalid authenticator code'); }
    finally { setLoading(false); }
  };

  const isOtp  = step === 'otp_sent';
  const isTotp = step === 'totp_required';

  const subtitle = isTotp ? 'Enter your authenticator code'
    : isOtp ? `Code sent to ${pendingEmail || email}`
    : 'Restricted access';

  const codeInput = (
    <Input
      type="text" value={code}
      onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
      required placeholder="000000" maxLength={6} autoFocus inputMode="numeric"
      className="h-14 text-center text-2xl tracking-[0.3em] font-mono"
    />
  );

  return (
    <div className="min-h-screen flex items-center justify-center bg-background text-foreground">
      <div className="w-full max-w-[400px] px-6">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="w-13 h-13 mx-auto mb-4 flex items-center justify-center rounded-2xl bg-[rgb(var(--tm-brand))]/10 border border-[rgb(var(--tm-brand))]/25" style={{ width: 52, height: 52 }}>
            <Shield className="w-6 h-6 text-[rgb(var(--tm-brand))]" />
          </div>
          <h1 className="text-foreground">TradeMentor Admin</h1>
          <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
        </div>

        <div className="tm-card p-8">
          {/* Step 1 — email + password */}
          {step === 'idle' && (
            <form onSubmit={handleLogin} className="flex flex-col gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="admin-email">Email</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
                  <Input id="admin-email" type="email" value={email} onChange={e => setEmail(e.target.value)} required
                         placeholder="admin@tradementor.ai" className="pl-9" />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="admin-pwd">Password</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
                  <Input id="admin-pwd" type={showPwd ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)} required
                         placeholder="••••••••" className="pl-9 pr-9" />
                  <button type="button" onClick={() => setShowPwd(v => !v)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                    {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              {error && <p className="text-sm text-[rgb(var(--tm-loss))] text-center">{error}</p>}
              <Button type="submit" disabled={loading} className="mt-1">{loading ? 'Checking…' : 'Continue'}</Button>
            </form>
          )}

          {/* Step 2A — email OTP */}
          {isOtp && (
            <form onSubmit={handleOtp} className="flex flex-col gap-4">
              <div className="flex items-center gap-2">
                <KeyRound className="w-4 h-4 text-[rgb(var(--tm-brand))]" />
                <span className="text-sm text-muted-foreground">Enter the 6-digit code sent to your email</span>
              </div>
              {codeInput}
              {error && <p className="text-sm text-[rgb(var(--tm-loss))] text-center">{error}</p>}
              <Button type="submit" disabled={loading || code.length !== 6}>{loading ? 'Verifying…' : 'Verify & Sign In'}</Button>
              <Button type="button" variant="link" size="sm" onClick={() => setCode('')} className="text-muted-foreground">Back</Button>
            </form>
          )}

          {/* Step 2B — TOTP */}
          {isTotp && (
            <form onSubmit={handleTotp} className="flex flex-col gap-4">
              <div className="flex items-center gap-2">
                <Smartphone className="w-4 h-4 text-[rgb(var(--tm-brand))]" />
                <span className="text-sm text-muted-foreground">Enter your 6-digit authenticator code</span>
              </div>
              {codeInput}
              <p className="text-xs text-muted-foreground text-center m-0">Open Google Authenticator or Authy and enter the current code</p>
              {error && <p className="text-sm text-[rgb(var(--tm-loss))] text-center">{error}</p>}
              <Button type="submit" disabled={loading || code.length !== 6}>{loading ? 'Verifying…' : 'Sign In'}</Button>
              <Button type="button" variant="link" size="sm" onClick={() => setCode('')} className="text-muted-foreground">Back</Button>
            </form>
          )}
        </div>

        <p className="text-center mt-6 text-xs text-muted-foreground/60">
          This area is restricted. Unauthorised access is prohibited.
        </p>
      </div>
    </div>
  );
}
