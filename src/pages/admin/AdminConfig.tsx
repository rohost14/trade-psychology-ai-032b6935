import { useEffect, useState } from 'react';
import { Save, Smartphone, ShieldCheck, ShieldOff, SlidersHorizontal } from 'lucide-react';
import { adminApi } from '@/lib/adminApi';
import { AdminPage, AdminCard, ErrorBanner, LoadingBlock, Spinner } from './_ui';
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

      <GlobalSettingsCard />
    </AdminPage>
  );
}

interface GlobalSettings {
  feature_whatsapp: boolean; feature_ai_coach: boolean; feature_push: boolean;
  signup_mode: string;
  model_primary: string; model_deep: string; model_reasoning: string; model_free: string;
}

function GlobalSettingsCard() {
  const [gs, setGs] = useState<GlobalSettings | null>(null);
  const [modes, setModes] = useState<string[]>([]);
  const [models, setModels] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    adminApi.getGlobalSettings()
      .then(d => { setGs(d.settings); setModes(d.signup_modes); setModels(d.model_allowlist); })
      .catch(e => setErr(e instanceof Error ? e.message : String(e)));
  }, []);

  const set = <K extends keyof GlobalSettings>(k: K, v: GlobalSettings[K]) =>
    setGs(prev => prev ? { ...prev, [k]: v } : prev);

  const save = async () => {
    if (!gs) return;
    setSaving(true); setErr('');
    try {
      const d = await adminApi.setGlobalSettings(gs as unknown as Record<string, unknown>);
      setGs(d.settings);
      setSaved(true); setTimeout(() => setSaved(false), 2500);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setSaving(false); }
  };

  const selectCls = 'h-9 px-3 rounded-lg bg-card border border-border text-foreground text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring';

  return (
    <AdminCard className="mt-5"
      title={<span className="inline-flex items-center gap-2"><SlidersHorizontal className="w-4 h-4 text-[rgb(var(--tm-brand))]" /> Global Settings</span>}
      subtitle="Runtime controls — take effect without a deploy. Kill-switches fail safe (stay enabled on error).">
      {!gs ? (err ? <ErrorBanner message={err} /> : <div className="flex justify-center py-4"><Spinner size={18} /></div>) : (
        <div className="space-y-6">
          <ErrorBanner message={err} />

          {/* Feature kill-switches */}
          <div>
            <div className="tm-label mb-2.5">Feature kill-switches</div>
            <div className="space-y-2.5">
              {([['feature_whatsapp', 'WhatsApp delivery'], ['feature_ai_coach', 'AI coach'], ['feature_push', 'Push notifications']] as const).map(([k, label]) => (
                <div key={k} className="flex items-center justify-between">
                  <span className="text-[13px] text-foreground">{label}</span>
                  <Switch checked={gs[k]} onCheckedChange={v => set(k, v)} />
                </div>
              ))}
            </div>
          </div>

          {/* Signup gate */}
          <div>
            <div className="tm-label mb-2">Registration</div>
            <div className="flex items-center justify-between">
              <span className="text-[13px] text-muted-foreground">New Zerodha signups (existing users unaffected)</span>
              <select className={selectCls} value={gs.signup_mode} onChange={e => set('signup_mode', e.target.value)}>
                {modes.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
          </div>

          {/* AI models */}
          <div>
            <div className="tm-label mb-2.5">AI models</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {([['model_primary', 'Primary (chat)'], ['model_deep', 'Deep analysis'], ['model_reasoning', 'Reasoning'], ['model_free', 'Free / cheap']] as const).map(([k, label]) => (
                <div key={k} className="space-y-1">
                  <Label className="text-[11px]">{label}</Label>
                  <select className={`${selectCls} w-full`} value={gs[k]} onChange={e => set(k, e.target.value)}>
                    {models.map(m => <option key={m} value={m}>{m}</option>)}
                  </select>
                </div>
              ))}
            </div>
          </div>

          <Button size="sm" onClick={save} disabled={saving}>
            <Save className="w-3.5 h-3.5" /> {saving ? 'Saving…' : saved ? 'Saved ✓' : 'Save global settings'}
          </Button>
        </div>
      )}
    </AdminCard>
  );
}
