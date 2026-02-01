// Goals Manager for TradeMentor AI
// Handles goal persistence with localStorage
// Includes commitment logging, streak tracking, and friction-based changes

import {
  TradingGoals,
  CommitmentLogEntry,
  StreakData,
  DailyAdherence,
  StreakMilestone,
  GoalAdherence,
} from '@/types/patterns';

// Storage keys
const STORAGE_KEYS = {
  GOALS: 'tradementor_goals',
  COMMITMENT_LOG: 'tradementor_commitment_log',
  STREAK_DATA: 'tradementor_streak',
  CHANGE_COOLDOWN: 'tradementor_change_cooldown',
};

// Default goals for new users
const DEFAULT_GOALS: TradingGoals = {
  id: generateId(),
  created_at: new Date().toISOString(),
  last_modified_at: new Date().toISOString(),
  max_risk_per_trade_percent: 2,
  max_daily_loss: 5000,
  max_trades_per_day: 10,
  require_stoploss: true,
  min_time_between_trades_minutes: 5,
  max_position_size_percent: 5,
  allowed_trading_start: '09:15',
  allowed_trading_end: '15:30',
  starting_capital: 100000,
  current_capital: 100000,
};

// ============================================
// GOALS MANAGEMENT
// ============================================

export function getGoals(): TradingGoals {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.GOALS);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (error) {
    console.error('Error reading goals:', error);
  }
  return { ...DEFAULT_GOALS, id: generateId(), created_at: new Date().toISOString() };
}

export function saveGoals(goals: TradingGoals, reason?: string): void {
  const previousGoals = getGoals();
  const updatedGoals = {
    ...goals,
    last_modified_at: new Date().toISOString(),
  };
  
  try {
    localStorage.setItem(STORAGE_KEYS.GOALS, JSON.stringify(updatedGoals));
    
    // Log the change
    logGoalModification(previousGoals, updatedGoals, reason);
  } catch (error) {
    console.error('Error saving goals:', error);
  }
}

export function resetGoalsToDefault(): void {
  const newGoals = {
    ...DEFAULT_GOALS,
    id: generateId(),
    created_at: new Date().toISOString(),
    last_modified_at: new Date().toISOString(),
  };
  
  localStorage.setItem(STORAGE_KEYS.GOALS, JSON.stringify(newGoals));
  addCommitmentLogEntry({
    id: generateId(),
    timestamp: new Date().toISOString(),
    type: 'goal_set',
    description: 'Goals reset to default values',
  });
}

// ============================================
// CHANGE COOLDOWN (Friction-based lock)
// ============================================

export function requestGoalChange(): { allowed: boolean; cooldownEnds?: string } {
  const cooldownData = localStorage.getItem(STORAGE_KEYS.CHANGE_COOLDOWN);
  
  if (cooldownData) {
    const { requestedAt, expiresAt } = JSON.parse(cooldownData);
    const now = new Date();
    
    if (new Date(expiresAt) > now) {
      // Still in cooldown
      return { allowed: false, cooldownEnds: expiresAt };
    }
  }
  
  // Start new cooldown (24 hours)
  const now = new Date();
  const expiresAt = new Date(now.getTime() + 24 * 60 * 60 * 1000);
  
  localStorage.setItem(
    STORAGE_KEYS.CHANGE_COOLDOWN,
    JSON.stringify({
      requestedAt: now.toISOString(),
      expiresAt: expiresAt.toISOString(),
    })
  );
  
  return { allowed: true };
}

export function checkChangeCooldown(): { inCooldown: boolean; expiresAt?: string; hoursRemaining?: number } {
  const cooldownData = localStorage.getItem(STORAGE_KEYS.CHANGE_COOLDOWN);
  
  if (!cooldownData) {
    return { inCooldown: false };
  }
  
  const { expiresAt } = JSON.parse(cooldownData);
  const now = new Date();
  const expiry = new Date(expiresAt);
  
  if (expiry > now) {
    const hoursRemaining = Math.ceil((expiry.getTime() - now.getTime()) / (60 * 60 * 1000));
    return { inCooldown: true, expiresAt, hoursRemaining };
  }
  
  // Cooldown expired, clear it
  localStorage.removeItem(STORAGE_KEYS.CHANGE_COOLDOWN);
  return { inCooldown: false };
}

export function cancelCooldown(): void {
  localStorage.removeItem(STORAGE_KEYS.CHANGE_COOLDOWN);
}

// ============================================
// MONTHLY REVIEW WINDOW
// ============================================

export function isReviewWindowOpen(): boolean {
  const now = new Date();
  const dayOfMonth = now.getDate();
  
  // Review window: 1st-3rd of each month
  return dayOfMonth >= 1 && dayOfMonth <= 3;
}

export function getNextReviewDate(): Date {
  const now = new Date();
  const nextMonth = new Date(now.getFullYear(), now.getMonth() + 1, 1);
  return nextMonth;
}

export function getDaysUntilReview(): number {
  const now = new Date();
  const nextReview = getNextReviewDate();
  const diffTime = nextReview.getTime() - now.getTime();
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
}

// ============================================
// COMMITMENT LOG
// ============================================

export function getCommitmentLog(): CommitmentLogEntry[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.COMMITMENT_LOG);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (error) {
    console.error('Error reading commitment log:', error);
  }
  return [];
}

export function addCommitmentLogEntry(entry: CommitmentLogEntry): void {
  const log = getCommitmentLog();
  log.unshift(entry); // Add to beginning
  
  // Keep last 100 entries
  const trimmedLog = log.slice(0, 100);
  
  try {
    localStorage.setItem(STORAGE_KEYS.COMMITMENT_LOG, JSON.stringify(trimmedLog));
  } catch (error) {
    console.error('Error saving commitment log:', error);
  }
}

function logGoalModification(previous: TradingGoals, updated: TradingGoals, reason?: string): void {
  const changes: string[] = [];
  
  if (previous.max_risk_per_trade_percent !== updated.max_risk_per_trade_percent) {
    changes.push(`Max risk/trade: ${previous.max_risk_per_trade_percent}% → ${updated.max_risk_per_trade_percent}%`);
  }
  if (previous.max_daily_loss !== updated.max_daily_loss) {
    changes.push(`Max daily loss: ₹${previous.max_daily_loss} → ₹${updated.max_daily_loss}`);
  }
  if (previous.max_trades_per_day !== updated.max_trades_per_day) {
    changes.push(`Max trades/day: ${previous.max_trades_per_day} → ${updated.max_trades_per_day}`);
  }
  if (previous.require_stoploss !== updated.require_stoploss) {
    changes.push(`Stop loss required: ${previous.require_stoploss} → ${updated.require_stoploss}`);
  }
  
  if (changes.length > 0) {
    addCommitmentLogEntry({
      id: generateId(),
      timestamp: new Date().toISOString(),
      type: 'goal_modified',
      description: changes.join('; '),
      reason: reason || 'User modified goals',
    });
  }
}

export function logGoalBroken(goalName: string, cost: number): void {
  addCommitmentLogEntry({
    id: generateId(),
    timestamp: new Date().toISOString(),
    type: 'goal_broken',
    description: `${goalName} was not followed`,
    cost,
  });
}

// ============================================
// STREAK TRACKING
// ============================================

export function getStreakData(): StreakData {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.STREAK_DATA);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (error) {
    console.error('Error reading streak data:', error);
  }
  
  return {
    current_streak_days: 0,
    longest_streak_days: 0,
    streak_start_date: null,
    daily_status: [],
    milestones_achieved: [],
  };
}

export function updateStreak(adherence: GoalAdherence[], isTradingDay: boolean = true): StreakData {
  const streak = getStreakData();
  const today = new Date().toISOString().split('T')[0];
  
  // Check if today was already recorded
  const existingToday = streak.daily_status.find((d) => d.date === today);
  if (existingToday) {
    return streak;
  }
  
  // Calculate if all goals were followed today
  const allGoalsFollowed = adherence.every((g) => g.times_broken === 0);
  const goalsBroken = adherence.filter((g) => g.times_broken > 0).map((g) => g.goal_name);
  
  // Add today's status
  streak.daily_status.unshift({
    date: today,
    all_goals_followed: allGoalsFollowed,
    goals_broken: goalsBroken,
    trading_day: isTradingDay,
  });
  
  // Keep last 60 days
  streak.daily_status = streak.daily_status.slice(0, 60);
  
  // Update streak count
  if (allGoalsFollowed && isTradingDay) {
    streak.current_streak_days++;
    
    if (!streak.streak_start_date) {
      streak.streak_start_date = today;
    }
    
    // Update longest streak
    if (streak.current_streak_days > streak.longest_streak_days) {
      streak.longest_streak_days = streak.current_streak_days;
    }
    
    // Check for milestones
    checkAndAddMilestone(streak);
  } else if (isTradingDay) {
    // Streak broken
    streak.current_streak_days = 0;
    streak.streak_start_date = null;
  }
  
  // Save updated streak
  try {
    localStorage.setItem(STORAGE_KEYS.STREAK_DATA, JSON.stringify(streak));
  } catch (error) {
    console.error('Error saving streak data:', error);
  }
  
  return streak;
}

function checkAndAddMilestone(streak: StreakData): void {
  const milestoneThresholds = [
    { days: 7, label: '7-Day Discipline' },
    { days: 14, label: '2-Week Warrior' },
    { days: 30, label: 'Monthly Master' },
    { days: 60, label: 'Trading Zen' },
  ];
  
  for (const threshold of milestoneThresholds) {
    if (streak.current_streak_days === threshold.days) {
      const alreadyAchieved = streak.milestones_achieved.some((m) => m.days === threshold.days);
      
      if (!alreadyAchieved) {
        streak.milestones_achieved.push({
          days: threshold.days,
          achieved_at: new Date().toISOString(),
          label: threshold.label,
        });
        
        // Log milestone
        addCommitmentLogEntry({
          id: generateId(),
          timestamp: new Date().toISOString(),
          type: 'streak_milestone',
          description: `🎉 Achieved ${threshold.label} streak!`,
        });
      }
    }
  }
}

export function resetStreak(): void {
  const defaultStreak: StreakData = {
    current_streak_days: 0,
    longest_streak_days: 0,
    streak_start_date: null,
    daily_status: [],
    milestones_achieved: [],
  };
  
  localStorage.setItem(STORAGE_KEYS.STREAK_DATA, JSON.stringify(defaultStreak));
}

// ============================================
// HELPER FUNCTIONS
// ============================================

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

// Get summary for nav badge
export function getGoalStatusForBadge(adherence: GoalAdherence[]): 'success' | 'warning' | 'danger' {
  const totalBroken = adherence.reduce((sum, g) => sum + g.times_broken, 0);
  const criticalBroken = adherence.filter((g) => 
    g.adherence_percent < 50 && 
    ['Max Daily Loss', 'Max Risk Per Trade'].includes(g.goal_name)
  ).length;
  
  if (criticalBroken > 0 || totalBroken > 5) return 'danger';
  if (totalBroken > 0) return 'warning';
  return 'success';
}

// Export for testing
export function clearAllGoalData(): void {
  localStorage.removeItem(STORAGE_KEYS.GOALS);
  localStorage.removeItem(STORAGE_KEYS.COMMITMENT_LOG);
  localStorage.removeItem(STORAGE_KEYS.STREAK_DATA);
  localStorage.removeItem(STORAGE_KEYS.CHANGE_COOLDOWN);
}
