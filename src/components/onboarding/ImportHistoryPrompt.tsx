/**
 * Empty/thin-state nudge: a dismissible banner shown on Dashboard + Analytics when the
 * user has little/no history, prompting them to import their Console tradebook. Kite only
 * returns today's trades, so a fresh user's analytics are empty until they import.
 */
import { useEffect, useState } from 'react';
import { Upload, X } from 'lucide-react';
import { api } from '@/lib/api';
import { isGuestMode } from '@/lib/guestMode';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { TradebookImportCard, type ImportResult } from '@/components/settings/TradebookImportCard';

const DISMISS_KEY = 'tradementor_import_prompt_dismissed';
const THIN_THRESHOLD = 10;   // fewer than this many completed trades = "thin"

export default function ImportHistoryPrompt() {
  const [show, setShow] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (isGuestMode()) return;
    if (localStorage.getItem(DISMISS_KEY)) return;
    let cancelled = false;
    api.get('/api/trades/completed?limit=1')
      .then(res => {
        const total = res.data?.total ?? 0;
        if (!cancelled && total < THIN_THRESHOLD) setShow(true);
      })
      .catch(() => { /* not authed / error — say nothing */ });
    return () => { cancelled = true; };
  }, []);

  const dismiss = () => {
    localStorage.setItem(DISMISS_KEY, '1');
    setShow(false);
  };

  const onImported = (r: ImportResult) => {
    if (r.imported > 0) {
      // History is in — stop nudging and let the fresh analytics take over.
      localStorage.setItem(DISMISS_KEY, '1');
      setTimeout(() => { setOpen(false); setShow(false); }, 1200);
    }
  };

  if (!show) return null;

  return (
    <>
      <div className="tm-card overflow-hidden mb-4 border border-[rgb(var(--tm-brand))]/25">
        <div className="flex items-center gap-3 px-4 py-3">
          <div className="w-9 h-9 rounded-lg bg-[rgb(var(--tm-brand))]/10 flex items-center justify-center shrink-0">
            <Upload className="w-4 h-4 text-tm-brand" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[13px] font-semibold text-foreground">Start with your real history</p>
            <p className="text-xs text-muted-foreground">
              Kite only shares today's trades. Import your Console tradebook to fill Analytics, Edge &amp; Habits instantly — analysis only, no alerts.
            </p>
          </div>
          <Button size="sm" className="shrink-0" onClick={() => setOpen(true)}>Import history</Button>
          <button onClick={dismiss} className="shrink-0 text-muted-foreground hover:text-foreground p-1" aria-label="Dismiss">
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-[560px] max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Import your trading history</DialogTitle></DialogHeader>
          <TradebookImportCard onImported={onImported} />
        </DialogContent>
      </Dialog>
    </>
  );
}
