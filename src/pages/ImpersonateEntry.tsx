import { useEffect } from 'react';
import { startImpersonation } from '@/lib/impersonation';

/**
 * Landing route for an admin "view as user" link. The impersonation token arrives in the
 * URL *hash* (never sent to the server / logs), is stored per-tab, then the tab hard-reloads
 * into the dashboard so every context re-initialises with the impersonation token.
 */
export default function ImpersonateEntry() {
  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    const token = params.get('token');
    if (!token) { window.location.replace('/welcome'); return; }
    startImpersonation(token, {
      name: params.get('name') || 'user',
      by:   params.get('by') || '',
      exp:  Number(params.get('exp')) || 0,
    });
    // Strip the hash so the token isn't left in the address bar, then hard-load the app.
    window.location.replace('/dashboard');
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background text-muted-foreground text-sm">
      Opening read-only view…
    </div>
  );
}
