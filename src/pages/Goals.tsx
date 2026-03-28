// Goals Page - Trading Commitments, Emotional Tax, and Streak Tracking
// Philosophy: Mirror, not blocker - show facts and let traders self-reflect

import { useState, useMemo, useEffect } from 'react';
import { Target, AlertTriangle, Link2, Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useGoals } from '@/hooks/useGoals';
import { useBroker } from '@/contexts/BrokerContext';
import { GoalCommitmentsCard } from '@/components/goals/GoalCommitmentsCard';
import { EmotionalTaxCard } from '@/components/goals/EmotionalTaxCard';
import { StreakTrackerCard } from '@/components/goals/StreakTrackerCard';
import { CommitmentLogCard } from '@/components/goals/CommitmentLogCard';
import { GoalEditModal } from '@/components/goals/GoalEditModal';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
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

  // Loading state
  if (brokerLoading || goalsLoading || tradesLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Not connected state
  if (!isConnected) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Target className="h-6 w-6 text-primary" />
            My Trading Commitments
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            Self-awareness through data, not restrictions
          </p>
        </div>
        <div className="flex flex-col items-center justify-center min-h-[50vh] bg-card rounded-lg border border-border">
          <div className="p-4 rounded-full bg-primary/10 mb-6">
            <Link2 className="h-12 w-12 text-primary" />
          </div>
          <h2 className="text-xl font-semibold text-foreground mb-2">Connect Your Broker</h2>
          <p className="text-muted-foreground text-center max-w-md mb-6">
            Connect your Zerodha account to track your trading commitments and see your discipline score.
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
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Target className="h-6 w-6 text-primary" />
            My Trading Commitments
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            Self-awareness through data, not restrictions
          </p>
        </div>
      </div>
      
      {/* Recommendations Banner (if any) */}
      {recommendations.length > 0 && (
        <Card className="border-warning/30 bg-warning/5">
          <CardContent className="py-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-warning flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-sm">Recommendations based on your patterns:</p>
                <ul className="mt-2 space-y-1">
                  {recommendations.map((rec, i) => (
                    <li key={i} className="text-sm text-muted-foreground flex items-center gap-2">
                      <span className="w-1 h-1 rounded-full bg-warning" />
                      {rec}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* Main Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left Column */}
        <div className="space-y-6">
          {/* Goal Commitments */}
          <GoalCommitmentsCard
            goals={goals}
            adherence={adherence}
            isReviewOpen={isReviewOpen}
            daysUntilReview={daysUntilReview}
            cooldown={cooldown}
            onRequestChange={handleRequestChange}
          />
          
          {/* Emotional Tax */}
          <EmotionalTaxCard tax={emotionalTax} period="month" />
        </div>
        
        {/* Right Column */}
        <div className="space-y-6">
          {/* Streak Tracker */}
          <StreakTrackerCard streak={streakData} goalDays={30} />
          
          {/* Commitment Log */}
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
