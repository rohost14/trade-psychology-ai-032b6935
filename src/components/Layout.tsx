import { useState, useEffect, useRef } from 'react';
import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  TrendingUp,
  MessageSquare,
  Settings,
  Shield,
  X,
  Brain,
  Bell,
  BookOpen,
  MoreHorizontal,
  ChevronRight,
  ChevronDown,
  BarChart2,
  AlertTriangle,
  ShieldAlert,
  Zap,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ThemeToggle } from './ThemeToggle';
import { AlertHistorySheet } from '@/components/alerts/AlertHistorySheet';
import TokenExpiredBanner from '@/components/alerts/TokenExpiredBanner';
import { useAlerts } from '@/contexts/AlertContext';
import { useBroker } from '@/contexts/BrokerContext';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import OnboardingGate from '@/components/onboarding/OnboardingGate';
import { CommandPalette } from './CommandPalette';

// Grouped desktop nav structure
const desktopNavGroups = [
  {
    type: 'link' as const,
    name: 'Dashboard',
    href: '/dashboard',
    icon: LayoutDashboard,
  },
  {
    type: 'dropdown' as const,
    name: 'Insights',
    icon: BarChart2,
    items: [
      { name: 'Analytics',       href: '/analytics',        icon: TrendingUp },
      { name: 'Discipline',      href: '/discipline',       icon: Zap },
      { name: 'My Patterns',     href: '/personalization',  icon: Brain },
      { name: 'Risk Monitor',    href: '/my-patterns',      icon: BarChart2 },
      { name: 'Reports',         href: '/reports',          icon: BookOpen },
    ],
  },
  {
    type: 'dropdown' as const,
    name: 'Risk',
    icon: AlertTriangle,
    items: [
      { name: 'Alerts',          href: '/alerts',          icon: Bell },
      { name: 'Blowup Shield',   href: '/blowup-shield',   icon: Shield },
      { name: 'Guardrails',      href: '/guardrails',      icon: ShieldAlert },
    ],
  },
  {
    type: 'link' as const,
    name: 'Chat',
    href: '/chat',
    icon: MessageSquare,
  },
  {
    type: 'link' as const,
    name: 'Settings',
    href: '/settings',
    icon: Settings,
  },
];

// 4 primary items always visible in bottom nav
const mobilePrimaryItems = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Analytics', href: '/analytics', icon: TrendingUp },
  { name: 'Alerts',    href: '/alerts',    icon: Bell },
  { name: 'Chat',      href: '/chat',      icon: MessageSquare },
];

// Overflow items accessible via "More" sheet (grouped)
const mobileMoreGroups = [
  {
    label: 'Insights',
    items: [
      { name: 'My Patterns',  href: '/personalization', icon: Brain },
      { name: 'Discipline',   href: '/discipline',      icon: Zap },
      { name: 'Risk Monitor', href: '/my-patterns',     icon: BarChart2 },
      { name: 'Reports',      href: '/reports',         icon: BookOpen },
    ],
  },
  {
    label: 'Risk',
    items: [
      { name: 'Blowup Shield',   href: '/blowup-shield',   icon: Shield },
      { name: 'Guardrails',      href: '/guardrails',      icon: ShieldAlert },
    ],
  },
  {
    label: 'Account',
    items: [
      { name: 'Settings', href: '/settings', icon: Settings },
    ],
  },
];

// Flat list of all overflow items (for active detection)
const mobileMoreItems = mobileMoreGroups.flatMap(g => g.items);

export default function Layout() {
  const [moreOpen, setMoreOpen] = useState(false);
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [cmdOpen, setCmdOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const navigate = useNavigate();
  const { alerts, unacknowledgedCount, acknowledgeAlert, acknowledgeAll, clearAllAlerts } = useAlerts();
  const { isConnected, isTokenExpired, isGuest, connect, exitGuestMode } = useBroker();
  const { isReconnecting: isWsReconnecting } = useWebSocket();

  // Close dropdown on outside click
  useEffect(() => {
    if (!openDropdown) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpenDropdown(null);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [openDropdown]);

  // Close dropdown on route change
  useEffect(() => {
    setOpenDropdown(null);
  }, [location.pathname]);

  // Close "More" sheet on Escape
  useEffect(() => {
    if (!moreOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setMoreOpen(false); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [moreOpen]);

  // Cmd+K / Ctrl+K to open command palette
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCmdOpen(open => !open);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  // Token expiry countdown — Zerodha tokens expire at 6:00 AM IST next day
  const [tokenExpiresIn, setTokenExpiresIn] = useState<string | null>(null);

  useEffect(() => {
    if (!isConnected || isTokenExpired) {
      setTokenExpiresIn(null);
      return;
    }

    function getExpiryMs(): number {
      const now = new Date();
      // 6 AM IST = 00:30 UTC
      const expiry = new Date(now);
      expiry.setUTCHours(0, 30, 0, 0);
      if (expiry.getTime() <= now.getTime()) {
        expiry.setUTCDate(expiry.getUTCDate() + 1);
      }
      return expiry.getTime() - now.getTime();
    }

    function formatCountdown(ms: number): string {
      const totalMins = Math.floor(ms / 60000);
      const h = Math.floor(totalMins / 60);
      const m = totalMins % 60;
      if (h > 0) return `${h}h ${m}m`;
      return `${m}m`;
    }

    const tick = () => {
      const ms = getExpiryMs();
      setTokenExpiresIn(formatCountdown(ms));
    };

    tick();
    const id = setInterval(tick, 60_000);
    return () => clearInterval(id);
  }, [isConnected, isTokenExpired]);

  const handleReconnect = async () => {
    setIsReconnecting(true);
    try {
      await connect();
    } catch (error) {
      console.error('Reconnect failed:', error);
    } finally {
      setIsReconnecting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Desktop Header */}
      <header className="hidden md:block sticky top-0 z-50 bg-card border-b border-border">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex h-14 items-center justify-between">
            {/* Logo + Nav */}
            <div className="flex items-center gap-6" ref={dropdownRef}>
              <div className="flex items-center gap-2">
                <Shield className="h-5 w-5 text-tm-brand" aria-hidden="true" />
                <span className="text-base font-semibold text-foreground">TradeMentor</span>
              </div>

              {/* Desktop Nav */}
              <nav className="flex items-center gap-0.5">
                {desktopNavGroups.map((group) => {
                  if (group.type === 'link') {
                    const isActive = location.pathname === group.href;
                    return (
                      <NavLink
                        key={group.name}
                        to={group.href}
                        aria-current={isActive ? 'page' : undefined}
                        className={cn(
                          'px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
                          isActive
                            ? 'bg-tm-brand/10 text-tm-brand'
                            : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                        )}
                      >
                        {group.name}
                      </NavLink>
                    );
                  }

                  // Dropdown group
                  const isOpen = openDropdown === group.name;
                  const isGroupActive = group.items.some(i => location.pathname === i.href);
                  const showRiskBadge = group.name === 'Risk' && unacknowledgedCount > 0;

                  return (
                    <div key={group.name} className="relative">
                      <button
                        onClick={() => setOpenDropdown(isOpen ? null : group.name)}
                        aria-expanded={isOpen}
                        aria-haspopup="menu"
                        className={cn(
                          'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors relative',
                          isGroupActive || isOpen
                            ? 'bg-tm-brand/10 text-tm-brand'
                            : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                        )}
                      >
                        {group.name}
                        {showRiskBadge && (
                          <span className="w-2 h-2 rounded-full bg-red-500" aria-label={`${unacknowledgedCount} unread alerts`} />
                        )}
                        <ChevronDown className={cn(
                          'h-3.5 w-3.5 transition-transform duration-150',
                          isOpen ? 'rotate-180' : ''
                        )} />
                      </button>

                      {isOpen && (
                        <div
                          role="menu"
                          className="absolute top-full left-0 mt-1 w-48 bg-card border border-border rounded-lg shadow-lg py-1 z-50"
                        >
                          {group.items.map((item) => {
                            const isItemActive = location.pathname === item.href;
                            const showBadge = item.href === '/alerts' && unacknowledgedCount > 0;
                            return (
                              <NavLink
                                key={item.name}
                                to={item.href}
                                role="menuitem"
                                className={cn(
                                  'flex items-center gap-2.5 px-3 py-2 text-sm transition-colors relative',
                                  isItemActive
                                    ? 'text-tm-brand bg-tm-brand/5'
                                    : 'text-foreground hover:bg-muted'
                                )}
                              >
                                <item.icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                                <span className="flex-1">{item.name}</span>
                                {showBadge && (
                                  <span className="bg-red-500 text-white text-[10px] font-bold min-w-[18px] h-[18px] rounded-full flex items-center justify-center px-1 leading-none">
                                    {unacknowledgedCount > 9 ? '9+' : unacknowledgedCount}
                                  </span>
                                )}
                              </NavLink>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </nav>
            </div>

            {/* Right side */}
            <div className="flex items-center gap-2.5">
              {/* WebSocket reconnecting indicator */}
              {isWsReconnecting && (
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-500 text-xs font-medium">
                  <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                  Reconnecting…
                </div>
              )}

              {/* Broker connection status */}
              <div className={cn(
                'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
                isTokenExpired
                  ? 'bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400'
                  : isConnected
                    ? 'bg-teal-50 text-teal-700 dark:bg-teal-900/20 dark:text-teal-400'
                    : 'bg-muted text-muted-foreground'
              )}>
                <span className={cn(
                  'w-1.5 h-1.5 rounded-full',
                  isTokenExpired ? 'bg-amber-500' : isConnected ? 'bg-teal-500' : 'bg-gray-400'
                )} />
                {isTokenExpired
                  ? 'Token expired'
                  : isConnected
                    ? 'Connected'
                    : 'Offline'
                }
              </div>

              <AlertHistorySheet
                alerts={alerts}
                unacknowledgedCount={unacknowledgedCount}
                onAcknowledge={acknowledgeAlert}
                onAcknowledgeAll={acknowledgeAll}
                onClearAll={clearAllAlerts}
              />
              <ThemeToggle />
            </div>
          </div>
        </div>
      </header>

      {/* Mobile Header */}
      <header className="md:hidden sticky top-0 z-50 bg-card border-b border-border">
        <div className="flex h-14 items-center justify-between px-4">
          <div className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-tm-brand" />
            <span className="font-semibold text-foreground">TradeMentor</span>
          </div>

          <div className="flex items-center gap-2">
            {/* WS reconnect indicator — mobile */}
            {isWsReconnecting && (
              <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-500 text-[11px] font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                Reconnecting
              </span>
            )}
            <AlertHistorySheet
              alerts={alerts}
              unacknowledgedCount={unacknowledgedCount}
              onAcknowledge={acknowledgeAlert}
              onAcknowledgeAll={acknowledgeAll}
              onClearAll={clearAllAlerts}
            />
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Guest Mode Banner */}
      {isGuest && (
        <div role="status" aria-live="polite" className="bg-amber-500/10 border-b border-amber-500/20 px-4 py-2 flex items-center justify-between gap-3 text-sm">
          <span className="text-amber-700 dark:text-amber-400 font-medium">
            Demo mode — showing sample data
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={connect}
              className="text-xs font-semibold text-tm-brand underline underline-offset-2 hover:no-underline"
            >
              Connect Zerodha
            </button>
            <button
              onClick={() => { exitGuestMode(); window.location.href = '/welcome'; }}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Exit
            </button>
          </div>
        </div>
      )}

      {/* Token Expired Banner */}
      {isTokenExpired && (
        <TokenExpiredBanner
          onReconnect={handleReconnect}
          isReconnecting={isReconnecting}
        />
      )}

      {/* Onboarding wizard — shown once after first sync for real users */}
      <OnboardingGate />

      {/* Main Content */}
      <main className="pb-20 md:pb-8">
        <div className="max-w-7xl mx-auto px-4 md:px-6 py-6">
          <ErrorBoundary key={location.pathname}>
            <Outlet />
          </ErrorBoundary>
        </div>
      </main>

      {/* Mobile Bottom Nav */}
      <nav aria-label="Main navigation" className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-card border-t border-border safe-area-inset-bottom">
        <div className="flex items-center h-16 px-1">
          {/* 4 primary tabs */}
          {mobilePrimaryItems.map((item) => {
            const isActive = location.pathname === item.href;
            const showBadge = item.href === '/alerts' && unacknowledgedCount > 0;
            return (
              <NavLink
                key={item.name}
                to={item.href}
                aria-current={isActive ? 'page' : undefined}
                aria-label={showBadge ? `${item.name} (${unacknowledgedCount} unread)` : item.name}
                className={cn(
                  'flex flex-col items-center justify-center flex-1 h-full py-2 transition-colors relative',
                  isActive ? 'text-tm-brand' : 'text-muted-foreground'
                )}
              >
                {isActive && (
                  <span aria-hidden="true" className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-0.5 rounded-full bg-tm-brand" />
                )}
                <div className="relative" aria-hidden="true">
                  <item.icon className="h-5 w-5" />
                  {showBadge && (
                    <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[9px] font-bold w-3.5 h-3.5 rounded-full flex items-center justify-center leading-none">
                      {unacknowledgedCount > 9 ? '9+' : unacknowledgedCount}
                    </span>
                  )}
                </div>
                <span aria-hidden="true" className="text-[10px] mt-1 font-medium">{item.name}</span>
              </NavLink>
            );
          })}

          {/* More tab */}
          {(() => {
            const isOverflowActive = mobileMoreItems.some(i => location.pathname === i.href);
            return (
              <button
                onClick={() => setMoreOpen(true)}
                className={cn(
                  'flex flex-col items-center justify-center flex-1 h-full py-2 transition-colors relative',
                  isOverflowActive ? 'text-primary' : 'text-muted-foreground'
                )}
              >
                {isOverflowActive && (
                  <span className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-0.5 rounded-full bg-tm-brand" />
                )}
                <MoreHorizontal className="h-5 w-5" />
                <span className="text-[10px] mt-1 font-medium">More</span>
              </button>
            );
          })()}
        </div>
      </nav>

      {/* More — bottom sheet */}
      {moreOpen && (
        <>
          {/* Backdrop */}
          <div
            aria-hidden="true"
            className="md:hidden fixed inset-0 z-[60] bg-black/40 animate-fade-in"
            onClick={() => setMoreOpen(false)}
          />
          {/* Sheet */}
          <div
            role="dialog"
            aria-modal="true"
            aria-label="More navigation"
            className="md:hidden fixed bottom-0 left-0 right-0 z-[70] bg-card rounded-t-2xl border-t border-border animate-slide-in-up safe-area-inset-bottom"
          >
            {/* Handle */}
            <div className="flex justify-center pt-3 pb-1" aria-hidden="true">
              <div className="w-10 h-1 rounded-full bg-muted-foreground/30" />
            </div>
            {/* Header */}
            <div className="flex items-center justify-between px-5 pt-2 pb-3">
              <span className="text-sm font-semibold text-foreground" id="more-sheet-title">More</span>
              <button
                onClick={() => setMoreOpen(false)}
                aria-label="Close navigation menu"
                className="p-1.5 rounded-full hover:bg-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <X className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              </button>
            </div>
            {/* Grouped nav items */}
            <nav aria-labelledby="more-sheet-title" className="px-3 pb-6 space-y-4">
              {mobileMoreGroups.map((group) => (
                <div key={group.label}>
                  <p className="px-4 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                    {group.label}
                  </p>
                  <div className="space-y-0.5">
                    {group.items.map((item) => {
                      const isActive = location.pathname === item.href;
                      return (
                        <button
                          key={item.name}
                          onClick={() => { navigate(item.href); setMoreOpen(false); }}
                          aria-current={isActive ? 'page' : undefined}
                          className={cn(
                            'w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                            isActive
                              ? 'bg-tm-brand/10 text-tm-brand'
                              : 'text-foreground hover:bg-muted'
                          )}
                        >
                          <item.icon className="h-5 w-5 shrink-0" />
                          <span className="flex-1 text-left">{item.name}</span>
                          {!isActive && <ChevronRight className="h-4 w-4 text-muted-foreground/50" />}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </nav>
          </div>
        </>
      )}

      <CommandPalette open={cmdOpen} onOpenChange={setCmdOpen} />
    </div>
  );
}
