import { useEffect, useState } from 'react';
import { RefreshCw, AlertTriangle, Clock, Play, ChevronDown, ChevronRight, Circle } from 'lucide-react';
import { adminApi } from '@/lib/adminApi';
import { useAdminAuth } from '@/contexts/AdminAuthContext';

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
  dm:       "'Inter', 'DM Sans', sans-serif",
};

// ─── Types ────────────────────────────────────────────────────────────────────
interface SystemData {
  redis: {
    status: string; version?: string; uptime_days?: number; connected_clients?: number;
    memory_used_mb?: number; memory_peak_mb?: number; memory_max_mb?: number | null;
    total_keys?: number; hit_rate_pct?: number | null; evicted_keys?: number;
    ops_per_sec?: number; detail?: string;
  };
  celery: { status: string; queue_depth?: number; ai_queue?: number; detail?: string };
  online_users: number | null;
  whatsapp: { configured: boolean; provider: string };
  db_pool: { pool_size: number; checked_in: number; checked_out: number; overflow: number } | null;
  config: { maintenance_mode: boolean; environment: string; sentry_enabled: boolean };
}

interface TaskItem {
  key: string; name: string; schedule: string; status: string;
  triggerable: boolean; last_run_at: string | null; next_run_at: string | null;
}

interface FailedTask {
  task_id: string; traceback: string; result: string;
}

interface TaskData {
  redis_connected: boolean;
  tasks: TaskItem[];
  queue_depths: Record<string, number | null>;
  failed_tasks: FailedTask[];
  failed_count: number;
}

// ─── Sub-components ───────────────────────────────────────────────────────────
function Card({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: '18px 20px', ...style }}>
      {children}
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <div style={{ fontSize: 12, fontWeight: 600, color: T.muted, textTransform: 'uppercase' as const, letterSpacing: '0.07em', marginBottom: 14 }}>{children}</div>;
}

function MetricRow({ label, value, color, mono }: { label: string; value: string | number | null | undefined; color?: string; mono?: boolean }) {
  if (value === null || value === undefined) return null;
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 0', borderBottom: `1px solid ${T.border}` }}>
      <span style={{ fontSize: 12, color: T.muted }}>{label}</span>
      <span style={{ fontSize: 12, fontWeight: 500, color: color || T.text, fontFamily: mono ? "'JetBrains Mono', monospace" : T.dm }}>
        {String(value)}
      </span>
    </div>
  );
}

function StatusPill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 10px', borderRadius: 20,
      background: ok ? T.greenBg : T.redBg,
      border: `1px solid ${ok ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}`,
    }}>
      <Circle size={5} fill={ok ? T.green : T.red} style={{ color: ok ? T.green : T.red }} />
      <span style={{ fontSize: 11, fontWeight: 600, color: ok ? T.green : T.red }}>{label}</span>
    </div>
  );
}

function TaskStatusDot({ status }: { status: string }) {
  const color = status === 'scheduled' ? T.green : status === 'error' ? T.red : T.amber;
  return <span style={{ display: 'inline-block', width: 7, height: 7, borderRadius: '50%', background: color, boxShadow: `0 0 5px ${color}60`, flexShrink: 0 }} />;
}

// ─── Failed tasks expandable row ──────────────────────────────────────────────
function FailedTaskRow({ task }: { task: FailedTask }) {
  const [open, setOpen] = useState(false);
  const shortId = task.task_id.slice(0, 8);
  return (
    <div style={{ borderBottom: `1px solid ${T.border}` }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 10,
          padding: '10px 0', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left' as const,
        }}
      >
        {open ? <ChevronDown size={12} style={{ color: T.dim, flexShrink: 0 }} /> : <ChevronRight size={12} style={{ color: T.dim, flexShrink: 0 }} />}
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: T.amber }}>{shortId}…</span>
        <span style={{ fontSize: 12, color: T.muted, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
          {task.result || task.traceback.split('\n').pop()?.trim() || 'Unknown error'}
        </span>
      </button>
      {open && (
        <div style={{
          margin: '0 0 10px 22px', padding: '10px 14px',
          borderRadius: 7, background: T.bg,
          border: `1px solid ${T.border2}`,
        }}>
          {task.result && (
            <p style={{ fontSize: 11, color: T.red, marginBottom: 6, fontFamily: "'JetBrains Mono', monospace", wordBreak: 'break-all' as const }}>
              {task.result}
            </p>
          )}
          {task.traceback && (
            <pre style={{ fontSize: 10, color: T.muted, margin: 0, whiteSpace: 'pre-wrap' as const, lineHeight: 1.5, wordBreak: 'break-all' as const }}>
              {task.traceback}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Beat schedule table ──────────────────────────────────────────────────────
function BeatScheduleTable({ tasks, canTrigger, triggering, triggerMsg, onTrigger }: {
  tasks: TaskItem[];
  canTrigger: boolean;
  triggering: string | null;
  triggerMsg: { key: string; ok: boolean; msg: string } | null;
  onTrigger: (key: string) => void;
}) {
  const noData    = tasks.filter(t => t.status === 'no_data').length;
  const errored   = tasks.filter(t => t.status === 'error').length;
  const scheduled = tasks.filter(t => t.status === 'scheduled').length;

  return (
    <Card style={{ gridColumn: '1 / -1' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Clock size={14} style={{ color: T.amber }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>Celery Beat Schedule</span>
          <span style={{ fontSize: 11, color: T.dim }}>{tasks.length} tasks</span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {scheduled > 0 && <StatusPill ok={true} label={`${scheduled} scheduled`} />}
          {noData > 0 && (
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 10px', borderRadius: 20, background: T.amberBg, border: '1px solid rgba(245,158,11,0.2)' }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: T.amber }}>{noData} no data (never run)</span>
            </div>
          )}
          {errored > 0 && <StatusPill ok={false} label={`${errored} error`} />}
        </div>
      </div>

      {triggerMsg && (
        <div style={{ marginBottom: 12, padding: '7px 12px', borderRadius: 8, background: triggerMsg.ok ? T.greenBg : T.redBg, border: `1px solid ${triggerMsg.ok ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}`, fontSize: 12, color: triggerMsg.ok ? T.green : T.red }}>
          <strong>{triggerMsg.key}</strong>: {triggerMsg.msg}
        </div>
      )}

      {/* Table header */}
      <div style={{ display: 'grid', gridTemplateColumns: '16px 1fr 160px 140px 140px 80px', gap: 12, padding: '0 0 8px', borderBottom: `1px solid ${T.border}`, marginBottom: 2 }}>
        {['', 'Task', 'Schedule', 'Last Run', 'Next Run', ''].map((h, i) => (
          <span key={i} style={{ fontSize: 10, fontWeight: 600, color: T.dim, textTransform: 'uppercase' as const, letterSpacing: '0.07em' }}>{h}</span>
        ))}
      </div>

      {tasks.map(t => (
        <div key={t.key} style={{ display: 'grid', gridTemplateColumns: '16px 1fr 160px 140px 140px 80px', gap: 12, alignItems: 'center', padding: '10px 0', borderBottom: `1px solid ${T.border}` }}>
          <TaskStatusDot status={t.status} />

          <div>
            <span style={{ fontSize: 12, fontWeight: 500, color: T.text }}>{t.name}</span>
            <span style={{ fontSize: 10, color: T.dim, marginLeft: 8, fontFamily: "'JetBrains Mono', monospace" }}>{t.key}</span>
          </div>

          <span style={{ fontSize: 11, color: T.muted }}>{t.schedule}</span>

          <span style={{ fontSize: 11, color: T.muted, fontVariantNumeric: 'tabular-nums' }}>
            {t.last_run_at
              ? new Date(t.last_run_at).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
              : <span style={{ color: T.dim }}>never</span>}
          </span>

          <span style={{ fontSize: 11, color: T.muted, fontVariantNumeric: 'tabular-nums' }}>
            {t.next_run_at
              ? new Date(t.next_run_at).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
              : <span style={{ color: T.dim }}>unknown</span>}
          </span>

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            {canTrigger && t.triggerable ? (
              <button
                onClick={() => onTrigger(t.key)}
                disabled={triggering === t.key}
                style={{
                  display: 'flex', alignItems: 'center', gap: 4,
                  padding: '4px 10px', borderRadius: 6,
                  background: T.amberBg, border: '1px solid rgba(245,158,11,0.25)',
                  color: T.amber, fontSize: 11, fontWeight: 600,
                  cursor: triggering === t.key ? 'not-allowed' : 'pointer',
                  opacity: triggering === t.key ? 0.5 : 1, fontFamily: T.dm,
                }}
              >
                <Play size={9} />
                {triggering === t.key ? '…' : 'Run'}
              </button>
            ) : (
              <span style={{ fontSize: 10, color: T.dim }}>—</span>
            )}
          </div>
        </div>
      ))}
    </Card>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────
export default function AdminSystemHealth() {
  const { admin } = useAdminAuth();
  const canTrigger = admin?.role === 'superadmin' || admin?.role === 'ops';

  const [sys,        setSys]        = useState<SystemData | null>(null);
  const [tasks,      setTasks]      = useState<TaskData | null>(null);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState('');
  const [ts,         setTs]         = useState('');
  const [triggering, setTriggering] = useState<string | null>(null);
  const [triggerMsg, setTriggerMsg] = useState<{ key: string; ok: boolean; msg: string } | null>(null);

  const load = async () => {
    setLoading(true); setError('');
    try {
      const [s, t] = await Promise.all([adminApi.system(), adminApi.tasks()]);
      setSys(s); setTasks(t);
      setTs(new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }));
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  const triggerTask = async (key: string) => {
    setTriggering(key); setTriggerMsg(null);
    try {
      const r = await adminApi.triggerTask(key);
      setTriggerMsg({ key, ok: true, msg: `Queued — ID: ${r.celery_id?.slice(0, 8)}…` });
    } catch (e: any) {
      setTriggerMsg({ key, ok: false, msg: e.message });
    } finally { setTriggering(null); }
  };

  useEffect(() => { load(); }, []);

  return (
    <div style={{ padding: '28px 32px', fontFamily: T.dm, maxWidth: 1100 }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: T.text, margin: 0, letterSpacing: '-0.02em' }}>System Health</h1>
          {ts && <p style={{ fontSize: 12, color: T.dim, marginTop: 4 }}>Last updated {ts} IST</p>}
        </div>
        <button onClick={load} disabled={loading} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 7, background: T.surface, border: `1px solid ${T.border}`, color: T.muted, fontSize: 12, cursor: loading ? 'not-allowed' : 'pointer', fontFamily: T.dm }}>
          <RefreshCw size={12} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          Refresh
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </button>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderRadius: 8, background: T.redBg, border: '1px solid rgba(239,68,68,0.18)', marginBottom: 20 }}>
          <AlertTriangle size={13} style={{ color: T.red }} />
          <span style={{ fontSize: 12, color: T.red }}>{error}</span>
        </div>
      )}

      {loading && !sys && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '56px 0' }}>
          <div style={{ width: 24, height: 24, border: `2px solid ${T.amber}`, borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
        </div>
      )}

      {sys && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 14 }}>

          {/* ── Redis ──────────────────────────────────────────────────── */}
          <Card>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <SectionTitle>Redis</SectionTitle>
              <StatusPill ok={sys.redis.status === 'ok'} label={sys.redis.status === 'ok' ? 'healthy' : 'error'} />
            </div>
            <MetricRow label="Version"      value={sys.redis.version} />
            <MetricRow label="Uptime"       value={sys.redis.uptime_days !== undefined ? `${sys.redis.uptime_days}d` : undefined} />
            <MetricRow label="Clients"      value={sys.redis.connected_clients} />
            <MetricRow label="Memory used"  value={sys.redis.memory_used_mb !== undefined ? `${sys.redis.memory_used_mb} MB` : undefined}
              color={sys.redis.memory_max_mb && sys.redis.memory_used_mb ? (sys.redis.memory_used_mb / sys.redis.memory_max_mb > 0.85 ? T.red : undefined) : undefined} />
            <MetricRow label="Memory peak"  value={sys.redis.memory_peak_mb !== undefined ? `${sys.redis.memory_peak_mb} MB` : undefined} />
            {sys.redis.memory_max_mb ? <MetricRow label="Memory limit" value={`${sys.redis.memory_max_mb} MB`} /> : null}
            <MetricRow label="Total keys"   value={sys.redis.total_keys} />
            <MetricRow label="Hit rate"     value={sys.redis.hit_rate_pct != null ? `${sys.redis.hit_rate_pct}%` : 'N/A'}
              color={sys.redis.hit_rate_pct != null ? (sys.redis.hit_rate_pct > 80 ? T.green : T.amber) : undefined} />
            <MetricRow label="Evicted"      value={sys.redis.evicted_keys}
              color={sys.redis.evicted_keys && sys.redis.evicted_keys > 0 ? T.amber : undefined} />
            <MetricRow label="Ops/sec"      value={sys.redis.ops_per_sec} />
            {sys.redis.detail && <MetricRow label="Error" value={sys.redis.detail} color={T.red} />}
          </Card>

          {/* ── Celery + DB pool ───────────────────────────────────────── */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <Card>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <SectionTitle>Celery Queues</SectionTitle>
                <StatusPill ok={sys.celery.status === 'ok'} label={sys.celery.status} />
              </div>
              <MetricRow label="Default queue" value={sys.celery.queue_depth}
                color={sys.celery.queue_depth !== undefined && sys.celery.queue_depth > 100 ? T.amber : undefined} />
              <MetricRow label="AI worker queue" value={sys.celery.ai_queue}
                color={sys.celery.ai_queue !== undefined && sys.celery.ai_queue > 50 ? T.amber : undefined} />
              {sys.celery.detail && <MetricRow label="Detail" value={sys.celery.detail} />}

              {/* Queue depth visualisation */}
              {(sys.celery.queue_depth !== undefined || sys.celery.ai_queue !== undefined) && (
                <div style={{ marginTop: 14 }}>
                  {[
                    { label: 'celery', depth: sys.celery.queue_depth ?? 0, warn: 100 },
                    { label: 'ai_worker', depth: sys.celery.ai_queue ?? 0, warn: 50 },
                  ].map(({ label, depth, warn }) => (
                    <div key={label} style={{ marginBottom: 10 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <span style={{ fontSize: 11, color: T.dim, fontFamily: "'JetBrains Mono', monospace" }}>{label}</span>
                        <span style={{ fontSize: 11, color: depth > warn ? T.amber : T.muted, fontVariantNumeric: 'tabular-nums' }}>{depth}</span>
                      </div>
                      <div style={{ height: 4, background: T.raised, borderRadius: 2, overflow: 'hidden' }}>
                        <div style={{
                          height: '100%',
                          width: `${Math.min(depth / warn * 100, 100)}%`,
                          background: depth > warn ? T.amber : T.green,
                          borderRadius: 2,
                        }} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {sys.db_pool && (
              <Card>
                <SectionTitle>DB Connection Pool</SectionTitle>
                <MetricRow label="Pool size"   value={sys.db_pool.pool_size} />
                <MetricRow label="Checked in"  value={sys.db_pool.checked_in} />
                <MetricRow label="Checked out" value={sys.db_pool.checked_out}
                  color={sys.db_pool.checked_out > sys.db_pool.pool_size * 0.8 ? T.amber : undefined} />
                <MetricRow label="Overflow"    value={sys.db_pool.overflow}
                  color={sys.db_pool.overflow > 0 ? T.amber : undefined} />
                {/* Pool utilization bar */}
                <div style={{ marginTop: 12 }}>
                  <div style={{ height: 5, background: T.raised, borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{
                      height: '100%',
                      width: `${(sys.db_pool.checked_out / (sys.db_pool.pool_size + sys.db_pool.overflow || 1)) * 100}%`,
                      background: sys.db_pool.checked_out > sys.db_pool.pool_size * 0.8 ? T.amber : T.green,
                      borderRadius: 3,
                    }} />
                  </div>
                  <span style={{ fontSize: 10, color: T.dim, marginTop: 4, display: 'block' }}>
                    Pool utilisation
                  </span>
                </div>
              </Card>
            )}
          </div>

          {/* ── Config + Integrations ──────────────────────────────────── */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <Card>
              <SectionTitle>Config</SectionTitle>
              <MetricRow label="Environment"  value={sys.config.environment} />
              <MetricRow label="Maintenance"  value={sys.config.maintenance_mode ? 'ON' : 'off'}
                color={sys.config.maintenance_mode ? T.red : T.green} />
              <MetricRow label="Online users" value={sys.online_users ?? 'N/A'} color={T.green} />
            </Card>

            <Card>
              <SectionTitle>Integrations</SectionTitle>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {[
                  { label: 'WhatsApp (Gupshup)', ok: sys.whatsapp.configured },
                  { label: 'Sentry',             ok: sys.config.sentry_enabled },
                ].map(({ label, ok }) => (
                  <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: `1px solid ${T.border}` }}>
                    <span style={{ fontSize: 12, color: T.muted }}>{label}</span>
                    <StatusPill ok={ok} label={ok ? 'enabled' : 'not configured'} />
                  </div>
                ))}
              </div>
            </Card>

            {/* Quick metrics */}
            <Card>
              <SectionTitle>Quick Metrics</SectionTitle>
              {tasks && (
                <>
                  <MetricRow label="Scheduled tasks"  value={tasks.tasks.filter(t => t.status === 'scheduled').length + ' / ' + tasks.tasks.length} />
                  <MetricRow label="Never run tasks"  value={tasks.tasks.filter(t => t.status === 'no_data').length}
                    color={tasks.tasks.filter(t => t.status === 'no_data').length > 0 ? T.amber : undefined} />
                  <MetricRow label="Failed (result)"  value={tasks.failed_count}
                    color={tasks.failed_count > 0 ? T.red : T.green} />
                </>
              )}
            </Card>
          </div>

          {/* ── Beat schedule — full width ─────────────────────────────── */}
          {tasks && (
            <BeatScheduleTable
              tasks={tasks.tasks}
              canTrigger={canTrigger}
              triggering={triggering}
              triggerMsg={triggerMsg}
              onTrigger={triggerTask}
            />
          )}

          {/* ── Failed tasks ───────────────────────────────────────────── */}
          {tasks && (
            <Card style={{ gridColumn: '1 / -1' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>Failed Tasks</span>
                  <span style={{ fontSize: 11, color: T.dim }}>(scanned last 200 Celery result-backend keys)</span>
                </div>
                {tasks.failed_count === 0
                  ? <StatusPill ok={true} label="0 failures" />
                  : (
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 10px', borderRadius: 20, background: T.redBg, border: '1px solid rgba(239,68,68,0.2)' }}>
                      <span style={{ fontSize: 11, fontWeight: 600, color: T.red }}>{tasks.failed_count} failed</span>
                    </div>
                  )}
              </div>

              {tasks.failed_tasks.length === 0 ? (
                <p style={{ fontSize: 12, color: T.dim, textAlign: 'center', padding: '16px 0' }}>
                  {tasks.failed_count === 0 ? 'No failures detected in result backend.' : 'Failures detected but no detail available.'}
                </p>
              ) : (
                <div>
                  <div style={{ display: 'grid', gridTemplateColumns: '22px 100px 1fr', gap: 12, padding: '0 0 8px', borderBottom: `1px solid ${T.border}`, marginBottom: 4 }}>
                    <span />
                    {['Task ID', 'Error preview'].map((h, i) => (
                      <span key={i} style={{ fontSize: 10, fontWeight: 600, color: T.dim, textTransform: 'uppercase' as const, letterSpacing: '0.07em' }}>{h}</span>
                    ))}
                  </div>
                  {tasks.failed_tasks.map(f => <FailedTaskRow key={f.task_id} task={f} />)}
                </div>
              )}
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
