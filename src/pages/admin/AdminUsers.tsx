import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, ChevronLeft, ChevronRight, Download } from 'lucide-react';
import { adminApi } from '@/lib/adminApi';
import { AdminPage, AdminCard, ErrorBanner, fmtNum, Spinner, type Accent } from './_ui';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';

// Matches backend /api/admin/users response shape
interface UserItem {
  account_id: string;
  broker_user_id: string;
  status: string;
  broker_email: string | null;
  created_at: string | null;
  last_trade_at: string | null;
  lifecycle: string;
  user: { id: string | null; email: string | null; guardian_phone: string | null } | null;
}

const ACCENT_RGB: Record<Accent, string> = {
  profit: 'rgb(var(--tm-profit))', loss: 'rgb(var(--tm-loss))',
  warning: 'rgb(var(--tm-obs))', brand: 'rgb(var(--tm-brand))', muted: 'rgb(var(--muted-foreground))',
};
const STATUS_ACCENT: Record<string, Accent> = {
  connected: 'profit', guest: 'warning', suspended: 'loss', disconnected: 'muted',
};
const LIFECYCLE_CFG: Record<string, { accent: Accent; label: string }> = {
  new:          { accent: 'brand',   label: 'New' },
  active:       { accent: 'profit',  label: 'Active' },
  at_risk:      { accent: 'warning', label: 'At Risk' },
  churned:      { accent: 'loss',    label: 'Churned' },
  inactive:     { accent: 'muted',   label: 'Inactive' },
  suspended:    { accent: 'loss',    label: 'Suspended' },
  disconnected: { accent: 'muted',   label: 'Disconnected' },
};

function Pill({ label, accent, capitalize }: { label: string; accent: Accent; capitalize?: boolean }) {
  const rgb = ACCENT_RGB[accent];
  return (
    <span
      className={`inline-block text-[11px] font-semibold px-2 py-0.5 rounded-full whitespace-nowrap ${capitalize ? 'capitalize' : ''}`}
      style={{ background: `color-mix(in srgb, ${rgb} 12%, transparent)`, color: rgb, border: `1px solid color-mix(in srgb, ${rgb} 25%, transparent)` }}
    >
      {label}
    </span>
  );
}

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
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }, [search, status, page]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setPage(1); }, [search, status]);

  const totalPages = Math.max(1, Math.ceil(total / 50));

  const exportCsv = (rows: UserItem[]) => {
    const header = 'account_id,broker_user_id,status,email,phone,joined\n';
    const body = rows.map(u =>
      [u.account_id, u.broker_user_id, u.status, u.user?.email || '', u.user?.guardian_phone || '',
       u.created_at ? new Date(u.created_at).toLocaleDateString() : ''].join(',')
    ).join('\n');
    const blob = new Blob([header + body], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url;
    a.download = `tradementor_users_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click(); URL.revokeObjectURL(url);
  };

  const displayName = (u: UserItem) => u.user?.email || u.broker_email || u.broker_user_id || '—';
  const cols = ['User / Zerodha ID', 'Status', 'Lifecycle', 'Phone', 'Last Trade', 'Joined'];

  return (
    <AdminPage
      title="Users"
      subtitle={`${fmtNum(total)} total`}
      actions={<Button variant="outline" size="sm" onClick={() => exportCsv(items)}><Download className="w-3.5 h-3.5" /> Export CSV</Button>}
    >
      {/* Filters */}
      <div className="flex gap-3 mb-5">
        <div className="relative flex-1 max-w-[320px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground pointer-events-none" />
          <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search email, Zerodha ID…" className="pl-9 h-10" />
        </div>
        <select
          value={status} onChange={e => setStatus(e.target.value)}
          className="h-10 px-3 rounded-lg bg-card border border-border text-foreground text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">All statuses</option>
          <option value="connected">Connected</option>
          <option value="disconnected">Disconnected</option>
          <option value="suspended">Suspended</option>
        </select>
      </div>

      <ErrorBanner message={error} />

      <AdminCard noPadding>
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              {cols.map(h => <TableHead key={h} className="table-header">{h}</TableHead>)}
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow className="hover:bg-transparent"><TableCell colSpan={cols.length} className="py-12 text-center"><div className="inline-block"><Spinner /></div></TableCell></TableRow>
            ) : items.length === 0 ? (
              <TableRow className="hover:bg-transparent"><TableCell colSpan={cols.length} className="py-12 text-center text-sm text-muted-foreground">No users found</TableCell></TableRow>
            ) : items.map(u => {
              const lc = LIFECYCLE_CFG[u.lifecycle] || LIFECYCLE_CFG.inactive;
              return (
                <TableRow key={u.account_id} onClick={() => navigate(`/admin/users/${u.account_id}`)} className="cursor-pointer">
                  <TableCell>
                    <div className="text-[13px] font-medium text-foreground">{displayName(u)}</div>
                    <div className="text-[11px] text-muted-foreground">{u.broker_user_id}</div>
                  </TableCell>
                  <TableCell><Pill label={u.status} accent={STATUS_ACCENT[u.status] || 'muted'} capitalize /></TableCell>
                  <TableCell><Pill label={lc.label} accent={lc.accent} /></TableCell>
                  <TableCell className="text-[13px] text-muted-foreground">{u.user?.guardian_phone || '—'}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {u.last_trade_at ? new Date(u.last_trade_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : '—'}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' }) : '—'}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </AdminCard>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 mt-6">
          <Button variant="outline" size="icon" className="h-8 w-8" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
            <ChevronLeft className="w-3.5 h-3.5" />
          </Button>
          <span className="text-[13px] text-muted-foreground">Page {page} of {totalPages}</span>
          <Button variant="outline" size="icon" className="h-8 w-8" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>
            <ChevronRight className="w-3.5 h-3.5" />
          </Button>
        </div>
      )}
    </AdminPage>
  );
}
