import { useState } from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  TrendingUp,
  MessageSquare,
  Settings,
  Shield,
  Menu,
  CircleDot,
  Power,
  PiggyBank,
  Target,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { ThemeToggle } from './ThemeToggle';
import { AlertHistorySheet } from '@/components/alerts/AlertHistorySheet';
import { useAlerts } from '@/contexts/AlertContext';

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Analytics', href: '/analytics', icon: TrendingUp },
  { name: 'Money Saved', href: '/money-saved', icon: PiggyBank },
  { name: 'Goals', href: '/goals', icon: Target },
  { name: 'AI Chat', href: '/chat', icon: MessageSquare },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export default function Layout() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const location = useLocation();
  const { alerts, unacknowledgedCount, acknowledgeAlert, acknowledgeAll, clearAllAlerts } = useAlerts();

  // Full nav items for mobile
  const MobileNavItems = ({ onItemClick }: { onItemClick?: () => void }) => (
    <nav className="space-y-2">
      {navigation.map((item) => {
        const isActive = location.pathname === item.href;
        return (
          <NavLink
            key={item.name}
            to={item.href}
            onClick={onItemClick}
            className={cn(
              'flex items-center gap-3 px-4 py-3 rounded-xl text-base font-medium transition-all duration-200',
              isActive
                ? 'bg-primary text-primary-foreground shadow-md'
                : 'text-muted-foreground hover:bg-accent hover:text-foreground hover-lift'
            )}
          >
            <item.icon className="h-5 w-5 flex-shrink-0" />
            <span>{item.name}</span>
          </NavLink>
        );
      })}
    </nav>
  );

  // Icon-only nav for desktop slim sidebar
  const DesktopNavItems = () => (
    <nav className="space-y-2">
      {navigation.map((item) => {
        const isActive = location.pathname === item.href;
        return (
          <Tooltip key={item.name} delayDuration={0}>
            <TooltipTrigger asChild>
              <NavLink
                to={item.href}
                className={cn(
                  'flex items-center justify-center w-11 h-11 rounded-xl transition-all duration-200',
                  isActive
                    ? 'bg-primary text-primary-foreground shadow-md'
                    : 'text-muted-foreground hover:bg-accent hover:text-foreground hover-lift'
                )}
              >
                <item.icon className="h-5 w-5" />
              </NavLink>
            </TooltipTrigger>
            <TooltipContent side="right" className="font-medium text-sm">
              {item.name}
            </TooltipContent>
          </Tooltip>
        );
      })}
    </nav>
  );

  return (
    <div className="min-h-screen bg-background">
      {/* Sticky Top Bar */}
      <header className="sticky top-0 z-50 h-16 border-b border-border bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80">
        <div className="flex h-full items-center justify-between px-4 lg:px-6">
          {/* Left: Logo + Mobile Menu */}
          <div className="flex items-center gap-3">
            {/* Mobile Menu Button */}
            <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
              <SheetTrigger asChild className="lg:hidden">
                <Button variant="ghost" size="icon" className="lg:hidden h-10 w-10 hover-scale">
                  <Menu className="h-5 w-5" />
                  <span className="sr-only">Open menu</span>
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-80 p-0">
                <div className="flex h-16 items-center gap-3 border-b border-border px-6">
                  <div className="p-2 rounded-lg bg-primary/10">
                    <Shield className="h-6 w-6 text-primary" />
                  </div>
                  <span className="text-lg font-bold text-foreground">TradeMentor AI</span>
                </div>
                <div className="p-4">
                  <MobileNavItems onItemClick={() => setMobileMenuOpen(false)} />
                </div>
              </SheetContent>
            </Sheet>

            {/* Logo */}
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10">
                <Shield className="h-5 w-5 text-primary" />
              </div>
              <span className="text-base font-bold text-foreground hidden sm:block">
                TradeMentor AI
              </span>
            </div>
          </div>

          {/* Right: Status + Actions */}
          <div className="flex items-center gap-2">
            {/* Connection Status */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-success/10 border border-success/20">
              <CircleDot className="h-3 w-3 text-success animate-pulse" />
              <span className="text-xs font-medium text-success hidden sm:block">Live</span>
            </div>

            {/* Alert Bell */}
            <AlertHistorySheet
              alerts={alerts}
              unacknowledgedCount={unacknowledgedCount}
              onAcknowledge={acknowledgeAlert}
              onAcknowledgeAll={acknowledgeAll}
              onClearAll={clearAllAlerts}
            />

            {/* Theme Toggle */}
            <ThemeToggle />

            {/* Disconnect Button */}
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground hover:text-destructive h-9 w-9 p-0 hover-scale"
                >
                  <Power className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Disconnect</TooltipContent>
            </Tooltip>
          </div>
        </div>
      </header>

      {/* Main Layout */}
      <div className="flex">
        {/* Sticky Slim Sidebar (Desktop) */}
        <aside className="hidden lg:flex flex-col items-center w-[72px] border-r border-border bg-card min-h-[calc(100vh-4rem)] sticky top-16 py-4">
          <DesktopNavItems />
        </aside>

        {/* Main Content - generous padding */}
        <main className="flex-1 min-w-0">
          <div className="p-5 lg:p-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
