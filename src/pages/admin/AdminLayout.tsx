import { useEffect } from 'react';
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Users, Activity, BarChart3, Settings,
  Shield, LogOut, ScrollText, Megaphone
} from 'lucide-react';
import { useAdminAuth } from '@/contexts/AdminAuthContext';
import { adminApi } from '@/lib/adminApi';

const NAV = [
  { to: '/admin/overview',   icon: LayoutDashboard, label: 'Overview'      },
  { to: '/admin/users',      icon: Users,           label: 'Users'         },
  { to: '/admin/system',     icon: Activity,        label: 'System Health' },
  { to: '/admin/insights',   icon: BarChart3,       label: 'Insights'      },
  { to: '/admin/broadcast',  icon: Megaphone,       label: 'Broadcast'     },
  { to: '/admin/audit-log',  icon: ScrollText,      label: 'Audit Log'     },
  { to: '/admin/config',     icon: Settings,        label: 'Config'        },
];

const C = {
  bg:      '#04040e',
  surface: 'rgba(255,255,255,0.03)',
  border:  'rgba(255,255,255,0.07)',
  amber:   '#f59e0b',
  text:    '#e2e8f0',
  muted:   'rgba(226,232,240,0.45)',
  dm:      "'DM Sans', sans-serif",
};

export default function AdminLayout() {
  const { admin, isLoading, logout } = useAdminAuth();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (!isLoading && !admin) navigate('/admin/login', { replace: true });
  }, [admin, isLoading, navigate]);

  const handleLogout = async () => {
    try { await adminApi.logout(); } catch {}
    logout();
    navigate('/admin/login', { replace: true });
  };

  if (isLoading) {
    return (
      <div style={{ minHeight: '100vh', background: C.bg, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ width: 32, height: 32, border: `2px solid ${C.amber}`, borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (!admin) return null;

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: C.bg, fontFamily: C.dm }}>
      {/* Sidebar */}
      <aside style={{
        width: 220, flexShrink: 0,
        background: 'rgba(255,255,255,0.02)',
        borderRight: `1px solid ${C.border}`,
        display: 'flex', flexDirection: 'column',
        position: 'sticky', top: 0, height: '100vh',
      }}>
        {/* Logo */}
        <div style={{ padding: '1.5rem 1.25rem', borderBottom: `1px solid ${C.border}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 9,
              background: 'rgba(245,158,11,0.12)',
              border: `1px solid rgba(245,158,11,0.3)`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Shield style={{ width: 16, height: 16, color: C.amber }} />
            </div>
            <div>
              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: C.text, lineHeight: 1.2 }}>TradeMentor</div>
              <div style={{ fontSize: '0.65rem', color: C.amber, fontWeight: 600, letterSpacing: '0.08em' }}>ADMIN</div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '1rem 0.75rem', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {NAV.map(({ to, icon: Icon, label }) => {
            const active = location.pathname === to || (to !== '/admin/overview' && location.pathname.startsWith(to));
            return (
              <NavLink key={to} to={to} style={{ textDecoration: 'none' }}>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '0.55rem 0.75rem', borderRadius: 9,
                  background: active ? 'rgba(245,158,11,0.1)' : 'transparent',
                  border: active ? '1px solid rgba(245,158,11,0.2)' : '1px solid transparent',
                  color: active ? C.amber : C.muted,
                  fontSize: '0.825rem', fontWeight: active ? 600 : 400,
                  transition: 'all 0.15s',
                  cursor: 'pointer',
                }}>
                  <Icon style={{ width: 15, height: 15, flexShrink: 0 }} />
                  {label}
                </div>
              </NavLink>
            );
          })}
        </nav>

        {/* User + Logout */}
        <div style={{ padding: '1rem 0.75rem', borderTop: `1px solid ${C.border}` }}>
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: '0.78rem', fontWeight: 600, color: C.text, marginBottom: 2 }}>{admin.name}</div>
            <div style={{ fontSize: '0.7rem', color: C.muted }}>{admin.email}</div>
          </div>
          <button
            onClick={handleLogout}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              width: '100%', padding: '0.5rem 0.75rem', borderRadius: 8,
              background: 'none', border: '1px solid rgba(255,255,255,0.06)',
              color: 'rgba(226,232,240,0.4)', fontSize: '0.78rem',
              cursor: 'pointer', fontFamily: C.dm,
              transition: 'all 0.15s',
            }}
          >
            <LogOut style={{ width: 13, height: 13 }} />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main style={{ flex: 1, overflow: 'auto', minWidth: 0 }}>
        <Outlet />
      </main>
    </div>
  );
}
