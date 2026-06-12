import { Fragment, useState, Suspense, lazy } from 'react';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { Link } from 'react-router-dom';
import {
  Link2, BarChart2, AlertTriangle, List,
  Moon, Percent, Crosshair, Calendar, BookOpen,
} from 'lucide-react';
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
const EdgeMapTab    = lazy(() => import('@/components/analytics/EdgeMapTab'));
const ExpiryTab     = lazy(() => import('@/components/analytics/ExpiryTab'));
const JournalCorrelationTab = lazy(() => import('@/components/analytics/JournalCorrelationTab'));

function TabSkeleton() {
  return (
    <div className="space-y-4 pt-2">
      <Skeleton className="h-[280px] rounded-xl" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px">
        {[1,2,3,4].map(i => <Skeleton key={i} className="h-20" />)}
      </div>
      <Skeleton className="h-[200px] rounded-xl" />
    </div>
  );
}

const PERIOD_OPTIONS = [
  { label: '7D',  days: 7  },
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
] as const;

const TABS = [
  { value: 'summary',  label: 'Summary',  icon: BarChart2,     group: 'core' as const },
  { value: 'patterns', label: 'Patterns', icon: AlertTriangle, group: 'core' as const },
  { value: 'trades',   label: 'Trades',   icon: List,          group: 'core' as const },
  { value: 'btst',     label: 'BTST',     icon: Moon,          group: 'deep' as const },
  { value: 'pnlpct',   label: 'Returns',  icon: Percent,       group: 'deep' as const },
  { value: 'edgemap',  label: 'Edge Map', icon: Crosshair,     group: 'deep' as const },
  { value: 'expiry',   label: 'Expiry',   icon: Calendar,      group: 'deep' as const },
  { value: 'journal',  label: 'Journal',  icon: BookOpen,      group: 'deep' as const },
] as const;

type TabValue = typeof TABS[number]['value'];

export default function Analytics() {
  const { isConnected, isLoading: brokerLoading, account } = useBroker();
  const [days, setDays] = useState(30);
  const [tab, setTab]   = useState<TabValue>('summary');
  const [instrumentPanel, setInstrumentPanel] = useState<string | null>(null);

  if (!brokerLoading && !isConnected) {
    return (
      <div className="w-full pb-12">
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
    <div className="w-full pb-12">
      {/* ── Page Header ── */}
      <div className="mb-4 flex items-center justify-between">
        <h1 className="t-heading-lg text-foreground">Analytics</h1>
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

      {/* ── Tab Bar — sticky so period switch & tab switch stay in view ── */}
      <div className="sticky top-0 z-20 bg-background/95 backdrop-blur-sm border-b border-border -mx-4 sm:-mx-6 px-4 sm:px-6 mb-6">
        <div
          role="tablist"
          aria-label="Analytics sections"
          className="flex overflow-x-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]"
        >
          {TABS.map(({ value, label, icon: Icon, group }, i) => (
            <Fragment key={value}>
              {/* Visual separator between core and deep-dive groups */}
              {i > 0 && TABS[i - 1].group !== group && (
                <div className="w-px bg-border/70 my-2 mx-1.5 shrink-0" />
              )}
              <button
                role="tab"
                aria-selected={tab === value}
                onClick={() => setTab(value)}
                className={cn(
                  'flex items-center gap-1.5 px-3.5 py-2.5 text-[13px] font-medium border-b-2 transition-colors -mb-px whitespace-nowrap shrink-0',
                  tab === value
                    ? 'border-tm-brand text-foreground'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                )}
              >
                <Icon className="h-3.5 w-3.5 shrink-0" />
                {label}
              </button>
            </Fragment>
          ))}
        </div>
      </div>

      {/* ── Tab Content ── */}
      <ErrorBoundary fallback={
        <div className="py-12 text-center text-sm text-muted-foreground">
          This tab failed to load. Try refreshing the page.
        </div>
      }>
        <Suspense fallback={<TabSkeleton />}>
          {tab === 'summary'  && (
            <SummaryTab
              days={days}
              onInstrumentClick={(underlying) => setInstrumentPanel(underlying)}
              onTabChange={(t) => setTab(t as TabValue)}
            />
          )}
          {tab === 'patterns' && <PatternsTab days={days} />}
          {tab === 'trades'   && <TradesTab days={days} />}
          {tab === 'btst'     && <BtstTab days={days} />}
          {tab === 'pnlpct'   && <PnlPercentTab days={days} />}
          {tab === 'edgemap'  && <EdgeMapTab days={days} />}
          {tab === 'expiry'   && <ExpiryTab days={days} />}
          {tab === 'journal'  && <JournalCorrelationTab days={days} />}
        </Suspense>
      </ErrorBoundary>

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
