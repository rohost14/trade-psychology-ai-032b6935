import { useState } from 'react';
import { Shield, KeyRound, Smartphone, LogOut } from 'lucide-react';
import { useAdminAuth } from '@/contexts/AdminAuthContext';
import { adminApi } from '@/lib/adminApi';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Spinner } from './_ui';

/**
 * Forced first-login setup. Rendered by AdminLayout in place of the app whenever the
 * signed-in admin still has `must_change_password` or an outstanding `totp_required`.
 * Step 1: set a real password (replaces the one-time temp password).
 * Step 2: enrol an authenticator (TOTP). Only when both are done does the app unlock.
 */
export default function AdminOnboarding() {
  const { admin, changePassword, refresh, logout } = useAdminAuth();
  const needsPassword = !!admin?.must_change_password;
  const needsTotp     = !needsPassword && !!admin?.totp_required && !admin?.has_totp;

  return (
    <div className="min-h-screen flex items-center justify-center bg-background text-foreground">
      <div className="w-full max-w-[440px] px-6">
        <div className="text-center mb-8">
          <div className="w-13 h-13 mx-auto mb-4 flex items-center justify-center rounded-2xl bg-[rgb(var(--tm-brand))]/10 border border-[rgb(var(--tm-brand))]/25" style={{ width: 52, height: 52 }}>
            <Shield className="w-6 h-6 text-[rgb(var(--tm-brand))]" />
          </div>
          <h1 className="text-foreground">Finish setting up your account</h1>
          <p className="mt-1 text-sm text-muted-foreground">Required before you can access the admin panel.</p>
        </div>

        {needsPassword && <PasswordStep onDone={changePassword} />}
        {needsTotp && <TotpStep onDone={refresh} />}

        <button onClick={logout} className="mt-6 mx-auto flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors">
          <LogOut size={12} /> Sign out
        </button>
      </div>
    </div>
  );
}

function PasswordStep({ onDone }: { onDone: (pw: string) => Promise<void> }) {
  const [pw, setPw]         = useState('');
  const [confirm, setConf]  = useState('');
  const [loading, setLoad]  = useState(false);
  const [error, setError]   = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (pw.length < 12) { setError('Password must be at least 12 characters.'); return; }
    if (pw !== confirm) { setError('Passwords do not match.'); return; }
    setError(''); setLoad(true);
    try { await onDone(pw); }
    catch (err: unknown) { setError(err instanceof Error ? err.message : 'Failed'); }
    finally { setLoad(false); }
  };

  return (
    <div className="tm-card p-8">
      <div className="flex items-center gap-2 mb-4">
        <KeyRound className="w-4 h-4 text-[rgb(var(--tm-brand))]" />
        <span className="text-sm font-semibold text-foreground">Set a new password</span>
      </div>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="np">New password</Label>
          <Input id="np" type="password" value={pw} onChange={e => setPw(e.target.value)} placeholder="At least 12 characters" autoFocus />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="cp">Confirm password</Label>
          <Input id="cp" type="password" value={confirm} onChange={e => setConf(e.target.value)} placeholder="Re-enter password" />
        </div>
        {error && <p className="text-sm text-[rgb(var(--tm-loss))]">{error}</p>}
        <Button type="submit" disabled={loading}>{loading ? 'Saving…' : 'Set password'}</Button>
      </form>
    </div>
  );
}

function TotpStep({ onDone }: { onDone: () => Promise<void> }) {
  const [data, setData]     = useState<{ secret: string; qr_uri: string } | null>(null);
  const [code, setCode]     = useState('');
  const [busy, setBusy]     = useState(false);
  const [error, setError]   = useState('');

  const init = async () => {
    setError(''); setBusy(true);
    try { setData(await adminApi.totpSetupInit()); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : 'Failed'); }
    finally { setBusy(false); }
  };

  const confirm = async () => {
    setError(''); setBusy(true);
    try { await adminApi.totpSetupConfirm(code); await onDone(); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : 'Invalid code'); }
    finally { setBusy(false); }
  };

  return (
    <div className="tm-card p-8">
      <div className="flex items-center gap-2 mb-4">
        <Smartphone className="w-4 h-4 text-[rgb(var(--tm-brand))]" />
        <span className="text-sm font-semibold text-foreground">Set up your authenticator</span>
      </div>

      {!data ? (
        <>
          <p className="text-[13px] text-muted-foreground mb-4">Your organisation requires TOTP two-factor. Set up Google Authenticator or Authy to continue.</p>
          {error && <p className="text-sm text-[rgb(var(--tm-loss))] mb-3">{error}</p>}
          <Button onClick={init} disabled={busy}>{busy ? 'Loading…' : 'Begin setup'}</Button>
        </>
      ) : (
        <>
          <p className="text-[13px] text-muted-foreground mb-3">
            1. Open your authenticator app<br />2. Scan the QR (or enter the secret)<br />3. Enter the 6-digit code
          </p>
          <img src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(data.qr_uri)}`}
               alt="TOTP QR" width={180} height={180} className="block mb-3 rounded-lg border border-border bg-white p-1" />
          <p className="text-[11px] text-muted-foreground mb-3 font-mono break-all">Manual secret: {data.secret}</p>
          <div className="flex gap-2.5 items-center">
            <Input type="text" value={code} inputMode="numeric"
              onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="000000" maxLength={6} className="w-[120px] text-center text-lg tracking-[0.2em] font-mono" />
            <Button onClick={confirm} disabled={code.length !== 6 || busy}>{busy ? <Spinner size={13} /> : 'Verify & Enable'}</Button>
          </div>
          {error && <p className="text-sm text-[rgb(var(--tm-loss))] mt-3">{error}</p>}
        </>
      )}
    </div>
  );
}
