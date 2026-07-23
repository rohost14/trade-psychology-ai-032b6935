import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, RefreshCw, Ban, CheckCircle, Trash2, Send,
  TrendingUp, TrendingDown, Bell, Smartphone, Monitor,
  Zap, AlertTriangle, RotateCcw, WifiOff, Circle, Eye,
} from 'lucide-react';
import { adminApi } from '@/lib/adminApi';
import { useAdminAuth } from '@/contexts/AdminAuthContext';
import { AdminCard, KpiCard, ErrorBanner, Spinner, type Accent } from './_ui';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { cn } from '@/lib/utils';

const ACCENT_RGB: Record<Accent, string> = {
  profit: 'rgb(var(--tm-profit))', loss: 'rgb(var(--tm-loss))',
  warning: 'rgb(var(--tm-obs))', brand: 'rgb(var(--tm-brand))', muted: 'rgb(var(--muted-foreground))',
};
const LC_ACCENT: Record<string, { accent: Accent; label: string }> = {
  new:          { accent: 'brand',   label: 'New' },
  active:       { accent: 'profit',  label: 'Active' },
  at_risk:      { accent: 'warning', label: 'At Risk' },
  churned:      { accent: 'loss',    label: 'Churned' },
  inactive:     { accent: 'muted',   label: 'Inactive' },
  suspended:    { accent: 'loss',    label: 'Suspended' },
  disconnected: { accent: 'muted',   label: 'Disconnected' },
};
const SEV_ACCENT: Record<string, Accent> = { critical: 'loss', high: 'warning', medium: 'brand', low: 'profit', info: 'muted' };
const sevRgb = (s: string | undefined) => ACCENT_RGB[SEV_ACCENT[s ?? 'info'] ?? 'muted'];

const TABS = ['Overview', 'Timeline', 'Limits', 'Comms'] as const;
type Tab = typeof TABS[number];

interface DetailData {
  account: {
    id: string; broker_user_id: string; broker_email: string | null;
    status: string; sync_status: string; last_sync_at: string | null;
    connected_at: string | null; created_at: string | null;
  };
  user: {
    id: string | null; email: string | null; display_name: string | null;
    guardian_phone: string | null; guardian_name: string | null; guardian_confirmed: boolean;
  } | null;
  profile: {
    trading_style: string | null; experience_level: string | null;
    risk_tolerance: string | null; trading_capital: number | null;
    daily_trade_limit: number | null; daily_loss_limit: number | null;
    max_position_size: number | null; cooldown_after_loss: number | null;
    push_enabled: boolean; whatsapp_enabled: boolean; email_enabled: boolean;
    alert_sensitivity: string | null; onboarding_completed: boolean;
  } | null;
  stats: { total_trades: number; total_alerts: number; push_subscription_count: number; last_trade_at: string | null };
  lifecycle: string;
  recent_alerts: { id: string; pattern_type: string; severity: string; message: string; detected_at: string | null; acknowledged: boolean }[];
}
interface TimelineEvent {
  type: 'trade' | 'alert'; time: string | null; id: string;
  symbol?: string; direction?: string; product?: string; status?: string; quantity?: number; price?: number | null; exchange?: string;
  pattern?: string; severity?: string; message?: string; acknowledged?: boolean;
}
interface PushStatus {
  subscription_count: number;
  subscriptions: { id: string; device_type: string; created_at: string | null; endpoint_tail: string | null }[];
  last_push_at: string | null; last_push_pattern: string | null; total_pushes_sent: number;
}
interface MsgHistory { id: string; admin_email: string; preview: string | null; to: string | null; success: boolean | null; created_at: string | null; }

// ── utils ──────────────────────────────────────────────────────────────────────
function fmtTs(iso: string | null, opts?: Intl.DateTimeFormatOptions): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', ...opts });
}
function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric' });
}
function relativeTime(iso: string | null): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}
function fmtINR(n: number | null | undefined): string {
  if (n == null) return '—';
  return '₹' + n.toLocaleString('en-IN');
}
const cap = (s: string | null | undefined) => s ? s.charAt(0).toUpperCase() + s.slice(1) : '—';

// ── small pieces ────────────────────────────────────────────────────────────────
function Row({ k, v, mono }: { k: string; v: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex justify-between items-center px-5 py-2.5 border-b border-border last:border-0">
      <span className="text-xs text-muted-foreground">{k}</span>
      <span className={cn('text-[13px] text-foreground', mono && 'font-mono text-xs')}>{v}</span>
    </div>
  );
}
function InfoCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="tm-card">
      <div className="px-5 py-3.5 border-b border-border"><span className="tm-label">{title}</span></div>
      <div>{children}</div>
    </div>
  );
}
function Pill({ accent, label, capitalize }: { accent: Accent; label: string; capitalize?: boolean }) {
  const rgb = ACCENT_RGB[accent];
  return (
    <span className={cn('inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold', capitalize && 'capitalize')}
      style={{ color: rgb, background: `color-mix(in srgb, ${rgb} 12%, transparent)` }}>
      <Circle size={5} fill={rgb} style={{ color: rgb }} />
      {label}
    </span>
  );
}

// ── Overview tab ─────────────────────────────────────────────────────────────────
function OverviewTab({ data }: { data: DetailData }) {
  const { profile, user, account, recent_alerts } = data;
  const profileRows: [string, string][] = [
    ['Trading style', cap(profile?.trading_style)],
    ['Experience', cap(profile?.experience_level)],
    ['Risk tolerance', cap(profile?.risk_tolerance)],
    ['Capital deployed', fmtINR(profile?.trading_capital ?? null)],
    ['Alert sensitivity', profile?.alert_sensitivity || '—'],
    ['Onboarding', profile?.onboarding_completed ? 'Completed' : 'Incomplete'],
  ];
  const notifRows: [string, boolean][] = [
    ['Push notifications', profile?.push_enabled ?? false],
    ['WhatsApp alerts', profile?.whatsapp_enabled ?? false],
    ['Email alerts', profile?.email_enabled ?? false],
  ];
  const guardianRows: [string, string][] = [
    ['Phone', user?.guardian_phone || '—'],
    ['Name', user?.guardian_name || '—'],
    ['Confirmed', user?.guardian_confirmed ? 'Yes' : 'No'],
  ];

  return (
    <div className="grid grid-cols-1 lg:[grid-template-columns:1fr_340px] gap-4">
      <div className="flex flex-col gap-3.5">
        <InfoCard title="Trading Profile">{profileRows.map(([k, v]) => <Row key={k} k={k} v={v} />)}</InfoCard>
        <InfoCard title="Notification Channels">
          {notifRows.map(([k, v]) => (
            <Row key={k} k={k} v={<span className="font-semibold" style={{ color: v ? ACCENT_RGB.profit : 'rgb(var(--muted-foreground))' }}>{v ? 'On' : 'Off'}</span>} />
          ))}
        </InfoCard>
      </div>
      <div className="flex flex-col gap-3.5">
        <InfoCard title="Guardian">{guardianRows.map(([k, v]) => <Row key={k} k={k} v={v} />)}</InfoCard>
        <InfoCard title="Account">
          {([
            ['Account ID', account.id.slice(0, 8) + '…'],
            ['Zerodha ID', account.broker_user_id || '—'],
            ['Sync status', account.sync_status || '—'],
            ['Last synced', relativeTime(account.last_sync_at)],
            ['Connected', fmtDate(account.connected_at)],
          ] as [string, string][]).map(([k, v]) => <Row key={k} k={k} v={v} mono />)}
        </InfoCard>
        {recent_alerts.length > 0 && (
          <InfoCard title="Recent Alerts">
            {recent_alerts.slice(0, 5).map(a => {
              const rgb = sevRgb(a.severity);
              return (
                <div key={a.id} className="flex items-start gap-2.5 px-4 py-2.5 border-b border-border last:border-0">
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full shrink-0 mt-0.5 uppercase tracking-wide"
                    style={{ color: rgb, background: `color-mix(in srgb, ${rgb} 14%, transparent)` }}>{a.severity}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-foreground capitalize">{a.pattern_type.replace(/_/g, ' ')}</div>
                    <div className="text-[11px] text-muted-foreground mt-0.5">{relativeTime(a.detected_at)}</div>
                  </div>
                  {a.acknowledged && <CheckCircle size={12} style={{ color: ACCENT_RGB.profit }} className="shrink-0 mt-0.5" />}
                </div>
              );
            })}
          </InfoCard>
        )}
      </div>
    </div>
  );
}

// ── Timeline tab ─────────────────────────────────────────────────────────────────
function TimelineRow({ ev }: { ev: TimelineEvent }) {
  const isTrade = ev.type === 'trade';
  const isBuy = ev.direction === 'BUY';
  const dotColor = isTrade ? (isBuy ? ACCENT_RGB.profit : ACCENT_RGB.loss) : sevRgb(ev.severity);
  return (
    <div className="flex gap-4 items-start py-2.5">
      <div className="w-[30px] shrink-0 flex justify-center pt-0.5">
        <div className="w-[9px] h-[9px] rounded-full shrink-0" style={{ background: dotColor, boxShadow: `0 0 0 2px rgb(var(--background)), 0 0 0 3px color-mix(in srgb, ${dotColor} 25%, transparent)` }} />
      </div>
      <div className="flex-1 tm-card px-3.5 py-2.5 min-w-0">
        {isTrade ? (
          <div className="flex items-center gap-2 flex-wrap">
            {isBuy ? <TrendingUp size={13} style={{ color: ACCENT_RGB.profit }} className="shrink-0" /> : <TrendingDown size={13} style={{ color: ACCENT_RGB.loss }} className="shrink-0" />}
            <span className="text-[13px] font-semibold text-foreground">{ev.symbol}</span>
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style={{ color: isBuy ? ACCENT_RGB.profit : ACCENT_RGB.loss, background: `color-mix(in srgb, ${isBuy ? ACCENT_RGB.profit : ACCENT_RGB.loss} 12%, transparent)` }}>{ev.direction}</span>
            <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground border border-border">{ev.product}</span>
            <div className="ml-auto flex gap-3 items-center">
              <span className="text-[11px] text-muted-foreground tabular-nums">{ev.quantity} lots{ev.price ? ` @ ₹${Number(ev.price).toFixed(2)}` : ''}</span>
              <span className="text-[11px] text-muted-foreground/60 whitespace-nowrap">{fmtTs(ev.time, { hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short', year: undefined })}</span>
            </div>
          </div>
        ) : (
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <Bell size={12} style={{ color: sevRgb(ev.severity) }} className="shrink-0" />
              <span className="text-[13px] font-semibold text-foreground capitalize">{ev.pattern?.replace(/_/g, ' ')}</span>
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style={{ color: sevRgb(ev.severity), background: `color-mix(in srgb, ${sevRgb(ev.severity)} 14%, transparent)` }}>{ev.severity}</span>
              {ev.acknowledged && <span className="text-[10px] flex items-center gap-1" style={{ color: ACCENT_RGB.profit }}><CheckCircle size={10} /> ack'd</span>}
              <span className="ml-auto text-[11px] text-muted-foreground/60 whitespace-nowrap">{fmtTs(ev.time, { hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short', year: undefined })}</span>
            </div>
            {ev.message && <div className="text-xs text-muted-foreground mt-1 leading-relaxed">{ev.message}</div>}
          </div>
        )}
      </div>
    </div>
  );
}

function TimelineTab({ accountId }: { accountId: string }) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<'all' | 'trade' | 'alert'>('all');
  const loaded = useRef(false);

  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;
    (async () => {
      try { const res = await adminApi.userTimeline(accountId); setEvents(res.events || []); }
      catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
      finally { setLoading(false); }
    })();
  }, [accountId]);

  const visible = filter === 'all' ? events : events.filter(e => e.type === filter);
  if (loading) return <div className="flex justify-center py-12"><Spinner size={24} /></div>;

  return (
    <div>
      <ErrorBanner message={error} />
      <div className="flex gap-1.5 mb-5">
        {(['all', 'trade', 'alert'] as const).map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={cn('px-3.5 py-1.5 rounded-full text-xs font-medium capitalize border transition-colors',
              filter === f ? 'bg-[rgb(var(--tm-brand))]/10 text-[rgb(var(--tm-brand))] border-[rgb(var(--tm-brand))]/40' : 'bg-card text-muted-foreground border-border hover:text-foreground')}>
            {f === 'all' ? `All (${events.length})` : f === 'trade' ? `Trades (${events.filter(e => e.type === 'trade').length})` : `Alerts (${events.filter(e => e.type === 'alert').length})`}
          </button>
        ))}
      </div>
      {visible.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground text-[13px]">No events found</div>
      ) : (
        <div className="relative">
          <div className="absolute left-[15px] top-[18px] bottom-0 w-px bg-border" />
          <div className="flex flex-col gap-px">{visible.map(ev => <TimelineRow key={ev.id} ev={ev} />)}</div>
        </div>
      )}
    </div>
  );
}

// ── Limits tab ───────────────────────────────────────────────────────────────────
function LimitsTab({ data, accountId, onSaved }: { data: DetailData; accountId: string; onSaved: () => void }) {
  const p = data.profile;
  const [form, setForm] = useState({
    daily_trade_limit: String(p?.daily_trade_limit ?? ''),
    daily_loss_limit: String(p?.daily_loss_limit ?? ''),
    cooldown_after_loss: String(p?.cooldown_after_loss ?? ''),
    max_position_size: String(p?.max_position_size ?? ''),
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  const isDirty =
    form.daily_trade_limit !== String(p?.daily_trade_limit ?? '') ||
    form.daily_loss_limit !== String(p?.daily_loss_limit ?? '') ||
    form.cooldown_after_loss !== String(p?.cooldown_after_loss ?? '') ||
    form.max_position_size !== String(p?.max_position_size ?? '');

  const handleSave = async () => {
    setSaving(true); setError(''); setSaved(false);
    const body: Record<string, number> = {};
    const dtl = parseInt(form.daily_trade_limit);
    const dll = parseFloat(form.daily_loss_limit);
    const cal = parseInt(form.cooldown_after_loss);
    const mps = parseFloat(form.max_position_size);
    if (!isNaN(dtl) && form.daily_trade_limit) body.daily_trade_limit = dtl;
    if (!isNaN(dll) && form.daily_loss_limit) body.daily_loss_limit = dll;
    if (!isNaN(cal) && form.cooldown_after_loss) body.cooldown_after_loss = cal;
    if (!isNaN(mps) && form.max_position_size) body.max_position_size = mps;
    if (!Object.keys(body).length) { setError('No valid values to save'); setSaving(false); return; }
    try {
      await adminApi.updateUserLimits(accountId, body);
      setSaved(true); onSaved(); setTimeout(() => setSaved(false), 3000);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setSaving(false); }
  };

  const field = (key: keyof typeof form, label: string, suffix: string, props: React.InputHTMLAttributes<HTMLInputElement>, prefix?: string) => (
    <div className="space-y-2">
      <Label>{label}</Label>
      <div className="relative flex items-center">
        {prefix && <span className="absolute left-3 text-sm text-muted-foreground">{prefix}</span>}
        <Input type="number" value={form[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
          placeholder={p?.[key as keyof typeof p] ? `Current: ${p[key as keyof typeof p]}` : 'Not set'}
          className={cn('tabular-nums', prefix && 'pl-7')} {...props} />
        <span className="absolute right-3 text-xs text-muted-foreground pointer-events-none">{suffix}</span>
      </div>
    </div>
  );

  return (
    <div className="max-w-[520px]">
      <p className="text-[13px] text-muted-foreground mb-6 leading-relaxed">
        Override this user's self-configured plan limits. Changes take effect on the next trade detection cycle. Leave fields blank to keep current values.
      </p>
      <ErrorBanner message={error} />
      <div className="flex flex-col gap-5">
        {field('daily_trade_limit', 'Daily Trade Limit', 'trades / day', { min: 1, max: 500 })}
        {field('daily_loss_limit', 'Daily Loss Limit', '', { min: 0 }, '₹')}
        {field('cooldown_after_loss', 'Cooldown After Loss', 'minutes', { min: 0, max: 1440 })}
        {field('max_position_size', 'Max Position Size', '% of capital', { min: 0.1, max: 100, step: 0.1 })}
        <div className="flex items-center gap-3 pt-1">
          <Button onClick={handleSave} disabled={saving || !isDirty}>
            {saving && <Spinner size={14} />} {saving ? 'Saving…' : 'Save Changes'}
          </Button>
          {saved && <span className="text-xs flex items-center gap-1.5" style={{ color: ACCENT_RGB.profit }}><CheckCircle size={13} /> Saved</span>}
        </div>
      </div>
    </div>
  );
}

// ── Comms tab ────────────────────────────────────────────────────────────────────
function CommsTab({ data, accountId }: { data: DetailData; accountId: string }) {
  const phone = data.user?.guardian_phone;
  const [pushStatus, setPushStatus] = useState<PushStatus | null>(null);
  const [loadingPush, setLoadingPush] = useState(true);
  const [testingPush, setTestingPush] = useState(false);
  const [testPushResult, setTestPushResult] = useState<string | null>(null);
  const pushLoaded = useRef(false);
  const [msgText, setMsgText] = useState('');
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [history, setHistory] = useState<MsgHistory[]>([]);
  const [loadingHist, setLoadingHist] = useState(true);

  useEffect(() => {
    if (pushLoaded.current) return;
    pushLoaded.current = true;
    adminApi.userPushStatus(accountId).then(setPushStatus).catch(() => setPushStatus(null)).finally(() => setLoadingPush(false));
    adminApi.messageHistory(accountId).then(setHistory).catch(() => {}).finally(() => setLoadingHist(false));
  }, [accountId]);

  const sendTestPush = async () => {
    setTestingPush(true); setTestPushResult(null);
    try { await adminApi.userTestPush(accountId); setTestPushResult('success'); }
    catch (e: unknown) { setTestPushResult('error:' + (e instanceof Error ? e.message : String(e))); }
    finally { setTestingPush(false); }
  };

  const sendMsg = async () => {
    if (!msgText.trim()) return;
    setSending(true); setSendResult(null);
    try {
      await adminApi.sendMessage(accountId, msgText);
      setSendResult({ ok: true, msg: 'Sent successfully' }); setMsgText('');
      adminApi.messageHistory(accountId).then(setHistory).catch(() => {});
    } catch (e: unknown) { setSendResult({ ok: false, msg: e instanceof Error ? e.message : String(e) }); }
    finally { setSending(false); }
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Push */}
      <div className="tm-card">
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
          <div className="flex items-center gap-2"><Smartphone size={13} className="text-muted-foreground" /><span className="tm-label">Push Notifications</span></div>
          {pushStatus && pushStatus.subscription_count > 0 && (
            <Button variant="outline" size="sm" onClick={sendTestPush} disabled={testingPush}>
              {testingPush ? <Spinner size={12} /> : <Zap size={12} />} Send test push
            </Button>
          )}
        </div>
        <div className="p-5">
          {loadingPush ? (
            <div className="flex gap-2 items-center text-muted-foreground text-xs"><Spinner size={14} /> Loading…</div>
          ) : !pushStatus ? (
            <p className="text-muted-foreground text-xs">Failed to load push status</p>
          ) : pushStatus.subscription_count === 0 ? (
            <div className="flex items-center gap-2"><WifiOff size={14} className="text-muted-foreground" /><span className="text-xs text-muted-foreground">No push subscriptions — user hasn't enabled notifications</span></div>
          ) : (
            <>
              <div className="flex gap-4 mb-4">
                <div><div className="text-[22px] font-bold tabular-nums" style={{ color: ACCENT_RGB.profit }}>{pushStatus.subscription_count}</div><div className="text-[11px] text-muted-foreground">subscribed {pushStatus.subscription_count === 1 ? 'device' : 'devices'}</div></div>
                <div><div className="text-[22px] font-bold tabular-nums text-foreground">{pushStatus.total_pushes_sent}</div><div className="text-[11px] text-muted-foreground">total sent</div></div>
                <div><div className="text-[13px] font-semibold text-foreground">{relativeTime(pushStatus.last_push_at)}</div><div className="text-[11px] text-muted-foreground">last push</div></div>
              </div>
              <div className="flex flex-col gap-1.5">
                {pushStatus.subscriptions.map(s => (
                  <div key={s.id} className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-muted border border-border">
                    {s.device_type === 'mobile' ? <Smartphone size={13} className="text-muted-foreground shrink-0" /> : <Monitor size={13} className="text-muted-foreground shrink-0" />}
                    <span className="text-xs text-foreground capitalize">{s.device_type || 'Unknown device'}</span>
                    <span className="text-[11px] text-muted-foreground/60 font-mono">…{s.endpoint_tail}</span>
                    <span className="ml-auto text-[11px] text-muted-foreground">{fmtDate(s.created_at)}</span>
                  </div>
                ))}
              </div>
              {testPushResult && (
                <div className="mt-3 text-xs" style={{ color: testPushResult === 'success' ? ACCENT_RGB.profit : ACCENT_RGB.loss }}>
                  {testPushResult === 'success' ? '✓ Test push sent' : testPushResult.slice(6)}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* WhatsApp */}
      <div className="tm-card">
        <div className="px-5 py-3.5 border-b border-border flex items-center gap-2"><Send size={13} className="text-muted-foreground" /><span className="tm-label">WhatsApp</span></div>
        <div className="p-5">
          {!phone ? (
            <p className="text-muted-foreground text-xs">No phone number — user must set a guardian phone in settings</p>
          ) : (
            <>
              <div className="text-xs text-muted-foreground mb-3.5">Sending to <span className="text-foreground font-mono">{phone}</span></div>
              <Textarea value={msgText} onChange={e => setMsgText(e.target.value.slice(0, 700))} placeholder="Type a message…" rows={3} />
              <div className="flex items-center justify-between mt-2.5">
                <span className="text-[11px] text-muted-foreground/60">{msgText.length}/700</span>
                <Button size="sm" onClick={sendMsg} disabled={!msgText.trim() || sending}>
                  {sending ? <Spinner size={13} /> : <Send size={13} />} {sending ? 'Sending…' : 'Send'}
                </Button>
              </div>
              {sendResult && <div className="mt-2.5 text-xs" style={{ color: sendResult.ok ? ACCENT_RGB.profit : ACCENT_RGB.loss }}>{sendResult.msg}</div>}
            </>
          )}
        </div>
      </div>

      {/* History */}
      <div className="tm-card">
        <div className="px-5 py-3.5 border-b border-border"><span className="tm-label">Message History</span></div>
        <div>
          {loadingHist ? (
            <div className="px-5 py-4 flex gap-2 items-center text-muted-foreground text-xs"><Spinner size={14} /> Loading…</div>
          ) : history.length === 0 ? (
            <p className="px-5 py-4 text-xs text-muted-foreground">No messages sent yet</p>
          ) : history.map(m => (
            <div key={m.id} className="px-5 py-2.5 border-b border-border last:border-0">
              <div className="flex justify-between items-center mb-1">
                <span className="text-[11px] text-muted-foreground/60">{m.admin_email}</span>
                <div className="flex gap-3 items-center">
                  <span className="text-[11px]" style={{ color: m.success ? ACCENT_RGB.profit : ACCENT_RGB.loss }}>{m.success ? 'delivered' : 'failed'}</span>
                  <span className="text-[11px] text-muted-foreground/60">{relativeTime(m.created_at)}</span>
                </div>
              </div>
              <p className="text-xs text-muted-foreground m-0">{m.preview}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Main ─────────────────────────────────────────────────────────────────────────
export default function AdminUserDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { admin: currentAdmin } = useAdminAuth();
  const isSuperadmin = currentAdmin?.role === 'superadmin';
  const canImpersonate = currentAdmin?.role === 'superadmin' || currentAdmin?.role === 'ops';
  const [impersonating, setImpersonating] = useState(false);

  const [data, setData] = useState<DetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<Tab>('Overview');

  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [suspending, setSuspending] = useState(false);
  const [eraseOpen, setEraseOpen] = useState(false);
  const [erasing, setErasing] = useState(false);
  const [clearing, setClearing] = useState(false);

  const load = async () => {
    if (!id) return;
    setLoading(true); setError('');
    try { setData(await adminApi.userDetail(id)); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleForceSync = async () => {
    if (!id) return;
    setSyncing(true); setSyncResult(null);
    try {
      const r = await adminApi.userForceSync(id);
      setSyncResult({ ok: true, msg: `Synced ${r.trades_synced} trades, ${r.positions_synced} positions` });
      load();
    } catch (e: unknown) { setSyncResult({ ok: false, msg: e instanceof Error ? e.message : String(e) }); }
    finally { setSyncing(false); setTimeout(() => setSyncResult(null), 6000); }
  };

  const handleSuspend = async () => {
    if (!id || suspending) return;
    setSuspending(true);
    try { await adminApi.suspendUser(id); await load(); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setSuspending(false); }
  };

  const handleErase = async () => {
    if (!id) return;
    setErasing(true);
    try { await adminApi.eraseUser(id); await load(); setEraseOpen(false); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setErasing(false); }
  };

  const handleImpersonate = async () => {
    if (!id) return;
    setImpersonating(true);
    try {
      const res = await adminApi.impersonateUser(id);
      const exp = Math.floor(Date.now() / 1000) + (res.expires_in || 1800);
      const params = new URLSearchParams({ token: res.token, name: res.display || 'user', by: currentAdmin?.email || '', exp: String(exp) });
      window.open(`/impersonate#${params.toString()}`, '_blank', 'noopener');
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setImpersonating(false); }
  };

  const handleClearRateLimit = async () => {
    if (!id) return;
    setClearing(true);
    try { const r = await adminApi.clearUserRateLimit(id); setSyncResult({ ok: true, msg: `Cleared ${r.keys_cleared} rate-limit key(s)` }); }
    catch (e: unknown) { setSyncResult({ ok: false, msg: e instanceof Error ? e.message : String(e) }); }
    finally { setClearing(false); setTimeout(() => setSyncResult(null), 5000); }
  };

  if (loading) return <div className="flex justify-center items-center py-[72px]"><Spinner size={24} /></div>;

  if (error && !data) return (
    <div className="px-6 py-6 md:px-8">
      <Button variant="ghost" size="sm" className="mb-5 -ml-2" onClick={() => navigate('/admin/users')}><ArrowLeft size={14} /> Back to Users</Button>
      <ErrorBanner message={error} />
    </div>
  );
  if (!data) return null;

  const { account, user, stats } = data;
  const isSuspended = account.status === 'suspended';
  const isErased = account.status === 'erased';
  const displayName = user?.display_name || user?.email || account.broker_email || account.broker_user_id;
  const initials = (displayName || '??').split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase();
  const lc = LC_ACCENT[data.lifecycle] || LC_ACCENT.inactive;

  return (
    <div className="px-6 py-6 md:px-8 mx-auto w-full" style={{ maxWidth: 1040 }}>
      <Button variant="ghost" size="sm" className="mb-5 -ml-2 text-muted-foreground" onClick={() => navigate('/admin/users')}><ArrowLeft size={13} /> Users</Button>

      {/* Header card */}
      <div className="tm-card mb-4 border-t-2" style={{ borderTopColor: ACCENT_RGB.brand }}>
        <div className="p-6 flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl shrink-0 flex items-center justify-center text-[17px] font-bold bg-[rgb(var(--tm-brand))]/10 border border-[rgb(var(--tm-brand))]/20 text-[rgb(var(--tm-brand))]">{initials}</div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2.5 flex-wrap mb-1.5">
              <h1 className="text-foreground m-0">{displayName}</h1>
              <Pill accent={lc.accent} label={lc.label} />
              <Pill accent={account.status === 'connected' ? 'profit' : account.status === 'suspended' ? 'loss' : 'muted'} label={account.status} capitalize />
            </div>
            <div className="flex gap-4 flex-wrap">
              {[account.broker_user_id && `ID: ${account.broker_user_id}`, user?.email, user?.guardian_phone, account.created_at && `Joined ${fmtDate(account.created_at)}`]
                .filter(Boolean).map(s => <span key={s as string} className="text-xs text-muted-foreground">{s}</span>)}
            </div>
          </div>
          <div className="flex gap-2 items-center shrink-0 flex-wrap justify-end">
            {canImpersonate && !isErased && (
              <Button variant="outline" size="sm" onClick={handleImpersonate} disabled={impersonating} title="Open a read-only view of this user's app in a new tab">
                {impersonating ? <Spinner size={13} /> : <Eye size={13} />} View as user
              </Button>
            )}
            {account.status === 'connected' && (
              <Button variant="outline" size="sm" onClick={handleForceSync} disabled={syncing}>
                {syncing ? <Spinner size={13} /> : <RefreshCw size={13} />} {syncing ? 'Syncing…' : 'Force Sync'}
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={handleClearRateLimit} disabled={clearing}>
              {clearing ? <Spinner size={13} /> : <RotateCcw size={13} />} Reset Limits
            </Button>
            {!isErased && (
              <Button variant="outline" size="sm" onClick={handleSuspend} disabled={suspending}
                style={{ color: isSuspended ? ACCENT_RGB.profit : ACCENT_RGB.loss }}>
                {suspending ? <Spinner size={13} /> : isSuspended ? <CheckCircle size={13} /> : <Ban size={13} />}
                {isSuspended ? 'Unsuspend' : 'Suspend'}
              </Button>
            )}
            {isSuperadmin && !isErased && (
              <Button variant="outline" size="sm" onClick={() => setEraseOpen(true)} style={{ color: ACCENT_RGB.loss }}>
                <Trash2 size={13} /> DPDP Erase
              </Button>
            )}
          </div>
        </div>
        {syncResult && (
          <div className="px-6 py-2 border-t border-border flex items-center gap-2"
            style={{ background: `color-mix(in srgb, ${syncResult.ok ? ACCENT_RGB.profit : ACCENT_RGB.loss} 8%, transparent)` }}>
            {syncResult.ok ? <CheckCircle size={13} style={{ color: ACCENT_RGB.profit }} /> : <AlertTriangle size={13} style={{ color: ACCENT_RGB.loss }} />}
            <span className="text-xs" style={{ color: syncResult.ok ? ACCENT_RGB.profit : ACCENT_RGB.loss }}>{syncResult.msg}</span>
          </div>
        )}
      </div>

      {/* DPDP erase confirm */}
      <AlertDialog open={eraseOpen} onOpenChange={setEraseOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2" style={{ color: ACCENT_RGB.loss }}><AlertTriangle size={18} /> DPDP Permanent Erasure</AlertDialogTitle>
            <AlertDialogDescription>
              Permanently wipes all PII: email, phone, access tokens, API keys. Sets status to "erased". <strong style={{ color: ACCENT_RGB.loss }}>This is irreversible.</strong>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={erasing}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={(e) => { e.preventDefault(); handleErase(); }} disabled={erasing}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              {erasing ? 'Erasing…' : 'Confirm Permanent Erasure'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {error && <ErrorBanner message={error} />}

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 mb-4">
        <KpiCard label="Total Trades" value={stats.total_trades} sub={stats.last_trade_at ? `Last ${relativeTime(stats.last_trade_at)}` : 'No trades yet'} />
        <KpiCard label="Total Alerts" value={stats.total_alerts} />
        <KpiCard label="Push Devices" value={stats.push_subscription_count} accent={stats.push_subscription_count > 0 ? 'profit' : undefined} />
        <KpiCard label="Account Status" value={account.status} sub={account.broker_user_id || undefined}
          accent={account.status === 'connected' ? 'profit' : account.status === 'suspended' ? 'loss' : undefined} />
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-border mb-5">
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={cn('px-4 py-2.5 text-[13px] font-medium border-b-2 -mb-px transition-colors',
              tab === t ? 'text-[rgb(var(--tm-brand))] border-[rgb(var(--tm-brand))]' : 'text-muted-foreground border-transparent hover:text-foreground')}>
            {t}
          </button>
        ))}
      </div>

      {tab === 'Overview' && <OverviewTab data={data} />}
      {tab === 'Timeline' && <TimelineTab accountId={id!} />}
      {tab === 'Limits'   && <LimitsTab data={data} accountId={id!} onSaved={load} />}
      {tab === 'Comms'    && <CommsTab data={data} accountId={id!} />}
    </div>
  );
}
