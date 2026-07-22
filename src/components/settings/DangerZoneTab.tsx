/**
 * Settings → Danger Zone
 *
 * Backs the two data rights the Privacy Policy commits to (DPDP Act 2023):
 *   §11 access/portability → download a full JSON copy of your data
 *   §12 erasure           → permanently delete the account
 *
 * Deletion is irreversible and gated behind typing the exact Zerodha user ID,
 * which the server re-verifies — the confirmation is not just client-side.
 */
import { useState } from 'react';
import { AlertTriangle, Download, Loader2, ShieldAlert, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';
import { TradebookImportCard } from '@/components/settings/TradebookImportCard';

export function DangerZoneTab() {
  const { account, exitGuestMode, isGuest } = useBroker();
  const [isExporting, setIsExporting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [confirmText, setConfirmText] = useState('');

  const brokerUserId = account?.broker_user_id ?? '';
  const canDelete = confirmText.trim().toUpperCase() === brokerUserId.trim().toUpperCase()
    && brokerUserId.length > 0;

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const res = await api.get('/api/account/export');
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `tradementor-data-export-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      const counts = res.data?.counts;
      toast.success('Data export downloaded', {
        description: counts
          ? `${counts.trades} trades · ${counts.completed_trades} completed · ${counts.journal_entries} journal entries · ${counts.risk_alerts} alerts`
          : undefined,
      });
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response?.status;
      toast.error(
        status === 429
          ? 'Too many exports — try again in an hour'
          : 'Could not generate your export. Please try again.',
      );
    } finally {
      setIsExporting(false);
    }
  };

  const handleDelete = async () => {
    if (!canDelete) return;
    setIsDeleting(true);
    try {
      await api.post('/api/account/delete', { confirmation: confirmText.trim() });
      toast.success('Account deleted', {
        description: 'Your account and all associated data have been permanently removed.',
      });
      // Nothing left to authenticate against — drop local state and leave.
      localStorage.clear();
      if (isGuest) exitGuestMode();
      window.location.href = '/welcome';
    } catch (error) {
      const err = error as { response?: { status?: number; data?: { detail?: unknown } } };
      const detail = err.response?.data?.detail;
      toast.error(
        typeof detail === 'string' ? detail : 'Account deletion failed — nothing was deleted.',
      );
      setIsDeleting(false);
    }
  };

  // Guest mode runs on demo data with no real account behind it. Its api layer
  // stubs POSTs to {success:true}, which would make "deletion" look like it
  // worked. Show the section read-only instead of faking a destructive action.
  if (isGuest) {
    return (
      <div className="tm-card px-5 py-8 text-center">
        <ShieldAlert className="h-8 w-8 text-muted-foreground/40 mx-auto mb-3" />
        <p className="text-sm font-medium text-foreground">Not available in demo mode</p>
        <p className="text-[13px] text-muted-foreground mt-1 max-w-sm mx-auto">
          Data export and account deletion act on a real connected account.
          Connect your Zerodha account to use them.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* ── Import ─────────────────────────────────────────────────────────── */}
      <TradebookImportCard />

      {/* ── Export ─────────────────────────────────────────────────────────── */}
      <div className="tm-card overflow-hidden">
        <div className="px-5 py-3.5 border-b border-border">
          <p className="text-sm font-semibold text-foreground flex items-center gap-2">
            <Download className="h-4 w-4" />
            Export your data
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Download everything TradeMentor holds about you as a JSON file
          </p>
        </div>
        <div className="p-5 space-y-4">
          <p className="text-[13px] text-muted-foreground leading-relaxed">
            Includes your profile, trades, completed positions, journal entries, behavioural
            alerts and session history. Broker credentials are excluded on purpose — your
            authoritative trade records always remain with Zerodha.
          </p>
          <Button variant="outline" onClick={handleExport} disabled={isExporting} className="gap-2">
            {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            {isExporting ? 'Preparing…' : 'Download my data'}
          </Button>
        </div>
      </div>

      {/* ── Delete ─────────────────────────────────────────────────────────── */}
      <div className="tm-card overflow-hidden border-tm-loss/40">
        <div className="px-5 py-3.5 border-b border-tm-loss/30 bg-red-50/60 dark:bg-red-900/10">
          <p className="text-sm font-semibold text-tm-loss flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />
            Delete your account
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Permanently erases your account and all associated data
          </p>
        </div>
        <div className="p-5 space-y-4">
          <div className="rounded-lg border border-tm-loss/30 bg-red-50/40 dark:bg-red-900/10 px-4 py-3">
            <p className="text-[13px] font-medium text-foreground mb-1.5">This cannot be undone.</p>
            <ul className="text-[12px] text-muted-foreground space-y-1">
              <li>· Your profile, trading rules and guardian settings</li>
              <li>· All trades, completed positions and P&amp;L history held here</li>
              <li>· Journal entries, behavioural alerts and coaching history</li>
              <li>· Your Zerodha connection — the access token is revoked immediately</li>
            </ul>
            <p className="text-[12px] text-muted-foreground mt-2">
              Your trade records at Zerodha are unaffected. Consider exporting your data first.
            </p>
          </div>

          {!showDelete ? (
            <Button
              variant="outline"
              onClick={() => setShowDelete(true)}
              className="gap-2 text-tm-loss border-tm-loss/40 hover:bg-red-50 dark:hover:bg-red-900/20"
            >
              <Trash2 className="h-4 w-4" />
              Delete my account
            </Button>
          ) : (
            <div className="space-y-3">
              <div className="space-y-2">
                <Label htmlFor="delete-confirm">
                  Type your Zerodha user ID{' '}
                  <span className="font-mono font-semibold text-foreground">{brokerUserId || '—'}</span>{' '}
                  to confirm
                </Label>
                <Input
                  id="delete-confirm"
                  autoComplete="off"
                  placeholder={brokerUserId || 'Zerodha user ID'}
                  value={confirmText}
                  onChange={e => setConfirmText(e.target.value)}
                  disabled={isDeleting}
                />
              </div>
              <div className="flex items-center gap-2">
                <Button
                  onClick={handleDelete}
                  disabled={!canDelete || isDeleting}
                  className="gap-2 bg-tm-loss hover:bg-tm-loss/90 text-white"
                >
                  {isDeleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                  {isDeleting ? 'Deleting…' : 'Permanently delete'}
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => { setShowDelete(false); setConfirmText(''); }}
                  disabled={isDeleting}
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
