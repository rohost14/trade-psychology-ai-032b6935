import { useEffect, useState } from 'react';
import { Clock, Play, ChevronDown, ChevronRight } from 'lucide-react';
import { adminApi } from '@/lib/adminApi';
import { useAdminAuth } from '@/contexts/AdminAuthContext';
import { AdminPage, AdminCard, ErrorBanner, LoadingBlock, RefreshButton, type Accent } from './_ui';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const ACCENT_RGB: Record<Accent, string> = {
  profit: 'rgb(var(--tm-profit))', loss: 'rgb(var(--tm-loss))',
  warning: 'rgb(var(--tm-obs))', brand: 'rgb(var(--tm-brand))', muted: 'rgb(var(--muted-foreground))',
};

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
interface FailedTask { task_id: string; traceback: string; result: string; }
interface TaskData {
  redis_connected: boolean; tasks: TaskItem[]; queue_depths: Record<string, number | null>;
  failed_tasks: FailedTask[]; failed_count: number;
}

// ── Small building blocks ────────────────────────────────────────────────────
function Pill({ ok, text }: { ok: boolean; text: string }) {
  const rgb = ok ? ACCENT_RGB.profit : ACCENT_RGB.loss;
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border"
      style={{ background: `color-mix(in srgb, ${rgb} 10%, transparent)`, borderColor: `color-mix(in srgb, ${rgb} 22%, transparent)` }}>
      <span className="w-[5px] h-[5px] rounded-full" style={{ background: rgb }} />
      <span className="text-[11px] font-semibold" style={{ color: rgb }}>{text}</span>
    </span>
  );
}

function WarnPill({ text, accent = 'warning' }: { text: string; accent?: Accent }) {
  const rgb = ACCENT_RGB[accent];
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full border text-[11px] font-semibold"
      style={{ background: `color-mix(in srgb, ${rgb} 10%, transparent)`, borderColor: `color-mix(in srgb, ${rgb} 20%, transparent)`, color: rgb }}>{text}</span>
  );
}

function Metric({ label, value, accent, mono }: { label: string; value: string | number | null | undefined; accent?: Accent; mono?: boolean }) {
  if (value === null || value === undefined) return null;
  return (
    <div className="flex justify-between items-center py-1.5 border-b border-border last:border-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={cn('text-xs font-medium', mono && 'font-mono')} style={{ color: accent ? ACCENT_RGB[accent] : 'rgb(var(--text-primary))' }}>{String(value)}</span>
    </div>
  );
}

const CardTitle = ({ children }: { children: React.ReactNode }) => <div className="tm-label mb-3.5">{children}</div>;

function TaskStatusDot({ status }: { status: string }) {
  const rgb = status === 'scheduled' ? ACCENT_RGB.profit : status === 'error' ? ACCENT_RGB.loss : ACCENT_RGB.warning;
  return <span className="inline-block w-[7px] h-[7px] rounded-full shrink-0" style={{ background: rgb, boxShadow: `0 0 5px color-mix(in srgb, ${rgb} 38%, transparent)` }} />;
}

function FailedTaskRow({ task }: { task: FailedTask }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-border">
      <button onClick={() => setOpen(o => !o)} className="w-full flex items-center gap-2.5 py-2.5 text-left">
        {open ? <ChevronDown size={12} className="text-muted-foreground/60 shrink-0" /> : <ChevronRight size={12} className="text-muted-foreground/60 shrink-0" />}
        <span className="font-mono text-[11px] text-[rgb(var(--tm-brand))]">{task.task_id.slice(0, 8)}…</span>
        <span className="text-xs text-muted-foreground flex-1 overflow-hidden text-ellipsis whitespace-nowrap">
          {task.result || task.traceback.split('\n').pop()?.trim() || 'Unknown error'}
        </span>
      </button>
      {open && (
        <div className="mb-2.5 ml-[22px] px-3.5 py-2.5 rounded-lg bg-background border border-border">
          {task.result && <p className="text-[11px] text-[rgb(var(--tm-loss))] mb-1.5 font-mono break-all">{task.result}</p>}
          {task.traceback && <pre className="text-[10px] text-muted-foreground m-0 whitespace-pre-wrap leading-relaxed break-all">{task.traceback}</pre>}
        </div>
      )}
    </div>
  );
}

function BeatScheduleTable({ tasks, canTrigger, triggering, triggerMsg, onTrigger }: {
  tasks: TaskItem[]; canTrigger: boolean; triggering: string | null;
  triggerMsg: { key: string; ok: boolean; msg: string } | null; onTrigger: (key: string) => void;
}) {
  const noData    = tasks.filter(t => t.status === 'no_data').length;
  const errored   = tasks.filter(t => t.status === 'error').length;
  const scheduled = tasks.filter(t => t.status === 'scheduled').length;
  const cols = '[grid-template-columns:16px_1fr_160px_140px_140px_80px]';

  return (
    <AdminCard className="lg:col-span-3" noPadding>
      <div className="p-5">
        <div className="flex justify-between items-center mb-4">
          <div className="flex items-center gap-2.5">
            <Clock size={14} className="text-[rgb(var(--tm-brand))]" />
            <span className="text-[13px] font-semibold text-foreground">Celery Beat Schedule</span>
            <span className="text-[11px] text-muted-foreground/70">{tasks.length} tasks</span>
          </div>
          <div className="flex gap-2">
            {scheduled > 0 && <Pill ok text={`${scheduled} scheduled`} />}
            {noData > 0 && <WarnPill text={`${noData} no data (never run)`} />}
            {errored > 0 && <Pill ok={false} text={`${errored} error`} />}
          </div>
        </div>

        {triggerMsg && (
          <div className="mb-3 px-3 py-1.5 rounded-lg text-xs border"
            style={{ color: ACCENT_RGB[triggerMsg.ok ? 'profit' : 'loss'],
                     background: `color-mix(in srgb, ${ACCENT_RGB[triggerMsg.ok ? 'profit' : 'loss']} 8%, transparent)`,
                     borderColor: `color-mix(in srgb, ${ACCENT_RGB[triggerMsg.ok ? 'profit' : 'loss']} 20%, transparent)` }}>
            <strong>{triggerMsg.key}</strong>: {triggerMsg.msg}
          </div>
        )}

        <div className={cn('grid gap-3 pb-2 border-b border-border', cols)}>
          {['', 'Task', 'Schedule', 'Last Run', 'Next Run', ''].map((h, i) => <span key={i} className="table-header">{h}</span>)}
        </div>

        {tasks.map(t => (
          <div key={t.key} className={cn('grid gap-3 items-center py-2.5 border-b border-border', cols)}>
            <TaskStatusDot status={t.status} />
            <div>
              <span className="text-xs font-medium text-foreground">{t.name}</span>
              <span className="text-[10px] text-muted-foreground/60 ml-2 font-mono">{t.key}</span>
            </div>
            <span className="text-[11px] text-muted-foreground">{t.schedule}</span>
            <span className="text-[11px] text-muted-foreground tabular-nums">
              {t.last_run_at ? new Date(t.last_run_at).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : <span className="text-muted-foreground/60">never</span>}
            </span>
            <span className="text-[11px] text-muted-foreground tabular-nums">
              {t.next_run_at ? new Date(t.next_run_at).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : <span className="text-muted-foreground/60">unknown</span>}
            </span>
            <div className="flex justify-end">
              {canTrigger && t.triggerable ? (
                <Button size="sm" variant="outline" className="h-7 px-2.5 text-[11px]" onClick={() => onTrigger(t.key)} disabled={triggering === t.key}>
                  <Play size={9} /> {triggering === t.key ? '…' : 'Run'}
                </Button>
              ) : <span className="text-[10px] text-muted-foreground/60">—</span>}
            </div>
          </div>
        ))}
      </div>
    </AdminCard>
  );
}

// ── Main ─────────────────────────────────────────────────────────────────────
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
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  };

  const triggerTask = async (key: string) => {
    setTriggering(key); setTriggerMsg(null);
    try {
      const r = await adminApi.triggerTask(key);
      setTriggerMsg({ key, ok: true, msg: `Queued — ID: ${r.celery_id?.slice(0, 8)}…` });
    } catch (e: unknown) { setTriggerMsg({ key, ok: false, msg: e instanceof Error ? e.message : String(e) }); }
    finally { setTriggering(null); }
  };

  useEffect(() => { load(); }, []);

  const redisMemAccent = sys?.redis.memory_max_mb && sys?.redis.memory_used_mb
    ? (sys.redis.memory_used_mb / sys.redis.memory_max_mb > 0.85 ? 'loss' as Accent : undefined) : undefined;

  return (
    <AdminPage
      title="System Health"
      subtitle={ts ? `Last updated ${ts} IST` : undefined}
      actions={<RefreshButton onClick={load} loading={loading} />}
    >
      <ErrorBanner message={error} />
      {loading && !sys && <LoadingBlock />}

      {sys && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3.5">
          {/* Redis */}
          <AdminCard noPadding>
            <div className="p-5">
              <div className="flex justify-between items-center mb-4">
                <CardTitle>Redis</CardTitle>
                <Pill ok={sys.redis.status === 'ok'} text={sys.redis.status === 'ok' ? 'healthy' : 'error'} />
              </div>
              <Metric label="Version" value={sys.redis.version} />
              <Metric label="Uptime" value={sys.redis.uptime_days !== undefined ? `${sys.redis.uptime_days}d` : undefined} />
              <Metric label="Clients" value={sys.redis.connected_clients} />
              <Metric label="Memory used" value={sys.redis.memory_used_mb !== undefined ? `${sys.redis.memory_used_mb} MB` : undefined} accent={redisMemAccent} />
              <Metric label="Memory peak" value={sys.redis.memory_peak_mb !== undefined ? `${sys.redis.memory_peak_mb} MB` : undefined} />
              {sys.redis.memory_max_mb ? <Metric label="Memory limit" value={`${sys.redis.memory_max_mb} MB`} /> : null}
              <Metric label="Total keys" value={sys.redis.total_keys} />
              <Metric label="Hit rate" value={sys.redis.hit_rate_pct != null ? `${sys.redis.hit_rate_pct}%` : 'N/A'}
                accent={sys.redis.hit_rate_pct != null ? (sys.redis.hit_rate_pct > 80 ? 'profit' : 'warning') : undefined} />
              <Metric label="Evicted" value={sys.redis.evicted_keys} accent={sys.redis.evicted_keys && sys.redis.evicted_keys > 0 ? 'warning' : undefined} />
              <Metric label="Ops/sec" value={sys.redis.ops_per_sec} />
              {sys.redis.detail && <Metric label="Error" value={sys.redis.detail} accent="loss" />}
            </div>
          </AdminCard>

          {/* Celery + DB pool */}
          <div className="flex flex-col gap-3.5">
            <AdminCard noPadding>
              <div className="p-5">
                <div className="flex justify-between items-center mb-4">
                  <CardTitle>Celery Queues</CardTitle>
                  <Pill ok={sys.celery.status === 'ok'} text={sys.celery.status} />
                </div>
                <Metric label="Default queue" value={sys.celery.queue_depth} accent={sys.celery.queue_depth !== undefined && sys.celery.queue_depth > 100 ? 'warning' : undefined} />
                <Metric label="AI worker queue" value={sys.celery.ai_queue} accent={sys.celery.ai_queue !== undefined && sys.celery.ai_queue > 50 ? 'warning' : undefined} />
                {sys.celery.detail && <Metric label="Detail" value={sys.celery.detail} />}
                {(sys.celery.queue_depth !== undefined || sys.celery.ai_queue !== undefined) && (
                  <div className="mt-3.5">
                    {[{ label: 'celery', depth: sys.celery.queue_depth ?? 0, warn: 100 }, { label: 'ai_worker', depth: sys.celery.ai_queue ?? 0, warn: 50 }].map(({ label, depth, warn }) => (
                      <div key={label} className="mb-2.5">
                        <div className="flex justify-between mb-1">
                          <span className="text-[11px] text-muted-foreground/60 font-mono">{label}</span>
                          <span className="text-[11px] tabular-nums" style={{ color: depth > warn ? ACCENT_RGB.warning : ACCENT_RGB.muted }}>{depth}</span>
                        </div>
                        <div className="h-1 rounded-sm bg-muted overflow-hidden">
                          <div className="h-full rounded-sm" style={{ width: `${Math.min(depth / warn * 100, 100)}%`, background: depth > warn ? ACCENT_RGB.warning : ACCENT_RGB.profit }} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </AdminCard>

            {sys.db_pool && (
              <AdminCard noPadding>
                <div className="p-5">
                  <CardTitle>DB Connection Pool</CardTitle>
                  <Metric label="Pool size" value={sys.db_pool.pool_size} />
                  <Metric label="Checked in" value={sys.db_pool.checked_in} />
                  <Metric label="Checked out" value={sys.db_pool.checked_out} accent={sys.db_pool.checked_out > sys.db_pool.pool_size * 0.8 ? 'warning' : undefined} />
                  <Metric label="Overflow" value={sys.db_pool.overflow} accent={sys.db_pool.overflow > 0 ? 'warning' : undefined} />
                  <div className="mt-3">
                    <div className="h-[5px] rounded bg-muted overflow-hidden">
                      <div className="h-full rounded" style={{ width: `${(sys.db_pool.checked_out / (sys.db_pool.pool_size + sys.db_pool.overflow || 1)) * 100}%`, background: sys.db_pool.checked_out > sys.db_pool.pool_size * 0.8 ? ACCENT_RGB.warning : ACCENT_RGB.profit }} />
                    </div>
                    <span className="text-[10px] text-muted-foreground/60 mt-1 block">Pool utilisation</span>
                  </div>
                </div>
              </AdminCard>
            )}
          </div>

          {/* Config + Integrations + Quick metrics */}
          <div className="flex flex-col gap-3.5">
            <AdminCard noPadding>
              <div className="p-5">
                <CardTitle>Config</CardTitle>
                <Metric label="Environment" value={sys.config.environment} />
                <Metric label="Maintenance" value={sys.config.maintenance_mode ? 'ON' : 'off'} accent={sys.config.maintenance_mode ? 'loss' : 'profit'} />
                <Metric label="Online users" value={sys.online_users ?? 'N/A'} accent="profit" />
              </div>
            </AdminCard>

            <AdminCard noPadding>
              <div className="p-5">
                <CardTitle>Integrations</CardTitle>
                <div className="flex flex-col gap-2.5">
                  {[{ label: 'WhatsApp (Gupshup)', ok: sys.whatsapp.configured }, { label: 'Sentry', ok: sys.config.sentry_enabled }].map(({ label, ok }) => (
                    <div key={label} className="flex justify-between items-center py-1.5 border-b border-border last:border-0">
                      <span className="text-xs text-muted-foreground">{label}</span>
                      <Pill ok={ok} text={ok ? 'enabled' : 'not configured'} />
                    </div>
                  ))}
                </div>
              </div>
            </AdminCard>

            {tasks && (
              <AdminCard noPadding>
                <div className="p-5">
                  <CardTitle>Quick Metrics</CardTitle>
                  <Metric label="Scheduled tasks" value={`${tasks.tasks.filter(t => t.status === 'scheduled').length} / ${tasks.tasks.length}`} />
                  <Metric label="Never run tasks" value={tasks.tasks.filter(t => t.status === 'no_data').length} accent={tasks.tasks.filter(t => t.status === 'no_data').length > 0 ? 'warning' : undefined} />
                  <Metric label="Failed (result)" value={tasks.failed_count} accent={tasks.failed_count > 0 ? 'loss' : 'profit'} />
                </div>
              </AdminCard>
            )}
          </div>

          {/* Beat schedule — full width */}
          {tasks && (
            <BeatScheduleTable tasks={tasks.tasks} canTrigger={canTrigger} triggering={triggering} triggerMsg={triggerMsg} onTrigger={triggerTask} />
          )}

          {/* Failed tasks — full width */}
          {tasks && (
            <AdminCard className="lg:col-span-3" noPadding>
              <div className="p-5">
                <div className="flex justify-between items-center mb-4">
                  <div className="flex items-center gap-2.5">
                    <span className="text-[13px] font-semibold text-foreground">Failed Tasks</span>
                    <span className="text-[11px] text-muted-foreground/70">(scanned last 200 Celery result-backend keys)</span>
                  </div>
                  {tasks.failed_count === 0 ? <Pill ok text="0 failures" /> : <WarnPill text={`${tasks.failed_count} failed`} accent="loss" />}
                </div>
                {tasks.failed_tasks.length === 0 ? (
                  <p className="text-xs text-muted-foreground/70 text-center py-4">
                    {tasks.failed_count === 0 ? 'No failures detected in result backend.' : 'Failures detected but no detail available.'}
                  </p>
                ) : (
                  <div>
                    <div className="grid gap-3 pb-2 border-b border-border mb-1 [grid-template-columns:22px_100px_1fr]">
                      <span />
                      {['Task ID', 'Error preview'].map((h, i) => <span key={i} className="table-header">{h}</span>)}
                    </div>
                    {tasks.failed_tasks.map(f => <FailedTaskRow key={f.task_id} task={f} />)}
                  </div>
                )}
              </div>
            </AdminCard>
          )}
        </div>
      )}
    </AdminPage>
  );
}
