import { useState, useEffect } from 'react';
import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, TrendingUp, MessageSquare, Settings,
  Shield, Brain, Bell, BookOpen, X, Zap, ShieldAlert,
  MoreHorizontal, ChevronRight,
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
import { Sidebar } from './Sidebar';

// 4 primary tabs always visible in mobile bottom nav
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
      { name: 'My Patterns', href: '/personalization', icon: Brain },
      { name: 'Discipline',  href: '/discipline',      icon: Zap },
      { name: 'Reports',     href: '/reports',          icon: BookOpen },
    ],
  },
  {
    label: 'Risk',
    items: [
      { name: 'Blowup Shield', href: '/blowup-shield', icon: Shield },
      { name: 'Guardrails',    href: '/guardrails',    icon: ShieldAlert },
    ],
  },
  {
    label: 'Account',
    items: [
      { name: 'Settings', href: '/settings', icon: Settings },
    ],
  },
];

const mobileMoreItems = mobileMoreGroups.flatMap(g => g.items);

const SIDEBAR_COLLAPSED_KEY = 'tradementor_sidebar_collapsed';

export default function Layout() {
  const [moreOpen, setMoreOpen] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [cmdOpen, setCmdOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true';
    } catch {
      return false;
    }
  });

  const location = useLocation();
  const navigate = useNavigate();
  const { alerts, unacknowledgedCount, acknowledgeAlert, acknowledgeAll, clearAllAlerts } = useAlerts();
  const { isConnected, isTokenExpired, isGuest, connect, exitGuestMode } = useBroker();
  const { isReconnecting: isWsReconnecting } = useWebSocket();

  const toggleSidebar = () => {
    setSidebarCollapsed(prev => {
      const next = !prev;
      try { localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next)); } catch {}
      return next;
    });
  };

  // Close "More" sheet on Escape
  useEffect(() => {
    if (!moreOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setMoreOpen(false); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [moreOpen]);

  // Close "More" on route change
  useEffect(() => { setMoreOpen(false); }, [location.pathname]);

  // Cmd+K / Ctrl+K for command palette
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
      {/* ── Desktop sidebar ─────────────────────────────────────────────────── */}
      <Sidebar collapsed={sidebarCollapsed} onToggle={toggleSidebar} />

      {/* ── Content wrapper (shifts right of sidebar on desktop) ────────────── */}
      <div className={cn(
        'min-h-screen flex flex-col transition-all duration-200 ease-in-out',
        sidebarCollapsed ? 'md:pl-16' : 'md:pl-60'
      )}>

        {/* ── Mobile header ───────────────────────────────────────────────── */}
        <header className="md:hidden sticky top-0 z-50 bg-card border-b border-border">
          <div className="flex h-14 items-center justify-between px-4">
            <div className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-tm-brand" aria-hidden="true" />
              <span className="font-semibold text-foreground">TradeMentor</span>
            </div>
            <div className="flex items-center gap-1.5">
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

        {/* ── Desktop WS reconnecting banner ──────────────────────────────── */}
        {isWsReconnecting && (
          <div className="hidden md:flex items-center gap-2 px-5 py-2 bg-amber-500/10 border-b border-amber-500/20 text-amber-600 dark:text-amber-400 text-xs font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse shrink-0" />
            WebSocket disconnected — attempting to reconnect…
          </div>
        )}

        {/* ── Guest mode banner ───────────────────────────────────────────── */}
        {isGuest && (
          <div
            role="status"
            aria-live="polite"
            className="bg-amber-500/10 border-b border-amber-500/20 px-4 py-2 flex items-center justify-between gap-3 text-sm"
          >
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

        {/* ── Token expired banner ────────────────────────────────────────── */}
        {isTokenExpired && (
          <TokenExpiredBanner
            onReconnect={handleReconnect}
            isReconnecting={isReconnecting}
          />
        )}

        {/* ── Onboarding wizard ───────────────────────────────────────────── */}
        <OnboardingGate />

        {/* ── Main content ────────────────────────────────────────────────── */}
        <main className="flex-1 pb-20 md:pb-8">
          <div className="w-full px-4 md:px-6 py-6">
            <ErrorBoundary key={location.pathname}>
              <Outlet />
            </ErrorBoundary>
          </div>
        </main>

        {/* ── Mobile bottom nav ───────────────────────────────────────────── */}
        <nav
          aria-label="Main navigation"
          className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-card border-t border-border safe-area-inset-bottom"
        >
          <div className="flex items-center h-14 px-1">
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
                    <span
                      aria-hidden="true"
                      className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-0.5 rounded-full bg-tm-brand"
                    />
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
                    isOverflowActive ? 'text-tm-brand' : 'text-muted-foreground'
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

        {/* ── More bottom sheet ────────────────────────────────────────────── */}
        {moreOpen && (
          <>
            <div
              aria-hidden="true"
              className="md:hidden fixed inset-0 z-[60] bg-black/40 animate-fade-in"
              onClick={() => setMoreOpen(false)}
            />
            <div
              role="dialog"
              aria-modal="true"
              aria-label="More navigation"
              className="md:hidden fixed bottom-0 left-0 right-0 z-[70] bg-card rounded-t-2xl border-t border-border animate-slide-in-up safe-area-inset-bottom"
            >
              <div className="flex justify-center pt-3 pb-1" aria-hidden="true">
                <div className="w-10 h-1 rounded-full bg-muted-foreground/30" />
              </div>
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
              <nav aria-labelledby="more-sheet-title" className="px-3 pb-6 space-y-4">
                {mobileMoreGroups.map((group) => (
                  <div key={group.label}>
                    <p className="t-overline text-muted-foreground/60 px-4 pb-1">
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
                              'w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-colors',
                              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
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
      </div>

      <CommandPalette open={cmdOpen} onOpenChange={setCmdOpen} />
    </div>
  );
}
