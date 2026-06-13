import { useState, useEffect, useRef } from 'react';
import { Send, Users, AlertTriangle, CheckCircle, History, X, ChevronRight, FileText, RefreshCw } from 'lucide-react';
import { adminApi } from '@/lib/adminApi';

// ─── Design tokens ────────────────────────────────────────────────────────────
const T = {
  bg:       '#09090b',
  surface:  '#111115',
  raised:   '#16161d',
  border:   '#1c1c28',
  border2:  '#252536',
  text:     '#f1f0f5',
  muted:    '#6b6a82',
  dim:      '#3a3a50',
  amber:    '#f59e0b',
  amberBg:  'rgba(245,158,11,0.1)',
  green:    '#22c55e',
  greenBg:  'rgba(34,197,94,0.08)',
  red:      '#ef4444',
  redBg:    'rgba(239,68,68,0.08)',
  blue:     '#3b82f6',
  dm:       "'Inter', 'DM Sans', sans-serif",
};

// ─── Types ────────────────────────────────────────────────────────────────────
type SegmentKey = 'connected' | 'all_with_phone' | 'long_inactive' | 'high_alerts';
type Phase = 'compose' | 'preview' | 'sending' | 'done';

interface BroadcastLog {
  id: string; created_by: string; segment: string; message: string;
  total: number; sent: number; failed: number; created_at: string | null;
}
interface Receipt { phone: string; status: string; error: string | null; sent_at: string | null; }
interface ReceiptDetail { broadcast: BroadcastLog & { message: string }; receipts: Receipt[]; }

// ─── Segment config ───────────────────────────────────────────────────────────
const SEGMENTS: { value: SegmentKey; label: string; desc: string; color: string; intent: string }[] = [
  {
    value:   'connected',
    label:   'Connected users',
    desc:    'Zerodha linked + phone on file',
    color:   T.green,
    intent:  'Core active base',
  },
  {
    value:   'all_with_phone',
    label:   'All with phone',
    desc:    'Everyone who provided a phone number',
    color:   T.amber,
    intent:  'Widest reach',
  },
  {
    value:   'long_inactive',
    label:   'Long inactive',
    desc:    'Connected, no trade in 14+ days',
    color:   T.muted,
    intent:  'Re-engagement',
  },
  {
    value:   'high_alerts',
    label:   'High alert users',
    desc:    '>5 behavioral alerts in last 7 days',
    color:   T.red,
    intent:  'Intervention',
  },
];

// ─── Message templates ────────────────────────────────────────────────────────
const TEMPLATES: { title: string; category: string; body: string }[] = [
  {
    title:    'Market opening nudge',
    category: 'Daily',
    body:     'Good morning! 🌅 Markets open in 30 minutes. Remember your plan for today — stick to your trade count limit and position sizing rules. Trade with intention, not impulse.',
  },
  {
    title:    'After-hours reflection',
    category: 'Daily',
    body:     "Today's session is closed. Take 5 minutes to review your trades — what went as planned? What didn't? Consistency tomorrow starts with honest reflection today.",
  },
  {
    title:    'Pattern intervention',
    category: 'Intervention',
    body:     "We noticed some behavioral patterns in your recent trading that may be costing you money. Open TradeMentor to see your personalized insights and what you can do differently tomorrow.",
  },
  {
    title:    'Weekly performance recap',
    category: 'Weekly',
    body:     "Your weekly trading summary is ready! Log in to TradeMentor to review your discipline score, top patterns, and P&L breakdown for the week. Small improvements compound fast.",
  },
  {
    title:    'Welcome back',
    category: 'Re-engagement',
    body:     "We haven't seen you trade in a while. Markets change, but your trading psychology is what you can control. Your TradeMentor account is waiting — pick up where you left off.",
  },
  {
    title:    'Risk awareness',
    category: 'Intervention',
    body:     "Heads up: our system detected elevated risk in your recent sessions. Please review your loss limits and position sizing before tomorrow's session. Your capital protection matters.",
  },
  {
    title:    'Feature announcement',
    category: 'Product',
    body:     "New on TradeMentor: we've upgraded our behavioral analysis engine. Your alerts are now more precise and actionable. Log in to see your updated pattern insights.",
  },
  {
    title:    'Expiry day reminder',
    category: 'Daily',
    body:     "Today is expiry day. Historical data shows F&O traders make more impulsive decisions near expiry. Stick to your pre-defined rules — exits included. Trade the plan.",
  },
];

// ─── Utilities ────────────────────────────────────────────────────────────────
const STATUS_COLOR: Record<string, string> = { sent: T.green, failed: T.red, queued: T.amber };

function DeliveryBar({ sent, failed, total }: { sent: number; failed: number; total: number }) {
  if (!total) return null;
  const sentPct   = Math.round((sent   / total) * 100);
  const failedPct = Math.round((failed / total) * 100);
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', height: 5, borderRadius: 3, overflow: 'hidden', background: T.raised }}>
        <div style={{ width: `${sentPct}%`,   background: T.green, transition: 'width 0.4s' }} />
        <div style={{ width: `${failedPct}%`, background: T.red }} />
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 5 }}>
        <span style={{ fontSize: 11, color: T.green }}>{sent} sent</span>
        {failed > 0 && <span style={{ fontSize: 11, color: T.red }}>{failed} failed</span>}
        <span style={{ fontSize: 11, color: T.dim }}>{total} total</span>
      </div>
    </div>
  );
}

// ─── Receipt modal ────────────────────────────────────────────────────────────
function ReceiptModal({ id, onClose }: { id: string; onClose: () => void }) {
  const [data, setData]       = useState<ReceiptDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');

  useEffect(() => {
    adminApi.broadcastReceipts(id)
      .then(setData).catch((e: any) => setError(e.message)).finally(() => setLoading(false));
  }, [id]);

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200 }}>
      <div style={{ width: '90%', maxWidth: 620, maxHeight: '82vh', display: 'flex', flexDirection: 'column', background: T.surface, border: `1px solid ${T.border}`, borderRadius: 14, overflow: 'hidden' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', borderBottom: `1px solid ${T.border}`, flexShrink: 0 }}>
          <h2 style={{ fontSize: 14, fontWeight: 700, color: T.text, margin: 0 }}>Delivery Receipts</h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: T.muted, padding: 4 }}>
            <X size={16} />
          </button>
        </div>

        <div style={{ overflowY: 'auto', padding: '16px 20px', flex: 1 }}>
          {loading && <p style={{ fontSize: 12, color: T.muted }}>Loading…</p>}
          {error   && <p style={{ fontSize: 12, color: T.red }}>{error}</p>}
          {data && (
            <>
              <div style={{ marginBottom: 18 }}>
                <p style={{ fontSize: 12, color: T.muted, margin: '0 0 8px' }}>
                  <strong style={{ color: T.text }}>{data.broadcast.segment}</strong>
                  {' · '}{data.broadcast.created_by}
                  {' · '}{data.broadcast.created_at ? new Date(data.broadcast.created_at).toLocaleString('en-IN') : '—'}
                </p>
                <div style={{ background: T.raised, borderRadius: 8, padding: '10px 14px', borderLeft: `3px solid ${T.amber}`, marginBottom: 10 }}>
                  <p style={{ fontSize: 12, color: T.text, margin: 0, whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{data.broadcast.message}</p>
                </div>
                <DeliveryBar sent={data.broadcast.sent} failed={data.broadcast.failed} total={data.broadcast.total} />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {data.receipts.map((r, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', borderRadius: 8, background: T.raised, border: `1px solid ${T.border}` }}>
                    <span style={{ fontSize: 12, fontFamily: "'JetBrains Mono', monospace", color: T.muted }}>{r.phone}</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      {r.error && <span style={{ fontSize: 11, color: T.red, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.error}</span>}
                      {r.sent_at && <span style={{ fontSize: 11, color: T.dim }}>{new Date(r.sent_at).toLocaleTimeString('en-IN')}</span>}
                      <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 20, background: `${STATUS_COLOR[r.status] ?? T.muted}22`, color: STATUS_COLOR[r.status] ?? T.muted, border: `1px solid ${STATUS_COLOR[r.status] ?? T.muted}44` }}>
                        {r.status}
                      </span>
                    </div>
                  </div>
                ))}
                {data.receipts.length === 0 && <p style={{ color: T.dim, fontSize: 12 }}>No receipts found.</p>}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Template picker modal ────────────────────────────────────────────────────
function TemplatePicker({ onSelect, onClose }: { onSelect: (body: string) => void; onClose: () => void }) {
  const categories = Array.from(new Set(TEMPLATES.map(t => t.category)));
  const [activeCat, setActiveCat] = useState(categories[0]);
  const filtered = TEMPLATES.filter(t => t.category === activeCat);

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200 }}>
      <div style={{ width: '90%', maxWidth: 680, maxHeight: '80vh', display: 'flex', flexDirection: 'column', background: T.surface, border: `1px solid ${T.border}`, borderRadius: 14, overflow: 'hidden' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', borderBottom: `1px solid ${T.border}`, flexShrink: 0 }}>
          <div>
            <h2 style={{ fontSize: 14, fontWeight: 700, color: T.text, margin: 0 }}>Message Templates</h2>
            <p style={{ fontSize: 11, color: T.dim, marginTop: 3 }}>Select a template to pre-fill your message. You can edit before sending.</p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: T.muted, padding: 4 }}>
            <X size={16} />
          </button>
        </div>

        {/* Category tabs */}
        <div style={{ display: 'flex', gap: 4, padding: '12px 20px', borderBottom: `1px solid ${T.border}`, flexShrink: 0, overflowX: 'auto' }}>
          {categories.map(cat => (
            <button key={cat} onClick={() => setActiveCat(cat)}
              style={{ padding: '5px 12px', borderRadius: 20, border: 'none', cursor: 'pointer', fontFamily: T.dm, fontSize: 12, fontWeight: activeCat === cat ? 600 : 400, background: activeCat === cat ? T.amberBg : T.raised, color: activeCat === cat ? T.amber : T.muted, whiteSpace: 'nowrap' }}>
              {cat}
            </button>
          ))}
        </div>

        {/* Templates */}
        <div style={{ overflowY: 'auto', padding: '14px 20px', flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filtered.map(tmpl => (
            <div key={tmpl.title} style={{ background: T.raised, border: `1px solid ${T.border}`, borderRadius: 10, padding: '14px 16px', cursor: 'pointer' }}
              onClick={() => { onSelect(tmpl.body); onClose(); }}
              onMouseEnter={e => (e.currentTarget.style.borderColor = T.amber)}
              onMouseLeave={e => (e.currentTarget.style.borderColor = T.border)}>
              <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 6 }}>{tmpl.title}</div>
              <p style={{ fontSize: 12, color: T.muted, margin: 0, lineHeight: 1.6 }}>{tmpl.body}</p>
              <div style={{ marginTop: 10, display: 'flex', justifyContent: 'flex-end' }}>
                <span style={{ fontSize: 11, color: T.amber, fontWeight: 600 }}>Use template →</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Compose form ─────────────────────────────────────────────────────────────
function ComposeForm({
  segment, setSegment, message, setMessage,
  segmentCounts, countsLoading,
  onPreview, onOpenTemplates,
}: {
  segment: SegmentKey; setSegment: (s: SegmentKey) => void;
  message: string; setMessage: (m: string) => void;
  segmentCounts: Record<string, number> | null; countsLoading: boolean;
  onPreview: () => void; onOpenTemplates: () => void;
}) {
  const MAX = 700;

  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: '24px' }}>
      {/* Segment selector */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em' }}>Target Segment</label>
          {countsLoading && <RefreshCw size={11} style={{ color: T.dim, animation: 'spin 1s linear infinite' }} />}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {SEGMENTS.map(s => {
            const count = segmentCounts?.[s.value];
            const active = segment === s.value;
            return (
              <button key={s.value} onClick={() => setSegment(s.value)}
                style={{
                  padding: '12px 14px', borderRadius: 10, textAlign: 'left', fontFamily: T.dm,
                  background: active ? `${s.color}12` : T.raised,
                  border: `1px solid ${active ? s.color + '50' : T.border}`,
                  cursor: 'pointer', transition: 'all 0.15s',
                }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: active ? s.color : T.text }}>{s.label}</span>
                  {count !== undefined && (
                    <span style={{ fontSize: 12, fontWeight: 700, color: s.color, fontVariantNumeric: 'tabular-nums' }}>
                      {count.toLocaleString('en-IN')}
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 11, color: T.dim }}>{s.desc}</div>
                <div style={{ fontSize: 10, color: active ? s.color : T.dim, marginTop: 3, fontWeight: 500 }}>{s.intent}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Message input */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em' }}>Message</label>
          <button onClick={onOpenTemplates}
            style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '4px 10px', borderRadius: 6, background: T.raised, border: `1px solid ${T.border}`, color: T.muted, fontSize: 11, cursor: 'pointer', fontFamily: T.dm }}>
            <FileText size={11} />
            Templates
          </button>
        </div>
        <textarea
          value={message}
          onChange={e => setMessage(e.target.value.slice(0, MAX))}
          placeholder="Write your message here. Be specific and helpful — this goes directly to users' WhatsApp."
          rows={6}
          style={{ width: '100%', padding: '12px', borderRadius: 10, background: T.raised, border: `1px solid ${T.border}`, color: T.text, fontFamily: T.dm, fontSize: 13, outline: 'none', resize: 'vertical', boxSizing: 'border-box', lineHeight: 1.65 }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: T.dim }}>Plain text only. No HTML or markdown.</span>
          <span style={{ fontSize: 11, color: message.length > MAX * 0.9 ? T.amber : T.dim, fontVariantNumeric: 'tabular-nums' }}>
            {message.length}/{MAX}
          </span>
        </div>
      </div>

      <button
        onClick={onPreview} disabled={!message.trim()}
        style={{
          display: 'flex', alignItems: 'center', gap: 8, padding: '10px 20px', borderRadius: 10,
          background: message.trim() ? T.amberBg : T.raised,
          border: `1px solid ${message.trim() ? 'rgba(245,158,11,0.35)' : T.border}`,
          color: message.trim() ? T.amber : T.dim,
          cursor: message.trim() ? 'pointer' : 'not-allowed', fontFamily: T.dm, fontWeight: 600, fontSize: 13,
        }}
      >
        <Users size={14} />
        Preview recipients
      </button>
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────
export default function AdminBroadcast() {
  const [tab,     setTab]     = useState<'compose' | 'history'>('compose');
  const [segment, setSegment] = useState<SegmentKey>('connected');
  const [message, setMessage] = useState('');
  const [phase,   setPhase]   = useState<Phase>('compose');

  const [preview,  setPreview]  = useState<{ recipient_count: number } | null>(null);
  const [result,   setResult]   = useState<{ sent: number; failed: number; total: number; broadcast_id?: string } | null>(null);
  const [error,    setError]    = useState('');

  const [logs,        setLogs]        = useState<BroadcastLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [selectedId,  setSelectedId]  = useState<string | null>(null);
  const [showTemplates, setShowTemplates] = useState(false);

  const [segmentCounts,  setSegmentCounts]  = useState<Record<string, number> | null>(null);
  const [countsLoading,  setCountsLoading]  = useState(false);
  const countsLoadedRef = useRef(false);

  // Load segment counts once when compose tab is active
  useEffect(() => {
    if (tab === 'compose' && !countsLoadedRef.current) {
      countsLoadedRef.current = true;
      setCountsLoading(true);
      adminApi.broadcastSegmentCounts()
        .then(setSegmentCounts)
        .catch(() => {})
        .finally(() => setCountsLoading(false));
    }
    if (tab === 'history') loadLogs();
  }, [tab]);

  const loadLogs = async () => {
    setLogsLoading(true);
    try { setLogs(await adminApi.broadcastLogs(30)); }
    catch (e: any) { setError(e.message); }
    finally { setLogsLoading(false); }
  };

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
      setResult(d); setPhase('done');
    } catch (e: any) { setError(e.message); setPhase('preview'); }
  };

  const reset = () => {
    setPhase('compose'); setMessage(''); setPreview(null); setResult(null); setError('');
  };

  const segCfg = SEGMENTS.find(s => s.value === segment)!;

  return (
    <div style={{ padding: '28px 32px', fontFamily: T.dm, maxWidth: 780 }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: T.text, margin: 0, letterSpacing: '-0.02em' }}>Broadcast</h1>
          <p style={{ fontSize: 12, color: T.dim, marginTop: 4 }}>WhatsApp messages to targeted user segments. Always preview before sending.</p>
        </div>
        {/* Tab switcher */}
        <div style={{ display: 'flex', background: T.raised, borderRadius: 9, padding: 3, border: `1px solid ${T.border}` }}>
          {(['compose', 'history'] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              style={{ padding: '6px 14px', borderRadius: 7, border: 'none', cursor: 'pointer', fontFamily: T.dm, fontSize: 12, fontWeight: tab === t ? 600 : 400, background: tab === t ? T.amberBg : 'transparent', color: tab === t ? T.amber : T.muted, display: 'flex', alignItems: 'center', gap: 5 }}>
              {t === 'history' && <History size={12} />}
              {t === 'compose' ? 'Compose' : 'History'}
            </button>
          ))}
        </div>
      </div>

      {/* Global error */}
      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderRadius: 8, background: T.redBg, border: '1px solid rgba(239,68,68,0.18)', marginBottom: 20 }}>
          <AlertTriangle size={13} style={{ color: T.red }} />
          <span style={{ fontSize: 12, color: T.red }}>{error}</span>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      {/* ── COMPOSE TAB ──────────────────────────────────────────────── */}
      {tab === 'compose' && (
        <>
          {phase === 'done' && result ? (
            <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 14, padding: '40px 32px', textAlign: 'center' }}>
              <CheckCircle size={44} style={{ color: T.green, margin: '0 auto 16px', display: 'block' }} />
              <h2 style={{ fontSize: 18, fontWeight: 700, color: T.text, marginBottom: 8 }}>Broadcast complete</h2>
              <div style={{ display: 'flex', justifyContent: 'center', gap: 48, marginBottom: 28 }}>
                <div><div style={{ fontSize: 32, fontWeight: 700, color: T.green, fontVariantNumeric: 'tabular-nums' }}>{result.sent}</div><div style={{ fontSize: 12, color: T.muted }}>sent</div></div>
                <div><div style={{ fontSize: 32, fontWeight: 700, color: result.failed > 0 ? T.red : T.muted, fontVariantNumeric: 'tabular-nums' }}>{result.failed}</div><div style={{ fontSize: 12, color: T.muted }}>failed</div></div>
                <div><div style={{ fontSize: 32, fontWeight: 700, color: T.text, fontVariantNumeric: 'tabular-nums' }}>{result.total}</div><div style={{ fontSize: 12, color: T.muted }}>total</div></div>
              </div>
              <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
                <button onClick={reset} style={{ padding: '9px 20px', borderRadius: 10, background: T.raised, border: `1px solid ${T.border}`, color: T.muted, cursor: 'pointer', fontFamily: T.dm, fontSize: 13 }}>
                  New broadcast
                </button>
                {result.broadcast_id && (
                  <button onClick={() => setSelectedId(result.broadcast_id!)}
                    style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 20px', borderRadius: 10, background: T.amberBg, border: '1px solid rgba(245,158,11,0.3)', color: T.amber, cursor: 'pointer', fontFamily: T.dm, fontSize: 13, fontWeight: 600 }}>
                    <ChevronRight size={13} /> View receipts
                  </button>
                )}
              </div>
            </div>

          ) : phase === 'preview' && preview ? (
            <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 14, padding: '24px' }}>
              {/* Segment + count summary */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20, padding: '14px 18px', borderRadius: 10, background: `${segCfg.color}10`, border: `1px solid ${segCfg.color}30` }}>
                <Users size={18} style={{ color: segCfg.color, flexShrink: 0 }} />
                <div>
                  <p style={{ fontSize: 15, fontWeight: 700, color: T.text, margin: 0 }}>
                    Sending to <span style={{ color: segCfg.color }}>{preview.recipient_count.toLocaleString('en-IN')}</span> users
                  </p>
                  <p style={{ fontSize: 12, color: T.muted, margin: 0 }}>Segment: {segCfg.label} · {segCfg.intent}</p>
                </div>
              </div>

              {/* Message preview */}
              <div style={{ background: T.raised, borderRadius: 10, padding: '14px 18px', marginBottom: 20, borderLeft: `3px solid ${T.amber}` }}>
                <p style={{ fontSize: 11, color: T.muted, margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Message</p>
                <p style={{ fontSize: 13, color: T.text, margin: 0, lineHeight: 1.65, whiteSpace: 'pre-wrap' }}>{message}</p>
              </div>

              <p style={{ fontSize: 12, color: T.red, marginBottom: 20 }}>
                ⚠ Cannot be undone. Messages sent immediately via WhatsApp. No scheduling.
              </p>

              <div style={{ display: 'flex', gap: 12 }}>
                <button
                  onClick={sendBroadcast}
                  disabled={phase === ('sending' as Phase) || preview.recipient_count === 0}
                  style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 22px', borderRadius: 10, background: 'linear-gradient(135deg, #f59e0b, #d97706)', color: '#000', border: 'none', fontFamily: T.dm, fontWeight: 700, fontSize: 13, cursor: preview.recipient_count === 0 ? 'not-allowed' : 'pointer', opacity: preview.recipient_count === 0 ? 0.5 : 1 }}>
                  <Send size={14} />
                  Send to {preview.recipient_count.toLocaleString('en-IN')} users
                </button>
                <button onClick={() => setPhase('compose')}
                  style={{ padding: '10px 18px', borderRadius: 10, background: 'none', border: `1px solid ${T.border}`, color: T.muted, cursor: 'pointer', fontFamily: T.dm, fontSize: 13 }}>
                  Edit
                </button>
              </div>
            </div>

          ) : (
            <ComposeForm
              segment={segment} setSegment={setSegment}
              message={message} setMessage={setMessage}
              segmentCounts={segmentCounts} countsLoading={countsLoading}
              onPreview={runDryRun}
              onOpenTemplates={() => setShowTemplates(true)}
            />
          )}
        </>
      )}

      {/* ── HISTORY TAB ──────────────────────────────────────────────── */}
      {tab === 'history' && (
        <div>
          {logsLoading && <p style={{ fontSize: 12, color: T.muted }}>Loading history…</p>}
          {!logsLoading && logs.length === 0 && (
            <p style={{ fontSize: 12, color: T.dim }}>No broadcasts sent yet.</p>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {logs.map(log => {
              const segConf = SEGMENTS.find(s => s.value === log.segment);
              return (
                <div key={log.id} style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: '14px 18px' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                        <span style={{ fontSize: 11, padding: '2px 9px', borderRadius: 20, background: `${segConf?.color ?? T.amber}18`, color: segConf?.color ?? T.amber, border: `1px solid ${segConf?.color ?? T.amber}30`, fontWeight: 600 }}>
                          {log.segment}
                        </span>
                        <span style={{ fontSize: 11, color: T.dim }}>by {log.created_by}</span>
                        <span style={{ fontSize: 11, color: T.dim }}>
                          {log.created_at ? new Date(log.created_at).toLocaleString('en-IN') : '—'}
                        </span>
                      </div>
                      <p style={{ fontSize: 13, color: T.text, margin: '0 0 6px', lineHeight: 1.5 }}>{log.message}</p>
                      <DeliveryBar sent={log.sent} failed={log.failed} total={log.total} />
                    </div>
                    <button
                      onClick={() => setSelectedId(log.id)}
                      style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 4, padding: '6px 12px', borderRadius: 8, background: T.raised, border: `1px solid ${T.border}`, color: T.muted, cursor: 'pointer', fontFamily: T.dm, fontSize: 12, whiteSpace: 'nowrap' }}>
                      <ChevronRight size={12} /> Receipts
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {selectedId    && <ReceiptModal id={selectedId} onClose={() => setSelectedId(null)} />}
      {showTemplates && <TemplatePicker onSelect={setMessage} onClose={() => setShowTemplates(false)} />}
    </div>
  );
}
