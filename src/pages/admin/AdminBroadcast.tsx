import { useState } from 'react';
import { Send, Users, AlertTriangle, CheckCircle } from 'lucide-react';
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

type Segment = 'connected' | 'all_with_phone';
type Phase = 'compose' | 'preview' | 'sending' | 'done';

interface Result { sent: number; failed: number; total: number }

export default function AdminBroadcast() {
  const [segment, setSegment]   = useState<Segment>('connected');
  const [message, setMessage]   = useState('');
  const [phase, setPhase]       = useState<Phase>('compose');
  const [preview, setPreview]   = useState<{ recipient_count: number } | null>(null);
  const [result, setResult]     = useState<Result | null>(null);
  const [error, setError]       = useState('');

  const runDryRun = async () => {
    setError('');
    try {
      const d = await adminApi.broadcast(segment, message, true);
      setPreview(d);
      setPhase('preview');
    } catch (e: any) { setError(e.message); }
  };

  const sendBroadcast = async () => {
    setPhase('sending'); setError('');
    try {
      const d = await adminApi.broadcast(segment, message, false);
      setResult(d);
      setPhase('done');
    } catch (e: any) { setError(e.message); setPhase('preview'); }
  };

  const reset = () => {
    setPhase('compose'); setMessage(''); setPreview(null); setResult(null); setError('');
  };

  const SEGMENTS: { value: Segment; label: string; desc: string }[] = [
    { value: 'connected',     label: 'Connected users',  desc: 'Users with Zerodha linked + phone number' },
    { value: 'all_with_phone', label: 'All with phone',   desc: 'Everyone who has provided a phone number' },
  ];

  return (
    <div style={{ padding: '2rem', fontFamily: C.dm, maxWidth: 680 }}>
      <div style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.3rem', fontWeight: 700, color: C.text, margin: 0 }}>Broadcast Message</h1>
        <p style={{ fontSize: '0.78rem', color: C.muted, marginTop: 6 }}>Send a WhatsApp message to a segment of users. Always preview before sending.</p>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0.75rem 1rem', borderRadius: 10, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', marginBottom: '1.5rem' }}>
          <AlertTriangle style={{ width: 14, height: 14, color: C.red }} />
          <span style={{ fontSize: '0.8rem', color: C.red }}>{error}</span>
        </div>
      )}

      {phase === 'done' && result ? (
        <div style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 16, padding: '2rem', textAlign: 'center' }}>
          <CheckCircle style={{ width: 40, height: 40, color: C.green, margin: '0 auto 1rem' }} />
          <h2 style={{ fontSize: '1rem', fontWeight: 700, color: C.text, marginBottom: 8 }}>Broadcast complete</h2>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '2rem', marginBottom: '1.5rem' }}>
            <div><div style={{ fontSize: '1.6rem', fontWeight: 700, color: C.green }}>{result.sent}</div><div style={{ fontSize: '0.72rem', color: C.muted }}>sent</div></div>
            <div><div style={{ fontSize: '1.6rem', fontWeight: 700, color: result.failed > 0 ? C.red : C.muted }}>{result.failed}</div><div style={{ fontSize: '0.72rem', color: C.muted }}>failed</div></div>
            <div><div style={{ fontSize: '1.6rem', fontWeight: 700, color: C.text }}>{result.total}</div><div style={{ fontSize: '0.72rem', color: C.muted }}>total</div></div>
          </div>
          <button onClick={reset} style={{ padding: '0.6rem 1.5rem', borderRadius: 10, background: 'rgba(255,255,255,0.06)', border: `1px solid ${C.border}`, color: C.muted, cursor: 'pointer', fontFamily: C.dm, fontSize: '0.82rem' }}>
            New broadcast
          </button>
        </div>
      ) : phase === 'preview' && preview ? (
        <div style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 16, padding: '1.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: '1.5rem' }}>
            <Users style={{ width: 18, height: 18, color: C.amber }} />
            <span style={{ fontSize: '1rem', fontWeight: 700, color: C.text }}>
              This will send to <span style={{ color: C.amber }}>{preview.recipient_count}</span> users
            </span>
          </div>

          <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: 12, padding: '1rem 1.25rem', marginBottom: '1.5rem', borderLeft: `3px solid ${C.amber}` }}>
            <p style={{ fontSize: '0.82rem', color: C.muted, margin: '0 0 4px', textTransform: 'uppercase', letterSpacing: '0.06em', fontSize: '0.68rem' }}>Message preview</p>
            <p style={{ fontSize: '0.85rem', color: C.text, margin: 0, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{message}</p>
          </div>

          <p style={{ fontSize: '0.75rem', color: C.red, marginBottom: '1.25rem' }}>
            ⚠ This cannot be undone. Messages will be sent immediately via WhatsApp.
          </p>

          <div style={{ display: 'flex', gap: 12 }}>
            <button
              onClick={sendBroadcast}
              disabled={phase === 'sending' || preview.recipient_count === 0}
              style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0.7rem 1.5rem', borderRadius: 10, background: 'linear-gradient(135deg, #f59e0b, #d97706)', color: '#000', border: 'none', fontFamily: C.dm, fontWeight: 700, fontSize: '0.875rem', cursor: preview.recipient_count === 0 ? 'not-allowed' : 'pointer', opacity: preview.recipient_count === 0 ? 0.5 : 1 }}
            >
              <Send style={{ width: 14, height: 14 }} />
              Send to {preview.recipient_count} users
            </button>
            <button onClick={() => setPhase('compose')} style={{ padding: '0.7rem 1.25rem', borderRadius: 10, background: 'none', border: `1px solid ${C.border}`, color: C.muted, cursor: 'pointer', fontFamily: C.dm, fontSize: '0.875rem' }}>
              Edit
            </button>
          </div>
        </div>
      ) : (
        <div style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 16, padding: '1.75rem' }}>
          {/* Segment selector */}
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', fontSize: '0.78rem', color: C.muted, marginBottom: 10 }}>Target segment</label>
            <div style={{ display: 'flex', gap: 10 }}>
              {SEGMENTS.map(s => (
                <button
                  key={s.value}
                  onClick={() => setSegment(s.value)}
                  style={{
                    flex: 1, padding: '0.75rem 1rem', borderRadius: 10, textAlign: 'left',
                    background: segment === s.value ? 'rgba(245,158,11,0.1)' : 'rgba(255,255,255,0.03)',
                    border: `1px solid ${segment === s.value ? 'rgba(245,158,11,0.35)' : C.border}`,
                    cursor: 'pointer', fontFamily: C.dm,
                  }}
                >
                  <div style={{ fontSize: '0.82rem', fontWeight: 600, color: segment === s.value ? C.amber : C.text, marginBottom: 3 }}>{s.label}</div>
                  <div style={{ fontSize: '0.72rem', color: C.dim }}>{s.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Message input */}
          <div style={{ marginBottom: '1.25rem' }}>
            <label style={{ display: 'block', fontSize: '0.78rem', color: C.muted, marginBottom: 8 }}>Message <span style={{ color: C.dim }}>(max 700 chars)</span></label>
            <textarea
              value={message} onChange={e => setMessage(e.target.value.slice(0, 700))}
              placeholder="Write your broadcast message here. Be specific and helpful — this goes directly to users' WhatsApp."
              rows={5}
              style={{ width: '100%', padding: '0.75rem', borderRadius: 10, background: 'rgba(255,255,255,0.04)', border: `1px solid ${C.border}`, color: C.text, fontFamily: C.dm, fontSize: '0.85rem', outline: 'none', resize: 'vertical', boxSizing: 'border-box', lineHeight: 1.6 }}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
              <span style={{ fontSize: '0.7rem', color: message.length > 600 ? C.amber : C.dim }}>{message.length}/700</span>
            </div>
          </div>

          <button
            onClick={runDryRun} disabled={!message.trim()}
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0.7rem 1.5rem', borderRadius: 10, background: !message.trim() ? 'rgba(255,255,255,0.04)' : 'rgba(245,158,11,0.12)', border: `1px solid ${!message.trim() ? C.border : 'rgba(245,158,11,0.3)'}`, color: !message.trim() ? C.dim : C.amber, cursor: !message.trim() ? 'not-allowed' : 'pointer', fontFamily: C.dm, fontWeight: 600, fontSize: '0.875rem' }}
          >
            <Users style={{ width: 14, height: 14 }} />
            Preview recipients
          </button>
        </div>
      )}
    </div>
  );
}
