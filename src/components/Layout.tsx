import { useState } from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  TrendingUp,
  MessageSquare,
  Settings,
  Shield,
  Menu,
  X,
  Brain,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ThemeToggle } from './ThemeToggle';
import { AlertHistorySheet } from '@/components/alerts/AlertHistorySheet';
import TokenExpiredBanner from '@/components/alerts/TokenExpiredBanner';
import { useAlerts } from '@/contexts/AlertContext';
import { useBroker } from '@/contexts/BrokerContext';

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Analytics', href: '/analytics', icon: TrendingUp },
  { name: 'Shield', href: '/blowup-shield', icon: Shield },
  { name: 'My Patterns', href: '/my-patterns', icon: Brain },
  { name: 'Chat', href: '/chat', icon: MessageSquare },
  { name: 'Settings', href: '/settings', icon: Settings },
];

// Mobile bottom nav items (limited to 5)
const mobileNavItems = navigation.slice(0, 5);

export default function Layout() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const location = useLocation();
  const { alerts, unacknowledgedCount, acknowledgeAlert, acknowledgeAll, clearAllAlerts } = useAlerts();
  const { isConnected, isTokenExpired, connect } = useBroker();

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
          <div className="flex h-16 items-center justify-between">
            {/* Logo */}
            <div className="flex items-center gap-8">
              <div className="flex items-center gap-2">
                <Shield className="h-6 w-6 text-primary" />
                <span className="text-lg font-semibold text-foreground">TradeMentor</span>
              </div>

              {/* Desktop Nav */}
              <nav className="flex items-center gap-1">
                {navigation.map((item) => {
                  const isActive = location.pathname === item.href;
                  return (
                    <NavLink
                      key={item.name}
                      to={item.href}
                      className={cn(
                        'px-3 py-2 rounded-md text-sm font-medium transition-colors',
                        isActive
                          ? 'bg-primary/10 text-primary'
                          : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                      )}
                    >
                      {item.name}
                    </NavLink>
                  );
                })}
              </nav>
            </div>

            {/* Right side */}
            <div className="flex items-center gap-3">
              {/* Connection status */}
              <div className={cn(
                'flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium',
                isTokenExpired
                  ? 'bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400'
                  : isConnected
                    ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400'
                    : 'bg-muted text-muted-foreground'
              )}>
                <span className={cn(
                  'w-2 h-2 rounded-full',
                  isTokenExpired ? 'bg-amber-500' : isConnected ? 'bg-green-500' : 'bg-gray-400'
                )} />
                {isTokenExpired ? 'Expired' : isConnected ? 'Connected' : 'Offline'}
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
            <Shield className="h-5 w-5 text-primary" />
            <span className="font-semibold text-foreground">TradeMentor</span>
          </div>

          <div className="flex items-center gap-2">
            <AlertHistorySheet
              alerts={alerts}
              unacknowledgedCount={unacknowledgedCount}
              onAcknowledge={acknowledgeAlert}
              onAcknowledgeAll={acknowledgeAll}
              onClearAll={clearAllAlerts}
            />
            <ThemeToggle />
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </Button>
          </div>
        </div>

        {/* Mobile menu dropdown */}
        {mobileMenuOpen && (
          <div className="border-t border-border bg-card px-4 py-3">
            <nav className="space-y-1">
              {navigation.map((item) => {
                const isActive = location.pathname === item.href;
                return (
                  <NavLink
                    key={item.name}
                    to={item.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium',
                      isActive
                        ? 'bg-primary/10 text-primary'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    <item.icon className="h-5 w-5" />
                    {item.name}
                  </NavLink>
                );
              })}
            </nav>
          </div>
        )}
      </header>

      {/* Token Expired Banner */}
      {isTokenExpired && (
        <TokenExpiredBanner
          onReconnect={handleReconnect}
          isReconnecting={isReconnecting}
        />
      )}

      {/* Main Content */}
      <main className="pb-20 md:pb-8">
        <div className="max-w-7xl mx-auto px-4 md:px-6 py-6">
          <Outlet />
        </div>
      </main>

      {/* Mobile Bottom Nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-card border-t border-border">
        <div className="flex items-center justify-around h-16 px-2">
          {mobileNavItems.map((item) => {
            const isActive = location.pathname === item.href;
            return (
              <NavLink
                key={item.name}
                to={item.href}
                className={cn(
                  'flex flex-col items-center justify-center flex-1 h-full py-2 transition-colors',
                  isActive
                    ? 'text-primary'
                    : 'text-muted-foreground'
                )}
              >
                <item.icon className={cn('h-5 w-5', isActive && 'text-primary')} />
                <span className="text-xs mt-1 font-medium">{item.name}</span>
              </NavLink>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
