/**
 * TermsUpdateGate — one-time notice when the Terms change under a logged-in user.
 *
 * This is the ONLY time a returning user should be asked about the terms. First
 * acceptance happens by pressing "Connect Zerodha" on the landing page, which is
 * recorded server-side in the OAuth callback (clickwrap by action). The old
 * landing page instead gated its button behind a React checkbox that reset on
 * every page load, so users re-ticked it daily and nothing was ever persisted.
 *
 * The backend only reports needs_acceptance when a stored acceptance exists and is
 * for an older version, so this renders nothing in the normal case. Users who
 * predate the acceptance column are stamped at their next login rather than
 * prompted here — asking them would be asking twice for the same thing.
 *
 * Failures are silent by design: a legal notice that cannot load must not become a
 * wall between the user and their positions.
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FileText, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';

interface TermsStatus {
  current_version: string;
  accepted_version: string | null;
  needs_acceptance: boolean;
}

export default function TermsUpdateGate() {
  const { isConnected, isGuest } = useBroker();
  const [show, setShow] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isConnected || isGuest) return;
    let cancelled = false;
    api.get<TermsStatus>('/api/legal/terms-status')
      .then(({ data }) => {
        if (!cancelled && data?.needs_acceptance) setShow(true);
      })
      .catch(() => { /* never block the app on this */ });
    return () => { cancelled = true; };
  }, [isConnected, isGuest]);

  const accept = async () => {
    setSaving(true);
    try {
      await api.post('/api/legal/accept');
      setShow(false);
    } catch {
      toast.error('Could not record that — please try again.');
      setSaving(false);
    }
  };

  if (!show) return null;

  return (
    // Not dismissible: no close button, and Escape / outside-click are ignored.
    // Acknowledging is one click, and a notice the user can wave away without
    // reading is not worth the code it takes to show it.
    <Dialog open onOpenChange={() => { /* intentionally inert */ }}>
      <DialogContent
        className="max-w-[460px]"
        onEscapeKeyDown={e => e.preventDefault()}
        onPointerDownOutside={e => e.preventDefault()}
        onInteractOutside={e => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            We&apos;ve updated our Terms
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <p className="text-[13px] text-muted-foreground leading-relaxed">
            Our{' '}
            <Link to="/terms" className="underline hover:text-foreground" target="_blank">
              Terms of Service
            </Link>{' '}
            and{' '}
            <Link to="/privacy" className="underline hover:text-foreground" target="_blank">
              Privacy Policy
            </Link>{' '}
            have changed since you last accepted them. Please review and continue.
          </p>

          <p className="text-[12px] text-muted-foreground leading-relaxed">
            TradeMentor is a behavioural mirror — it shows you what you did. It is not
            investment advice, and it never places, modifies or cancels orders.
          </p>

          <Button onClick={accept} disabled={saving} className="w-full gap-2">
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            {saving ? 'Saving…' : 'I understand — continue'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
