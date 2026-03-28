import { useEffect, useState } from 'react';
import { RefreshCw, AlertTriangle, Clock } from 'lucide-react';
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

interface SystemData {
  redis:        { status: string; version?: string; uptime_days?: number; connected_clients?: number; memory_used_mb?: number; memory_peak_mb?: number; memory_max_mb?: number | null; total_keys?: number; hit_rate_pct?: number | null; evicted_keys?: number; ops_per_sec?: number; detail?: string };
  celery:       { status: string; queue_depth?: number; ai_queue?: number; detail?: string };
  online_users: number | null;
  whatsapp:     { configured: boolean; provider: string };
  email:        { configured: boolean };
  db_pool:      { pool_size: number; checked_in: number; checked_out: number; overflow: number } | null;
  config:       { maintenance_mode: boolean; environment: string; sentry_enabled: boolean };
}

interface TaskData {
  redis_connected: boolean;
  tasks: { key: string; name: string; schedule: string; status: string; last_run_at: string | null; next_run_at: string | null }[];
  queue_depths: Record<string, number | null>;
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 14, padding: '1.25rem 1.5rem' }}>
      <h2 style={{ fontSize: '0.85rem', fontWeight: 600, color: C.text, marginBottom: '0.9rem' }}>{title}</h2>
      {children}
    </div>
  );
}

function Row({ label, value, color }: { label: string; value: string | number | null | undefined; color?: string }) {
  if (value === null || value === undefined) return null;
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.45rem 0', borderBottom: `1px solid rgba(255,255,255,0.04)` }}>
      <span style={{ fontSize: '0.8rem', color: C.muted }}>{label}</span>
      <span style={{ fontSize: '0.8rem', fontWeight: 500, color: color || C.text }}>{String(value)}</span>
    </div>
  );
}

function Badge({ ok, yes, no }: { ok: boolean; yes: string; no: string }) {
  return <span style={{ fontSize: '0.7rem', fontWeight: 600, padding: '0.18rem 0.55rem', borderRadius: 20, background: ok ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)', color: ok ? C.green : C.red, border: `1px solid ${ok ? 'rgba(16,185,129,0.25)' : 'rgba(239,68,68,0.25)'}` }}>{ok ? yes : no}</span>;
}

function TaskStatusDot({ status }: { status: string }) {
  const color = status === 'scheduled' ? C.green : status === 'error' ? C.red : C.amber;
  return <span style={{ display: 'inline-block', width: 7, height: 7, borderRadius: '50%', background: color, boxShadow: `0 0 5px ${color}` }} />;
}

export default function AdminSystemHealth() {
  const [sys,     setSys]     = useState<SystemData | null>(null);
  const [tasks,   setTasks]   = useState<TaskData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');

  const load = async () => {
    setLoading(true); setError('');
    try {
      const [s, t] = await Promise.all([adminApi.system(), adminApi.tasks()]);
      setSys(s); setTasks(t);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  return (
    <div style={{ padding: '2rem', fontFamily: C.dm }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.3rem', fontWeight: 700, color: C.text, margin: 0 }}>System Health</h1>
        <button onClick={load} disabled={loading} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0.5rem 1rem', borderRadius: 9, background: 'rgba(255,255,255,0.04)', border: `1px solid ${C.border}`, color: C.muted, fontSize: '0.78rem', cursor: loading ? 'not-allowed' : 'pointer', fontFamily: C.dm }}>
          <RefreshCw style={{ width: 13, height: 13, animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          Refresh
        </button>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0.75rem 1rem', borderRadius: 10, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', marginBottom: '1.5rem' }}>
          <AlertTriangle style={{ width: 14, height: 14, color: C.red }} />
          <span style={{ fontSize: '0.8rem', color: C.red }}>{error}</span>
        </div>
      )}

      {loading && !sys && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
          <div style={{ width: 28, height: 28, border: `2px solid ${C.amber}`, borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
        </div>
      )}

      {sys && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>

          {/* Redis — full metrics */}
          <Card title="Redis">
            <Row label="Status"           value={sys.redis.status}         color={sys.redis.status === 'ok' ? C.green : C.red} />
            <Row label="Version"          value={sys.redis.version} />
            <Row label="Uptime"           value={sys.redis.uptime_days !== undefined ? `${sys.redis.uptime_days}d` : undefined} />
            <Row label="Clients"          value={sys.redis.connected_clients} />
            <Row label="Memory used"      value={sys.redis.memory_used_mb !== undefined ? `${sys.redis.memory_used_mb} MB` : undefined} />
            <Row label="Memory peak"      value={sys.redis.memory_peak_mb !== undefined ? `${sys.redis.memory_peak_mb} MB` : undefined} />
            {sys.redis.memory_max_mb && <Row label="Memory limit" value={`${sys.redis.memory_max_mb} MB`} />}
            <Row label="Total keys"       value={sys.redis.total_keys} />
            <Row label="Hit rate"         value={sys.redis.hit_rate_pct !== null && sys.redis.hit_rate_pct !== undefined ? `${sys.redis.hit_rate_pct}%` : 'N/A'} color={sys.redis.hit_rate_pct !== null && sys.redis.hit_rate_pct !== undefined ? (sys.redis.hit_rate_pct > 80 ? C.green : C.amber) : undefined} />
            <Row label="Evicted keys"     value={sys.redis.evicted_keys}  color={sys.redis.evicted_keys && sys.redis.evicted_keys > 0 ? C.amber : undefined} />
            <Row label="Ops/sec"          value={sys.redis.ops_per_sec} />
            {sys.redis.detail && <Row label="Error" value={sys.redis.detail} color={C.red} />}
          </Card>

          {/* Celery + DB pool */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <Card title="Celery Queues">
              <Row label="Status"         value={sys.celery.status}       color={sys.celery.status === 'ok' ? C.green : C.amber} />
              <Row label="Default queue"  value={sys.celery.queue_depth}  color={sys.celery.queue_depth !== undefined && sys.celery.queue_depth > 100 ? C.amber : undefined} />
              <Row label="AI worker queue" value={sys.celery.ai_queue}    color={sys.celery.ai_queue !== undefined && sys.celery.ai_queue > 50 ? C.amber : undefined} />
              {sys.celery.detail && <Row label="Detail" value={sys.celery.detail} />}
            </Card>

            {sys.db_pool && (
              <Card title="DB Connection Pool">
                <Row label="Pool size"     value={sys.db_pool.pool_size} />
                <Row label="Checked in"    value={sys.db_pool.checked_in} />
                <Row label="Checked out"   value={sys.db_pool.checked_out} color={sys.db_pool.checked_out > 8 ? C.amber : undefined} />
                <Row label="Overflow"      value={sys.db_pool.overflow}   color={sys.db_pool.overflow > 0 ? C.amber : undefined} />
              </Card>
            )}
          </div>

          {/* Integrations */}
          <Card title="Integrations">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                { label: 'WhatsApp (Gupshup)', ok: sys.whatsapp.configured, yes: 'configured',  no: 'not configured' },
                { label: 'Email (SMTP/SES)',   ok: sys.email.configured,    yes: 'configured',  no: 'not configured' },
                { label: 'Sentry',             ok: sys.config.sentry_enabled, yes: 'enabled',   no: 'disabled' },
              ].map(({ label, ok, yes, no }) => (
                <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.82rem', color: C.muted }}>{label}</span>
                  <Badge ok={ok} yes={yes} no={no} />
                </div>
              ))}
            </div>
          </Card>

          {/* Config + Online */}
          <Card title="Config">
            <Row label="Environment"     value={sys.config.environment} />
            <Row label="Maintenance"     value={sys.config.maintenance_mode ? 'ON' : 'off'} color={sys.config.maintenance_mode ? C.red : C.green} />
            <Row label="Online users"    value={sys.online_users ?? 'N/A'} color={C.green} />
          </Card>

          {/* Scheduled tasks */}
          {tasks && (
            <div style={{ gridColumn: '1 / -1', background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 14, padding: '1.25rem 1.5rem' }}>
              <h2 style={{ fontSize: '0.85rem', fontWeight: 600, color: C.text, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: 8 }}>
                <Clock style={{ width: 14, height: 14, color: C.amber }} />
                Celery Beat — Scheduled Tasks
              </h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
                {tasks.tasks.map(t => (
                  <div key={t.key} style={{ background: 'rgba(255,255,255,0.02)', border: `1px solid ${C.border}`, borderRadius: 10, padding: '0.9rem 1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8 }}>
                      <TaskStatusDot status={t.status} />
                      <span style={{ fontSize: '0.8rem', fontWeight: 600, color: C.text }}>{t.name}</span>
                    </div>
                    <div style={{ fontSize: '0.72rem', color: C.dim, marginBottom: 6 }}>{t.schedule}</div>
                    <div style={{ fontSize: '0.7rem', color: C.muted }}>
                      Last: {t.last_run_at ? new Date(t.last_run_at).toLocaleString() : <span style={{ color: C.dim }}>never</span>}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: C.muted }}>
                      Next: {t.next_run_at ? new Date(t.next_run_at).toLocaleString() : <span style={{ color: C.dim }}>unknown</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
