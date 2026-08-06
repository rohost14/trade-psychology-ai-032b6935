import { useEffect, useState } from 'react';

/**
 * Thin top status rail for the Dashboard — page marker + IST market clock.
 * Ported from the Lovable MarketRail (minus the shadcn SidebarTrigger, since our
 * app uses its own Layout nav).
 */
const MARKET_OPEN_MIN = 9 * 60 + 15;   // 09:15 IST
const MARKET_CLOSE_MIN = 15 * 60 + 30; // 15:30 IST

function useMarketClock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  // Wall-clock in IST
  const ist = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }));
  const mins = ist.getHours() * 60 + ist.getMinutes();
  const open = mins >= MARKET_OPEN_MIN && mins < MARKET_CLOSE_MIN;
  const toClose = Math.max(0, MARKET_CLOSE_MIN - mins);
  const closeIn = `${Math.floor(toClose / 60).toString().padStart(2, '0')}:${(toClose % 60).toString().padStart(2, '0')}`;
  const clock = ist.toLocaleTimeString('en-IN', { hour12: false });
  return { open, closeIn, clock };
}

/**
 * Inline market status, not a header row.
 *
 * This used to be a full-width bar with a 3px accent, a title reading "Trading
 * Desk" and a clock: a whole row of chrome above the number the page exists to
 * show, restating what the sidebar already says. The status itself is worth
 * keeping, so it now rides in the session block's header line instead of
 * claiming a row of its own.
 */
export function MarketRail() {
  const { open, closeIn, clock } = useMarketClock();

  return (
    <span className="flex items-center gap-2.5 shrink-0">
      <span className="hidden sm:flex items-center gap-1.5">
        <span className={`h-1.5 w-1.5 rounded-full ${open ? 'bg-profit animate-pulse' : 'bg-muted-foreground'}`} />
        <span className="t-label">{open ? 'Market open' : 'Closed'}</span>
        <span className="text-[11px] font-tabular font-medium text-foreground">{closeIn}</span>
      </span>
      <span className="text-[11px] text-muted-foreground font-tabular hidden md:inline">{clock}</span>
    </span>
  );
}
