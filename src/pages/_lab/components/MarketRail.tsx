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

export function MarketRail({ title = 'Trading Desk' }: { title?: string }) {
  const { open, closeIn, clock } = useMarketClock();

  return (
    <header className="-mx-4 sm:-mx-6 lg:-mx-8 -mt-4 sm:-mt-6 border-b border-border bg-card mb-4">
      <div className="min-h-12 flex items-center px-4 sm:px-6 lg:px-8 gap-3 py-2">
        <div className="min-w-0 flex items-center gap-2.5">
          <span className="h-5 w-[3px] rounded-full bg-primary shrink-0" aria-hidden />
          <h1 className="text-[14px] font-semibold tracking-tight text-foreground truncate leading-tight">{title}</h1>
        </div>

        <div className="ml-auto flex items-center gap-3 shrink-0">
          <div className="hidden sm:flex items-center gap-1.5">
            <span className={`h-1.5 w-1.5 rounded-full ${open ? 'bg-profit animate-pulse' : 'bg-muted-foreground'}`} />
            <span className="t-label">{open ? 'Market open' : 'Closed'}</span>
            <span className="text-[11px] font-tabular font-medium text-foreground tabular-nums">{closeIn}</span>
          </div>
          <span className="text-[11px] text-muted-foreground font-tabular hidden md:inline">{clock}</span>
        </div>
      </div>
    </header>
  );
}
