import { useState, Suspense, lazy } from 'react';
import { Link } from 'react-router-dom';
import { Link2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { useBroker } from '@/contexts/BrokerContext';
import ExportReportButton from '@/components/analytics/ExportReportButton';
import ComplianceDisclaimer from '@/components/ComplianceDisclaimer';
import InstrumentPanel from '@/components/analytics/InstrumentPanel';

const SummaryTab    = lazy(() => import('@/components/analytics/SummaryTab'));
const PatternsTab   = lazy(() => import('@/components/analytics/PatternsTab'));
const TradesTab     = lazy(() => import('@/components/analytics/TradesTab'));
const BtstTab       = lazy(() => import('@/components/analytics/BtstTab'));
const PnlPercentTab = lazy(() => import('@/components/analytics/PnlPercentTab'));

function TabSkeleton() {
  return (
    <div className="space-y-4 pt-2">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[1,2,3,4].map(i => <Skeleton key={i} className="h-20 rounded-xl" />)}
      </div>
      <Skeleton className="h-64 rounded-xl" />
      <Skeleton className="h-48 rounded-xl" />
    </div>
  );
}

const PERIOD_OPTIONS = [
  { label: '7D',  days: 7  },
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
] as const;

const TABS = [
  { value: 'summary',  label: 'Summary'  },
  { value: 'patterns', label: 'Patterns' },
  { value: 'trades',   label: 'Trades'   },
  { value: 'btst',     label: 'BTST'     },
  { value: 'pnlpct',   label: '% Return' },
] as const;

type TabValue = typeof TABS[number]['value'];

export default function Analytics() {
  const { isConnected, isLoading: brokerLoading, account } = useBroker();
  const [days, setDays] = useState(30);
  const [tab, setTab]   = useState<TabValue>('summary');
  const [instrumentPanel, setInstrumentPanel] = useState<string | null>(null);

  if (!brokerLoading && !isConnected) {
    return (
      <div className="max-w-5xl mx-auto pb-12">
        <div className="flex flex-col items-center justify-center min-h-[60vh]">
          <div className="p-4 rounded-full bg-tm-brand/10 mb-6">
            <Link2 className="h-12 w-12 text-tm-brand" />
          </div>
          <h2 className="text-xl font-semibold text-foreground mb-2">Connect Your Broker</h2>
          <p className="text-sm text-muted-foreground text-center max-w-md mb-6">
            Connect your Zerodha account to see your trading analytics.
          </p>
          <Link to="/settings">
            <Button size="lg" className="bg-tm-brand hover:bg-tm-brand/90 text-white gap-2">
              <Link2 className="h-4 w-4" />
              Connect Zerodha
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto pb-12">
      {/* ── Page Header ── */}
      <div className="mb-5 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-foreground tracking-tight">Analytics</h1>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-0.5 p-0.5 bg-slate-100 dark:bg-neutral-800 rounded-lg">
            {PERIOD_OPTIONS.map((opt) => (
              <button
                key={opt.days}
                onClick={() => setDays(opt.days)}
                aria-pressed={days === opt.days}
                aria-label={`Show last ${opt.label}`}
                className={cn(
                  'px-3 py-1.5 text-[12px] font-medium rounded-md transition-all',
                  days === opt.days
                    ? 'bg-white dark:bg-neutral-700 text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
          {account?.id && <ExportReportButton brokerAccountId={account.id} />}
        </div>
      </div>

      {/* ── Tab Bar ── */}
      <div role="tablist" aria-label="Analytics sections" className="flex gap-0 border-b border-border mb-6">
        {TABS.map(({ value, label }) => (
          <button
            key={value}
            role="tab"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={cn(
              'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px',
              tab === value
                ? 'border-tm-brand text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── Tab Content ── */}
      <Suspense fallback={<TabSkeleton />}>
        {tab === 'summary'  && (
          <SummaryTab
            days={days}
            onInstrumentClick={(underlying) => setInstrumentPanel(underlying)}
          />
        )}
        {tab === 'patterns' && <PatternsTab days={days} />}
        {tab === 'trades'   && <TradesTab days={days} />}
        {tab === 'btst'     && <BtstTab days={days} />}
        {tab === 'pnlpct'   && <PnlPercentTab days={days} />}
      </Suspense>

      <ComplianceDisclaimer variant="footer" className="mt-8" />

      {/* ── Instrument Drill-down Panel ── */}
      {instrumentPanel && (
        <InstrumentPanel
          underlying={instrumentPanel}
          days={days}
          onClose={() => setInstrumentPanel(null)}
        />
      )}
    </div>
  );
}
