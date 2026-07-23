import { useEffect, useState, useCallback } from 'react';
import { ChevronLeft, ChevronRight, Shield } from 'lucide-react';
import { adminApi } from '@/lib/adminApi';
import { AdminPage, AdminCard, ErrorBanner, LoadingBlock, fmtNum, type Accent } from './_ui';
import { Button } from '@/components/ui/button';

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
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const d = await adminApi.auditLog({ page, action: action || undefined });
      setItems(d.items); setTotal(d.total);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }, [page, action]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setPage(1); }, [action]);

  const totalPages = Math.max(1, Math.ceil(total / 50));

  return (
    <AdminPage
      title="Audit Log"
      subtitle={`${fmtNum(total)} actions recorded`}
      actions={
        <select
          value={action} onChange={e => setAction(e.target.value)}
          className="h-9 px-3 rounded-lg bg-card border border-border text-foreground text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">All actions</option>
          {Object.entries(ACTION_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      }
    >
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
