import { useEffect } from 'react';
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Users, Activity, BarChart3, Settings,
  LogOut, ScrollText, Megaphone, Shield, ShieldCheck,
} from 'lucide-react';
import { useAdminAuth } from '@/contexts/AdminAuthContext';
import { adminApi } from '@/lib/adminApi';
import { cn } from '@/lib/utils';
import { Spinner } from './_ui';
import AdminOnboarding from './AdminOnboarding';

const NAV_GROUPS = [
  {
    label: 'Monitor',
    items: [
      { to: '/admin/overview',  icon: LayoutDashboard, label: 'Overview',   roles: ['superadmin','ops','support'] },
      { to: '/admin/users',     icon: Users,           label: 'Users',      roles: ['superadmin','ops','support'] },
      { to: '/admin/system',    icon: Activity,        label: 'System',     roles: ['superadmin','ops','support'] },
      { to: '/admin/insights',  icon: BarChart3,       label: 'Insights',   roles: ['superadmin','ops','support'] },
    ],
  },
  {
    label: 'Operations',
    items: [
      { to: '/admin/broadcast', icon: Megaphone,  label: 'Broadcast', roles: ['superadmin','ops'] },
      { to: '/admin/audit-log', icon: ScrollText, label: 'Audit Log', roles: ['superadmin','ops','support'] },
    ],
  },
  {
    label: 'System',
    items: [
      { to: '/admin/admins', icon: ShieldCheck, label: 'Admins', roles: ['superadmin'] },
      { to: '/admin/config', icon: Settings,    label: 'Config', roles: ['superadmin'] },
    ],
  },
];

export default function AdminLayout() {
  const { admin, isLoading, logout } = useAdminAuth();
  const navigate  = useNavigate();
  const location  = useLocation();

  useEffect(() => {
    if (!isLoading && !admin) navigate('/admin/login', { replace: true });
  }, [admin, isLoading, navigate]);

  const handleLogout = async () => {
    try { await adminApi.logout(); } catch {}
    logout();
    navigate('/admin/login', { replace: true });
  };

  const initials = admin?.name
    ? admin.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
    : '??';

  if (isLoading) return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <Spinner size={28} />
    </div>
  );

  if (!admin) return null;

  // Forced first-login setup — block the app until temp password is changed and,
  // if required, an authenticator is enrolled.
  if (admin.must_change_password || (admin.totp_required && !admin.has_totp)) {
    return <AdminOnboarding />;
  }

  return (
    <div className="flex min-h-screen bg-background text-foreground">

      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside className="flex flex-col sticky top-0 h-screen shrink-0 w-[236px] bg-card border-r border-border">

        {/* Logo */}
        <div className="flex items-center gap-2.5 px-4 py-4 border-b border-border">
          <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-[rgb(var(--tm-brand))]/15 border border-[rgb(var(--tm-brand))]/25">
            <Shield size={14} className="text-[rgb(var(--tm-brand))]" />
          </div>
          <div>
            <div className="text-xs font-semibold leading-tight text-foreground">TradeMentor</div>
            <div className="text-[10px] font-bold tracking-[0.1em] text-[rgb(var(--tm-brand))]">ADMIN</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-3 px-2 [scrollbar-width:none]">
          {NAV_GROUPS.map(group => {
            const visible = group.items.filter(item => item.roles.includes(admin.role || 'superadmin'));
            if (!visible.length) return null;
            return (
              <div key={group.label} className="mb-4">
                <div className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground/60">
                  {group.label}
                </div>
                {visible.map(({ to, icon: Icon, label }) => {
                  const active = location.pathname === to || (to !== '/admin/overview' && location.pathname.startsWith(to));
                  return (
                    <NavLink
                      key={to}
                      to={to}
                      className={cn(
                        'flex items-center gap-2.5 pr-3 py-2 rounded-md text-[13px] transition-colors border-l-2',
                        active
                          ? 'text-[rgb(var(--tm-brand))] bg-[rgb(var(--tm-brand))]/[0.07] border-[rgb(var(--tm-brand))] pl-2.5 font-medium'
                          : 'text-muted-foreground hover:text-foreground border-transparent pl-3',
                      )}
                    >
                      <Icon size={14} className={cn('shrink-0', active ? 'opacity-100' : 'opacity-70')} />
                      {label}
                    </NavLink>
                  );
                })}
              </div>
            );
          })}
        </nav>

        {/* User row */}
        <div className="px-3 py-3 border-t border-border">
          <div className="flex items-center gap-2.5 mb-2.5">
            <div className="flex items-center justify-center w-7 h-7 rounded-full text-[11px] font-bold shrink-0 bg-[rgb(var(--tm-brand))]/15 text-[rgb(var(--tm-brand))]">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[12px] font-medium truncate text-foreground">{admin.name}</div>
              <div className="text-[11px] truncate text-muted-foreground">{admin.email}</div>
            </div>
            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wide bg-[rgb(var(--tm-brand))]/10 text-[rgb(var(--tm-brand))]">
              {(admin.role || 'SA').slice(0, 2).toUpperCase()}
            </span>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 w-full px-2.5 py-1.5 rounded-md text-[12px] text-muted-foreground hover:text-foreground hover:bg-accent/20 transition-colors"
          >
            <LogOut size={12} />
            Sign out
          </button>
        </div>
      </aside>

      {/* ── Main ────────────────────────────────────────────────────────── */}
      <main className="flex-1 overflow-auto min-w-0">
        <Outlet />
      </main>
    </div>
  );
}
