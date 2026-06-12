import { useState, useEffect } from 'react';
import { Send, Users, AlertTriangle, CheckCircle, History, X, ChevronRight } from 'lucide-react';
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
type Phase   = 'compose' | 'preview' | 'sending' | 'done';

interface BroadcastLog {
  id: string; created_by: string; segment: string; message: string;
  total: number; sent: number; failed: number; created_at: string | null;
}
interface Receipt { phone: string; status: string; error: string | null; sent_at: string | null }
interface ReceiptDetail { broadcast: BroadcastLog & { message: string }; receipts: Receipt[] }

const SEGMENTS: { value: Segment; label: string; desc: string }[] = [
  { value: 'connected',      label: 'Connected users',  desc: 'Users with Zerodha linked + phone number' },
  { value: 'all_with_phone', label: 'All with phone',   desc: 'Everyone who has provided a phone number' },
];

function DeliveryBar({ sent, failed, total }: { sent: number; failed: number; total: number }) {
  if (!total) return null;
  const sentPct   = Math.round((sent   / total) * 100);
  const failedPct = Math.round((failed / total) * 100);
  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ display: 'flex', height: 5, borderRadius: 3, overflow: 'hidden', background: 'rgba(255,255,255,0.06)' }}>
        <div style={{ width: `${sentPct}%`, background: C.green, transition: 'width 0.4s' }} />
        <div style={{ width: `${failedPct}%`, background: C.red }} />
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 4 }}>
        <span style={{ fontSize: '0.68rem', color: C.green }}>{sent} sent</span>
        {failed > 0 && <span style={{ fontSize: '0.68rem', color: C.red }}>{failed} failed</span>}
        <span style={{ fontSize: '0.68rem', color: C.dim }}>{total} total</span>
      </div>
    </div>
  );
}

function ReceiptModal({ id, onClose }: { id: string; onClose: () => void }) {
  const [data, setData]       = useState<ReceiptDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');

  useEffect(() => {
    adminApi.broadcastReceipts(id)
      .then(setData)
      .catch((e: any) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  const STATUS_COLOR: Record<string, string> = { sent: C.green, failed: C.red, queued: C.amber };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
      <div style={{ width: '90%', maxWidth: 600, maxHeight: '80vh', display: 'flex', flexDirection: 'column', background: '#0a0a1a', border: `1px solid ${C.border}`, borderRadius: 16, overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1.25rem 1.5rem', borderBottom: `1px solid ${C.border}` }}>
          <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: C.text, margin: 0 }}>Delivery Receipts</h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: C.muted, padding: 4 }}>
            <X style={{ width: 16, height: 16 }} />
          </button>
        </div>

        <div style={{ overflowY: 'auto', padding: '1.25rem 1.5rem', flex: 1 }}>
          {loading && <p style={{ color: C.muted, fontSize: '0.82rem' }}>Loading…</p>}
          {error   && <p style={{ color: C.red,   fontSize: '0.82rem' }}>{error}</p>}

          {data && (
            <>
              <div style={{ marginBottom: '1.25rem' }}>
                <p style={{ fontSize: '0.78rem', color: C.muted, margin: '0 0 4px' }}>
                  Segment: <strong style={{ color: C.text }}>{data.broadcast.segment}</strong>
                  {' · '}By: <strong style={{ color: C.text }}>{data.broadcast.created_by}</strong>
                  {' · '}{data.broadcast.created_at ? new Date(data.broadcast.created_at).toLocaleString() : '—'}
                </p>
                <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: 8, padding: '0.75rem 1rem', borderLeft: `3px solid ${C.amber}`, marginBottom: 10 }}>
                  <p style={{ fontSize: '0.82rem', color: C.text, margin: 0, whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>{data.broadcast.message}</p>
                </div>
                <DeliveryBar sent={data.broadcast.sent} failed={data.broadcast.failed} total={data.broadcast.total} />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {data.receipts.map((r, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.5rem 0.75rem', borderRadius: 8, background: 'rgba(255,255,255,0.02)', border: `1px solid ${C.border}` }}>
                    <span style={{ fontSize: '0.78rem', fontFamily: 'monospace', color: C.muted }}>{r.phone}</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      {r.error && <span style={{ fontSize: '0.68rem', color: C.red, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.error}</span>}
                      {r.sent_at && <span style={{ fontSize: '0.68rem', color: C.dim }}>{new Date(r.sent_at).toLocaleTimeString()}</span>}
                      <span style={{ fontSize: '0.7rem', fontWeight: 600, padding: '0.15rem 0.45rem', borderRadius: 20, background: `${STATUS_COLOR[r.status] ?? C.muted}22`, color: STATUS_COLOR[r.status] ?? C.muted, border: `1px solid ${STATUS_COLOR[r.status] ?? C.muted}44` }}>
                        {r.status}
                      </span>
                    </div>
                  </div>
                ))}
                {data.receipts.length === 0 && <p style={{ color: C.dim, fontSize: '0.8rem' }}>No receipts found.</p>}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function AdminBroadcast() {
  const [tab, setTab]           = useState<'compose' | 'history'>('compose');
  const [segment, setSegment]   = useState<Segment>('connected');
  const [message, setMessage]   = useState('');
  const [phase, setPhase]       = useState<Phase>('compose');
  const [preview, setPreview]   = useState<{ recipient_count: number } | null>(null);
  const [result, setResult]     = useState<{ sent: number; failed: number; total: number; broadcast_id?: string } | null>(null);
  const [error, setError]       = useState('');

  const [logs, setLogs]               = useState<BroadcastLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [selectedId, setSelectedId]   = useState<string | null>(null);

  const loadLogs = async () => {
    setLogsLoading(true);
    try { setLogs(await adminApi.broadcastLogs(30)); }
    catch (e: any) { setError(e.message); }
    finally { setLogsLoading(false); }
  };

  useEffect(() => { if (tab === 'history') loadLogs(); }, [tab]);

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

  return (
    <div style={{ padding: '2rem', fontFamily: C.dm, maxWidth: 740 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.3rem', fontWeight: 700, color: C.text, margin: 0 }}>Broadcast Message</h1>
          <p style={{ fontSize: '0.78rem', color: C.muted, marginTop: 4 }}>Send WhatsApp messages to user segments. Always preview before sending.</p>
        </div>
        <div style={{ display: 'flex', background: 'rgba(255,255,255,0.04)', borderRadius: 10, padding: 3, border: `1px solid ${C.border}` }}>
          {(['compose', 'history'] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              style={{ padding: '0.4rem 0.9rem', borderRadius: 8, border: 'none', cursor: 'pointer', fontFamily: C.dm, fontSize: '0.8rem', fontWeight: tab === t ? 600 : 400, background: tab === t ? 'rgba(245,158,11,0.15)' : 'transparent', color: tab === t ? C.amber : C.muted, transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: 5 }}>
              {t === 'history' && <History style={{ width: 12, height: 12 }} />}
              {t === 'compose' ? 'Compose' : 'History'}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0.75rem 1rem', borderRadius: 10, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', marginBottom: '1.5rem' }}>
          <AlertTriangle style={{ width: 14, height: 14, color: C.red }} />
          <span style={{ fontSize: '0.8rem', color: C.red }}>{error}</span>
        </div>
      )}

      {/* ── COMPOSE TAB ── */}
      {tab === 'compose' && (
        <>
          {phase === 'done' && result ? (
            <div style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 16, padding: '2rem', textAlign: 'center' }}>
              <CheckCircle style={{ width: 40, height: 40, color: C.green, margin: '0 auto 1rem' }} />
              <h2 style={{ fontSize: '1rem', fontWeight: 700, color: C.text, marginBottom: 8 }}>Broadcast complete</h2>
              <div style={{ display: 'flex', justifyContent: 'center', gap: '2rem', marginBottom: '1.5rem' }}>
                <div><div style={{ fontSize: '1.6rem', fontWeight: 700, color: C.green }}>{result.sent}</div><div style={{ fontSize: '0.72rem', color: C.muted }}>sent</div></div>
                <div><div style={{ fontSize: '1.6rem', fontWeight: 700, color: result.failed > 0 ? C.red : C.muted }}>{result.failed}</div><div style={{ fontSize: '0.72rem', color: C.muted }}>failed</div></div>
                <div><div style={{ fontSize: '1.6rem', fontWeight: 700, color: C.text }}>{result.total}</div><div style={{ fontSize: '0.72rem', color: C.muted }}>total</div></div>
              </div>
              <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
                <button onClick={reset} style={{ padding: '0.6rem 1.5rem', borderRadius: 10, background: 'rgba(255,255,255,0.06)', border: `1px solid ${C.border}`, color: C.muted, cursor: 'pointer', fontFamily: C.dm, fontSize: '0.82rem' }}>
                  New broadcast
                </button>
                {result.broadcast_id && (
                  <button onClick={() => setSelectedId(result.broadcast_id!)}
                    style={{ padding: '0.6rem 1.5rem', borderRadius: 10, background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.25)', color: C.amber, cursor: 'pointer', fontFamily: C.dm, fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <ChevronRight style={{ width: 13, height: 13 }} /> View receipts
                  </button>
                )}
              </div>
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
                <p style={{ fontSize: '0.68rem', color: C.muted, margin: '0 0 4px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Message preview</p>
                <p style={{ fontSize: '0.85rem', color: C.text, margin: 0, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{message}</p>
              </div>
              <p style={{ fontSize: '0.75rem', color: C.red, marginBottom: '1.25rem' }}>
                ⚠ Cannot be undone. Messages sent immediately via WhatsApp.
              </p>
              <div style={{ display: 'flex', gap: 12 }}>
                <button onClick={sendBroadcast} disabled={phase === 'sending' || preview.recipient_count === 0}
                  style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0.7rem 1.5rem', borderRadius: 10, background: 'linear-gradient(135deg, #f59e0b, #d97706)', color: '#000', border: 'none', fontFamily: C.dm, fontWeight: 700, fontSize: '0.875rem', cursor: preview.recipient_count === 0 ? 'not-allowed' : 'pointer', opacity: preview.recipient_count === 0 ? 0.5 : 1 }}>
                  <Send style={{ width: 14, height: 14 }} />
                  Send to {preview.recipient_count} users
                </button>
                <button onClick={() => setPhase('compose')}
                  style={{ padding: '0.7rem 1.25rem', borderRadius: 10, background: 'none', border: `1px solid ${C.border}`, color: C.muted, cursor: 'pointer', fontFamily: C.dm, fontSize: '0.875rem' }}>
                  Edit
                </button>
              </div>
            </div>

          ) : (
            <div style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 16, padding: '1.75rem' }}>
              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', color: C.muted, marginBottom: 10 }}>Target segment</label>
                <div style={{ display: 'flex', gap: 10 }}>
                  {SEGMENTS.map(s => (
                    <button key={s.value} onClick={() => setSegment(s.value)}
                      style={{ flex: 1, padding: '0.75rem 1rem', borderRadius: 10, textAlign: 'left', background: segment === s.value ? 'rgba(245,158,11,0.1)' : 'rgba(255,255,255,0.03)', border: `1px solid ${segment === s.value ? 'rgba(245,158,11,0.35)' : C.border}`, cursor: 'pointer', fontFamily: C.dm }}>
                      <div style={{ fontSize: '0.82rem', fontWeight: 600, color: segment === s.value ? C.amber : C.text, marginBottom: 3 }}>{s.label}</div>
                      <div style={{ fontSize: '0.72rem', color: C.dim }}>{s.desc}</div>
                    </button>
                  ))}
                </div>
              </div>
              <div style={{ marginBottom: '1.25rem' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', color: C.muted, marginBottom: 8 }}>Message <span style={{ color: C.dim }}>(max 700 chars)</span></label>
                <textarea value={message} onChange={e => setMessage(e.target.value.slice(0, 700))}
                  placeholder="Write your broadcast message here. Be specific and helpful — this goes directly to users' WhatsApp."
                  rows={5}
                  style={{ width: '100%', padding: '0.75rem', borderRadius: 10, background: 'rgba(255,255,255,0.04)', border: `1px solid ${C.border}`, color: C.text, fontFamily: C.dm, fontSize: '0.85rem', outline: 'none', resize: 'vertical', boxSizing: 'border-box', lineHeight: 1.6 }}
                />
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
                  <span style={{ fontSize: '0.7rem', color: message.length > 600 ? C.amber : C.dim }}>{message.length}/700</span>
                </div>
              </div>
              <button onClick={runDryRun} disabled={!message.trim()}
                style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0.7rem 1.5rem', borderRadius: 10, background: !message.trim() ? 'rgba(255,255,255,0.04)' : 'rgba(245,158,11,0.12)', border: `1px solid ${!message.trim() ? C.border : 'rgba(245,158,11,0.3)'}`, color: !message.trim() ? C.dim : C.amber, cursor: !message.trim() ? 'not-allowed' : 'pointer', fontFamily: C.dm, fontWeight: 600, fontSize: '0.875rem' }}>
                <Users style={{ width: 14, height: 14 }} />
                Preview recipients
              </button>
            </div>
          )}
        </>
      )}

      {/* ── HISTORY TAB ── */}
      {tab === 'history' && (
        <div>
          {logsLoading && <p style={{ color: C.muted, fontSize: '0.82rem' }}>Loading history…</p>}
          {!logsLoading && logs.length === 0 && (
            <p style={{ color: C.dim, fontSize: '0.82rem' }}>No broadcasts sent yet.</p>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {logs.map(log => (
              <div key={log.id} style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 12, padding: '1rem 1.25rem' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.5rem', borderRadius: 20, background: 'rgba(245,158,11,0.1)', color: C.amber, border: '1px solid rgba(245,158,11,0.2)', fontWeight: 600 }}>
                        {log.segment}
                      </span>
                      <span style={{ fontSize: '0.72rem', color: C.dim }}>by {log.created_by}</span>
                      <span style={{ fontSize: '0.72rem', color: C.dim }}>
                        {log.created_at ? new Date(log.created_at).toLocaleString() : '—'}
                      </span>
                    </div>
                    <p style={{ fontSize: '0.82rem', color: C.text, margin: '0 0 6px', lineHeight: 1.4 }}>{log.message}</p>
                    <DeliveryBar sent={log.sent} failed={log.failed} total={log.total} />
                  </div>
                  <button onClick={() => setSelectedId(log.id)}
                    style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 4, padding: '0.4rem 0.75rem', borderRadius: 8, background: 'rgba(255,255,255,0.04)', border: `1px solid ${C.border}`, color: C.muted, cursor: 'pointer', fontFamily: C.dm, fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                    <ChevronRight style={{ width: 12, height: 12 }} /> Receipts
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {selectedId && <ReceiptModal id={selectedId} onClose={() => setSelectedId(null)} />}
    </div>
  );
}
