import { useState } from 'react';
import { Link } from 'react-router-dom';
import { BarChart3, Link2 } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useBroker } from '@/contexts/BrokerContext';
import ExportReportButton from '@/components/analytics/ExportReportButton';
import OverviewTab from '@/components/analytics/OverviewTab';
import BehaviorTab from '@/components/analytics/BehaviorTab';
import PerformanceTab from '@/components/analytics/PerformanceTab';
import RiskTab from '@/components/analytics/RiskTab';

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
      <Tabs defaultValue="overview">
        <TabsList className="w-full justify-start bg-muted/50 mb-6">
          <TabsTrigger value="overview" className="gap-1.5">
            Overview
          </TabsTrigger>
          <TabsTrigger value="behavior" className="gap-1.5">
            Behavior
          </TabsTrigger>
          <TabsTrigger value="performance" className="gap-1.5">
            Performance
          </TabsTrigger>
          <TabsTrigger value="risk" className="gap-1.5">
            Risk
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <OverviewTab days={days} />
        </TabsContent>
        <TabsContent value="behavior">
          <BehaviorTab days={days} />
        </TabsContent>
        <TabsContent value="performance">
          <PerformanceTab days={days} />
        </TabsContent>
        <TabsContent value="risk">
          <RiskTab days={days} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
