import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, RefreshCw, Ban, CheckCircle, Trash2, Send,
  TrendingUp, TrendingDown, Bell, Smartphone, Monitor,
  Zap, AlertTriangle, Clock, RotateCcw, Wifi, WifiOff,
  ChevronDown, Circle,
} from 'lucide-react';
import { adminApi } from '@/lib/adminApi';
import { useAdminAuth } from '@/contexts/AdminAuthContext';

// ─── Design tokens ───────────────────────────────────────────────────────────
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
  blueBg:   'rgba(59,130,246,0.1)',
};

const TABS = ['Overview', 'Timeline', 'Limits', 'Comms'] as const;
type Tab = typeof TABS[number];

// ─── Lifecycle config ────────────────────────────────────────────────────────
const LC: Record<string, { color: string; bg: string; label: string }> = {
  new:          { color: T.blue,  bg: T.blueBg,   label: 'New' },
  active:       { color: T.green, bg: T.greenBg,  label: 'Active' },
  at_risk:      { color: T.amber, bg: T.amberBg,  label: 'At Risk' },
  churned:      { color: T.red,   bg: T.redBg,    label: 'Churned' },
  inactive:     { color: T.muted, bg: 'rgba(107,106,130,0.12)', label: 'Inactive' },
  suspended:    { color: T.red,   bg: T.redBg,    label: 'Suspended' },
  disconnected: { color: T.muted, bg: 'rgba(107,106,130,0.12)', label: 'Disconnected' },
};

const SEV: Record<string, string> = {
  critical: '#ef4444', high: '#f97316', medium: T.amber, low: T.green, info: T.muted,
};

// ─── Types ───────────────────────────────────────────────────────────────────
interface DetailData {
  account: {
    id: string; broker_user_id: string; broker_email: string | null;
    status: string; sync_status: string; last_sync_at: string | null;
    connected_at: string | null; created_at: string | null;
  };
  user: {
    id: string | null; email: string | null; display_name: string | null;
    guardian_phone: string | null; guardian_name: string | null;
    guardian_confirmed: boolean;
  } | null;
  profile: {
    trading_style: string | null; experience_level: string | null;
    risk_tolerance: string | null; trading_capital: number | null;
    daily_trade_limit: number | null; daily_loss_limit: number | null;
    max_position_size: number | null; cooldown_after_loss: number | null;
    push_enabled: boolean; whatsapp_enabled: boolean; email_enabled: boolean;
    alert_sensitivity: string | null; onboarding_completed: boolean;
  } | null;
  stats: {
    total_trades: number; total_alerts: number;
    push_subscription_count: number; last_trade_at: string | null;
  };
  lifecycle: string;
  recent_alerts: {
    id: string; pattern_type: string; severity: string;
    message: string; detected_at: string | null; acknowledged: boolean;
  }[];
}

interface TimelineEvent {
  type: 'trade' | 'alert';
  time: string | null;
  id: string;
  // trade
  symbol?: string; direction?: string; product?: string;
  status?: string; quantity?: number; price?: number | null; exchange?: string;
  // alert
  pattern?: string; severity?: string; message?: string; acknowledged?: boolean;
}

interface PushStatus {
  subscription_count: number;
  subscriptions: { id: string; device_type: string; created_at: string | null; endpoint_tail: string | null }[];
  last_push_at: string | null; last_push_pattern: string | null; total_pushes_sent: number;
}

interface MsgHistory {
  id: string; admin_email: string; preview: string | null;
  to: string | null; success: boolean | null; created_at: string | null;
}

// ─── Utilities ───────────────────────────────────────────────────────────────
function fmtTs(iso: string | null, opts?: Intl.DateTimeFormatOptions): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
    ...opts,
  });
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-IN', {
    timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric',
  });
}

function relativeTime(iso: string | null): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1)  return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function fmtINR(n: number | null | undefined): string {
  if (n == null) return '—';
  return '₹' + n.toLocaleString('en-IN');
}

// ─── Shared sub-components ───────────────────────────────────────────────────
function Spinner({ size = 20 }: { size?: number }) {
  return (
    <>
      <div style={{
        width: size, height: size, borderRadius: '50%',
        border: `2px solid ${T.amber}`, borderTopColor: 'transparent',
        animation: 'spin 0.75s linear infinite', flexShrink: 0,
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </>
  );
}

function InlineError({ msg }: { msg: string }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '9px 14px', borderRadius: 8, marginBottom: 16,
      background: T.redBg, border: `1px solid rgba(239,68,68,0.2)`,
    }}>
      <AlertTriangle size={13} style={{ color: T.red, flexShrink: 0 }} />
      <span style={{ fontSize: 12, color: T.red }}>{msg}</span>
    </div>
  );
}

function StatChip({ label, value, sub, accent }: {
  label: string; value: string | number; sub?: string; accent?: string;
}) {
  return (
    <div style={{
      background: T.surface, border: `1px solid ${T.border}`,
      borderRadius: 10, padding: '14px 18px',
    }}>
      <div style={{ fontSize: 11, fontWeight: 500, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>
        {label}
      </div>
      <div style={{
        fontSize: 22, fontWeight: 700, color: accent || T.text,
        fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.02em',
      }}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
      {sub && <div style={{ fontSize: 11, color: T.muted, marginTop: 3 }}>{sub}</div>}
    </div>
  );
}

function LifecyclePill({ lc }: { lc: string }) {
  const cfg = LC[lc] || LC.inactive;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 10px', borderRadius: 20,
      background: cfg.bg, fontSize: 11, fontWeight: 600,
      color: cfg.color, letterSpacing: '0.03em',
    }}>
      <Circle size={5} fill={cfg.color} style={{ color: cfg.color }} />
      {cfg.label}
    </span>
  );
}

function StatusPill({ status }: { status: string }) {
  const color = status === 'connected' ? T.green : status === 'suspended' ? T.red : T.muted;
  const bg    = status === 'connected' ? T.greenBg : status === 'suspended' ? T.redBg : 'rgba(107,106,130,0.1)';
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 10px', borderRadius: 20,
      background: bg, fontSize: 11, fontWeight: 600,
      color, letterSpacing: '0.03em', textTransform: 'capitalize',
    }}>
      <Circle size={5} fill={color} style={{ color }} />
      {status}
    </span>
  );
}

// ─── Tab content components ──────────────────────────────────────────────────
function OverviewTab({ data }: { data: DetailData }) {
  const { profile, user, account, recent_alerts } = data;

  const profileRows: [string, string][] = [
    ['Trading style',  profile?.trading_style     ? profile.trading_style.charAt(0).toUpperCase() + profile.trading_style.slice(1) : '—'],
    ['Experience',     profile?.experience_level  ? profile.experience_level.charAt(0).toUpperCase() + profile.experience_level.slice(1) : '—'],
    ['Risk tolerance', profile?.risk_tolerance    ? profile.risk_tolerance.charAt(0).toUpperCase() + profile.risk_tolerance.slice(1) : '—'],
    ['Capital deployed', fmtINR(profile?.trading_capital ?? null)],
    ['Alert sensitivity', profile?.alert_sensitivity || '—'],
    ['Onboarding', profile?.onboarding_completed ? 'Completed' : 'Incomplete'],
  ];

  const notifRows: [string, boolean][] = [
    ['Push notifications', profile?.push_enabled ?? false],
    ['WhatsApp alerts',    profile?.whatsapp_enabled ?? false],
    ['Email alerts',       profile?.email_enabled ?? false],
  ];

  const guardianRows: [string, string][] = [
    ['Phone',     user?.guardian_phone || '—'],
    ['Name',      user?.guardian_name  || '—'],
    ['Confirmed', user?.guardian_confirmed ? 'Yes' : 'No'],
  ];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 16 }}>
      {/* Left column */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Profile */}
        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10 }}>
          <div style={{ padding: '14px 20px', borderBottom: `1px solid ${T.border}` }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em' }}>Trading Profile</span>
          </div>
          <div style={{ padding: '6px 0' }}>
            {profileRows.map(([k, v]) => (
              <div key={k} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '9px 20px', borderBottom: `1px solid ${T.border}`,
              }}>
                <span style={{ fontSize: 12, color: T.muted }}>{k}</span>
                <span style={{ fontSize: 13, fontWeight: 500, color: T.text }}>{v}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Notifications */}
        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10 }}>
          <div style={{ padding: '14px 20px', borderBottom: `1px solid ${T.border}` }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em' }}>Notification Channels</span>
          </div>
          {notifRows.map(([k, v]) => (
            <div key={k} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '10px 20px', borderBottom: `1px solid ${T.border}`,
            }}>
              <span style={{ fontSize: 12, color: T.muted }}>{k}</span>
              <span style={{ fontSize: 12, fontWeight: 600, color: v ? T.green : T.muted }}>
                {v ? 'On' : 'Off'}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Right column */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Guardian */}
        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10 }}>
          <div style={{ padding: '14px 20px', borderBottom: `1px solid ${T.border}` }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em' }}>Guardian</span>
          </div>
          {guardianRows.map(([k, v]) => (
            <div key={k} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '9px 20px', borderBottom: `1px solid ${T.border}`,
            }}>
              <span style={{ fontSize: 12, color: T.muted }}>{k}</span>
              <span style={{ fontSize: 12, color: T.text }}>{v}</span>
            </div>
          ))}
        </div>

        {/* Account meta */}
        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10 }}>
          <div style={{ padding: '14px 20px', borderBottom: `1px solid ${T.border}` }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em' }}>Account</span>
          </div>
          {[
            ['Account ID', account.id.slice(0, 8) + '…'],
            ['Zerodha ID', account.broker_user_id || '—'],
            ['Sync status', account.sync_status || '—'],
            ['Last synced', relativeTime(account.last_sync_at)],
            ['Connected',   fmtDate(account.connected_at)],
          ].map(([k, v]) => (
            <div key={k} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '9px 20px', borderBottom: `1px solid ${T.border}`,
            }}>
              <span style={{ fontSize: 12, color: T.muted }}>{k}</span>
              <span style={{ fontSize: 12, color: T.text, fontFamily: 'monospace' }}>{v}</span>
            </div>
          ))}
        </div>

        {/* Recent alerts */}
        {recent_alerts.length > 0 && (
          <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10 }}>
            <div style={{ padding: '14px 20px', borderBottom: `1px solid ${T.border}` }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em' }}>Recent Alerts</span>
            </div>
            {recent_alerts.slice(0, 5).map(a => (
              <div key={a.id} style={{
                display: 'flex', alignItems: 'flex-start', gap: 10,
                padding: '10px 16px', borderBottom: `1px solid ${T.border}`,
              }}>
                <span style={{
                  fontSize: 10, fontWeight: 700, padding: '2px 7px',
                  borderRadius: 20, flexShrink: 0, marginTop: 1,
                  background: `${SEV[a.severity] || T.muted}18`,
                  color: SEV[a.severity] || T.muted, textTransform: 'uppercase', letterSpacing: '0.05em',
                }}>{a.severity}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, color: T.text, textTransform: 'capitalize' }}>
                    {a.pattern_type.replace(/_/g, ' ')}
                  </div>
                  <div style={{ fontSize: 11, color: T.muted, marginTop: 1 }}>{relativeTime(a.detected_at)}</div>
                </div>
                {a.acknowledged && <CheckCircle size={12} style={{ color: T.green, flexShrink: 0, marginTop: 2 }} />}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TimelineTab({ accountId }: { accountId: string }) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState('');
  const [filter, setFilter] = useState<'all' | 'trade' | 'alert'>('all');
  const loaded = useRef(false);

  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;
    (async () => {
      try {
        const res = await adminApi.userTimeline(accountId);
        setEvents(res.events || []);
      } catch (e: any) { setError(e.message); }
      finally { setLoading(false); }
    })();
  }, [accountId]);

  const visible = filter === 'all' ? events : events.filter(e => e.type === filter);

  if (loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
      <Spinner size={24} />
    </div>
  );

  return (
    <div>
      {error && <InlineError msg={error} />}

      {/* Filter bar */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 20 }}>
        {(['all', 'trade', 'alert'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{
              padding: '5px 14px', borderRadius: 20, fontSize: 12, fontWeight: 500,
              cursor: 'pointer', textTransform: 'capitalize',
              border: filter === f ? `1px solid ${T.amber}` : `1px solid ${T.border}`,
              background: filter === f ? T.amberBg : T.surface,
              color: filter === f ? T.amber : T.muted,
              transition: 'all 0.12s',
            }}
          >
            {f === 'all' ? `All (${events.length})` : f === 'trade' ? `Trades (${events.filter(e => e.type === 'trade').length})` : `Alerts (${events.filter(e => e.type === 'alert').length})`}
          </button>
        ))}
      </div>

      {visible.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '48px 0', color: T.muted, fontSize: 13 }}>
          No events found
        </div>
      ) : (
        <div style={{ position: 'relative' }}>
          {/* Vertical rail */}
          <div style={{
            position: 'absolute', left: 15, top: 18, bottom: 0,
            width: 1, background: T.border,
          }} />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {visible.map(ev => (
              <TimelineRow key={ev.id} ev={ev} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function TimelineRow({ ev }: { ev: TimelineEvent }) {
  const isTrade = ev.type === 'trade';
  const isBuy   = ev.direction === 'BUY';

  const dotColor = isTrade
    ? (isBuy ? T.green : T.red)
    : (SEV[ev.severity || ''] || T.amber);

  return (
    <div style={{
      display: 'flex', gap: 16, alignItems: 'flex-start',
      padding: '10px 0 10px 0',
    }}>
      {/* Dot */}
      <div style={{
        width: 30, flexShrink: 0, display: 'flex', justifyContent: 'center',
        paddingTop: 2,
      }}>
        <div style={{
          width: 9, height: 9, borderRadius: '50%',
          background: dotColor,
          boxShadow: `0 0 0 2px ${T.bg}, 0 0 0 3px ${dotColor}40`,
          flexShrink: 0,
        }} />
      </div>

      {/* Content */}
      <div style={{
        flex: 1, background: T.surface, border: `1px solid ${T.border}`,
        borderRadius: 9, padding: '10px 14px', minWidth: 0,
      }}>
        {isTrade ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            {isBuy
              ? <TrendingUp size={13} style={{ color: T.green, flexShrink: 0 }} />
              : <TrendingDown size={13} style={{ color: T.red, flexShrink: 0 }} />}
            <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{ev.symbol}</span>
            <span style={{
              fontSize: 10, fontWeight: 700, padding: '1px 7px', borderRadius: 20,
              background: isBuy ? T.greenBg : T.redBg,
              color: isBuy ? T.green : T.red,
            }}>{ev.direction}</span>
            <span style={{
              fontSize: 10, fontWeight: 500, padding: '1px 7px', borderRadius: 20,
              background: T.raised, color: T.muted, border: `1px solid ${T.border}`,
            }}>{ev.product}</span>
            <div style={{ marginLeft: 'auto', display: 'flex', flex: 'flex-end', gap: 12, alignItems: 'center' }}>
              <span style={{ fontSize: 11, color: T.muted, fontVariantNumeric: 'tabular-nums' }}>
                {ev.quantity} lots{ev.price ? ` @ ₹${Number(ev.price).toFixed(2)}` : ''}
              </span>
              <span style={{ fontSize: 11, color: T.dim, whiteSpace: 'nowrap' }}>
                {fmtTs(ev.time, { hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short' })}
              </span>
            </div>
          </div>
        ) : (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <Bell size={12} style={{ color: SEV[ev.severity || ''] || T.amber, flexShrink: 0 }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: T.text, textTransform: 'capitalize' }}>
                {ev.pattern?.replace(/_/g, ' ')}
              </span>
              <span style={{
                fontSize: 10, fontWeight: 700, padding: '1px 7px', borderRadius: 20,
                background: `${SEV[ev.severity || ''] || T.amber}18`,
                color: SEV[ev.severity || ''] || T.amber,
              }}>{ev.severity}</span>
              {ev.acknowledged && (
                <span style={{ fontSize: 10, color: T.green, display: 'flex', alignItems: 'center', gap: 3 }}>
                  <CheckCircle size={10} /> ack'd
                </span>
              )}
              <span style={{ marginLeft: 'auto', fontSize: 11, color: T.dim, whiteSpace: 'nowrap' }}>
                {fmtTs(ev.time, { hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short' })}
              </span>
            </div>
            {ev.message && (
              <div style={{ fontSize: 12, color: T.muted, marginTop: 4, lineHeight: 1.5 }}>
                {ev.message}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function LimitsTab({ data, accountId, onSaved }: {
  data: DetailData; accountId: string; onSaved: () => void;
}) {
  const p = data.profile;
  const [form, setForm] = useState({
    daily_trade_limit:   String(p?.daily_trade_limit  ?? ''),
    daily_loss_limit:    String(p?.daily_loss_limit   ?? ''),
    cooldown_after_loss: String(p?.cooldown_after_loss ?? ''),
    max_position_size:   String(p?.max_position_size  ?? ''),
  });
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState('');
  const [saved, setSaved]   = useState(false);

  const isDirty =
    form.daily_trade_limit   !== String(p?.daily_trade_limit  ?? '') ||
    form.daily_loss_limit    !== String(p?.daily_loss_limit   ?? '') ||
    form.cooldown_after_loss !== String(p?.cooldown_after_loss ?? '') ||
    form.max_position_size   !== String(p?.max_position_size  ?? '');

  const handleSave = async () => {
    setSaving(true); setError(''); setSaved(false);
    const body: Record<string, number> = {};
    const dtl = parseInt(form.daily_trade_limit);
    const dll = parseFloat(form.daily_loss_limit);
    const cal = parseInt(form.cooldown_after_loss);
    const mps = parseFloat(form.max_position_size);
    if (!isNaN(dtl) && form.daily_trade_limit) body.daily_trade_limit  = dtl;
    if (!isNaN(dll) && form.daily_loss_limit)  body.daily_loss_limit   = dll;
    if (!isNaN(cal) && form.cooldown_after_loss) body.cooldown_after_loss = cal;
    if (!isNaN(mps) && form.max_position_size)   body.max_position_size  = mps;

    if (!Object.keys(body).length) {
      setError('No valid values to save'); setSaving(false); return;
    }

    try {
      await adminApi.updateUserLimits(accountId, body);
      setSaved(true);
      onSaved();
      setTimeout(() => setSaved(false), 3000);
    } catch (e: any) { setError(e.message); }
    finally { setSaving(false); }
  };

  const inp = (style?: React.CSSProperties): React.CSSProperties => ({
    padding: '8px 12px', borderRadius: 8, border: `1px solid ${T.border2}`,
    background: T.raised, color: T.text, fontSize: 14,
    fontVariantNumeric: 'tabular-nums', outline: 'none',
    width: '100%', boxSizing: 'border-box',
    fontFamily: "'Inter', 'DM Sans', sans-serif",
    transition: 'border-color 0.12s',
    ...style,
  });

  return (
    <div style={{ maxWidth: 520 }}>
      <p style={{ fontSize: 13, color: T.muted, marginBottom: 24, lineHeight: 1.6 }}>
        Override this user's self-configured plan limits. Changes take effect on the next trade detection cycle. Leave fields blank to keep current values.
      </p>

      {error && <InlineError msg={error} />}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* Trade limit */}
        <div>
          <label style={{ fontSize: 12, fontWeight: 600, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em', display: 'block', marginBottom: 8 }}>
            Daily Trade Limit
          </label>
          <div style={{ position: 'relative' }}>
            <input
              type="number" min={1} max={500} value={form.daily_trade_limit}
              onChange={e => setForm(f => ({ ...f, daily_trade_limit: e.target.value }))}
              placeholder={p?.daily_trade_limit ? `Current: ${p.daily_trade_limit}` : 'Not set'}
              style={inp()}
            />
            <span style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', fontSize: 12, color: T.muted }}>trades / day</span>
          </div>
        </div>

        {/* Loss limit */}
        <div>
          <label style={{ fontSize: 12, fontWeight: 600, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em', display: 'block', marginBottom: 8 }}>
            Daily Loss Limit
          </label>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <span style={{ position: 'absolute', left: 12, fontSize: 14, color: T.muted }}>₹</span>
            <input
              type="number" min={0} value={form.daily_loss_limit}
              onChange={e => setForm(f => ({ ...f, daily_loss_limit: e.target.value }))}
              placeholder={p?.daily_loss_limit ? `Current: ${p.daily_loss_limit}` : 'Not set'}
              style={inp({ paddingLeft: 26 })}
            />
          </div>
        </div>

        {/* Cooldown */}
        <div>
          <label style={{ fontSize: 12, fontWeight: 600, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em', display: 'block', marginBottom: 8 }}>
            Cooldown After Loss
          </label>
          <div style={{ position: 'relative' }}>
            <input
              type="number" min={0} max={1440} value={form.cooldown_after_loss}
              onChange={e => setForm(f => ({ ...f, cooldown_after_loss: e.target.value }))}
              placeholder={p?.cooldown_after_loss ? `Current: ${p.cooldown_after_loss}` : 'Not set'}
              style={inp()}
            />
            <span style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', fontSize: 12, color: T.muted }}>minutes</span>
          </div>
        </div>

        {/* Position size */}
        <div>
          <label style={{ fontSize: 12, fontWeight: 600, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em', display: 'block', marginBottom: 8 }}>
            Max Position Size
          </label>
          <div style={{ position: 'relative' }}>
            <input
              type="number" min={0.1} max={100} step={0.1} value={form.max_position_size}
              onChange={e => setForm(f => ({ ...f, max_position_size: e.target.value }))}
              placeholder={p?.max_position_size ? `Current: ${p.max_position_size}` : 'Not set'}
              style={inp()}
            />
            <span style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', fontSize: 12, color: T.muted }}>% of capital</span>
          </div>
        </div>

        {/* Save */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, paddingTop: 4 }}>
          <button
            onClick={handleSave}
            disabled={saving || !isDirty}
            style={{
              display: 'flex', alignItems: 'center', gap: 7,
              padding: '9px 20px', borderRadius: 9, fontSize: 13, fontWeight: 600,
              cursor: saving || !isDirty ? 'not-allowed' : 'pointer',
              background: isDirty ? T.amber : T.surface,
              color: isDirty ? '#000' : T.muted,
              border: `1px solid ${isDirty ? T.amber : T.border}`,
              opacity: !isDirty ? 0.5 : 1,
              transition: 'all 0.15s', fontFamily: 'inherit',
            }}
          >
            {saving && <Spinner size={14} />}
            {saving ? 'Saving…' : 'Save Changes'}
          </button>
          {saved && (
            <span style={{ fontSize: 12, color: T.green, display: 'flex', alignItems: 'center', gap: 5 }}>
              <CheckCircle size={13} /> Saved
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function CommsTab({ data, accountId }: { data: DetailData; accountId: string }) {
  const phone = data.user?.guardian_phone;

  // Push status
  const [pushStatus, setPushStatus] = useState<PushStatus | null>(null);
  const [loadingPush, setLoadingPush] = useState(true);
  const [testingPush, setTestingPush] = useState(false);
  const [testPushResult, setTestPushResult] = useState<string | null>(null);
  const pushLoaded = useRef(false);

  // WhatsApp
  const [msgText, setMsgText]     = useState('');
  const [sending, setSending]     = useState(false);
  const [sendResult, setSendResult] = useState<{ ok: boolean; msg: string } | null>(null);

  // Message history
  const [history, setHistory]     = useState<MsgHistory[]>([]);
  const [loadingHist, setLoadingHist] = useState(true);

  useEffect(() => {
    if (pushLoaded.current) return;
    pushLoaded.current = true;
    adminApi.userPushStatus(accountId)
      .then(setPushStatus)
      .catch(() => setPushStatus(null))
      .finally(() => setLoadingPush(false));

    adminApi.messageHistory(accountId)
      .then(setHistory)
      .catch(() => {})
      .finally(() => setLoadingHist(false));
  }, [accountId]);

  const sendTestPush = async () => {
    setTestingPush(true); setTestPushResult(null);
    try {
      await adminApi.userTestPush(accountId);
      setTestPushResult('success');
    } catch (e: any) {
      setTestPushResult('error:' + e.message);
    } finally { setTestingPush(false); }
  };

  const sendMsg = async () => {
    if (!msgText.trim()) return;
    setSending(true); setSendResult(null);
    try {
      await adminApi.sendMessage(accountId, msgText);
      setSendResult({ ok: true, msg: 'Sent successfully' });
      setMsgText('');
      adminApi.messageHistory(accountId).then(setHistory).catch(() => {});
    } catch (e: any) {
      setSendResult({ ok: false, msg: e.message });
    } finally { setSending(false); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Push notifications */}
      <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10 }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 20px', borderBottom: `1px solid ${T.border}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Smartphone size={13} style={{ color: T.muted }} />
            <span style={{ fontSize: 12, fontWeight: 600, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em' }}>Push Notifications</span>
          </div>
          {pushStatus && pushStatus.subscription_count > 0 && (
            <button
              onClick={sendTestPush} disabled={testingPush}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '5px 12px', borderRadius: 8, fontSize: 12, fontWeight: 500,
                cursor: testingPush ? 'not-allowed' : 'pointer',
                background: T.raised, border: `1px solid ${T.border2}`,
                color: T.muted, fontFamily: 'inherit',
              }}
            >
              {testingPush ? <Spinner size={12} /> : <Zap size={12} />}
              Send test push
            </button>
          )}
        </div>
        <div style={{ padding: '16px 20px' }}>
          {loadingPush ? (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', color: T.muted, fontSize: 12 }}>
              <Spinner size={14} /> Loading…
            </div>
          ) : !pushStatus ? (
            <p style={{ color: T.muted, fontSize: 12 }}>Failed to load push status</p>
          ) : pushStatus.subscription_count === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <WifiOff size={14} style={{ color: T.muted }} />
              <span style={{ fontSize: 12, color: T.muted }}>No push subscriptions — user hasn't enabled notifications</span>
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: T.green, fontVariantNumeric: 'tabular-nums' }}>
                    {pushStatus.subscription_count}
                  </div>
                  <div style={{ fontSize: 11, color: T.muted }}>subscribed {pushStatus.subscription_count === 1 ? 'device' : 'devices'}</div>
                </div>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: T.text, fontVariantNumeric: 'tabular-nums' }}>
                    {pushStatus.total_pushes_sent}
                  </div>
                  <div style={{ fontSize: 11, color: T.muted }}>total sent</div>
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: T.text }}>
                    {relativeTime(pushStatus.last_push_at)}
                  </div>
                  <div style={{ fontSize: 11, color: T.muted }}>last push</div>
                </div>
              </div>

              {/* Subscriptions list */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {pushStatus.subscriptions.map(s => (
                  <div key={s.id} style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '8px 12px', borderRadius: 8,
                    background: T.raised, border: `1px solid ${T.border}`,
                  }}>
                    {s.device_type === 'mobile'
                      ? <Smartphone size={13} style={{ color: T.muted, flexShrink: 0 }} />
                      : <Monitor size={13} style={{ color: T.muted, flexShrink: 0 }} />}
                    <span style={{ fontSize: 12, color: T.text, textTransform: 'capitalize' }}>
                      {s.device_type || 'Unknown device'}
                    </span>
                    <span style={{ fontSize: 11, color: T.dim, fontFamily: 'monospace' }}>
                      …{s.endpoint_tail}
                    </span>
                    <span style={{ marginLeft: 'auto', fontSize: 11, color: T.muted }}>
                      {fmtDate(s.created_at)}
                    </span>
                  </div>
                ))}
              </div>

              {testPushResult && (
                <div style={{ marginTop: 12, fontSize: 12, color: testPushResult === 'success' ? T.green : T.red }}>
                  {testPushResult === 'success' ? '✓ Test push sent' : testPushResult.slice(6)}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* WhatsApp */}
      <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10 }}>
        <div style={{ padding: '14px 20px', borderBottom: `1px solid ${T.border}`, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Send size={13} style={{ color: T.muted }} />
          <span style={{ fontSize: 12, fontWeight: 600, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em' }}>WhatsApp</span>
        </div>
        <div style={{ padding: '16px 20px' }}>
          {!phone ? (
            <p style={{ color: T.muted, fontSize: 12 }}>No phone number — user must set a guardian phone in settings</p>
          ) : (
            <>
              <div style={{ fontSize: 12, color: T.muted, marginBottom: 14 }}>
                Sending to <span style={{ color: T.text, fontFamily: 'monospace' }}>{phone}</span>
              </div>
              <textarea
                value={msgText}
                onChange={e => setMsgText(e.target.value.slice(0, 700))}
                placeholder="Type a message…"
                rows={3}
                style={{
                  width: '100%', padding: '10px 14px', borderRadius: 9,
                  background: T.raised, border: `1px solid ${T.border2}`,
                  color: T.text, fontSize: 13, resize: 'vertical',
                  outline: 'none', boxSizing: 'border-box',
                  fontFamily: "'Inter', 'DM Sans', sans-serif", lineHeight: 1.5,
                }}
              />
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 10 }}>
                <span style={{ fontSize: 11, color: T.dim }}>{msgText.length}/700</span>
                <button
                  onClick={sendMsg}
                  disabled={!msgText.trim() || sending}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    padding: '8px 18px', borderRadius: 9, fontSize: 13, fontWeight: 600,
                    cursor: !msgText.trim() || sending ? 'not-allowed' : 'pointer',
                    background: msgText.trim() ? T.amberBg : T.surface,
                    color: msgText.trim() ? T.amber : T.muted,
                    border: `1px solid ${msgText.trim() ? T.amber : T.border}`,
                    opacity: !msgText.trim() ? 0.5 : 1,
                    fontFamily: 'inherit', transition: 'all 0.15s',
                  }}
                >
                  {sending ? <Spinner size={13} /> : <Send size={13} />}
                  {sending ? 'Sending…' : 'Send'}
                </button>
              </div>
              {sendResult && (
                <div style={{ marginTop: 10, fontSize: 12, color: sendResult.ok ? T.green : T.red }}>
                  {sendResult.msg}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Message history */}
      <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10 }}>
        <div style={{ padding: '14px 20px', borderBottom: `1px solid ${T.border}` }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em' }}>Message History</span>
        </div>
        <div style={{ padding: '8px 0' }}>
          {loadingHist ? (
            <div style={{ padding: '16px 20px', display: 'flex', gap: 8, alignItems: 'center', color: T.muted, fontSize: 12 }}>
              <Spinner size={14} /> Loading…
            </div>
          ) : history.length === 0 ? (
            <p style={{ padding: '16px 20px', fontSize: 12, color: T.muted }}>No messages sent yet</p>
          ) : history.map(m => (
            <div key={m.id} style={{
              padding: '10px 20px', borderBottom: `1px solid ${T.border}`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <span style={{ fontSize: 11, color: T.dim }}>{m.admin_email}</span>
                <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                  <span style={{ fontSize: 11, color: m.success ? T.green : T.red }}>
                    {m.success ? 'delivered' : 'failed'}
                  </span>
                  <span style={{ fontSize: 11, color: T.dim }}>{relativeTime(m.created_at)}</span>
                </div>
              </div>
              <p style={{ fontSize: 12, color: T.muted, margin: 0 }}>{m.preview}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Main component ──────────────────────────────────────────────────────────
export default function AdminUserDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { admin: currentAdmin } = useAdminAuth();
  const isSuperadmin = currentAdmin?.role === 'superadmin';

  const [data, setData]             = useState<DetailData | null>(null);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');
  const [tab, setTab]               = useState<Tab>('Overview');

  // Action states
  const [syncing, setSyncing]       = useState(false);
  const [syncResult, setSyncResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [suspending, setSuspending] = useState(false);
  const [eraseOpen, setEraseOpen]   = useState(false);
  const [erasing, setErasing]       = useState(false);
  const [clearing, setClearing]     = useState(false);

  const load = async () => {
    if (!id) return;
    setLoading(true); setError('');
    try { setData(await adminApi.userDetail(id)); }
    catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [id]);

  const handleForceSync = async () => {
    if (!id) return;
    setSyncing(true); setSyncResult(null);
    try {
      const r = await adminApi.userForceSync(id);
      setSyncResult({
        ok: true,
        msg: `Synced ${r.trades_synced} trades, ${r.positions_synced} positions`,
      });
      load(); // refresh stats
    } catch (e: any) {
      setSyncResult({ ok: false, msg: e.message });
    } finally {
      setSyncing(false);
      setTimeout(() => setSyncResult(null), 6000);
    }
  };

  const handleSuspend = async () => {
    if (!id || suspending) return;
    setSuspending(true);
    try { await adminApi.suspendUser(id); await load(); }
    catch (e: any) { setError(e.message); }
    finally { setSuspending(false); }
  };

  const handleErase = async () => {
    if (!id) return;
    setErasing(true);
    try { await adminApi.eraseUser(id); await load(); setEraseOpen(false); }
    catch (e: any) { setError(e.message); }
    finally { setErasing(false); }
  };

  const handleClearRateLimit = async () => {
    if (!id) return;
    setClearing(true);
    try {
      const r = await adminApi.clearUserRateLimit(id);
      setSyncResult({ ok: true, msg: `Cleared ${r.keys_cleared} rate-limit key(s)` });
    } catch (e: any) { setSyncResult({ ok: false, msg: e.message }); }
    finally {
      setClearing(false);
      setTimeout(() => setSyncResult(null), 5000);
    }
  };

  // ── Loading / error states ─────────────────────────────────────────────────
  if (loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '72px 0' }}>
      <Spinner size={24} />
    </div>
  );

  if (error && !data) return (
    <div style={{ padding: '28px 32px', fontFamily: "'Inter', 'DM Sans', sans-serif" }}>
      <button onClick={() => navigate('/admin/users')} style={backBtn}>
        <ArrowLeft size={14} /> Back to Users
      </button>
      <InlineError msg={error} />
    </div>
  );

  if (!data) return null;

  const { account, user, stats } = data;
  const isSuspended  = account.status === 'suspended';
  const isErased     = account.status === 'erased';
  const displayName  = user?.display_name || user?.email || account.broker_email || account.broker_user_id;
  const initials     = (displayName || '??').split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase();

  return (
    <div style={{
      padding: '28px 32px',
      fontFamily: "'Inter', 'DM Sans', sans-serif",
      maxWidth: 1040,
    }}>
      {/* Back */}
      <button onClick={() => navigate('/admin/users')} style={backBtn}>
        <ArrowLeft size={13} /> Users
      </button>

      {/* ── Header card ──────────────────────────────────────────────────────── */}
      <div style={{
        background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12,
        borderTop: `2px solid ${T.amber}`, marginBottom: 16,
        overflow: 'hidden',
      }}>
        <div style={{ padding: '20px 24px', display: 'flex', alignItems: 'flex-start', gap: 16 }}>
          {/* Avatar */}
          <div style={{
            width: 48, height: 48, borderRadius: 12, flexShrink: 0,
            background: T.amberBg, border: `1px solid rgba(245,158,11,0.2)`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 17, fontWeight: 700, color: T.amber,
          }}>
            {initials}
          </div>

          {/* Name + meta */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 5 }}>
              <h1 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: 0, letterSpacing: '-0.02em' }}>
                {displayName}
              </h1>
              <LifecyclePill lc={data.lifecycle} />
              <StatusPill status={account.status} />
            </div>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              {[
                account.broker_user_id && `ID: ${account.broker_user_id}`,
                user?.email,
                user?.guardian_phone,
                account.created_at && `Joined ${fmtDate(account.created_at)}`,
              ].filter(Boolean).map(s => (
                <span key={s as string} style={{ fontSize: 12, color: T.muted }}>{s}</span>
              ))}
            </div>
          </div>

          {/* Action buttons */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            {/* Force sync */}
            {account.status === 'connected' && (
              <button onClick={handleForceSync} disabled={syncing} style={actionBtn}>
                {syncing ? <Spinner size={13} /> : <RefreshCw size={13} />}
                {syncing ? 'Syncing…' : 'Force Sync'}
              </button>
            )}

            {/* Rate limit reset */}
            <button onClick={handleClearRateLimit} disabled={clearing} style={actionBtn}>
              {clearing ? <Spinner size={13} /> : <RotateCcw size={13} />}
              Reset Limits
            </button>

            {/* Suspend */}
            {!isErased && (
              <button
                onClick={handleSuspend} disabled={suspending}
                style={{
                  ...actionBtn,
                  background: isSuspended ? T.greenBg : T.redBg,
                  color: isSuspended ? T.green : T.red,
                  border: `1px solid ${isSuspended ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'}`,
                }}
              >
                {suspending
                  ? <Spinner size={13} />
                  : isSuspended ? <CheckCircle size={13} /> : <Ban size={13} />}
                {isSuspended ? 'Unsuspend' : 'Suspend'}
              </button>
            )}

            {/* DPDP */}
            {isSuperadmin && !isErased && (
              <button onClick={() => setEraseOpen(v => !v)} style={{ ...actionBtn, color: T.red, border: '1px solid rgba(239,68,68,0.2)', background: T.redBg }}>
                <Trash2 size={13} /> DPDP Erase
              </button>
            )}
          </div>
        </div>

        {/* Sync / action result banner */}
        {syncResult && (
          <div style={{
            padding: '8px 24px', borderTop: `1px solid ${T.border}`,
            background: syncResult.ok ? T.greenBg : T.redBg,
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            {syncResult.ok
              ? <CheckCircle size={13} style={{ color: T.green }} />
              : <AlertTriangle size={13} style={{ color: T.red }} />}
            <span style={{ fontSize: 12, color: syncResult.ok ? T.green : T.red }}>
              {syncResult.msg}
            </span>
          </div>
        )}
      </div>

      {/* DPDP confirmation */}
      {eraseOpen && isSuperadmin && (
        <div style={{
          background: T.redBg, border: '1px solid rgba(239,68,68,0.25)',
          borderRadius: 10, padding: '18px 22px', marginBottom: 16,
        }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: T.red, marginBottom: 8 }}>
            ⚠ DPDP Permanent Erasure
          </div>
          <p style={{ fontSize: 13, color: 'rgba(241,240,245,0.65)', lineHeight: 1.6, margin: '0 0 16px' }}>
            Permanently wipes all PII: email, phone, access tokens, API keys. Sets status to "erased". <strong style={{ color: T.red }}>Irreversible.</strong>
          </p>
          <div style={{ display: 'flex', gap: 10 }}>
            <button onClick={handleErase} disabled={erasing} style={{
              padding: '8px 18px', borderRadius: 9, fontSize: 13, fontWeight: 700,
              background: T.red, color: '#fff', border: 'none',
              cursor: erasing ? 'not-allowed' : 'pointer', fontFamily: 'inherit',
              opacity: erasing ? 0.6 : 1,
            }}>
              {erasing ? 'Erasing…' : 'Confirm Permanent Erasure'}
            </button>
            <button onClick={() => setEraseOpen(false)} style={{
              padding: '8px 16px', borderRadius: 9, fontSize: 13,
              background: 'none', border: `1px solid ${T.border}`,
              color: T.muted, cursor: 'pointer', fontFamily: 'inherit',
            }}>Cancel</button>
          </div>
        </div>
      )}

      {error && <InlineError msg={error} />}

      {/* ── Stats row ─────────────────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 16 }}>
        <StatChip label="Total Trades"  value={stats.total_trades}  sub={stats.last_trade_at ? `Last ${relativeTime(stats.last_trade_at)}` : 'No trades yet'} />
        <StatChip label="Total Alerts"  value={stats.total_alerts} />
        <StatChip label="Push Devices"  value={stats.push_subscription_count} accent={stats.push_subscription_count > 0 ? T.green : undefined} />
        <StatChip label="Account Status" value={account.status} sub={account.broker_user_id || undefined} accent={account.status === 'connected' ? T.green : account.status === 'suspended' ? T.red : undefined} />
      </div>

      {/* ── Tab bar ──────────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex', borderBottom: `1px solid ${T.border}`,
        marginBottom: 22, gap: 0,
      }}>
        {TABS.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: '9px 18px', fontSize: 13, fontWeight: 500,
              cursor: 'pointer', background: 'none', border: 'none',
              borderBottom: tab === t ? `2px solid ${T.amber}` : '2px solid transparent',
              color: tab === t ? T.amber : T.muted,
              marginBottom: -1,
              fontFamily: 'inherit', transition: 'color 0.12s',
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* ── Tab content ──────────────────────────────────────────────────── */}
      {tab === 'Overview' && <OverviewTab data={data} />}
      {tab === 'Timeline' && <TimelineTab accountId={id!} />}
      {tab === 'Limits'   && <LimitsTab data={data} accountId={id!} onSaved={load} />}
      {tab === 'Comms'    && <CommsTab data={data} accountId={id!} />}
    </div>
  );
}

// ─── Shared styles ────────────────────────────────────────────────────────────
const backBtn: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 6,
  background: 'none', border: 'none', color: '#6b6a82',
  cursor: 'pointer', fontFamily: "'Inter', 'DM Sans', sans-serif",
  fontSize: 13, marginBottom: 20, padding: 0,
};

const actionBtn: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 6,
  padding: '7px 14px', borderRadius: 9, fontSize: 12, fontWeight: 500,
  cursor: 'pointer', background: '#16161d',
  border: '1px solid #252536', color: '#6b6a82',
  fontFamily: "'Inter', 'DM Sans', sans-serif",
  transition: 'all 0.12s',
};
