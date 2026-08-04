/**
 * Settings → Data
 *
 * Import and export live here, not in Danger Zone. Importing your history is a
 * growth action — it is the single best thing a new user can do, because Kite only
 * returns today's trades and Analytics stays empty without it. It used to sit in a
 * tab called "Danger Zone", directly above "Delete your account", and MyRecord even
 * told people to go there. Nobody goes looking for a constructive action in the
 * destructive-actions drawer.
 *
 * Danger Zone now holds only what is actually dangerous: account deletion.
 * Export stays here with import — both are routine data-portability operations
 * (Privacy Policy §11, DPDP Act 2023). Only deletion is irreversible.
 */
import { useState } from 'react';
import { Download, Loader2, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';
import { TradebookImportCard } from '@/components/settings/TradebookImportCard';

export function DataTab() {
  const { isGuest } = useBroker();
  const [isExporting, setIsExporting] = useState(false);

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

  // Guest mode runs on demo data with no real account behind it, and its api layer
  // stubs POSTs to {success:true} — an "import" would appear to work and change
  // nothing. Say so rather than fake it.
  if (isGuest) {
    return (
      <div className="tm-card px-5 py-8 text-center">
        <ShieldAlert className="h-8 w-8 text-muted-foreground/40 mx-auto mb-3" />
        <p className="text-sm font-medium text-foreground">Not available in demo mode</p>
        <p className="text-[13px] text-muted-foreground mt-1 max-w-sm mx-auto">
          Importing and exporting act on a real connected account.
          Connect your Zerodha account to use them.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <TradebookImportCard />

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
    </div>
  );
}
