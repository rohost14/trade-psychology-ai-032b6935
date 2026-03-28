import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Send, Ban, CheckCircle, AlertTriangle } from 'lucide-react';
import { adminApi } from '@/lib/adminApi';

const C = {
  text:   '#e2e8f0',
  muted:  'rgba(226,232,240,0.45)',
  dim:    'rgba(226,232,240,0.25)',
  border: 'rgba(255,255,255,0.07)',
  amber:  '#f59e0b',
  green:  '#10b981',
  red:    '#ef4444',
  dm:     "'DM Sans', sans-serif",
};

// Matches backend /api/admin/users/{id} response shape
interface UserDetailData {
  account: { id: string; broker_user_id: string; broker_email: string | null; status: string; created_at: string | null };
  user: { id: string | null; email: string | null; guardian_phone: string | null } | null;
  profile: { risk_tolerance: string | null; email_enabled: boolean; trading_style: string | null } | null;
  stats: { total_trades: number; total_alerts: number };
  recent_alerts: { id: string; pattern_type: string; severity: string; created_at: string }[];
}

const SEV_COLORS: Record<string, string> = { critical: C.red, high: '#f97316', medium: C.amber, low: C.green };

export default function AdminUserDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [data, setData]             = useState<UserDetailData | null>(null);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');
  const [msgText, setMsgText]       = useState('');
  const [msgStatus, setMsgStatus]   = useState('');
  const [suspending, setSuspending] = useState(false);

  const load = async () => {
    if (!id) return;
    setLoading(true); setError('');
    try { setData(await adminApi.userDetail(id)); }
    catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [id]);

  const sendMessage = async () => {
    if (!id || !msgText.trim()) return;
    setMsgStatus('sending');
    try {
      await adminApi.sendMessage(id, msgText);
      setMsgStatus('sent'); setMsgText('');
      setTimeout(() => setMsgStatus(''), 3000);
    } catch (e: any) { setMsgStatus('error:' + e.message); }
  };

  const toggleSuspend = async () => {
    if (!id) return;
    setSuspending(true);
    try { await adminApi.suspendUser(id); await load(); }
    catch (e: any) { setError(e.message); }
    finally { setSuspending(false); }
  };

  if (loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
      <div style={{ width: 28, height: 28, border: `2px solid ${C.amber}`, borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );

  if (error && !data) return (
    <div style={{ padding: '2rem', fontFamily: C.dm }}>
      <button onClick={() => navigate('/admin/users')} style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none', color: C.muted, cursor: 'pointer', fontFamily: C.dm, fontSize: '0.82rem', marginBottom: '1.5rem' }}>
        <ArrowLeft style={{ width: 14, height: 14 }} /> Back
      </button>
      <div style={{ color: C.red, fontSize: '0.85rem' }}>{error}</div>
    </div>
  );

  if (!data) return null;

  const isSuspended = data.account.status === 'suspended';
  const displayName = data.user?.email || data.account.broker_email || data.account.broker_user_id;
  const phone       = data.user?.guardian_phone;

  return (
    <div style={{ padding: '2rem', fontFamily: C.dm, maxWidth: 900 }}>
      <button onClick={() => navigate('/admin/users')} style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none', color: C.muted, cursor: 'pointer', fontFamily: C.dm, fontSize: '0.82rem', marginBottom: '1.5rem' }}>
        <ArrowLeft style={{ width: 14, height: 14 }} /> Back to Users
      </button>

      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 700, color: C.text, margin: '0 0 4px' }}>{displayName}</h1>
          <p style={{ fontSize: '0.78rem', color: C.muted, margin: 0 }}>Zerodha ID: {data.account.broker_user_id}</p>
          {phone && <p style={{ fontSize: '0.75rem', color: C.dim, margin: '2px 0 0' }}>{phone}</p>}
        </div>
        <button
          onClick={toggleSuspend} disabled={suspending}
          style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0.55rem 1rem', borderRadius: 9, background: isSuspended ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)', border: `1px solid ${isSuspended ? 'rgba(16,185,129,0.25)' : 'rgba(239,68,68,0.25)'}`, color: isSuspended ? C.green : C.red, fontSize: '0.8rem', cursor: suspending ? 'not-allowed' : 'pointer', fontFamily: C.dm, opacity: suspending ? 0.6 : 1 }}
        >
          {isSuspended ? <CheckCircle style={{ width: 13, height: 13 }} /> : <Ban style={{ width: 13, height: 13 }} />}
          {isSuspended ? 'Unsuspend' : 'Suspend'}
        </button>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0.6rem 1rem', borderRadius: 9, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', marginBottom: '1rem' }}>
          <AlertTriangle style={{ width: 13, height: 13, color: C.red }} />
          <span style={{ fontSize: '0.78rem', color: C.red }}>{error}</span>
        </div>
      )}

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '2rem' }}>
        {[
          { label: 'Status',        value: data.account.status },
          { label: 'Total Trades',  value: data.stats.total_trades },
          { label: 'Total Alerts',  value: data.stats.total_alerts },
          { label: 'Risk Tolerance', value: data.profile?.risk_tolerance || '—' },
        ].map(({ label, value }) => (
          <div key={label} style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 12, padding: '1rem' }}>
            <div style={{ fontSize: '0.72rem', color: C.muted, marginBottom: 6 }}>{label}</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: C.text, textTransform: 'capitalize' }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Profile details */}
      {data.profile && (
        <div style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 14, padding: '1.25rem', marginBottom: '2rem' }}>
          <h2 style={{ fontSize: '0.85rem', fontWeight: 600, color: C.text, marginBottom: '0.75rem' }}>Profile</h2>
          <div style={{ display: 'flex', gap: '2rem' }}>
            <div><span style={{ fontSize: '0.72rem', color: C.dim }}>Trading Style</span><div style={{ fontSize: '0.82rem', color: C.text, textTransform: 'capitalize' }}>{data.profile.trading_style || '—'}</div></div>
            <div><span style={{ fontSize: '0.72rem', color: C.dim }}>Email Alerts</span><div style={{ fontSize: '0.82rem', color: data.profile.email_enabled ? C.green : C.muted }}>{data.profile.email_enabled ? 'Enabled' : 'Disabled'}</div></div>
          </div>
        </div>
      )}

      {/* Send WhatsApp */}
      <div style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 14, padding: '1.25rem', marginBottom: '2rem' }}>
        <h2 style={{ fontSize: '0.85rem', fontWeight: 600, color: C.text, marginBottom: '0.75rem' }}>Send WhatsApp Message</h2>
        {!phone ? (
          <p style={{ fontSize: '0.78rem', color: C.dim }}>No phone number on file for this user.</p>
        ) : (
          <>
            <p style={{ fontSize: '0.75rem', color: C.dim, marginBottom: 8 }}>Sending to {phone}</p>
            <textarea
              value={msgText} onChange={e => setMsgText(e.target.value.slice(0, 700))}
              placeholder="Type a message (max 700 chars)…" rows={3}
              style={{ width: '100%', padding: '0.75rem', borderRadius: 9, background: 'rgba(255,255,255,0.04)', border: `1px solid ${C.border}`, color: C.text, fontFamily: C.dm, fontSize: '0.82rem', outline: 'none', resize: 'vertical', boxSizing: 'border-box' }}
            />
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 10 }}>
              <span style={{ fontSize: '0.7rem', color: C.dim }}>{msgText.length}/700</span>
              <button
                onClick={sendMessage} disabled={!msgText.trim() || msgStatus === 'sending'}
                style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0.5rem 1rem', borderRadius: 9, background: 'rgba(245,158,11,0.15)', border: '1px solid rgba(245,158,11,0.3)', color: C.amber, fontSize: '0.8rem', cursor: !msgText.trim() ? 'not-allowed' : 'pointer', fontFamily: C.dm, opacity: !msgText.trim() ? 0.5 : 1 }}
              >
                <Send style={{ width: 13, height: 13 }} />
                {msgStatus === 'sending' ? 'Sending…' : 'Send'}
              </button>
            </div>
            {msgStatus === 'sent' && <p style={{ fontSize: '0.75rem', color: C.green, marginTop: 8 }}>Sent</p>}
            {msgStatus.startsWith('error:') && <p style={{ fontSize: '0.75rem', color: C.red, marginTop: 8 }}>{msgStatus.slice(6)}</p>}
          </>
        )}
      </div>

      {/* Recent Alerts */}
      <div style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 14, padding: '1.25rem' }}>
        <h2 style={{ fontSize: '0.85rem', fontWeight: 600, color: C.text, marginBottom: '1rem' }}>Recent Alerts</h2>
        {data.recent_alerts.length === 0 ? (
          <p style={{ fontSize: '0.82rem', color: C.dim }}>No alerts yet</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {data.recent_alerts.map(a => (
              <div key={a.id} style={{ padding: '0.7rem 1rem', borderRadius: 10, background: 'rgba(255,255,255,0.02)', border: `1px solid ${C.border}`, display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: '0.68rem', fontWeight: 600, padding: '0.15rem 0.5rem', borderRadius: 20, background: `${SEV_COLORS[a.severity] || C.muted}18`, color: SEV_COLORS[a.severity] || C.muted, flexShrink: 0 }}>{a.severity}</span>
                <span style={{ fontSize: '0.78rem', color: C.muted, flex: 1, textTransform: 'capitalize' }}>{a.pattern_type.replace(/_/g, ' ')}</span>
                <span style={{ fontSize: '0.7rem', color: C.dim, flexShrink: 0 }}>{new Date(a.created_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
