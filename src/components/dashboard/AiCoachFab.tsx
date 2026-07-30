/**
 * AiCoachFab — floating action button for AI coach.
 *
 * Fixed: bottom-[72px] mobile (clears 56px bottom nav + 16px gap), bottom-6 desktop.
 * Pulses when the user has unread danger alerts (coach is relevant right now).
 */

import { Link } from 'react-router-dom';
import { Bot } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useBroker } from '@/contexts/BrokerContext';
import { useAlerts } from '@/contexts/AlertContext';

export function AiCoachFab() {
  const { isConnected, isGuest } = useBroker();
  const { alerts } = useAlerts();

  if (!isConnected || isGuest) return null;

  // Severity lives on the pattern, not the alert wrapper — reading a.severity
  // was always undefined, so the danger badge never appeared.
  const dangerCount = alerts.filter(a => a.pattern.severity === 'danger' && !a.acknowledged).length;
  const hasDanger = dangerCount > 0;

  return (
    <Link
      to="/chat"
      aria-label="Open AI coach"
      className={cn(
        // Position: above bottom nav on mobile, near bottom-right on desktop
        'fixed bottom-[72px] right-4 md:bottom-6 md:right-6 z-40',
        // Size
        'w-14 h-14 rounded-full',
        // Flat accent. The teal gradient and coloured glow this carried were
        // hard-coded palette values that bypassed the brand token entirely,
        // and gradients are banned (§4). It floats, so it keeps a shadow (§8).
        'bg-primary text-primary-foreground shadow-lg',
        // Interaction
        'flex items-center justify-center',
        'transition-transform duration-150 hover:scale-105 active:scale-95',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
        // Pulse when danger alerts present
        hasDanger && 'animate-pulse-slow',
      )}
    >
      <Bot className="h-5 w-5" />

      {/* Badge: count of unread danger alerts */}
      {hasDanger && (
        <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-danger text-danger-foreground text-[10px] font-bold font-tabular flex items-center justify-center leading-none">
          {dangerCount > 9 ? '9+' : dangerCount}
        </span>
      )}
    </Link>
  );
}
