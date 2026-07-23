import { useEffect, useState, useCallback } from 'react';
import { UserPlus, MoreHorizontal, Copy, Check, ShieldCheck, KeyRound, LogOut, Ban, RotateCcw } from 'lucide-react';
import { adminApi } from '@/lib/adminApi';
import { useAdminAuth } from '@/contexts/AdminAuthContext';
import { AdminPage, AdminCard, ErrorBanner, LoadingBlock, Spinner, type Accent } from './_ui';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface AdminRow {
  id: string; email: string; name: string; role: string;
  is_active: boolean; has_totp: boolean; must_change_password: boolean; totp_required: boolean;
  last_login_at: string | null; created_at: string | null; created_by: string | null;
}

const ACCENT_RGB: Record<Accent, string> = {
  profit: 'rgb(var(--tm-profit))', loss: 'rgb(var(--tm-loss))',
  warning: 'rgb(var(--tm-obs))', brand: 'rgb(var(--tm-brand))', muted: 'rgb(var(--muted-foreground))',
};
const ROLE_ACCENT: Record<string, Accent> = { superadmin: 'brand', ops: 'warning', support: 'muted' };

function Pill({ accent, label, capitalize }: { accent: Accent; label: string; capitalize?: boolean }) {
  const rgb = ACCENT_RGB[accent];
  return (
    <span className={`inline-block text-[11px] font-semibold px-2 py-0.5 rounded-full ${capitalize ? 'capitalize' : ''}`}
      style={{ color: rgb, background: `color-mix(in srgb, ${rgb} 12%, transparent)`, border: `1px solid color-mix(in srgb, ${rgb} 25%, transparent)` }}>
      {label}
    </span>
  );
}

const fmtDate = (iso: string | null) => iso ? new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' }) : '—';

export default function AdminAdmins() {
  const { admin: me } = useAdminAuth();
  const [rows, setRows]       = useState<AdminRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [rowBusy, setRowBusy] = useState<string | null>(null);

  const [createOpen, setCreateOpen]   = useState(false);
  const [form, setForm]               = useState({ email: '', name: '', role: 'support' });
  const [creating, setCreating]       = useState(false);
  const [createErr, setCreateErr]     = useState('');

  const [tempPw, setTempPw]           = useState<{ email: string; password: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try { const d = await adminApi.admins(); setRows(d.admins); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const act = async (id: string, fn: () => Promise<unknown>) => {
    setRowBusy(id); setError('');
    try { await fn(); await load(); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setRowBusy(null); }
  };

  const changeRole = (r: AdminRow, role: string) => act(r.id, () => adminApi.patchAdmin(r.id, { role }));
  const toggleActive = (r: AdminRow) => act(r.id, () => adminApi.patchAdmin(r.id, { is_active: !r.is_active }));
  const forceLogout = (r: AdminRow) => act(r.id, () => adminApi.forceLogoutAdmin(r.id));
  const resetTotp = (r: AdminRow) => act(r.id, () => adminApi.resetAdminTotp(r.id));
  const resetPassword = async (r: AdminRow) => {
    setRowBusy(r.id); setError('');
    try {
      const res = await adminApi.resetAdminPassword(r.id);
      setTempPw({ email: r.email, password: res.temp_password });
      await load();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setRowBusy(null); }
  };

  const create = async () => {
    setCreating(true); setCreateErr('');
    try {
      const res = await adminApi.createAdmin({ email: form.email.trim(), name: form.name.trim(), role: form.role });
      setCreateOpen(false);
      setForm({ email: '', name: '', role: 'support' });
      setTempPw({ email: res.admin.email, password: res.temp_password });
      await load();
    } catch (e: unknown) { setCreateErr(e instanceof Error ? e.message : String(e)); }
    finally { setCreating(false); }
  };

  const cols = ['Admin', 'Role', '2FA', 'Status', 'Last login', ''];

  return (
    <AdminPage
      title="Admins"
      subtitle={`${rows.length} admin ${rows.length === 1 ? 'account' : 'accounts'}`}
      actions={<Button size="sm" onClick={() => { setCreateErr(''); setCreateOpen(true); }}><UserPlus className="w-3.5 h-3.5" /> New admin</Button>}
    >
      <ErrorBanner message={error} />

      {loading ? <LoadingBlock /> : (
        <AdminCard noPadding>
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">{cols.map(h => <TableHead key={h} className="table-header">{h}</TableHead>)}</TableRow>
            </TableHeader>
            <TableBody>
              {rows.map(r => {
                const isSelf = r.email === me?.email;
                const busy = rowBusy === r.id;
                return (
                  <TableRow key={r.id} className="hover:bg-transparent">
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span className="text-[13px] font-medium text-foreground">{r.name}</span>
                        {isSelf && <span className="text-[10px] px-1.5 py-px rounded-full bg-muted text-muted-foreground">you</span>}
                      </div>
                      <div className="text-[11px] text-muted-foreground">{r.email}</div>
                    </TableCell>
                    <TableCell>
                      {isSelf ? <Pill accent={ROLE_ACCENT[r.role] ?? 'muted'} label={r.role} capitalize /> : (
                        <select value={r.role} disabled={busy} onChange={e => changeRole(r, e.target.value)}
                          className="h-8 px-2 rounded-md bg-card border border-border text-foreground text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring capitalize">
                          <option value="superadmin">superadmin</option>
                          <option value="ops">ops</option>
                          <option value="support">support</option>
                        </select>
                      )}
                    </TableCell>
                    <TableCell>
                      {r.has_totp ? <Pill accent="profit" label="TOTP" />
                        : r.totp_required ? <Pill accent="warning" label="TOTP pending" />
                        : <span className="text-xs text-muted-foreground">Email OTP</span>}
                    </TableCell>
                    <TableCell>
                      {r.is_active ? <Pill accent="profit" label="Active" /> : <Pill accent="muted" label="Inactive" />}
                      {r.must_change_password && <div className="text-[10px] text-[rgb(var(--tm-obs))] mt-0.5">pwd reset pending</div>}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">{fmtDate(r.last_login_at)}</TableCell>
                    <TableCell className="text-right">
                      {busy ? <span className="inline-block"><Spinner size={14} /></span> : isSelf ? <span className="text-[11px] text-muted-foreground/60">—</span> : (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8"><MoreHorizontal className="w-4 h-4" /></Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-52">
                            <DropdownMenuItem onClick={() => toggleActive(r)}>
                              <Ban className="w-3.5 h-3.5" /> {r.is_active ? 'Deactivate' : 'Reactivate'}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => forceLogout(r)}>
                              <LogOut className="w-3.5 h-3.5" /> Force logout
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={() => resetPassword(r)}>
                              <KeyRound className="w-3.5 h-3.5" /> Reset password
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => resetTotp(r)} disabled={!r.has_totp}>
                              <RotateCcw className="w-3.5 h-3.5" /> Reset TOTP
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
              {rows.length === 0 && (
                <TableRow className="hover:bg-transparent"><TableCell colSpan={cols.length} className="py-12 text-center text-sm text-muted-foreground">No admins</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </AdminCard>
      )}

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-[rgb(var(--tm-brand))]" /> New admin</DialogTitle>
            <DialogDescription>Creates an account with a one-time temp password. They must change it and enrol an authenticator on first login.</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-1">
            <div className="space-y-1.5">
              <Label htmlFor="a-email">Email</Label>
              <Input id="a-email" type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} placeholder="name@tradementor.ai" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="a-name">Name</Label>
              <Input id="a-name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Full name" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="a-role">Role</Label>
              <select id="a-role" value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))}
                className="w-full h-10 px-3 rounded-lg bg-card border border-border text-foreground text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring">
                <option value="support">support — read-only + per-user message</option>
                <option value="ops">ops — broadcast, tasks, suspend</option>
                <option value="superadmin">superadmin — full access</option>
              </select>
            </div>
            {createErr && <p className="text-sm text-[rgb(var(--tm-loss))]">{createErr}</p>}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={create} disabled={creating || !form.email.trim() || !form.name.trim()}>{creating ? 'Creating…' : 'Create admin'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Temp-password reveal (create + reset) */}
      <TempPasswordDialog data={tempPw} onClose={() => setTempPw(null)} />
    </AdminPage>
  );
}

function TempPasswordDialog({ data, onClose }: { data: { email: string; password: string } | null; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    if (!data) return;
    navigator.clipboard?.writeText(data.password).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); }).catch(() => {});
  };
  return (
    <Dialog open={!!data} onOpenChange={o => { if (!o) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><KeyRound className="w-4 h-4 text-[rgb(var(--tm-brand))]" /> One-time password</DialogTitle>
          <DialogDescription>Share this with <strong className="text-foreground">{data?.email}</strong> over a secure channel. It won't be shown again — they'll set their own on first login.</DialogDescription>
        </DialogHeader>
        <div className="flex items-center gap-2 my-1">
          <code className="flex-1 px-3 py-2.5 rounded-lg bg-muted border border-border font-mono text-sm text-foreground break-all">{data?.password}</code>
          <Button variant="outline" size="icon" onClick={copy}>{copied ? <Check className="w-4 h-4 text-[rgb(var(--tm-profit))]" /> : <Copy className="w-4 h-4" />}</Button>
        </div>
        <DialogFooter><Button onClick={onClose}>Done</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
