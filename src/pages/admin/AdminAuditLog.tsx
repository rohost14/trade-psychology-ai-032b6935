import { useEffect, useState, useCallback } from 'react';
import { ChevronLeft, ChevronRight, Shield, Download } from 'lucide-react';
import { adminApi } from '@/lib/adminApi';
import { AdminPage, AdminCard, ErrorBanner, LoadingBlock, fmtNum, type Accent } from './_ui';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface AuditItem {
  id: string; admin_email: string; action: string;
  target_type: string | null; target_id: string | null;
  details: Record<string, unknown> | null; created_at: string | null;
}

// action → accent token
const ACTION_ACCENT: Record<string, Accent> = {
  login: 'profit', admin_login: 'profit', logout: 'muted',
  suspend_user: 'loss', unsuspend_user: 'profit',
  delete: 'loss', erase: 'loss',
  send_message: 'brand', broadcast: 'warning',
  set_maintenance: 'loss', set_announcement: 'warning', set_detector_flag: 'warning',
  create_admin: 'brand', update_admin: 'warning', force_logout_admin: 'warning',
  reset_admin_totp: 'warning', reset_admin_password: 'loss', change_password: 'brand',
};
const ACCENT_RGB: Record<Accent, string> = {
  profit: 'rgb(var(--tm-profit))', loss: 'rgb(var(--tm-loss))',
  warning: 'rgb(var(--tm-obs))', brand: 'rgb(var(--tm-brand))', muted: 'rgb(var(--muted-foreground))',
};

const ACTION_LABELS: Record<string, string> = {
  login: 'Login', admin_login: 'Login', logout: 'Logout',
  suspend_user: 'Suspend user', unsuspend_user: 'Unsuspend user',
  send_message: 'Send message', broadcast: 'Broadcast',
  set_maintenance: 'Maintenance toggle', set_announcement: 'Announcement set',
  set_detector_flag: 'Detector flag',
  create_admin: 'Admin created', update_admin: 'Admin updated', force_logout_admin: 'Admin force-logout',
  reset_admin_totp: 'Admin TOTP reset', reset_admin_password: 'Admin password reset', change_password: 'Password changed',
};

function DetailChip({ k, v }: { k: string; v: unknown }) {
  if (v === null || v === undefined) return null;
  return (
    <span className="text-[11px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
      {k}: <span className="text-foreground">{String(v).slice(0, 60)}</span>
    </span>
  );
}

export default function AdminAuditLog() {
  const [items, setItems]     = useState<AuditItem[]>([]);
  const [total, setTotal]     = useState(0);
  const [page, setPage]       = useState(1);
  const [action, setAction]   = useState('');
  const [adminEmail, setAdminEmail] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo]     = useState('');
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError]     = useState('');

  const filters = useCallback(() => ({
    action:      action || undefined,
    admin_email: adminEmail || undefined,
    date_from:   dateFrom || undefined,
    date_to:     dateTo || undefined,
  }), [action, adminEmail, dateFrom, dateTo]);

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const d = await adminApi.auditLog({ page, ...filters() });
      setItems(d.items); setTotal(d.total);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }, [page, filters]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setPage(1); }, [action, adminEmail, dateFrom, dateTo]);

  const totalPages = Math.max(1, Math.ceil(total / 50));

  const exportCsv = async () => {
    setExporting(true); setError('');
    try {
      const d = await adminApi.auditLog({ page: 1, limit: 5000, ...filters() });
      const rows: AuditItem[] = d.items;
      const esc = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`;
      const header = 'time,admin_email,action,target_type,target_id,details\n';
      const body = rows.map(r => [
        r.created_at ? new Date(r.created_at).toISOString() : '',
        r.admin_email, r.action, r.target_type ?? '', r.target_id ?? '',
        r.details ? JSON.stringify(r.details) : '',
      ].map(esc).join(',')).join('\n');
      const blob = new Blob([header + body], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url;
      a.download = `tradementor_audit_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click(); URL.revokeObjectURL(url);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setExporting(false); }
  };

  return (
    <AdminPage
      title="Audit Log"
      subtitle={`${fmtNum(total)} actions recorded`}
      actions={
        <Button variant="outline" size="sm" onClick={exportCsv} disabled={exporting}>
          <Download className="w-3.5 h-3.5" /> {exporting ? 'Exporting…' : 'Export CSV'}
        </Button>
      }
    >
      {/* Filter bar */}
      <div className="flex flex-wrap gap-2.5 mb-5">
        <select
          value={action} onChange={e => setAction(e.target.value)}
          className="h-9 px-3 rounded-lg bg-card border border-border text-foreground text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">All actions</option>
          {Object.entries(ACTION_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <Input value={adminEmail} onChange={e => setAdminEmail(e.target.value)} placeholder="Admin email…" className="h-9 w-[200px]" />
        <div className="flex items-center gap-1.5">
          <label className="text-[11px] text-muted-foreground">From</label>
          <Input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="h-9 w-[150px]" />
        </div>
        <div className="flex items-center gap-1.5">
          <label className="text-[11px] text-muted-foreground">To</label>
          <Input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="h-9 w-[150px]" />
        </div>
        {(action || adminEmail || dateFrom || dateTo) && (
          <Button variant="ghost" size="sm" onClick={() => { setAction(''); setAdminEmail(''); setDateFrom(''); setDateTo(''); }}>Clear</Button>
        )}
      </div>

      <ErrorBanner message={error} />

      <AdminCard noPadding>
        {loading ? <LoadingBlock />
        : items.length === 0 ? <div className="py-12 text-center text-sm text-muted-foreground">No audit entries yet</div>
        : items.map((item, i) => {
            const rgb = ACCENT_RGB[ACTION_ACCENT[item.action] ?? 'muted'];
            const label = ACTION_LABELS[item.action] || item.action;
            return (
              <div key={item.id} className={`flex items-start gap-3.5 px-5 py-3.5 ${i < items.length - 1 ? 'border-b border-border' : ''}`}>
                <div className="w-[30px] h-[30px] rounded-lg flex items-center justify-center shrink-0 mt-0.5 border"
                     style={{ background: `color-mix(in srgb, ${rgb} 12%, transparent)`, borderColor: `color-mix(in srgb, ${rgb} 25%, transparent)` }}>
                  <Shield className="w-3.5 h-3.5" style={{ color: rgb }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2.5 mb-1 flex-wrap">
                    <span className="text-[13px] font-semibold" style={{ color: rgb }}>{label}</span>
                    <span className="text-xs text-muted-foreground">{item.admin_email}</span>
                    {item.target_id && item.target_id !== 'global' && (
                      <span className="text-[11px] text-muted-foreground/60 font-mono">{item.target_id.slice(0, 12)}…</span>
                    )}
                  </div>
                  {item.details && (
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(item.details).slice(0, 4).map(([k, v]) => <DetailChip key={k} k={k} v={v} />)}
                    </div>
                  )}
                </div>
                <div className="text-[11px] text-muted-foreground/60 shrink-0 whitespace-nowrap">
                  {item.created_at ? new Date(item.created_at).toLocaleString() : '—'}
                </div>
              </div>
            );
          })}
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
