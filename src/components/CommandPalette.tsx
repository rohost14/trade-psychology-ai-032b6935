// Command Palette — Cmd/Ctrl+K to open
// Navigation + quick actions for power users

import { useNavigate } from 'react-router-dom';
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from '@/components/ui/command';
import {
  LayoutDashboard, TrendingUp, Bell, Shield, Brain,
  BookOpen, MessageSquare, Settings, CheckCheck, Scale,
} from 'lucide-react';
import { useAlerts } from '@/contexts/AlertContext';

const NAV_COMMANDS = [
  { name: 'Dashboard',        href: '/dashboard',       icon: LayoutDashboard },
  { name: 'Analytics',        href: '/analytics',       icon: TrendingUp },
  { name: 'Alerts',           href: '/alerts',          icon: Bell },
  { name: 'My Rules',         href: '/my-rules',        icon: Scale },
  { name: 'Blowup Shield',    href: '/blowup-shield',   icon: Shield },
  { name: 'Reports',          href: '/reports',         icon: BookOpen },
  { name: 'Chat',             href: '/chat',            icon: MessageSquare },
  { name: 'Settings',         href: '/settings',        icon: Settings },
];

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const navigate = useNavigate();
  const { acknowledgeAll, unacknowledgedCount } = useAlerts();

  function run(fn: () => void) {
    onOpenChange(false);
    fn();
  }

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Go to page, run action…" />
      <CommandList>
        {/* "No results." is a dead end — it reports a fact and leaves the user to
            guess what this box can even do. Naming the two things it searches
            turns the empty state into the answer. */}
        <CommandEmpty>
          <div className="py-5 px-4 text-center">
            <p className="text-[13px] font-medium text-foreground">Nothing matches that</p>
            <p className="text-[12px] text-muted-foreground mt-1">
              Try a page name — Dashboard, Analytics, Alerts, Journal — or an action
              like &ldquo;sync&rdquo; or &ldquo;acknowledge&rdquo;.
            </p>
          </div>
        </CommandEmpty>

        <CommandGroup heading="Navigate">
          {NAV_COMMANDS.map(cmd => (
            <CommandItem
              key={cmd.href}
              value={cmd.name}
              onSelect={() => run(() => navigate(cmd.href))}
            >
              <cmd.icon className="mr-2 h-4 w-4 text-muted-foreground" />
              {cmd.name}
            </CommandItem>
          ))}
        </CommandGroup>

        {unacknowledgedCount > 0 && (
          <>
            <CommandSeparator />
            <CommandGroup heading="Actions">
              <CommandItem
                value="acknowledge all alerts"
                onSelect={() => run(acknowledgeAll)}
              >
                <CheckCheck className="mr-2 h-4 w-4 text-muted-foreground" />
                Acknowledge all alerts
                <span className="ml-auto text-xs text-muted-foreground">{unacknowledgedCount}</span>
              </CommandItem>
            </CommandGroup>
          </>
        )}
      </CommandList>
    </CommandDialog>
  );
}
