import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, ChevronLeft, ChevronRight, AlertTriangle, Download } from 'lucide-react';
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

// Matches backend /api/admin/users response shape
interface UserItem {
  account_id: string;
  broker_user_id: string;
  status: string;
  broker_email: string | null;
  created_at: string | null;
  user: { id: string | null; email: string | null; guardian_phone: string | null } | null;
}

const STATUS_COLORS: Record<string, string> = {
  connected: C.green, guest: C.amber, suspended: C.red, disconnected: C.muted,
};

export default function AdminUsers() {
  const navigate = useNavigate();
  const [items, setItems]       = useState<UserItem[]>([]);
  const [search, setSearch]     = useState('');
  const [status, setStatus]     = useState('');
  const [page, setPage]         = useState(1);
  const [total, setTotal]       = useState(0);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const d = await adminApi.users({ search: search || undefined, status: status || undefined, page });
      setItems(d.items); setTotal(d.total);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }, [search, status, page]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setPage(1); }, [search, status]);

  const totalPages = Math.max(1, Math.ceil(total / 50));

  const exportCsv = (rows: UserItem[]) => {
    const header = 'account_id,broker_user_id,status,email,phone,joined\n';
    const body = rows.map(u =>
      [u.account_id, u.broker_user_id, u.status,
       u.user?.email || '', u.user?.guardian_phone || '',
       u.created_at ? new Date(u.created_at).toLocaleDateString() : ''
      ].join(',')
    ).join('\n');
    const blob = new Blob([header + body], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url;
    a.download = `tradementor_users_${new Date().toISOString().slice(0,10)}.csv`;
    a.click(); URL.revokeObjectURL(url);
  };

  const displayName = (u: UserItem) =>
    u.user?.email || u.broker_email || u.broker_user_id || '—';

  return (
    <div style={{ padding: '2rem', fontFamily: C.dm }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
        <div>
          <h1 style={{ fontSize: '1.3rem', fontWeight: 700, color: C.text, margin: 0 }}>Users</h1>
          <p style={{ fontSize: '0.78rem', color: C.muted, marginTop: 4 }}>{total.toLocaleString()} total</p>
        </div>
        <button
          onClick={() => exportCsv(items)}
          style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0.5rem 1rem', borderRadius: 9, background: 'rgba(255,255,255,0.04)', border: `1px solid ${C.border}`, color: C.muted, fontSize: '0.78rem', cursor: 'pointer', fontFamily: C.dm }}
        >
          <Download style={{ width: 13, height: 13 }} />
          Export CSV
        </button>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 12, marginBottom: '1.5rem' }}>
        <div style={{ position: 'relative', flex: 1, maxWidth: 320 }}>
          <Search style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', width: 14, height: 14, color: C.dim }} />
          <input
            value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search email, Zerodha ID…"
            style={{ width: '100%', padding: '0.6rem 0.75rem 0.6rem 2.2rem', borderRadius: 9, background: 'rgba(255,255,255,0.04)', border: `1px solid ${C.border}`, color: C.text, fontFamily: C.dm, fontSize: '0.82rem', outline: 'none', boxSizing: 'border-box' }}
          />
        </div>
        <select
          value={status} onChange={e => setStatus(e.target.value)}
          style={{ padding: '0.6rem 0.75rem', borderRadius: 9, background: 'rgba(255,255,255,0.04)', border: `1px solid ${C.border}`, color: C.text, fontFamily: C.dm, fontSize: '0.82rem', outline: 'none' }}
        >
          <option value="">All statuses</option>
          <option value="connected">Connected</option>
          <option value="disconnected">Disconnected</option>
          <option value="suspended">Suspended</option>
        </select>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0.75rem 1rem', borderRadius: 10, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', marginBottom: '1rem' }}>
          <AlertTriangle style={{ width: 14, height: 14, color: C.red }} />
          <span style={{ fontSize: '0.8rem', color: C.red }}>{error}</span>
        </div>
      )}

      <div style={{ background: 'rgba(255,255,255,0.02)', border: `1px solid ${C.border}`, borderRadius: 14, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {['User / Zerodha ID', 'Status', 'Phone', 'Joined'].map(h => (
                <th key={h} style={{ padding: '0.75rem 1rem', textAlign: 'left', fontSize: '0.72rem', fontWeight: 600, color: C.dim, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={4} style={{ padding: '3rem', textAlign: 'center' }}>
                  <div style={{ display: 'inline-block', width: 24, height: 24, border: `2px solid ${C.amber}`, borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
                  <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={4} style={{ padding: '3rem', textAlign: 'center', fontSize: '0.82rem', color: C.dim }}>No users found</td></tr>
            ) : items.map((u, i) => (
              <tr
                key={u.account_id}
                onClick={() => navigate(`/admin/users/${u.account_id}`)}
                style={{ borderBottom: i < items.length - 1 ? `1px solid rgba(255,255,255,0.04)` : 'none', cursor: 'pointer', transition: 'background 0.12s' }}
                onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.03)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              >
                <td style={{ padding: '0.8rem 1rem' }}>
                  <div style={{ fontSize: '0.82rem', fontWeight: 500, color: C.text }}>{displayName(u)}</div>
                  <div style={{ fontSize: '0.7rem', color: C.muted }}>{u.broker_user_id}</div>
                </td>
                <td style={{ padding: '0.8rem 1rem' }}>
                  <span style={{ fontSize: '0.7rem', fontWeight: 600, padding: '0.2rem 0.55rem', borderRadius: 20, background: `${STATUS_COLORS[u.status] || C.muted}18`, color: STATUS_COLORS[u.status] || C.muted, border: `1px solid ${STATUS_COLORS[u.status] || C.muted}30`, textTransform: 'capitalize' }}>{u.status}</span>
                </td>
                <td style={{ padding: '0.8rem 1rem', fontSize: '0.78rem', color: C.muted }}>{u.user?.guardian_phone || '—'}</td>
                <td style={{ padding: '0.8rem 1rem', fontSize: '0.75rem', color: C.muted }}>
                  {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
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
