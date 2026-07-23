import { useEffect, useState } from 'react';
import { Save, Smartphone, ShieldCheck, ShieldOff } from 'lucide-react';
import { adminApi } from '@/lib/adminApi';
import { AdminPage, AdminCard, ErrorBanner, LoadingBlock } from './_ui';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';

interface ConfigData {
  maintenance_mode: boolean;
  maintenance_message: string;
  announcement: string | null;
}

export default function AdminConfig() {
  const [, setConfig]                   = useState<ConfigData | null>(null);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState('');
  const [maintEnabled, setMaintEnabled] = useState(false);
  const [maintMsg, setMaintMsg]         = useState('');
  const [announcement, setAnnouncement] = useState('');
  const [saving, setSaving]             = useState<string | null>(null);
  const [saved, setSaved]               = useState<string | null>(null);

  // TOTP setup state
  const [totpPhase, setTotpPhase]       = useState<'idle' | 'setup'>('idle');
  const [totpData, setTotpData]         = useState<{ secret: string; qr_uri: string } | null>(null);
  const [totpCode, setTotpCode]         = useState('');
  const [totpMsg, setTotpMsg]           = useState('');

  const load = async () => {
    setLoading(true); setError('');
    try {
      const d: ConfigData = await adminApi.getConfig();
      setConfig(d);
      setMaintEnabled(d.maintenance_mode);
      setMaintMsg(d.maintenance_message || '');
      setAnnouncement(d.announcement || '');
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const saveMaintenance = async () => {
    setSaving('maintenance'); setError('');
    try {
      await adminApi.setMaintenance(maintEnabled, maintMsg || undefined);
      setSaved('maintenance'); setTimeout(() => setSaved(null), 2500);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setSaving(null); }
  };

  const saveAnnouncement = async () => {
    setSaving('announcement'); setError('');
    try {
      await adminApi.setAnnouncement(announcement || null);
      setSaved('announcement'); setTimeout(() => setSaved(null), 2500);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setSaving(null); }
  };

  const initTotpSetup = async () => {
    setTotpMsg('');
    try {
      const d = await adminApi.totpSetupInit();
      setTotpData(d); setTotpPhase('setup');
    } catch (e: unknown) { setTotpMsg(e instanceof Error ? e.message : String(e)); }
  };

  const confirmTotp = async () => {
    setTotpMsg('');
    try {
      await adminApi.totpSetupConfirm(totpCode);
      setTotpPhase('idle'); setTotpData(null); setTotpCode('');
      setTotpMsg('TOTP enabled. Next login will require authenticator code.');
    } catch (e: unknown) { setTotpMsg(e instanceof Error ? e.message : String(e)); }
  };

  const disableTotp = async () => {
    setTotpMsg('');
    try {
      await adminApi.totpDisable();
      setTotpMsg('TOTP disabled. Email OTP will be used for next login.');
    } catch (e: unknown) { setTotpMsg(e instanceof Error ? e.message : String(e)); }
  };

  const saveBtnLabel = (key: string) => saving === key ? 'Saving…' : saved === key ? 'Saved ✓' : 'Save';
  const totpOk = totpMsg.includes('enabled') || totpMsg.includes('disabled');

  if (loading) return <AdminPage title="Config" maxWidth={720}><LoadingBlock /></AdminPage>;

  return (
    <AdminPage title="Config" maxWidth={720}>
      <ErrorBanner message={error} />

      {/* Maintenance Mode */}
      <AdminCard className="mb-5" title="Maintenance Mode" subtitle="Returns 503 for all API requests when enabled (applies across all workers)"
        right={<Switch checked={maintEnabled} onCheckedChange={setMaintEnabled} />}>
        <div className="space-y-1.5 mb-3">
          <Label htmlFor="maint-msg">Message (shown to users)</Label>
          <Input id="maint-msg" value={maintMsg} onChange={e => setMaintMsg(e.target.value)} placeholder="We're under maintenance. Back soon." />
        </div>
        <Button size="sm" onClick={saveMaintenance} disabled={saving === 'maintenance'}>
          <Save className="w-3.5 h-3.5" /> {saveBtnLabel('maintenance')}
        </Button>
      </AdminCard>

      {/* Announcement */}
      <AdminCard className="mb-5" title="Announcement Banner" subtitle="Shown across the app. Persists server-side. Leave blank to clear.">
        <Textarea value={announcement} onChange={e => setAnnouncement(e.target.value)} rows={3}
          placeholder="e.g. Scheduled maintenance on Sunday 2am–4am IST" className="mb-3" />
        <Button size="sm" onClick={saveAnnouncement} disabled={saving === 'announcement'}>
          <Save className="w-3.5 h-3.5" /> {saveBtnLabel('announcement')}
        </Button>
      </AdminCard>

      {/* TOTP MFA */}
      <AdminCard
        title={<span className="inline-flex items-center gap-2"><Smartphone className="w-4 h-4 text-[rgb(var(--tm-brand))]" /> Authenticator App (TOTP)</span>}
        subtitle="Replace email OTP with Google Authenticator or Authy for stronger MFA."
      >
        {totpMsg && <p className="text-[13px] mb-3" style={{ color: totpOk ? 'rgb(var(--tm-profit))' : 'rgb(var(--tm-loss))' }}>{totpMsg}</p>}

        {totpPhase === 'idle' && (
          <div className="flex gap-2.5">
            <Button size="sm" variant="outline" onClick={initTotpSetup}><ShieldCheck className="w-3.5 h-3.5" /> Set Up TOTP</Button>
            <Button size="sm" variant="outline" onClick={disableTotp} className="text-[rgb(var(--tm-loss))]"><ShieldOff className="w-3.5 h-3.5" /> Disable TOTP</Button>
          </div>
        )}

        {totpPhase === 'setup' && totpData && (
          <div>
            <p className="text-[13px] text-muted-foreground mb-3">
              1. Open Google Authenticator or Authy<br />
              2. Scan the QR code below (or enter secret manually)<br />
              3. Enter the 6-digit code to confirm
            </p>
            <img
              src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(totpData.qr_uri)}`}
              alt="TOTP QR Code" width={180} height={180}
              className="block mb-3 rounded-lg border border-border bg-white p-1"
            />
            <p className="text-[11px] text-muted-foreground mb-3 font-mono break-all">Manual secret: {totpData.secret}</p>
            <div className="flex gap-2.5 items-center">
              <Input type="text" value={totpCode} inputMode="numeric"
                onChange={e => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000" maxLength={6} className="w-[120px] text-center text-lg tracking-[0.2em] font-mono" />
              <Button size="sm" onClick={confirmTotp} disabled={totpCode.length !== 6}>Verify & Enable</Button>
              <Button size="sm" variant="ghost" onClick={() => { setTotpPhase('idle'); setTotpData(null); setTotpCode(''); }}>Cancel</Button>
            </div>
          </div>
        )}
      </AdminCard>
    </AdminPage>
  );
}
