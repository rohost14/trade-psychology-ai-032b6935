/**
 * Analytics — post-market review: what behaviours cost money over time.
 *
 * Behaviour is the landing tab, not Overview. Everything on Overview — P&L,
 * win rate, profit factor, equity curve — a trader already has in Zerodha
 * Console, free, from the same account; leading with it meant opening on our
 * least differentiated screen while the analysis only this app can do sat
 * three tabs deep. docs/design/02_WEB_SCREENS.md already specified this, and
 * the shipped page had been contradicting it.
 *
 * Behaviour reads: the one leak worth acting on and the rule that constrains
 * it, then the same leaks ranked by realized money, then when they happened.
 */
import { Fragment, useState, Suspense, lazy } from 'react';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { Link } from 'react-router-dom';
import {
  Link2, BarChart2, Crosshair, Brain, Layers, Repeat,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { useBroker } from '@/contexts/BrokerContext';
import ReportCard from '@/components/analytics/ReportCard';
import PnlCalendar from '@/components/analytics/PnlCalendar';
import ImportHistoryPrompt from '@/components/onboarding/ImportHistoryPrompt';
import EdgeLeakCard from '@/components/analytics/EdgeLeakCard';
import StrategyCard from '@/components/analytics/StrategyCard';
import ExportReportButton from '@/components/analytics/ExportReportButton';
import ComplianceDisclaimer from '@/components/ComplianceDisclaimer';
import InstrumentPanel from '@/components/analytics/InstrumentPanel';

const OverviewTab  = lazy(() => import('@/components/analytics/OverviewTab'));
const EdgeTab      = lazy(() => import('@/components/analytics/EdgeTab'));
const TradeDnaTab  = lazy(() => import('@/components/analytics/TradeDnaTab'));
const BehaviorTab  = lazy(() => import('@/components/analytics/BehaviorTab'));
const SessionsTab  = lazy(() => import('@/components/analytics/SessionsTab'));
const BtstTab      = lazy(() => import('@/components/analytics/BtstTab'));
const HabitsTab    = lazy(() => import('@/components/analytics/HabitsTab'));

function TabSkeleton() {
  return (
    <div className="space-y-4 pt-2 animate-pulse">
      <Skeleton className="h-16 rounded-lg" />
      <Skeleton className="h-[260px] rounded-lg" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px">
        {[1,2,3,4].map(i => <Skeleton key={i} className="h-20" />)}
      </div>
      <Skeleton className="h-[200px] rounded-lg" />
    </div>
  );
}

const PERIOD_OPTIONS = [
  { label: '7D',  days: 7  },
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
] as const;

// Consolidated from 6 tabs → 4 (Overview · Edge · Behaviour · Advanced). The
// ReportCard hero sits above the tabs as the always-visible front door.
const TABS = [
  { value: 'habits',    label: 'Habits',     icon: Repeat,    group: 'core' as const },
  { value: 'edge',      label: 'Edge',       icon: Crosshair, group: 'core' as const },
  { value: 'overview',  label: 'Overview',   icon: BarChart2, group: 'core' as const },
  { value: 'advanced',  label: 'Advanced',   icon: Layers,    group: 'deep' as const },
] as const;

type TabValue = typeof TABS[number]['value'];

export default function Analytics() {
  const { isConnected, isLoading: brokerLoading, account } = useBroker();
  const [days, setDays] = useState(30);
  const [tab, setTab]   = useState<TabValue>('habits');
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

      {/* ── Page Header ──────────────────────────────────────────────────────── */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="t-heading-lg text-foreground">Analytics</h1>
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-0.5 p-0.5 bg-muted rounded-lg">
            {PERIOD_OPTIONS.map(opt => (
              <button
                key={opt.days}
                onClick={() => setDays(opt.days)}
                aria-pressed={days === opt.days}
                aria-label={`Show last ${opt.label}`}
                className={cn(
                  'px-3 py-1.5 text-[12px] font-medium rounded-md transition-all',
                  days === opt.days
                    ? 'bg-card text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
          {account?.id && <ExportReportButton brokerAccountId={account.id} />}
        </div>
      </div>

      <ImportHistoryPrompt />

      {/* ── Report Card hero — the front door ────────────────────────────────── */}
      <div className="mb-6">
        <ReportCard days={days} />
      </div>

      {/* ── Tab Bar ──────────────────────────────────────────────────────────── */}
      <div className="sticky top-0 z-20 bg-background/95 backdrop-blur-sm border-b border-border -mx-4 sm:-mx-6 px-4 sm:px-6 mb-6">
        <div
          role="tablist"
          aria-label="Analytics sections"
          className="flex overflow-x-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]"
        >
          {TABS.map(({ value, label, icon: Icon, group }, i) => (
            <Fragment key={value}>
              {i > 0 && TABS[i - 1].group !== group && (
                <div className="w-px bg-border/70 my-2 mx-1.5 shrink-0" />
              )}
              <button
                role="tab"
                aria-selected={tab === value}
                onClick={() => { setTab(value); window.scrollTo({ top: 0, behavior: 'smooth' }); }}
                className={cn(
                  'flex items-center gap-1.5 px-3.5 py-2.5 text-[13px] font-medium border-b-2 transition-colors -mb-px whitespace-nowrap shrink-0',
                  tab === value
                    ? 'border-tm-brand text-foreground'
                    : 'border-transparent text-muted-foreground hover:text-foreground',
                )}
              >
                <Icon className={cn('h-3.5 w-3.5 shrink-0', tab === value && 'text-foreground')} />
                {label}
              </button>
            </Fragment>
          ))}
        </div>
      </div>

      {/* ── Tab Content ──────────────────────────────────────────────────────── */}
      <ErrorBoundary fallback={
        <div className="tm-card flex flex-col items-center text-center gap-3 py-12 px-4">
          <p className="text-sm font-medium text-foreground">This tab hit an error</p>
          <p className="text-xs text-muted-foreground max-w-xs">Something went wrong rendering this view. Reloading usually fixes it.</p>
          <Button size="sm" variant="outline" onClick={() => window.location.reload()}>Reload</Button>
        </div>
      }>
        <Suspense fallback={<TabSkeleton />}>
          {tab === 'overview' && (
            <div className="space-y-5">
              <OverviewTab days={days} />
            </div>
          )}
          {tab === 'edge'     && (
            <div className="space-y-5">
              <EdgeLeakCard days={days} />
              <StrategyCard days={days} />
              <EdgeTab days={days} onInstrumentClick={u => setInstrumentPanel(u)} />
            </div>
          )}
          {tab === 'habits' && (
            <div className="space-y-5">
              <HabitsTab days={days} />
              {/* Conditional performance, options behaviour and emotion-vs-P&L:
                  trade- and journal-derived tendencies. The alert-derived half
                  of this tab moved to Alerts with the rest of the patterns. */}
              <BehaviorTab days={days} />
            </div>
          )}
          {tab === 'advanced' && (
            <div className="space-y-5">
              <PnlCalendar days={days} />
              <SessionsTab days={days} />
              <TradeDnaTab days={days} />
              <BtstTab days={days} />
            </div>
          )}
        </Suspense>
      </ErrorBoundary>

      <ComplianceDisclaimer variant="footer" className="mt-8" />

      {/* Instrument Drill-down Panel */}
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
