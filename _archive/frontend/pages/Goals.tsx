// Goals Page - Trading Commitments, Emotional Tax, and Streak Tracking
// Philosophy: Mirror, not blocker - show facts and let traders self-reflect

import { useState, useMemo, useEffect } from 'react';
import { Target, AlertTriangle, Link2 } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { Link } from 'react-router-dom';
import { useGoals } from '@/hooks/useGoals';
import { useBroker } from '@/contexts/BrokerContext';
import { GoalCommitmentsCard } from '@/components/goals/GoalCommitmentsCard';
import { EmotionalTaxCard } from '@/components/goals/EmotionalTaxCard';
import { StreakTrackerCard } from '@/components/goals/StreakTrackerCard';
import { CommitmentLogCard } from '@/components/goals/CommitmentLogCard';
import { GoalEditModal } from '@/components/goals/GoalEditModal';
import { Button } from '@/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { toast } from 'sonner';
import { api } from '@/lib/api';

import { calculateGoalAdherence, calculateEmotionalTax, getTopRecommendations } from '@/lib/emotionalTaxCalculator';
// patternDetector removed — backend is the single detection engine
import { TradingGoals } from '@/types/patterns';
import { Trade } from '@/types/api';

export default function Goals() {
  const { isConnected, isLoading: brokerLoading, account } = useBroker();
  const {
    goals,
    updateGoals,
    commitmentLog,
    streakData,
    isReviewOpen,
    daysUntilReview,
    cooldown,
    startCooldown,
    isLoading: goalsLoading,
  } = useGoals();

  const [showEditModal, setShowEditModal] = useState(false);
  const [showCooldownDialog, setShowCooldownDialog] = useState(false);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [tradesLoading, setTradesLoading] = useState(false);

  // Fetch real trades
  useEffect(() => {
    if (!isConnected || !account) return;

    const fetchTrades = async () => {
      setTradesLoading(true);
      try {
        const response = await api.get('/api/trades/', {
          params: {
            limit: 100,
            status: 'COMPLETE'
          }
        });

        const fetchedTrades: Trade[] = (response.data.trades || []).map((t: any) => ({
          id: t.id,
          tradingsymbol: t.tradingsymbol,
          exchange: t.exchange,
          trade_type: t.transaction_type === 'BUY' ? 'BUY' : 'SELL',
          quantity: t.filled_quantity || t.quantity,
          price: t.average_price || t.price,
          pnl: t.pnl || 0,
          traded_at: t.order_timestamp || t.created_at,
          order_id: t.order_id
        }));

        setTrades(fetchedTrades);
      } catch (error) {
        console.error('Error fetching trades for goals:', error);
      } finally {
        setTradesLoading(false);
      }
    };

    fetchTrades();
  }, [isConnected, account]);

  // Patterns now come from backend — Goals page is deprecated (use My Patterns + Alerts)
  const patterns = useMemo(() => [], []);
  const adherence = useMemo(
    () => calculateGoalAdherence(trades, patterns, goals),
    [trades, patterns, goals]
  );
  const emotionalTax = useMemo(
    () => calculateEmotionalTax(patterns, trades),
    [patterns, trades]
  );
  const recommendations = useMemo(
    () => getTopRecommendations(emotionalTax),
    [emotionalTax]
  );
  
  const handleRequestChange = () => {
    if (cooldown.inCooldown) {
      toast.error(`Please wait ${cooldown.hoursRemaining} hours before requesting another change.`);
      return;
    }
    setShowCooldownDialog(true);
  };
  
  const handleConfirmCooldown = () => {
    const result = startCooldown();
    if (result.allowed) {
      setShowCooldownDialog(false);
      setShowEditModal(true);
      toast.info('24-hour cooldown started. You can now edit your goals.');
    }
  };
  
  const handleSaveGoals = (updates: Partial<TradingGoals>, reason: string) => {
    updateGoals(updates, reason);
    toast.success('Goals updated successfully. Your commitment has been logged.');
  };

  if (brokerLoading || goalsLoading || tradesLoading) {
    return (
      <div className="max-w-4xl mx-auto space-y-4 pb-12">
        <Skeleton className="h-8 w-56" />
        <div className="grid grid-cols-2 gap-4">
          {[1,2,3,4].map(i => <Skeleton key={i} className="h-48 rounded-xl" />)}
        </div>
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="max-w-4xl mx-auto pb-12">
        <div className="mb-5">
          <h1 className="text-lg font-semibold text-foreground tracking-tight">My Goals</h1>
        </div>
        <div className="tm-card flex flex-col items-center justify-center min-h-[50vh] text-center py-16">
          <div className="p-4 rounded-full bg-teal-50 dark:bg-teal-900/20 mb-5">
            <Link2 className="h-10 w-10 text-tm-brand" />
          </div>
          <h2 className="text-base font-semibold text-foreground mb-1">Connect Your Broker</h2>
          <p className="text-sm text-muted-foreground max-w-sm mb-5">
            Connect your Zerodha account to track trading commitments and discipline streaks.
          </p>
          <Link to="/settings">
            <Button size="sm" className="gap-2 bg-tm-brand hover:bg-tm-brand/90 text-white">
              <Link2 className="h-4 w-4" />
              Connect Zerodha
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto pb-12">
      {/* Page header */}
      <div className="mb-5">
        <h1 className="text-lg font-semibold text-foreground tracking-tight">My Goals</h1>
      </div>

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div className="tm-card border-l-2 border-l-tm-obs px-5 py-4 flex items-start gap-3 mb-5">
          <AlertTriangle className="h-4 w-4 text-tm-obs flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-[12px] font-semibold text-foreground mb-1.5">Recommendations based on your patterns:</p>
            <ul className="space-y-1">
              {recommendations.map((rec, i) => (
                <li key={i} className="text-[12px] text-muted-foreground flex items-center gap-2">
                  <span className="w-1 h-1 rounded-full bg-tm-obs flex-shrink-0" />
                  {rec}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Main Grid */}
      <div className="grid gap-5 lg:grid-cols-2">
        {/* Left Column */}
        <div className="space-y-5">
          <GoalCommitmentsCard
            goals={goals}
            adherence={adherence}
            isReviewOpen={isReviewOpen}
            daysUntilReview={daysUntilReview}
            cooldown={cooldown}
            onRequestChange={handleRequestChange}
          />
          <EmotionalTaxCard tax={emotionalTax} period="month" />
        </div>
        {/* Right Column */}
        <div className="space-y-5">
          <StreakTrackerCard streak={streakData} goalDays={30} />
          <CommitmentLogCard log={commitmentLog} />
        </div>
      </div>
      
      {/* Cooldown Confirmation Dialog */}
      <AlertDialog open={showCooldownDialog} onOpenChange={setShowCooldownDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Start 24-Hour Cooldown?</AlertDialogTitle>
            <AlertDialogDescription>
              Once you request a change, a 24-hour cooldown will begin. After the cooldown, you can modify your goals. This friction is designed to prevent impulsive changes during emotional trading.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmCooldown}>
              Start Cooldown & Edit
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      
      {/* Edit Modal */}
      <GoalEditModal
        open={showEditModal}
        onOpenChange={setShowEditModal}
        goals={goals}
        adherence={adherence}
        onSave={handleSaveGoals}
      />
    </div>
  );
}
