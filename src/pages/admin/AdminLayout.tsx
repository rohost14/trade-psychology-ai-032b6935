import { useEffect } from 'react';
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Users, Activity, BarChart3, Settings,
  LogOut, ScrollText, Megaphone, Shield,
} from 'lucide-react';
import { useAdminAuth } from '@/contexts/AdminAuthContext';
import { adminApi } from '@/lib/adminApi';

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
      { to: '/admin/config', icon: Settings, label: 'Config', roles: ['superadmin'] },
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
    <div className="min-h-screen flex items-center justify-center" style={{ background: '#09090b' }}>
      <div className="w-7 h-7 rounded-full border-2 border-amber-500 border-t-transparent animate-spin" />
    </div>
  );

  if (!admin) return null;

  return (
    <div className="flex min-h-screen" style={{ background: '#09090b', fontFamily: "'Inter', 'DM Sans', sans-serif" }}>

      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside className="flex flex-col sticky top-0 h-screen shrink-0" style={{ width: 236, background: '#0f0f14', borderRight: '1px solid #1c1c28' }}>

        {/* Logo */}
        <div className="flex items-center gap-2.5 px-4 py-4" style={{ borderBottom: '1px solid #1c1c28' }}>
          <div className="flex items-center justify-center w-7 h-7 rounded-lg" style={{ background: 'rgba(245,158,11,0.15)', border: '1px solid rgba(245,158,11,0.25)' }}>
            <Shield size={14} className="text-amber-400" />
          </div>
          <div>
            <div className="text-xs font-semibold leading-tight" style={{ color: '#f1f0f5' }}>TradeMentor</div>
            <div className="text-[10px] font-bold tracking-widest" style={{ color: '#f59e0b', letterSpacing: '0.1em' }}>ADMIN</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-3 px-2" style={{ scrollbarWidth: 'none' }}>
          {NAV_GROUPS.map(group => {
            const visible = group.items.filter(item => item.roles.includes(admin.role || 'superadmin'));
            if (!visible.length) return null;
            return (
              <div key={group.label} className="mb-4">
                <div className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-widest" style={{ color: '#3a3a50', letterSpacing: '0.12em' }}>
                  {group.label}
                </div>
                {visible.map(({ to, icon: Icon, label }) => {
                  const active = location.pathname === to || (to !== '/admin/overview' && location.pathname.startsWith(to));
                  return (
                    <NavLink key={to} to={to} style={{ textDecoration: 'none', display: 'block' }}>
                      <div
                        className="flex items-center gap-2.5 px-3 py-2 rounded-md text-[13px] transition-all duration-100"
                        style={{
                          color:      active ? '#fbbf24' : '#6b6a82',
                          background: active ? 'rgba(245,158,11,0.07)' : 'transparent',
                          borderLeft: active ? '2px solid #f59e0b' : '2px solid transparent',
                          fontWeight:  active ? 500 : 400,
                          marginLeft: -2,
                          paddingLeft: active ? 10 : 12,
                        }}
                      >
                        <Icon size={14} style={{ flexShrink: 0, opacity: active ? 1 : 0.6 }} />
                        {label}
                      </div>
                    </NavLink>
                  );
                })}
              </div>
            );
          })}
        </nav>

        {/* User row */}
        <div className="px-3 py-3" style={{ borderTop: '1px solid #1c1c28' }}>
          <div className="flex items-center gap-2.5 mb-2.5">
            <div className="flex items-center justify-center w-7 h-7 rounded-full text-[11px] font-bold shrink-0" style={{ background: 'rgba(245,158,11,0.15)', color: '#f59e0b' }}>
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[12px] font-medium truncate" style={{ color: '#d4d4e8' }}>{admin.name}</div>
              <div className="text-[11px] truncate" style={{ color: '#52526a' }}>{admin.email}</div>
            </div>
            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase" style={{ background: 'rgba(245,158,11,0.1)', color: '#f59e0b', letterSpacing: '0.06em' }}>
              {(admin.role || 'SA').slice(0, 2).toUpperCase()}
            </span>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 w-full px-2.5 py-1.5 rounded-md text-[12px] transition-colors"
            style={{ background: 'transparent', border: 'none', color: '#52526a', cursor: 'pointer' }}
            onMouseEnter={e => (e.currentTarget.style.color = '#a0a0b8')}
            onMouseLeave={e => (e.currentTarget.style.color = '#52526a')}
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
