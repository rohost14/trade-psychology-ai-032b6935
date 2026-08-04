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
import ImportRecap from './ImportRecap';

const DISMISS_KEY = 'tradementor_import_prompt_dismissed';
const THIN_THRESHOLD = 10;   // fewer than this many completed trades = "thin"
const SNOOZE_DAYS = 30;

/**
 * Dismissal snoozes for 30 days; it does not kill the prompt forever.
 *
 * The X used to write a permanent flag, so one stray click meant the user never
 * saw the import nudge again — on a product where Kite returns no history and
 * Analytics is empty until you import. People routinely decide to import months
 * after first seeing the offer. Importing also stops the prompt for good on its
 * own (see onImported), so the only thing being snoozed is a "not now".
 *
 * The legacy value was the string '1'. Anything unparseable is treated as expired,
 * which un-sticks users who permanently dismissed it under the old behaviour.
 */
function isSnoozed(): boolean {
  const raw = localStorage.getItem(DISMISS_KEY);
  if (!raw) return false;
  if (raw === 'permanent') return true;      // written after a successful import
  const until = Number(raw);
  return Number.isFinite(until) && until > Date.now();
}

export default function ImportHistoryPrompt() {
  const [show, setShow] = useState(false);
  const [open, setOpen] = useState(false);
  const [recap, setRecap] = useState(false);

  useEffect(() => {
    if (isGuestMode()) return;
    if (isSnoozed()) return;
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
    localStorage.setItem(DISMISS_KEY, String(Date.now() + SNOOZE_DAYS * 86_400_000));
    setShow(false);
  };

  const onImported = (r: ImportResult) => {
    if (r.imported > 0) {
      // History is in — the offer is answered, so this one IS permanent (unlike a
      // dismissal, which only snoozes). Reveal the recap: "here's what we found".
      localStorage.setItem(DISMISS_KEY, 'permanent');
      setRecap(true);
    }
  };

  const closeDialog = () => { setOpen(false); setShow(false); };

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
          {/* 44px hit area on a 16px icon. The negative margin cancels the extra
              padding so the row looks identical — this buys touch accuracy, not
              visual weight. It was 24px, which is a mis-tap on a phone, and after
              the snooze change a mis-tap now costs 30 days of not seeing this. */}
          <button
            onClick={dismiss}
            className="shrink-0 h-11 w-11 -m-2.5 flex items-center justify-center text-muted-foreground hover:text-foreground"
            aria-label="Dismiss"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) { setShow(false); setRecap(false); } }}>
        <DialogContent className="max-w-[560px] max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle>{recap ? 'Import complete' : 'Import your trading history'}</DialogTitle></DialogHeader>
          {recap ? <ImportRecap onClose={closeDialog} /> : <TradebookImportCard onImported={onImported} />}
        </DialogContent>
      </Dialog>
    </>
  );
}
