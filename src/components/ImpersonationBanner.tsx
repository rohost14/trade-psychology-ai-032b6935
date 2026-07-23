import { Eye, LogOut } from 'lucide-react';
import { getImpersonationMeta, stopImpersonation } from '@/lib/impersonation';

/**
 * Persistent read-only banner shown whenever the current tab is an admin
 * impersonation session ("view as user"). Rendered by Layout above the content.
 */
export default function ImpersonationBanner() {
  const meta = getImpersonationMeta();
  if (!meta) return null;

  const exit = () => {
    stopImpersonation();
    // New tab — try to close; if the browser blocks it, drop to a neutral page.
    window.close();
    window.location.replace('/welcome');
  };

  return (
    <div className="sticky top-0 z-50 flex items-center justify-center gap-3 px-4 py-2 text-sm font-medium text-white"
      style={{ background: 'rgb(var(--tm-brand))' }}>
      <Eye className="w-4 h-4 shrink-0" />
      <span className="truncate">
        Read-only admin view — <strong>{meta.name}</strong>. Changes are disabled.
      </span>
      <button onClick={exit} className="ml-2 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/15 hover:bg-white/25 transition-colors shrink-0">
        <LogOut className="w-3.5 h-3.5" /> Exit
      </button>
    </div>
  );
}
