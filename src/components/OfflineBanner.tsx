/**
 * Global offline indicator. Mounted once at app root; shows a sticky banner whenever the
 * browser loses connectivity so failed requests read as "you're offline" instead of
 * cryptic errors. The axios interceptor suppresses its network-error toast while offline
 * so this is the single source of truth.
 */
import { useEffect, useState } from 'react';
import { WifiOff } from 'lucide-react';

export default function OfflineBanner() {
  const [offline, setOffline] = useState(typeof navigator !== 'undefined' && !navigator.onLine);

  useEffect(() => {
    const goOnline = () => setOffline(false);
    const goOffline = () => setOffline(true);
    window.addEventListener('online', goOnline);
    window.addEventListener('offline', goOffline);
    return () => {
      window.removeEventListener('online', goOnline);
      window.removeEventListener('offline', goOffline);
    };
  }, []);

  if (!offline) return null;

  return (
    <div className="fixed top-0 inset-x-0 z-[100] flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white bg-tm-loss">
      <WifiOff className="w-4 h-4 shrink-0" />
      You're offline — showing last known data. We'll reconnect automatically.
    </div>
  );
}
