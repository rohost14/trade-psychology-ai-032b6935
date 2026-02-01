// Goals Page - Trading Commitments, Emotional Tax, and Streak Tracking
// Philosophy: Mirror, not blocker - show facts and let traders self-reflect

import { useState, useMemo } from 'react';
import { Target, TrendingDown, Flame, AlertTriangle } from 'lucide-react';
import { useGoals } from '@/hooks/useGoals';
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

// Mock data for demonstration (will be replaced with real trade data)
import { calculateGoalAdherence, calculateEmotionalTax, getTopRecommendations } from '@/lib/emotionalTaxCalculator';
import { detectAllPatterns } from '@/lib/patternDetector';
import { TradingGoals } from '@/types/patterns';
import { Trade } from '@/types/api';

// Mock trades for demonstration
const mockTrades: Trade[] = [
  {
    id: '1',
    tradingsymbol: 'NIFTY 21500 CE',
    exchange: 'NFO',
    trade_type: 'BUY',
    quantity: 50,
    price: 150,
    pnl: -2500,
    traded_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    order_id: '1',
  },
  {
    id: '2',
    tradingsymbol: 'NIFTY 21500 CE',
    exchange: 'NFO',
    trade_type: 'BUY',
    quantity: 100,
    price: 145,
    pnl: -4000,
    traded_at: new Date(Date.now() - 1.9 * 60 * 60 * 1000).toISOString(),
    order_id: '2',
  },
  {
    id: '3',
    tradingsymbol: 'BANKNIFTY 46000 PE',
    exchange: 'NFO',
    trade_type: 'SELL',
    quantity: 25,
    price: 200,
    pnl: 3500,
    traded_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    order_id: '3',
  },
];

export default function Goals() {
  const {
    goals,
    updateGoals,
    commitmentLog,
    streakData,
    isReviewOpen,
    daysUntilReview,
    cooldown,
    startCooldown,
  } = useGoals();
  
  const [showEditModal, setShowEditModal] = useState(false);
  const [showCooldownDialog, setShowCooldownDialog] = useState(false);
  
  // Calculate patterns and adherence from mock data
  const patterns = useMemo(() => detectAllPatterns(mockTrades), []);
  const adherence = useMemo(
    () => calculateGoalAdherence(mockTrades, patterns, goals),
    [patterns, goals]
  );
  const emotionalTax = useMemo(
    () => calculateEmotionalTax(patterns, mockTrades),
    [patterns]
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
