import { useEffect, useState, useCallback } from 'react';
import { ChevronLeft, ChevronRight, Shield } from 'lucide-react';
import { adminApi } from '@/lib/adminApi';

const C = {
  text:   '#e2e8f0',
  muted:  'rgba(226,232,240,0.45)',
  dim:    'rgba(226,232,240,0.25)',
  border: 'rgba(255,255,255,0.07)',
  amber:  '#f59e0b',
  green:  '#10b981',
  red:    '#ef4444',
  orange: '#f97316',
  dm:     "'DM Sans', sans-serif",
};

interface AuditItem {
  id: string; admin_email: string; action: string;
  target_type: string | null; target_id: string | null;
  details: Record<string, any> | null; created_at: string | null;
}

const ACTION_COLORS: Record<string, string> = {
  login: C.green, logout: C.dim,
  suspend_user: C.red, unsuspend_user: C.green,
  send_message: C.amber, broadcast: C.orange,
  set_maintenance: C.red, set_announcement: C.amber,
};

const ACTION_LABELS: Record<string, string> = {
  login: 'Login', logout: 'Logout',
  suspend_user: 'Suspend user', unsuspend_user: 'Unsuspend user',
  send_message: 'Send message', broadcast: 'Broadcast',
  set_maintenance: 'Maintenance toggle', set_announcement: 'Announcement set',
};

function DetailChip({ k, v }: { k: string; v: any }) {
  if (v === null || v === undefined) return null;
  return (
    <span style={{ fontSize: '0.68rem', padding: '0.1rem 0.45rem', borderRadius: 6, background: 'rgba(255,255,255,0.06)', color: C.muted }}>
      {k}: <span style={{ color: C.text }}>{String(v).slice(0, 60)}</span>
    </span>
  );
}

export default function AdminAuditLog() {
  const [items, setItems]     = useState<AuditItem[]>([]);
  const [total, setTotal]     = useState(0);
  const [page, setPage]       = useState(1);
  const [action, setAction]   = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const d = await adminApi.auditLog({ page, action: action || undefined });
      setItems(d.items); setTotal(d.total);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }, [page, action]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setPage(1); }, [action]);

  const totalPages = Math.max(1, Math.ceil(total / 50));

  return (
    <div style={{ padding: '2rem', fontFamily: C.dm }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '1.3rem', fontWeight: 700, color: C.text, margin: 0 }}>Audit Log</h1>
          <p style={{ fontSize: '0.75rem', color: C.dim, marginTop: 4 }}>{total.toLocaleString()} actions recorded</p>
        </div>
        <select
          value={action} onChange={e => setAction(e.target.value)}
          style={{ padding: '0.5rem 0.75rem', borderRadius: 9, background: 'rgba(255,255,255,0.04)', border: `1px solid ${C.border}`, color: C.text, fontFamily: C.dm, fontSize: '0.8rem', outline: 'none' }}
        >
          <option value="">All actions</option>
          {Object.entries(ACTION_LABELS).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
      </div>

      {error && <div style={{ padding: '0.75rem 1rem', borderRadius: 10, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', marginBottom: '1rem', fontSize: '0.8rem', color: C.red }}>{error}</div>}

      <div style={{ background: 'rgba(255,255,255,0.02)', border: `1px solid ${C.border}`, borderRadius: 14, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
            <div style={{ width: 24, height: 24, border: `2px solid ${C.amber}`, borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        ) : items.length === 0 ? (
          <div style={{ padding: '3rem', textAlign: 'center', fontSize: '0.82rem', color: C.dim }}>No audit entries yet</div>
        ) : (
          <div>
            {items.map((item, i) => {
              const color = ACTION_COLORS[item.action] || C.muted;
              const label = ACTION_LABELS[item.action] || item.action;
              return (
                <div
                  key={item.id}
                  style={{
                    display: 'flex', alignItems: 'flex-start', gap: 14,
                    padding: '0.9rem 1.25rem',
                    borderBottom: i < items.length - 1 ? `1px solid rgba(255,255,255,0.04)` : 'none',
                  }}
                >
                  <div style={{ width: 30, height: 30, borderRadius: 9, background: `${color}15`, border: `1px solid ${color}30`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 2 }}>
                    <Shield style={{ width: 13, height: 13, color }} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                      <span style={{ fontSize: '0.82rem', fontWeight: 600, color }}>{label}</span>
                      <span style={{ fontSize: '0.75rem', color: C.muted }}>{item.admin_email}</span>
                      {item.target_id && item.target_id !== 'global' && (
                        <span style={{ fontSize: '0.7rem', color: C.dim, fontFamily: 'monospace' }}>{item.target_id.slice(0, 12)}…</span>
                      )}
                    </div>
                    {item.details && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {Object.entries(item.details).slice(0, 4).map(([k, v]) => (
                          <DetailChip key={k} k={k} v={v} />
                        ))}
                      </div>
                    )}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: C.dim, flexShrink: 0, whiteSpace: 'nowrap' }}>
                    {item.created_at ? new Date(item.created_at).toLocaleString() : '—'}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {totalPages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, marginTop: '1.5rem' }}>
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} style={{ padding: '0.4rem 0.6rem', borderRadius: 8, background: 'rgba(255,255,255,0.04)', border: `1px solid ${C.border}`, color: C.muted, cursor: page === 1 ? 'not-allowed' : 'pointer', opacity: page === 1 ? 0.4 : 1 }}>
            <ChevronLeft style={{ width: 14, height: 14 }} />
          </button>
          <span style={{ fontSize: '0.78rem', color: C.muted }}>Page {page} of {totalPages}</span>
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} style={{ padding: '0.4rem 0.6rem', borderRadius: 8, background: 'rgba(255,255,255,0.04)', border: `1px solid ${C.border}`, color: C.muted, cursor: page === totalPages ? 'not-allowed' : 'pointer', opacity: page === totalPages ? 0.4 : 1 }}>
            <ChevronRight style={{ width: 14, height: 14 }} />
          </button>
        </div>
      )}
    </div>
  );
}
