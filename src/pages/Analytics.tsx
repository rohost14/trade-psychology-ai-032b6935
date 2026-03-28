import { useState, Suspense, lazy } from 'react';
import { Link } from 'react-router-dom';
import { BarChart3, Link2 } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { useBroker } from '@/contexts/BrokerContext';
import ExportReportButton from '@/components/analytics/ExportReportButton';
import ComplianceDisclaimer from '@/components/ComplianceDisclaimer';

// Lazy-load each tab — only downloaded when user opens that tab
const SummaryTab  = lazy(() => import('@/components/analytics/SummaryTab'));
const BehaviorTab = lazy(() => import('@/components/analytics/BehaviorTab'));
const TimingTab   = lazy(() => import('@/components/analytics/TimingTab'));
const ProgressTab = lazy(() => import('@/components/analytics/ProgressTab'));
const TradesTab   = lazy(() => import('@/components/analytics/TradesTab'));

function TabSkeleton() {
  return (
    <div className="space-y-4 pt-2">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[1,2,3,4].map(i => <Skeleton key={i} className="h-24 rounded-xl" />)}
      </div>
      <Skeleton className="h-56 rounded-xl" />
    </div>
  );
}

const PERIOD_OPTIONS = [
  { label: '7D', days: 7 },
  { label: '14D', days: 14 },
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
] as const;

export default function Analytics() {
  const { isConnected, isLoading: brokerLoading, account } = useBroker();
  const [days, setDays] = useState(30);

  // Not connected state
  if (!brokerLoading && !isConnected) {
    return (
      <div className="max-w-6xl mx-auto pb-12">
        <div className="flex flex-col items-center justify-center min-h-[60vh]">
          <div className="p-4 rounded-full bg-primary/10 mb-6">
            <Link2 className="h-12 w-12 text-primary" />
          </div>
          <h2 className="text-2xl font-semibold text-foreground mb-2">Connect Your Broker</h2>
          <p className="text-muted-foreground text-center max-w-md mb-6">
            Connect your Zerodha account to see your trading analytics and behavioral insights.
          </p>
          <Link to="/settings">
            <Button size="lg" className="gap-2">
              <Link2 className="h-5 w-5" />
              Connect Zerodha
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto pb-12">
      {/* Page Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Analytics</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Performance insights and behavioral patterns
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Period Selector */}
          <div className="flex items-center gap-1 p-1 bg-muted rounded-lg">
            {PERIOD_OPTIONS.map((opt) => (
              <button
                key={opt.days}
                onClick={() => setDays(opt.days)}
                className={cn(
                  'px-3 py-1.5 text-xs font-medium rounded-md transition-all',
                  days === opt.days
                    ? 'bg-background text-foreground shadow-sm'
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

      {/* Tabs */}
      <Tabs defaultValue="summary">
        <TabsList className="w-full justify-start rounded-none bg-transparent border-b border-border p-0 h-auto gap-0 mb-6">
          {(['summary','behavior','timing','progress','trades'] as const).map((tab) => (
            <TabsTrigger
              key={tab}
              value={tab}
              className="relative rounded-none bg-transparent border-b-2 border-transparent px-4 py-2.5 text-sm capitalize text-muted-foreground hover:text-foreground transition-colors data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-foreground data-[state=active]:shadow-none"
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="summary">
          <Suspense fallback={<TabSkeleton />}><SummaryTab days={days} /></Suspense>
        </TabsContent>
        <TabsContent value="behavior">
          <Suspense fallback={<TabSkeleton />}><BehaviorTab days={days} /></Suspense>
        </TabsContent>
        <TabsContent value="timing">
          <Suspense fallback={<TabSkeleton />}><TimingTab days={days} /></Suspense>
        </TabsContent>
        <TabsContent value="progress">
          <Suspense fallback={<TabSkeleton />}><ProgressTab days={days} /></Suspense>
        </TabsContent>
        <TabsContent value="trades">
          <Suspense fallback={<TabSkeleton />}><TradesTab days={days} /></Suspense>
        </TabsContent>
      </Tabs>

      <ComplianceDisclaimer variant="footer" className="mt-6" />
    </div>
  );
}
