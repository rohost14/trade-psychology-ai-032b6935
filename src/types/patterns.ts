// Behavioral Pattern Types for TradeMentor AI
// Philosophy: Mirror, not blocker - show facts, not restrictions

import { Trade } from './api';

// ============================================
// BEHAVIORAL PATTERNS
// ============================================

export type PatternType =
  | 'overtrading'
  | 'revenge_trading'
  | 'fomo'
  | 'no_stoploss'
  | 'early_exit'
  | 'position_sizing'
  | 'loss_aversion'
  | 'winning_streak_overconfidence';

export type PatternSeverity = 'low' | 'medium' | 'high' | 'critical';

export interface BehaviorPattern {
  id: string;
  type: PatternType;
  name: string;
  severity: PatternSeverity;
  detected_at: string;
  
  // The facts we show (mirror approach)
  description: string;
  evidence: PatternEvidence;
  
  // Historical context
  historical_insight: string; // "Last time you did this, you lost ₹X"
  frequency_this_week: number;
  frequency_this_month: number;
  
  // Financial impact
  estimated_cost: number; // ₹ impact of this pattern
  
  // Actionable insight (not a command, just information)
  insight: string;
}

export interface PatternEvidence {
  trades_involved: string[]; // Trade IDs
  time_window_minutes: number;
  trigger_condition: string; // e.g., "5 trades in 30 minutes"
  threshold_exceeded_by: number; // percentage over threshold
}

// ============================================
// EMOTIONAL TAX
// ============================================

export interface EmotionalTax {
  // Summary
  total_cost_all_time: number;
  total_cost_this_month: number;
  total_cost_this_week: number;
  
  // Breakdown by pattern type
  breakdown: EmotionalTaxBreakdown[];
  
  // Insights
  worst_pattern: PatternType;
  worst_pattern_cost: number;
  improvement_vs_last_month: number; // percentage
}

export interface EmotionalTaxBreakdown {
  pattern_type: PatternType;
  pattern_name: string;
  occurrences: number;
  total_cost: number;
  avg_cost_per_occurrence: number;
  
  // The story the data tells
  insight: string; // "Revenge trades cost you 3x more than planned trades"
}

// ============================================
// TRADING GOALS (Self-Commitments)
// ============================================

export interface TradingGoals {
  id: string;
  created_at: string;
  last_modified_at: string;
  
  // Core goals
  max_risk_per_trade_percent: number; // e.g., 2%
  max_daily_loss: number; // in ₹
  max_trades_per_day: number;
  require_stoploss: boolean;
  min_time_between_trades_minutes: number;
  max_position_size_percent: number; // of capital
  
  // Trading hours discipline
  allowed_trading_start: string; // "09:15"
  allowed_trading_end: string; // "15:30"
  
  // Capital
  starting_capital: number;
  current_capital: number;
}

export interface GoalAdherence {
  goal_name: string;
  goal_value: string; // formatted for display
  
  // Performance
  times_followed: number;
  times_broken: number;
  adherence_percent: number;
  
  // Cost of breaking
  cost_when_broken: number;
  
  // Trend
  trend: 'improving' | 'stable' | 'declining';
  trend_vs_last_week: number; // percentage change
}

// ============================================
// COMMITMENT LOG (Accountability Trail)
// ============================================

export interface CommitmentLogEntry {
  id: string;
  timestamp: string;
  type: 'goal_set' | 'goal_modified' | 'goal_broken' | 'streak_milestone';
  
  // What happened
  description: string;
  
  // For modifications
  previous_value?: string;
  new_value?: string;
  reason?: string; // User's reason for change
  
  // For breaks
  pattern_type?: PatternType;
  cost?: number;
}

// ============================================
// STREAK TRACKING
// ============================================

export interface StreakData {
  current_streak_days: number;
  longest_streak_days: number;
  streak_start_date: string | null;
  
  // Daily adherence
  daily_status: DailyAdherence[];
  
  // Milestones
  milestones_achieved: StreakMilestone[];
}

export interface DailyAdherence {
  date: string;
  all_goals_followed: boolean;
  goals_broken: string[]; // which goals were broken
  trading_day: boolean; // was it a trading day?
}

export interface StreakMilestone {
  days: number;
  achieved_at: string;
  label: string; // "7-day discipline", "30-day master"
}

// ============================================
// PATTERN DETECTION CONFIG
// ============================================

export interface PatternDetectionConfig {
  // Overtrading thresholds
  overtrading_trades_per_30min: number; // default: 5
  overtrading_trades_per_hour: number; // default: 8
  
  // Revenge trading detection
  revenge_max_time_after_loss_minutes: number; // default: 5
  revenge_min_loss_to_trigger: number; // default: 500
  
  // FOMO detection
  fomo_rapid_entry_after_big_move_minutes: number; // default: 2
  fomo_big_move_threshold_percent: number; // default: 1%
  
  // Position sizing
  position_max_percent_of_capital: number; // default: 5%
  
  // Early exit detection
  early_exit_min_profit_missed_percent: number; // default: 50%
}

// ============================================
// ANALYSIS TIME WINDOWS
// ============================================

export type AnalysisWindow = '7d' | '30d' | '45d' | '60d' | 'all';

export interface AnalysisTimeframe {
  window: AnalysisWindow;
  start_date: string;
  end_date: string;
  trading_days: number;
  total_trades: number;
}

// ============================================
// PATTERN DETECTION RESULT
// ============================================

export interface PatternAnalysisResult {
  timeframe: AnalysisTimeframe;
  patterns_detected: BehaviorPattern[];
  emotional_tax: EmotionalTax;
  goal_adherence: GoalAdherence[];
  streak: StreakData;
  
  // Summary insights
  primary_weakness: PatternType | null;
  primary_strength: string | null;
  improvement_areas: string[];
  positive_trends: string[];
}
