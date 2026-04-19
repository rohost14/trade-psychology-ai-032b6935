import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, TrendingUp, MessageSquare, Settings,
  Shield, Brain, Bell, BookOpen, Zap, ShieldAlert,
  ChevronLeft, ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAlerts } from '@/contexts/AlertContext';
import { useBroker } from '@/contexts/BrokerContext';
import { ThemeToggle } from './ThemeToggle';
import { AlertHistorySheet } from '@/components/alerts/AlertHistorySheet';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

const sections = [
  {
    group: null,
    items: [
      { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, hasBadge: false },
      { name: 'Analytics', href: '/analytics', icon: TrendingUp, hasBadge: false },
    ],
  },
  {
    group: 'Insights',
    items: [
      { name: 'My Patterns', href: '/personalization', icon: Brain, hasBadge: false },
      { name: 'Discipline',  href: '/discipline',      icon: Zap,  hasBadge: false },
      { name: 'Reports',     href: '/reports',          icon: BookOpen, hasBadge: false },
    ],
  },
  {
    group: 'Risk',
    items: [
      { name: 'Alerts',        href: '/alerts',        icon: Bell,       hasBadge: true },
      { name: 'Blowup Shield', href: '/blowup-shield', icon: Shield,     hasBadge: false },
      { name: 'Guardrails',    href: '/guardrails',    icon: ShieldAlert, hasBadge: false },
    ],
  },
];

const bottomItems = [
  { name: 'Chat',     href: '/chat',     icon: MessageSquare },
  { name: 'Settings', href: '/settings', icon: Settings },
];

function NavItem({
  name, href, icon: Icon, hasBadge = false, collapsed, unreadCount,
}: {
  name: string; href: string; icon: React.ElementType;
  hasBadge?: boolean; collapsed: boolean; unreadCount: number;
}) {
  const location = useLocation();
  const isActive = location.pathname === href;
  const showBadge = hasBadge && unreadCount > 0;

  return (
    <NavLink
      to={href}
      title={collapsed ? name : undefined}
      aria-current={isActive ? 'page' : undefined}
      className={cn(
        'relative flex items-center rounded-lg transition-colors duration-100 select-none',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-tm-brand/60 focus-visible:ring-offset-1',
        collapsed
          ? 'h-9 w-9 mx-auto justify-center'
          : 'h-9 px-3 gap-2.5',
        isActive
          ? 'bg-tm-brand/10 text-tm-brand'
          : [
              'text-muted-foreground',
              'hover:bg-black/[0.04] dark:hover:bg-white/[0.05]',
              'hover:text-foreground',
            ]
      )}
    >
      {/* Active left accent bar */}
      {isActive && !collapsed && (
        <span
          aria-hidden="true"
          className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-tm-brand"
        />
      )}

      <Icon className={cn('h-4 w-4 shrink-0', isActive ? 'text-tm-brand' : '')} />

      {!collapsed && (
        <span className={cn('flex-1 text-sm truncate', isActive ? 'font-semibold' : 'font-normal')}>
          {name}
        </span>
      )}

      {/* Badge — expanded: pill; collapsed: dot */}
      {showBadge && !collapsed && (
        <span className="ml-auto bg-red-500 text-white text-[10px] font-bold min-w-[18px] h-[18px] rounded-full flex items-center justify-center px-1 leading-none animate-badge-pulse">
          {unreadCount > 9 ? '9+' : unreadCount}
        </span>
      )}
      {showBadge && collapsed && (
        <span
          aria-label={`${unreadCount} unread alerts`}
          className="absolute top-0.5 right-0.5 w-2 h-2 rounded-full bg-red-500"
        />
      )}
    </NavLink>
  );
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { unacknowledgedCount, alerts, acknowledgeAlert, acknowledgeAll, clearAllAlerts } = useAlerts();
  const { isConnected, isTokenExpired, account } = useBroker();

  const borderClass = 'border-black/[0.07] dark:border-white/[0.06]';

  return (
    <aside
      className={cn(
        'hidden md:flex flex-col fixed top-0 left-0 h-screen z-40',
        'bg-tm-sidebar border-r transition-all duration-200 ease-in-out',
        borderClass,
        collapsed ? 'w-16' : 'w-60'
      )}
    >
      {/* ── Logo ───────────────────────────────────────────────────────────── */}
      <div className={cn(
        'flex items-center h-14 shrink-0 border-b', borderClass,
        collapsed ? 'justify-center' : 'px-4 gap-2.5'
      )}>
        <Shield className="h-5 w-5 shrink-0 text-tm-brand" aria-hidden="true" />
        {!collapsed && (
          <span className="text-[15px] font-semibold text-foreground truncate">TradeMentor</span>
        )}
      </div>

      {/* ── Main nav ───────────────────────────────────────────────────────── */}
      <nav
        aria-label="Main navigation"
        className="flex-1 overflow-y-auto overflow-x-hidden py-3 px-2 space-y-4"
      >
        {sections.map((section, si) => (
          <div key={si}>
            {section.group && !collapsed && (
              <p className="t-overline text-tm-tertiary px-3 pb-1.5 pt-0.5">
                {section.group}
              </p>
            )}
            {section.group && collapsed && <div className="h-px mx-2 bg-border my-1.5" />}
            <div className="space-y-0.5">
              {section.items.map((item) => (
                <NavItem
                  key={item.href}
                  {...item}
                  collapsed={collapsed}
                  unreadCount={unacknowledgedCount}
                />
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* ── Bottom section ─────────────────────────────────────────────────── */}
      <div className={cn('shrink-0 border-t py-2 px-2 space-y-0.5', borderClass)}>
        {bottomItems.map((item) => (
          <NavItem
            key={item.href}
            {...item}
            collapsed={collapsed}
            unreadCount={0}
          />
        ))}

        {/* Utility buttons row */}
        <div className={cn(
          'flex mt-1',
          collapsed ? 'flex-col items-center gap-1' : 'items-center gap-1 px-1'
        )}>
          <AlertHistorySheet
            alerts={alerts}
            unacknowledgedCount={unacknowledgedCount}
            onAcknowledge={acknowledgeAlert}
            onAcknowledgeAll={acknowledgeAll}
            onClearAll={clearAllAlerts}
          />
          <ThemeToggle />
        </div>

        {/* Connection status */}
        {!collapsed ? (
          <div className={cn(
            'mt-1.5 mx-1 px-2.5 py-2 rounded-lg',
            isTokenExpired
              ? 'bg-amber-500/10'
              : isConnected
                ? 'bg-tm-brand/[0.07]'
                : 'bg-muted'
          )}>
            <div className="flex items-center gap-2 min-w-0">
              <span className={cn(
                'w-1.5 h-1.5 rounded-full shrink-0',
                isTokenExpired ? 'bg-amber-500 animate-pulse'
                  : isConnected ? 'bg-tm-brand'
                    : 'bg-muted-foreground'
              )} />
              <span className={cn(
                'text-xs font-medium truncate',
                isTokenExpired ? 'text-amber-600 dark:text-amber-400'
                  : isConnected ? 'text-tm-brand'
                    : 'text-muted-foreground'
              )}>
                {isTokenExpired
                  ? 'Token expired'
                  : isConnected
                    ? (account?.display_name || account?.broker_user_id || 'Connected')
                    : 'Not connected'
                }
              </span>
            </div>
          </div>
        ) : (
          <div className="flex justify-center mt-1 pb-1">
            <span
              className={cn(
                'w-2 h-2 rounded-full',
                isTokenExpired ? 'bg-amber-500 animate-pulse'
                  : isConnected ? 'bg-tm-brand'
                    : 'bg-muted-foreground/40'
              )}
              title={isTokenExpired ? 'Token expired' : isConnected ? 'Connected' : 'Not connected'}
            />
          </div>
        )}
      </div>

      {/* ── Collapse toggle ─────────────────────────────────────────────────── */}
      <button
        onClick={onToggle}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        className={cn(
          'absolute -right-3 top-[68px] z-50',
          'w-6 h-6 rounded-full bg-card border border-border shadow-sm',
          'flex items-center justify-center',
          'text-muted-foreground hover:text-foreground hover:bg-muted',
          'transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
        )}
      >
        {collapsed
          ? <ChevronRight className="h-3 w-3" />
          : <ChevronLeft className="h-3 w-3" />
        }
      </button>
    </aside>
  );
}
