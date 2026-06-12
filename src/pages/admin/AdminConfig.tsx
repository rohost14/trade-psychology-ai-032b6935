import { useEffect, useState } from 'react';
import { Save, AlertTriangle, Smartphone, ShieldCheck, ShieldOff } from 'lucide-react';
import { adminApi } from '@/lib/adminApi';

const C = {
  text:   '#e2e8f0',
  muted:  'rgba(226,232,240,0.45)',
  dim:    'rgba(226,232,240,0.25)',
  border: 'rgba(255,255,255,0.07)',
  amber:  '#f59e0b',
  red:    '#ef4444',
  green:  '#10b981',
  dm:     "'DM Sans', sans-serif",
};

interface ConfigData {
  maintenance_mode: boolean;
  maintenance_message: string;
  announcement: string | null;
}

export default function AdminConfig() {
  const [config, setConfig]             = useState<ConfigData | null>(null);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState('');
  const [maintEnabled, setMaintEnabled] = useState(false);
  const [maintMsg, setMaintMsg]         = useState('');
  const [announcement, setAnnouncement] = useState('');
  const [saving, setSaving]             = useState<string | null>(null);
  const [saved, setSaved]               = useState<string | null>(null);

  // TOTP setup state
  const [totpPhase, setTotpPhase]       = useState<'idle' | 'setup' | 'confirm'>('idle');
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
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const saveMaintenance = async () => {
    setSaving('maintenance'); setError('');
    try {
      await adminApi.setMaintenance(maintEnabled, maintMsg || undefined);
      setSaved('maintenance'); setTimeout(() => setSaved(null), 2500);
    } catch (e: any) { setError(e.message); }
    finally { setSaving(null); }
  };

  const saveAnnouncement = async () => {
    setSaving('announcement'); setError('');
    try {
      await adminApi.setAnnouncement(announcement || null);
      setSaved('announcement'); setTimeout(() => setSaved(null), 2500);
    } catch (e: any) { setError(e.message); }
    finally { setSaving(null); }
  };

  const initTotpSetup = async () => {
    setTotpMsg('');
    try {
      const d = await adminApi.totpSetupInit();
      setTotpData(d);
      setTotpPhase('setup');
    } catch (e: any) { setTotpMsg(e.message); }
  };

  const confirmTotp = async () => {
    setTotpMsg('');
    try {
      await adminApi.totpSetupConfirm(totpCode);
      setTotpPhase('idle'); setTotpData(null); setTotpCode('');
      setTotpMsg('TOTP enabled. Next login will require authenticator code.');
    } catch (e: any) { setTotpMsg(e.message); }
  };

  const disableTotp = async () => {
    setTotpMsg('');
    try {
      await adminApi.totpDisable();
      setTotpMsg('TOTP disabled. Email OTP will be used for next login.');
    } catch (e: any) { setTotpMsg(e.message); }
  };

  if (loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
      <div style={{ width: 28, height: 28, border: `2px solid ${C.amber}`, borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );

  return (
    <div style={{ padding: '2rem', fontFamily: C.dm, maxWidth: 680 }}>
      <h1 style={{ fontSize: '1.3rem', fontWeight: 700, color: C.text, marginBottom: '2rem' }}>Config</h1>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0.75rem 1rem', borderRadius: 10, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', marginBottom: '1.5rem' }}>
          <AlertTriangle style={{ width: 14, height: 14, color: C.red }} />
          <span style={{ fontSize: '0.8rem', color: C.red }}>{error}</span>
        </div>
      )}

      {/* Maintenance Mode */}
      <div style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 14, padding: '1.5rem', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <div>
            <h2 style={{ fontSize: '0.9rem', fontWeight: 600, color: C.text, margin: '0 0 4px' }}>Maintenance Mode</h2>
            <p style={{ fontSize: '0.75rem', color: C.muted, margin: 0 }}>Returns 503 for all API requests when enabled</p>
          </div>
          <button
            onClick={() => setMaintEnabled(v => !v)}
            style={{
              width: 44, height: 24, borderRadius: 12, border: 'none', cursor: 'pointer',
              background: maintEnabled ? C.amber : 'rgba(255,255,255,0.1)',
              position: 'relative', transition: 'background 0.2s',
            }}
          >
            <div style={{
              width: 18, height: 18, borderRadius: 9, background: '#fff',
              position: 'absolute', top: 3, left: maintEnabled ? 23 : 3,
              transition: 'left 0.2s',
            }} />
          </button>
        </div>

        <div>
          <label style={{ display: 'block', fontSize: '0.75rem', color: C.muted, marginBottom: 6 }}>Message (shown to users)</label>
          <input
            value={maintMsg}
            onChange={e => setMaintMsg(e.target.value)}
            placeholder="We're under maintenance. Back soon."
            style={{ width: '100%', padding: '0.65rem 0.75rem', borderRadius: 9, background: 'rgba(255,255,255,0.04)', border: `1px solid ${C.border}`, color: C.text, fontFamily: C.dm, fontSize: '0.82rem', outline: 'none', boxSizing: 'border-box', marginBottom: 12 }}
          />
          <button
            onClick={saveMaintenance} disabled={saving === 'maintenance'}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0.55rem 1rem', borderRadius: 9, background: 'rgba(245,158,11,0.12)', border: '1px solid rgba(245,158,11,0.25)', color: C.amber, fontSize: '0.8rem', cursor: saving === 'maintenance' ? 'not-allowed' : 'pointer', fontFamily: C.dm }}
          >
            <Save style={{ width: 13, height: 13 }} />
            {saving === 'maintenance' ? 'Saving…' : saved === 'maintenance' ? 'Saved ✓' : 'Save'}
          </button>
        </div>
      </div>

      {/* Announcement */}
      <div style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 14, padding: '1.5rem', marginBottom: '1.5rem' }}>
        <div style={{ marginBottom: '1.25rem' }}>
          <h2 style={{ fontSize: '0.9rem', fontWeight: 600, color: C.text, margin: '0 0 4px' }}>Announcement Banner</h2>
          <p style={{ fontSize: '0.75rem', color: C.muted, margin: 0 }}>Shown across the app. Resets on server restart. Leave blank to clear.</p>
        </div>
        <textarea
          value={announcement}
          onChange={e => setAnnouncement(e.target.value)}
          placeholder="e.g. Scheduled maintenance on Sunday 2am–4am IST"
          rows={3}
          style={{ width: '100%', padding: '0.65rem 0.75rem', borderRadius: 9, background: 'rgba(255,255,255,0.04)', border: `1px solid ${C.border}`, color: C.text, fontFamily: C.dm, fontSize: '0.82rem', outline: 'none', resize: 'vertical', boxSizing: 'border-box', marginBottom: 12 }}
        />
        <button
          onClick={saveAnnouncement} disabled={saving === 'announcement'}
          style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0.55rem 1rem', borderRadius: 9, background: 'rgba(245,158,11,0.12)', border: '1px solid rgba(245,158,11,0.25)', color: C.amber, fontSize: '0.8rem', cursor: saving === 'announcement' ? 'not-allowed' : 'pointer', fontFamily: C.dm }}
        >
          <Save style={{ width: 13, height: 13 }} />
          {saving === 'announcement' ? 'Saving…' : saved === 'announcement' ? 'Saved ✓' : 'Save'}
        </button>
      </div>

      {/* TOTP MFA */}
      <div style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 14, padding: '1.5rem' }}>
        <div style={{ marginBottom: '1.25rem' }}>
          <h2 style={{ fontSize: '0.9rem', fontWeight: 600, color: C.text, margin: '0 0 4px', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Smartphone style={{ width: 15, height: 15, color: C.amber }} /> Authenticator App (TOTP)
          </h2>
          <p style={{ fontSize: '0.75rem', color: C.muted, margin: 0 }}>
            Replace email OTP with Google Authenticator or Authy for stronger MFA.
          </p>
        </div>

        {totpMsg && (
          <p style={{ fontSize: '0.78rem', color: totpMsg.includes('enabled') || totpMsg.includes('disabled') ? C.green : C.red, marginBottom: 12 }}>{totpMsg}</p>
        )}

        {totpPhase === 'idle' && (
          <div style={{ display: 'flex', gap: 10 }}>
            <button onClick={initTotpSetup}
              style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0.55rem 1rem', borderRadius: 9, background: 'rgba(245,158,11,0.12)', border: '1px solid rgba(245,158,11,0.25)', color: C.amber, fontSize: '0.8rem', cursor: 'pointer', fontFamily: C.dm }}>
              <ShieldCheck style={{ width: 13, height: 13 }} /> Set Up TOTP
            </button>
            <button onClick={disableTotp}
              style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0.55rem 1rem', borderRadius: 9, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: C.red, fontSize: '0.8rem', cursor: 'pointer', fontFamily: C.dm }}>
              <ShieldOff style={{ width: 13, height: 13 }} /> Disable TOTP
            </button>
          </div>
        )}

        {totpPhase === 'setup' && totpData && (
          <div>
            <p style={{ fontSize: '0.78rem', color: C.muted, marginBottom: 12 }}>
              1. Open Google Authenticator or Authy<br />
              2. Scan the QR code below (or enter secret manually)<br />
              3. Enter the 6-digit code to confirm
            </p>
            {/* QR Code via Google Charts API — no external dependency */}
            <img
              src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(totpData.qr_uri)}`}
              alt="TOTP QR Code"
              style={{ display: 'block', marginBottom: 12, borderRadius: 8, border: `1px solid ${C.border}` }}
            />
            <p style={{ fontSize: '0.7rem', color: C.dim, marginBottom: 12, fontFamily: 'monospace', wordBreak: 'break-all' }}>
              Manual secret: {totpData.secret}
            </p>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <input
                type="text" value={totpCode}
                onChange={e => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000" maxLength={6}
                style={{ width: 120, padding: '0.6rem 0.75rem', borderRadius: 9, background: 'rgba(255,255,255,0.04)', border: `1px solid ${C.border}`, color: C.text, fontFamily: 'monospace', fontSize: '1.1rem', textAlign: 'center', letterSpacing: '0.2em', outline: 'none' }}
              />
              <button onClick={confirmTotp} disabled={totpCode.length !== 6}
                style={{ padding: '0.6rem 1rem', borderRadius: 9, background: 'rgba(245,158,11,0.15)', border: '1px solid rgba(245,158,11,0.3)', color: C.amber, fontSize: '0.8rem', cursor: totpCode.length !== 6 ? 'not-allowed' : 'pointer', fontFamily: C.dm, opacity: totpCode.length !== 6 ? 0.5 : 1 }}>
                Verify & Enable
              </button>
              <button onClick={() => { setTotpPhase('idle'); setTotpData(null); setTotpCode(''); }}
                style={{ padding: '0.6rem 0.75rem', borderRadius: 9, background: 'none', border: `1px solid ${C.border}`, color: C.muted, fontSize: '0.8rem', cursor: 'pointer', fontFamily: C.dm }}>
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
