import { useState, useRef, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import {
  Bell, Settings, ChevronDown, User, RefreshCw,
  Shield, Target, Radar, FileText, AlertTriangle,
  TrendingUp, Brain, BookOpen, MessageSquare, ShieldAlert,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAlerts } from '@/contexts/AlertContext';
import { useBroker } from '@/contexts/BrokerContext';

// ── Nav structure — mirrors original Layout grouped dropdowns ─────────────────

const NAV = [
  {
    type: 'link' as const,
    label: 'Dashboard',
    href: '/dashboard-v2',
  },
  {
    type: 'dropdown' as const,
    label: 'Insights',
    items: [
      { label: 'Analytics',   href: '/analytics',   icon: TrendingUp },
      { label: 'My Patterns', href: '/my-patterns',  icon: Brain },
      { label: 'Reports',     href: '/reports',      icon: FileText },
    ],
  },
  {
    type: 'dropdown' as const,
    label: 'Risk',
    badge: true, // shows unread count
    items: [
      { label: 'Alerts',          href: '/alerts',          icon: Bell },
      { label: 'Blowup Shield',   href: '/blowup-shield',   icon: Shield },
      { label: 'Session Limits',  href: '/guardrails',      icon: ShieldAlert },
      { label: 'Portfolio Radar', href: '/portfolio-radar', icon: Radar },
    ],
  },
  {
    type: 'link' as const,
    label: 'Coach',
    href: '/chat',
  },
  {
    type: 'link' as const,
    label: 'Goals',
    href: '/goals',
  },
];

interface TopNavbarProps {
  tradeCount: number;
  goalProgress?: { current: number; target: number } | null;
  onSync: () => void;
  isSyncing: boolean;
  activeHref?: string;
}

export default function TopNavbar({
  tradeCount,
  goalProgress,
  onSync,
  isSyncing,
  activeHref = '/dashboard-v2',
}: TopNavbarProps) {
  const { unacknowledgedCount } = useAlerts();
  const { account } = useBroker();
  const navigate = useNavigate();
  const location = useLocation();

  const [openDropdown, setOpenDropdown] = useState<string | null>(null);
  const [avatarOpen, setAvatarOpen] = useState(false);
  const navRef = useRef<HTMLDivElement>(null);
  const avatarRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (navRef.current && !navRef.current.contains(e.target as Node)) setOpenDropdown(null);
      if (avatarRef.current && !avatarRef.current.contains(e.target as Node)) setAvatarOpen(false);
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Close dropdown on navigation
  useEffect(() => { setOpenDropdown(null); }, [location.pathname]);

  const initials = account?.broker_name?.slice(0, 2).toUpperCase() || 'TM';

  function isGroupActive(items: { href: string }[]): boolean {
    return items.some(i => location.pathname === i.href);
  }

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 h-[60px] bg-[#0F172A] border-b border-slate-800 flex items-center px-6">

      {/* Logo */}
      <Link to="/dashboard-v2" className="flex items-center gap-2.5 mr-8 shrink-0">
        <div className="w-7 h-7 rounded-md bg-[#0F8E7D] flex items-center justify-center">
          <span className="text-white text-xs font-bold">TM</span>
        </div>
        <span className="text-white font-semibold text-sm tracking-tight">TradeMentor</span>
      </Link>

      {/* Primary nav */}
      <div className="flex items-center gap-0.5 flex-1" ref={navRef}>
        {NAV.map((item) => {

          // ── Simple link ──────────────────────────────────────────────────
          if (item.type === 'link') {
            const isActive = location.pathname === item.href || activeHref === item.href;
            return (
              <Link
                key={item.href}
                to={item.href}
                className={cn(
                  'relative px-3 py-1.5 rounded-md text-sm font-medium transition-colors duration-100',
                  isActive
                    ? 'text-teal-300 bg-teal-900/20'
                    : 'text-slate-300 hover:text-white hover:bg-slate-800'
                )}
              >
                {item.label}
                {isActive && (
                  <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-4 h-0.5 bg-teal-400 rounded-full" />
                )}
              </Link>
            );
          }

          // ── Dropdown ─────────────────────────────────────────────────────
          const isOpen    = openDropdown === item.label;
          const isActive  = isGroupActive(item.items);
          const showBadge = item.badge && unacknowledgedCount > 0;

          return (
            <div key={item.label} className="relative">
              <button
                onClick={() => setOpenDropdown(isOpen ? null : item.label)}
                className={cn(
                  'relative flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors duration-100',
                  isActive || isOpen
                    ? 'text-teal-300 bg-teal-900/20'
                    : 'text-slate-300 hover:text-white hover:bg-slate-800'
                )}
              >
                {item.label}
                {showBadge && (
                  <span className="flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full bg-amber-500 text-white text-[10px] font-bold leading-none">
                    {unacknowledgedCount > 9 ? '9+' : unacknowledgedCount}
                  </span>
                )}
                <ChevronDown className={cn(
                  'w-3.5 h-3.5 transition-transform duration-150',
                  isOpen && 'rotate-180'
                )} />
              </button>

              {isOpen && (
                <div className="absolute top-full left-0 mt-1.5 w-52 bg-white border border-slate-200 rounded-xl shadow-lg py-1.5 z-50">
                  {item.items.map((sub) => {
                    const isSubActive = location.pathname === sub.href;
                    const showSubBadge = sub.href === '/alerts' && unacknowledgedCount > 0;
                    return (
                      <Link
                        key={sub.href}
                        to={sub.href}
                        onClick={() => setOpenDropdown(null)}
                        className={cn(
                          'flex items-center gap-3 px-4 py-2.5 text-sm transition-colors',
                          isSubActive
                            ? 'text-[#0F8E7D] bg-teal-50'
                            : 'text-slate-700 hover:bg-slate-50 hover:text-slate-900'
                        )}
                      >
                        <sub.icon className={cn(
                          'w-4 h-4 shrink-0',
                          isSubActive ? 'text-[#0F8E7D]' : 'text-slate-400'
                        )} />
                        <span className="flex-1 font-medium">{sub.label}</span>
                        {showSubBadge && (
                          <span className="bg-amber-500 text-white text-[10px] font-bold min-w-[18px] h-[18px] rounded-full flex items-center justify-center px-1 leading-none">
                            {unacknowledgedCount > 9 ? '9+' : unacknowledgedCount}
                          </span>
                        )}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Compact stat */}
      {(tradeCount > 0 || goalProgress) && (
        <div className="flex items-center gap-1.5 text-sm text-slate-400 mr-5 shrink-0 font-mono tabular-nums">
          <span>{tradeCount} trades</span>
          {goalProgress && (
            <>
              <span className="text-slate-700">·</span>
              <span className="text-teal-400">Goal {goalProgress.current}/{goalProgress.target}</span>
            </>
          )}
        </div>
      )}

      {/* Right actions */}
      <div className="flex items-center gap-1.5 shrink-0">

        {/* Sync */}
        <button
          onClick={onSync}
          disabled={isSyncing}
          title="Sync trades"
          className="w-8 h-8 flex items-center justify-center rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition-colors disabled:opacity-40"
        >
          <RefreshCw className={cn('w-4 h-4', isSyncing && 'animate-spin')} />
        </button>

        {/* Bell */}
        <button className="relative w-8 h-8 flex items-center justify-center rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition-colors">
          <Bell className="w-4 h-4" />
          {unacknowledgedCount > 0 && (
            <span className="absolute top-1 right-1 w-2 h-2 bg-amber-500 rounded-full" />
          )}
        </button>

        {/* Settings */}
        <Link
          to="/settings"
          className="w-8 h-8 flex items-center justify-center rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
        >
          <Settings className="w-4 h-4" />
        </Link>

        {/* Avatar */}
        <div ref={avatarRef} className="relative ml-1">
          <button
            onClick={() => setAvatarOpen(o => !o)}
            className="w-8 h-8 rounded-full bg-[#0F8E7D] flex items-center justify-center text-white text-xs font-bold hover:opacity-90 transition-opacity"
          >
            {initials}
          </button>

          {avatarOpen && (
            <div className="absolute top-full right-0 mt-1.5 w-48 bg-white border border-slate-200 rounded-xl shadow-lg py-1 z-50">
              <div className="px-4 py-2.5 border-b border-slate-100">
                <p className="text-[11px] text-slate-400 font-medium uppercase tracking-wide">Signed in as</p>
                <p className="text-sm font-semibold text-slate-900 truncate mt-0.5">
                  {account?.broker_name || 'Trader'}
                </p>
              </div>
              <Link
                to="/settings"
                onClick={() => setAvatarOpen(false)}
                className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
              >
                <User className="w-4 h-4 text-slate-400" />
                Profile & Settings
              </Link>
              <button
                onClick={() => { setAvatarOpen(false); navigate('/welcome'); }}
                className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-[#B13D44] hover:bg-red-50 transition-colors"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}
