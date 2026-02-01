// Hook for Goals state management
// Uses backend API for persistence with localStorage as fallback

import { useState, useEffect, useCallback } from 'react';
import {
  TradingGoals,
  CommitmentLogEntry,
  StreakData,
  GoalAdherence,
} from '@/types/patterns';
import { useBroker } from '@/contexts/BrokerContext';
import {
  fetchGoals,
  updateGoals as apiUpdateGoals,
  GoalsApiResponse,
} from '@/lib/goalsApi';
import {
  getGoals as getLocalGoals,
  saveGoals as saveLocalGoals,
  getCommitmentLog as getLocalCommitmentLog,
  getStreakData as getLocalStreakData,
  isReviewWindowOpen,
  getDaysUntilReview,
  checkChangeCooldown,
  requestGoalChange,
  cancelCooldown,
  getGoalStatusForBadge,
} from '@/lib/goalsManager';

interface UseGoalsReturn {
  // Goals
  goals: TradingGoals;
  updateGoals: (updates: Partial<TradingGoals>, reason?: string) => void;

  // Commitment Log
  commitmentLog: CommitmentLogEntry[];

  // Streak
  streakData: StreakData;

  // Review Window
  isReviewOpen: boolean;
  nextReviewDate: Date;
  daysUntilReview: number;

  // Cooldown
  cooldown: {
    inCooldown: boolean;
    hoursRemaining?: number;
    expiresAt?: string;
  };
  startCooldown: () => { allowed: boolean; cooldownEnds?: string };
  cancelEditCooldown: () => void;

  // Adherence
  getStatusBadge: (adherence: GoalAdherence[]) => 'success' | 'warning' | 'danger';

  // Loading & Refresh
  isLoading: boolean;
  refresh: () => void;
}

export function useGoals(): UseGoalsReturn {
  const { account, isConnected } = useBroker();
  const [isLoading, setIsLoading] = useState(false);

  // State - start with localStorage defaults
  const [goals, setGoals] = useState<TradingGoals>(getLocalGoals);
  const [commitmentLog, setCommitmentLog] = useState<CommitmentLogEntry[]>(getLocalCommitmentLog);
  const [streakData, setStreakData] = useState<StreakData>(getLocalStreakData);
  const [isReviewOpen, setIsReviewOpen] = useState(isReviewWindowOpen());
  const [daysUntilReview, setDaysUntilReview] = useState(getDaysUntilReview());
  const [cooldown, setCooldown] = useState(checkChangeCooldown);

  // Fetch from backend when connected
  const fetchFromBackend = useCallback(async () => {
    if (!isConnected || !account?.id) {
      return;
    }

    setIsLoading(true);
    try {
      const data = await fetchGoals(account.id);
      if (data) {
        // Transform API response to match TradingGoals type
        setGoals({
          id: data.goals.id,
          created_at: data.goals.created_at,
          last_modified_at: data.goals.last_modified_at,
          max_risk_per_trade_percent: data.goals.max_risk_per_trade_percent,
          max_daily_loss: data.goals.max_daily_loss,
          max_trades_per_day: data.goals.max_trades_per_day,
          require_stoploss: data.goals.require_stoploss,
          min_time_between_trades_minutes: data.goals.min_time_between_trades_minutes,
          max_position_size_percent: data.goals.max_position_size_percent,
          allowed_trading_start: data.goals.allowed_trading_start,
          allowed_trading_end: data.goals.allowed_trading_end,
          starting_capital: data.goals.starting_capital,
          current_capital: data.goals.current_capital,
        } as TradingGoals);

        setCommitmentLog(data.commitment_log || []);
        setStreakData(data.streak || getLocalStreakData());
        setIsReviewOpen(data.is_review_open);
        setDaysUntilReview(data.days_until_review);

        // Also save to localStorage as cache
        saveLocalGoals(data.goals as unknown as TradingGoals);
      }
    } catch (error) {
      console.error('Error fetching goals from backend:', error);
      // Keep using localStorage data
    } finally {
      setIsLoading(false);
    }
  }, [isConnected, account?.id]);

  // Fetch on mount and when account changes
  useEffect(() => {
    fetchFromBackend();
  }, [fetchFromBackend]);

  // Update goals - sends to backend if connected
  const updateGoals = useCallback(
    async (updates: Partial<TradingGoals>, reason?: string) => {
      // Update local state immediately
      const newGoals = { ...goals, ...updates, last_modified_at: new Date().toISOString() };
      setGoals(newGoals);
      saveLocalGoals(newGoals, reason);

      // Sync to backend if connected
      if (isConnected && account?.id) {
        try {
          await apiUpdateGoals(account.id, updates, reason);
          // Refresh from backend to get updated log
          fetchFromBackend();
        } catch (error) {
          console.error('Error syncing goals to backend:', error);
        }
      }
    },
    [goals, isConnected, account?.id, fetchFromBackend]
  );

  const refresh = useCallback(() => {
    setCooldown(checkChangeCooldown());
    setIsReviewOpen(isReviewWindowOpen());
    setDaysUntilReview(getDaysUntilReview());
    fetchFromBackend();
  }, [fetchFromBackend]);

  const startCooldown = useCallback(() => {
    const result = requestGoalChange();
    setCooldown(checkChangeCooldown());
    return result;
  }, []);

  const cancelEditCooldown = useCallback(() => {
    cancelCooldown();
    setCooldown(checkChangeCooldown());
  }, []);

  // Calculate next review date
  const getNextReviewDate = (): Date => {
    const now = new Date();
    const nextMonth = new Date(now.getFullYear(), now.getMonth() + 1, 1);
    return nextMonth;
  };

  return {
    goals,
    updateGoals,
    commitmentLog,
    streakData,
    isReviewOpen,
    nextReviewDate: getNextReviewDate(),
    daysUntilReview,
    cooldown,
    startCooldown,
    cancelEditCooldown,
    getStatusBadge: getGoalStatusForBadge,
    isLoading,
    refresh,
  };
}
