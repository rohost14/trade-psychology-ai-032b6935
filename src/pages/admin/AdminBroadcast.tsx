import { useState, useEffect, useRef } from 'react';
import { Send, Users, CheckCircle, History, ChevronRight, FileText, RefreshCw } from 'lucide-react';
import { adminApi } from '@/lib/adminApi';
import { AdminPage, AdminCard, ErrorBanner, EmptyState, type Accent } from './_ui';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

type SegmentKey = 'connected' | 'all_with_phone' | 'long_inactive' | 'high_alerts';
type Phase = 'compose' | 'preview' | 'sending' | 'done';

interface BroadcastLog {
  id: string; created_by: string; segment: string; message: string;
  total: number; sent: number; failed: number; created_at: string | null;
}
interface Receipt { phone: string; status: string; error: string | null; sent_at: string | null; }
interface ReceiptDetail { broadcast: BroadcastLog & { message: string }; receipts: Receipt[]; }

const ACCENT_RGB: Record<Accent, string> = {
  profit: 'rgb(var(--tm-profit))', loss: 'rgb(var(--tm-loss))',
  warning: 'rgb(var(--tm-obs))', brand: 'rgb(var(--tm-brand))', muted: 'rgb(var(--muted-foreground))',
};

const SEGMENTS: { value: SegmentKey; label: string; desc: string; accent: Accent; intent: string }[] = [
  { value: 'connected',      label: 'Connected users', desc: 'Zerodha linked + phone on file',        accent: 'profit',  intent: 'Core active base' },
  { value: 'all_with_phone', label: 'All with phone',  desc: 'Everyone who provided a phone number',  accent: 'warning', intent: 'Widest reach' },
  { value: 'long_inactive',  label: 'Long inactive',   desc: 'Connected, no trade in 14+ days',       accent: 'muted',   intent: 'Re-engagement' },
  { value: 'high_alerts',    label: 'High alert users', desc: '>5 behavioral alerts in last 7 days',  accent: 'loss',    intent: 'Intervention' },
];

const TEMPLATES: { title: string; category: string; body: string }[] = [
  { title: 'Market opening nudge', category: 'Daily', body: 'Good morning! 🌅 Markets open in 30 minutes. Remember your plan for today — stick to your trade count limit and position sizing rules. Trade with intention, not impulse.' },
  { title: 'After-hours reflection', category: 'Daily', body: "Today's session is closed. Take 5 minutes to review your trades — what went as planned? What didn't? Consistency tomorrow starts with honest reflection today." },
  { title: 'Pattern intervention', category: 'Intervention', body: "We noticed some behavioral patterns in your recent trading that may be costing you money. Open TradeMentor to see your personalized insights and what you can do differently tomorrow." },
  { title: 'Weekly performance recap', category: 'Weekly', body: "Your weekly trading summary is ready! Log in to TradeMentor to review your discipline score, top patterns, and P&L breakdown for the week. Small improvements compound fast." },
  { title: 'Welcome back', category: 'Re-engagement', body: "We haven't seen you trade in a while. Markets change, but your trading psychology is what you can control. Your TradeMentor account is waiting — pick up where you left off." },
  { title: 'Risk awareness', category: 'Intervention', body: "Heads up: our system detected elevated risk in your recent sessions. Please review your loss limits and position sizing before tomorrow's session. Your capital protection matters." },
  { title: 'Feature announcement', category: 'Product', body: "New on TradeMentor: we've upgraded our behavioral analysis engine. Your alerts are now more precise and actionable. Log in to see your updated pattern insights." },
  // "Historical data shows F&O traders make more impulsive decisions near
  // expiry" was removed 2026-09-03. These templates are SENT TO TRADERS over
  // push and WhatsApp, so an unsourced population claim here reaches them the
  // same way any other copy does — and no source was found for it. Replaced
  // with a statement about the day and the trader's own rules, which asserts
  // nothing about anyone else.
  { title: 'Expiry day reminder', category: 'Daily', body: "Today is expiry day — often a faster session than usual. Before you increase activity, check the limits you set for yourself. Trade the plan, exits included." },
];

const STATUS_ACCENT: Record<string, Accent> = { sent: 'profit', failed: 'loss', queued: 'warning' };

function DeliveryBar({ sent, failed, total }: { sent: number; failed: number; total: number }) {
  if (!total) return null;
  const sentPct = Math.round((sent / total) * 100);
  const failedPct = Math.round((failed / total) * 100);
  return (
    <div className="mt-2">
      <div className="flex h-[5px] rounded overflow-hidden bg-muted">
        <div style={{ width: `${sentPct}%`, background: ACCENT_RGB.profit }} className="transition-[width] duration-500" />
        <div style={{ width: `${failedPct}%`, background: ACCENT_RGB.loss }} />
      </div>
      <div className="flex gap-3 mt-1.5">
        <span className="text-[11px]" style={{ color: ACCENT_RGB.profit }}>{sent} sent</span>
        {failed > 0 && <span className="text-[11px]" style={{ color: ACCENT_RGB.loss }}>{failed} failed</span>}
        <span className="text-[11px] text-muted-foreground/60">{total} total</span>
      </div>
    </div>
  );
}

function ReceiptModal({ id, onClose }: { id: string; onClose: () => void }) {
  const [data, setData]       = useState<ReceiptDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');

  useEffect(() => {
    adminApi.broadcastReceipts(id).then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [id]);

  return (
    <Dialog open onOpenChange={o => { if (!o) onClose(); }}>
      <DialogContent className="max-w-[620px] max-h-[82vh] overflow-hidden flex flex-col">
        <DialogHeader><DialogTitle>Delivery Receipts</DialogTitle></DialogHeader>
        <div className="overflow-y-auto flex-1 -mx-6 px-6">
          {loading && <p className="text-xs text-muted-foreground">Loading…</p>}
          {error && <p className="text-xs text-[rgb(var(--tm-loss))]">{error}</p>}
          {data && (
            <>
              <div className="mb-4">
                <p className="text-xs text-muted-foreground mb-2">
                  <strong className="text-foreground">{data.broadcast.segment}</strong>
                  {' · '}{data.broadcast.created_by}
                  {' · '}{data.broadcast.created_at ? new Date(data.broadcast.created_at).toLocaleString('en-IN') : '—'}
                </p>
                <div className="bg-muted rounded-lg px-3.5 py-2.5 border-l-[3px] mb-2.5" style={{ borderLeftColor: ACCENT_RGB.brand }}>
                  <p className="text-xs text-foreground m-0 whitespace-pre-wrap leading-relaxed">{data.broadcast.message}</p>
                </div>
                <DeliveryBar sent={data.broadcast.sent} failed={data.broadcast.failed} total={data.broadcast.total} />
              </div>
              <div className="flex flex-col gap-1 pb-2">
                {data.receipts.map((r, i) => {
                  const rgb = ACCENT_RGB[STATUS_ACCENT[r.status] ?? 'muted'];
                  return (
                    <div key={i} className="flex items-center justify-between px-3 py-2 rounded-lg bg-muted border border-border">
                      <span className="text-xs font-mono text-muted-foreground">{r.phone}</span>
                      <div className="flex items-center gap-2.5">
                        {r.error && <span className="text-[11px] text-[rgb(var(--tm-loss))] max-w-[180px] overflow-hidden text-ellipsis whitespace-nowrap">{r.error}</span>}
                        {r.sent_at && <span className="text-[11px] text-muted-foreground/60">{new Date(r.sent_at).toLocaleTimeString('en-IN')}</span>}
                        <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full border"
                          style={{ color: rgb, background: `color-mix(in srgb, ${rgb} 13%, transparent)`, borderColor: `color-mix(in srgb, ${rgb} 27%, transparent)` }}>{r.status}</span>
                      </div>
                    </div>
                  );
                })}
                {data.receipts.length === 0 && <p className="text-muted-foreground/60 text-xs">No receipts found.</p>}
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function TemplatePicker({ onSelect, onClose }: { onSelect: (body: string) => void; onClose: () => void }) {
  const categories = Array.from(new Set(TEMPLATES.map(t => t.category)));
  const [activeCat, setActiveCat] = useState(categories[0]);
  const filtered = TEMPLATES.filter(t => t.category === activeCat);

  return (
    <Dialog open onOpenChange={o => { if (!o) onClose(); }}>
      <DialogContent className="max-w-[680px] max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Message Templates</DialogTitle>
          <DialogDescription>Select a template to pre-fill your message. You can edit before sending.</DialogDescription>
        </DialogHeader>
        <div className="flex gap-1 py-1 overflow-x-auto shrink-0">
          {categories.map(cat => (
            <button key={cat} onClick={() => setActiveCat(cat)}
              className={cn('px-3 py-1.5 rounded-full text-xs whitespace-nowrap transition-colors',
                activeCat === cat ? 'font-semibold bg-[rgb(var(--tm-brand))]/10 text-[rgb(var(--tm-brand))]' : 'bg-muted text-muted-foreground hover:text-foreground')}>
              {cat}
            </button>
          ))}
        </div>
        <div className="overflow-y-auto flex-1 flex flex-col gap-2.5 -mx-6 px-6 pb-2">
          {filtered.map(tmpl => (
            <button key={tmpl.title} onClick={() => { onSelect(tmpl.body); onClose(); }}
              className="text-left bg-muted border border-border rounded-lg px-4 py-3.5 hover:border-[rgb(var(--tm-brand))] transition-colors">
              <div className="text-[13px] font-semibold text-foreground mb-1.5">{tmpl.title}</div>
              <p className="text-xs text-muted-foreground m-0 leading-relaxed">{tmpl.body}</p>
              <div className="mt-2.5 flex justify-end">
                <span className="text-[11px] text-[rgb(var(--tm-brand))] font-semibold">Use template →</span>
              </div>
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ComposeForm({
  segment, setSegment, message, setMessage, segmentCounts, countsLoading, onPreview, onOpenTemplates,
}: {
  segment: SegmentKey; setSegment: (s: SegmentKey) => void;
  message: string; setMessage: (m: string) => void;
  segmentCounts: Record<string, number> | null; countsLoading: boolean;
  onPreview: () => void; onOpenTemplates: () => void;
}) {
  const MAX = 700;
  return (
    <AdminCard>
      {/* Segment selector */}
      <div className="mb-6">
        <div className="flex justify-between items-center mb-3">
          <span className="tm-label">Target Segment</span>
          {countsLoading && <RefreshCw size={11} className="text-muted-foreground/60 animate-spin" />}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {SEGMENTS.map(s => {
            const count = segmentCounts?.[s.value];
            const active = segment === s.value;
            const rgb = ACCENT_RGB[s.accent];
            return (
              <button key={s.value} onClick={() => setSegment(s.value)}
                className={cn('px-3.5 py-3 rounded-lg text-left transition-all border', active ? '' : 'bg-muted border-border hover:border-border')}
                style={active ? { background: `color-mix(in srgb, ${rgb} 10%, transparent)`, borderColor: `color-mix(in srgb, ${rgb} 45%, transparent)` } : undefined}>
                <div className="flex justify-between items-start mb-1">
                  <span className="text-[13px] font-semibold" style={{ color: active ? rgb : 'rgb(var(--text-primary))' }}>{s.label}</span>
                  {count !== undefined && <span className="text-xs font-bold tabular-nums" style={{ color: rgb }}>{count.toLocaleString('en-IN')}</span>}
                </div>
                <div className="text-[11px] text-muted-foreground/70">{s.desc}</div>
                <div className="text-[10px] mt-0.5 font-medium" style={{ color: active ? rgb : 'rgb(var(--muted-foreground))' }}>{s.intent}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Message */}
      <div className="mb-5">
        <div className="flex justify-between items-center mb-2">
          <span className="tm-label">Message</span>
          <Button variant="outline" size="sm" className="h-7 px-2.5 text-[11px]" onClick={onOpenTemplates}><FileText size={11} /> Templates</Button>
        </div>
        <Textarea value={message} onChange={e => setMessage(e.target.value.slice(0, MAX))} rows={6}
          placeholder="Write your message here. Be specific and helpful — this goes directly to users' WhatsApp." className="leading-relaxed" />
        <div className="flex justify-between mt-1.5 items-center">
          <span className="text-[11px] text-muted-foreground/60">Plain text only. No HTML or markdown.</span>
          <span className="text-[11px] tabular-nums" style={{ color: message.length > MAX * 0.9 ? ACCENT_RGB.warning : 'rgb(var(--muted-foreground))' }}>{message.length}/{MAX}</span>
        </div>
      </div>

      <Button onClick={onPreview} disabled={!message.trim()} variant="outline"><Users size={14} /> Preview recipients</Button>
    </AdminCard>
  );
}

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

  const loadLogs = async () => {
    setLogsLoading(true);
    try { setLogs(await adminApi.broadcastLogs(30)); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLogsLoading(false); }
  };

  useEffect(() => {
    if (tab === 'compose' && !countsLoadedRef.current) {
      countsLoadedRef.current = true;
      setCountsLoading(true);
      adminApi.broadcastSegmentCounts().then(setSegmentCounts).catch(() => {}).finally(() => setCountsLoading(false));
    }
    if (tab === 'history') loadLogs();
  }, [tab]); // eslint-disable-line react-hooks/exhaustive-deps

  const runDryRun = async () => {
    setError('');
    try { const d = await adminApi.broadcast(segment, message, true); setPreview(d); setPhase('preview'); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
  };

  const sendBroadcast = async () => {
    setPhase('sending'); setError('');
    try { const d = await adminApi.broadcast(segment, message, false); setResult(d); setPhase('done'); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); setPhase('preview'); }
  };

  const reset = () => { setPhase('compose'); setMessage(''); setPreview(null); setResult(null); setError(''); };
  const segCfg = SEGMENTS.find(s => s.value === segment)!;
  const segRgb = ACCENT_RGB[segCfg.accent];

  return (
    <AdminPage
      title="Broadcast"
      subtitle="WhatsApp messages to targeted user segments. Always preview before sending."
      maxWidth={820}
      actions={
        <div className="flex bg-muted rounded-lg p-0.5 border border-border">
          {(['compose', 'history'] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={cn('px-3.5 py-1.5 rounded-md text-xs flex items-center gap-1.5 transition-colors',
                tab === t ? 'font-semibold bg-[rgb(var(--tm-brand))]/10 text-[rgb(var(--tm-brand))]' : 'text-muted-foreground hover:text-foreground')}>
              {t === 'history' && <History size={12} />}
              {t === 'compose' ? 'Compose' : 'History'}
            </button>
          ))}
        </div>
      }
    >
      <ErrorBanner message={error} />

      {/* COMPOSE */}
      {tab === 'compose' && (
        phase === 'done' && result ? (
          <AdminCard>
            <div className="text-center py-8">
              <CheckCircle size={44} className="mx-auto mb-4 block" style={{ color: ACCENT_RGB.profit }} />
              <h2 className="text-foreground mb-2">Broadcast complete</h2>
              <div className="flex justify-center gap-12 mb-7">
                <div><div className="text-[32px] font-bold tabular-nums" style={{ color: ACCENT_RGB.profit }}>{result.sent}</div><div className="text-xs text-muted-foreground">sent</div></div>
                <div><div className="text-[32px] font-bold tabular-nums" style={{ color: result.failed > 0 ? ACCENT_RGB.loss : 'rgb(var(--muted-foreground))' }}>{result.failed}</div><div className="text-xs text-muted-foreground">failed</div></div>
                <div><div className="text-[32px] font-bold tabular-nums text-foreground">{result.total}</div><div className="text-xs text-muted-foreground">total</div></div>
              </div>
              <div className="flex gap-2.5 justify-center">
                <Button variant="outline" onClick={reset}>New broadcast</Button>
                {result.broadcast_id && <Button onClick={() => setSelectedId(result.broadcast_id!)}><ChevronRight size={13} /> View receipts</Button>}
              </div>
            </div>
          </AdminCard>
        ) : phase === 'preview' && preview ? (
          <AdminCard>
            <div className="flex items-center gap-3 mb-5 px-4 py-3.5 rounded-lg border"
              style={{ background: `color-mix(in srgb, ${segRgb} 10%, transparent)`, borderColor: `color-mix(in srgb, ${segRgb} 28%, transparent)` }}>
              <Users size={18} style={{ color: segRgb }} className="shrink-0" />
              <div>
                <p className="text-[15px] font-bold text-foreground m-0">Sending to <span style={{ color: segRgb }}>{preview.recipient_count.toLocaleString('en-IN')}</span> users</p>
                <p className="text-xs text-muted-foreground m-0">Segment: {segCfg.label} · {segCfg.intent}</p>
              </div>
            </div>
            <div className="bg-muted rounded-lg px-4 py-3.5 mb-5 border-l-[3px]" style={{ borderLeftColor: ACCENT_RGB.brand }}>
              <p className="tm-label mb-1.5">Message</p>
              <p className="text-[13px] text-foreground m-0 leading-relaxed whitespace-pre-wrap">{message}</p>
            </div>
            <p className="text-xs text-[rgb(var(--tm-loss))] mb-5">⚠ Cannot be undone. Messages sent immediately via WhatsApp. No scheduling.</p>
            <div className="flex gap-3">
              <Button onClick={sendBroadcast} disabled={phase === ('sending' as Phase) || preview.recipient_count === 0}>
                <Send size={14} /> Send to {preview.recipient_count.toLocaleString('en-IN')} users
              </Button>
              <Button variant="outline" onClick={() => setPhase('compose')}>Edit</Button>
            </div>
          </AdminCard>
        ) : (
          <ComposeForm segment={segment} setSegment={setSegment} message={message} setMessage={setMessage}
            segmentCounts={segmentCounts} countsLoading={countsLoading} onPreview={runDryRun} onOpenTemplates={() => setShowTemplates(true)} />
        )
      )}

      {/* HISTORY */}
      {tab === 'history' && (
        <div>
          {logsLoading && <p className="text-xs text-muted-foreground">Loading history…</p>}
          {!logsLoading && logs.length === 0 && <EmptyState>No broadcasts sent yet.</EmptyState>}
          <div className="flex flex-col gap-2.5">
            {logs.map(log => {
              const segConf = SEGMENTS.find(s => s.value === log.segment);
              const rgb = ACCENT_RGB[segConf?.accent ?? 'warning'];
              return (
                <AdminCard key={log.id} bodyClassName="px-4 py-3.5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                        <span className="text-[11px] px-2 py-0.5 rounded-full font-semibold border"
                          style={{ color: rgb, background: `color-mix(in srgb, ${rgb} 13%, transparent)`, borderColor: `color-mix(in srgb, ${rgb} 27%, transparent)` }}>{log.segment}</span>
                        <span className="text-[11px] text-muted-foreground/60">by {log.created_by}</span>
                        <span className="text-[11px] text-muted-foreground/60">{log.created_at ? new Date(log.created_at).toLocaleString('en-IN') : '—'}</span>
                      </div>
                      <p className="text-[13px] text-foreground mb-1.5 leading-snug">{log.message}</p>
                      <DeliveryBar sent={log.sent} failed={log.failed} total={log.total} />
                    </div>
                    <Button variant="outline" size="sm" className="shrink-0" onClick={() => setSelectedId(log.id)}><ChevronRight size={12} /> Receipts</Button>
                  </div>
                </AdminCard>
              );
            })}
          </div>
        </div>
      )}

      {selectedId    && <ReceiptModal id={selectedId} onClose={() => setSelectedId(null)} />}
      {showTemplates && <TemplatePicker onSelect={setMessage} onClose={() => setShowTemplates(false)} />}
    </AdminPage>
  );
}
