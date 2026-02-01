// Emotional Tax Calculator for TradeMentor AI
// Calculates the ₹ cost of breaking trading rules
// Philosophy: Show the data, let traders make informed decisions

import { Trade } from '@/types/api';
import {
  BehaviorPattern,
  EmotionalTax,
  EmotionalTaxBreakdown,
  PatternType,
  TradingGoals,
  GoalAdherence,
} from '@/types/patterns';

// Pattern display names
const PATTERN_NAMES: Record<PatternType, string> = {
  overtrading: 'Overtrading',
  revenge_trading: 'Revenge Trading',
  fomo: 'FOMO Entry',
  no_stoploss: 'No Stop Loss',
  early_exit: 'Early Exit',
  position_sizing: 'Position Sizing',
  loss_aversion: 'Loss Aversion',
  winning_streak_overconfidence: 'Overconfidence',
};

// ============================================
// EMOTIONAL TAX CALCULATION
// ============================================

export function calculateEmotionalTax(
  patterns: BehaviorPattern[],
  trades: Trade[]
): EmotionalTax {
  const now = new Date();
  const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
  
  // Calculate breakdown by pattern type
  const breakdownMap = new Map<PatternType, { occurrences: number; totalCost: number }>();
  
  for (const pattern of patterns) {
    const existing = breakdownMap.get(pattern.type) || { occurrences: 0, totalCost: 0 };
    existing.occurrences++;
    existing.totalCost += pattern.estimated_cost;
    breakdownMap.set(pattern.type, existing);
  }
  
  // Convert to breakdown array
  const breakdown: EmotionalTaxBreakdown[] = [];
  let totalCostAllTime = 0;
  let totalCostThisWeek = 0;
  let totalCostThisMonth = 0;
  
  for (const [patternType, data] of breakdownMap) {
    const avgCost = data.occurrences > 0 ? data.totalCost / data.occurrences : 0;
    
    breakdown.push({
      pattern_type: patternType,
      pattern_name: PATTERN_NAMES[patternType],
      occurrences: data.occurrences,
      total_cost: data.totalCost,
      avg_cost_per_occurrence: avgCost,
      insight: generateInsight(patternType, data.occurrences, data.totalCost, avgCost),
    });
    
    totalCostAllTime += data.totalCost;
  }
  
  // Calculate weekly and monthly costs
  for (const pattern of patterns) {
    const patternDate = new Date(pattern.detected_at);
    if (patternDate >= weekAgo) {
      totalCostThisWeek += pattern.estimated_cost;
    }
    if (patternDate >= monthAgo) {
      totalCostThisMonth += pattern.estimated_cost;
    }
  }
  
  // Find worst pattern
  const sortedBreakdown = [...breakdown].sort((a, b) => b.total_cost - a.total_cost);
  const worstPattern = sortedBreakdown[0];
  
  // Calculate improvement vs last month (would need historical data)
  // For now, estimate based on trend
  const improvementVsLastMonth = calculateImprovementTrend(patterns);
  
  return {
    total_cost_all_time: totalCostAllTime,
    total_cost_this_month: totalCostThisMonth,
    total_cost_this_week: totalCostThisWeek,
    breakdown: sortedBreakdown,
    worst_pattern: worstPattern?.pattern_type || 'overtrading',
    worst_pattern_cost: worstPattern?.total_cost || 0,
    improvement_vs_last_month: improvementVsLastMonth,
  };
}

// ============================================
// GOAL ADHERENCE CALCULATION
// ============================================

export function calculateGoalAdherence(
  trades: Trade[],
  patterns: BehaviorPattern[],
  goals: TradingGoals
): GoalAdherence[] {
  const adherence: GoalAdherence[] = [];
  
  // Max trades per day adherence
  const tradesByDay = groupTradesByDay(trades);
  let daysFollowed = 0;
  let daysBroken = 0;
  let costWhenBroken = 0;
  
  for (const [date, dayTrades] of tradesByDay) {
    if (dayTrades.length <= goals.max_trades_per_day) {
      daysFollowed++;
    } else {
      daysBroken++;
      // Estimate cost: sum of losses after exceeding limit
      const excessTrades = dayTrades.slice(goals.max_trades_per_day);
      costWhenBroken += excessTrades
        .filter((t) => t.pnl < 0)
        .reduce((sum, t) => sum + Math.abs(t.pnl), 0);
    }
  }
  
  adherence.push({
    goal_name: 'Max Trades Per Day',
    goal_value: `${goals.max_trades_per_day} trades`,
    times_followed: daysFollowed,
    times_broken: daysBroken,
    adherence_percent: calculateAdherencePercent(daysFollowed, daysBroken),
    cost_when_broken: costWhenBroken,
    trend: daysBroken === 0 ? 'improving' : daysBroken > 3 ? 'declining' : 'stable',
    trend_vs_last_week: 0,
  });
  
  // Max daily loss adherence
  let daysWithinLimit = 0;
  let daysExceeded = 0;
  let exceededCost = 0;
  
  for (const [date, dayTrades] of tradesByDay) {
    const dayPnL = dayTrades.reduce((sum, t) => sum + t.pnl, 0);
    if (dayPnL >= -goals.max_daily_loss) {
      daysWithinLimit++;
    } else {
      daysExceeded++;
      exceededCost += Math.abs(dayPnL) - goals.max_daily_loss;
    }
  }
  
  adherence.push({
    goal_name: 'Max Daily Loss',
    goal_value: `₹${goals.max_daily_loss.toLocaleString('en-IN')}`,
    times_followed: daysWithinLimit,
    times_broken: daysExceeded,
    adherence_percent: calculateAdherencePercent(daysWithinLimit, daysExceeded),
    cost_when_broken: exceededCost,
    trend: daysExceeded === 0 ? 'improving' : daysExceeded > 2 ? 'declining' : 'stable',
    trend_vs_last_week: 0,
  });
  
  // Risk per trade adherence
  const maxRiskAmount = (goals.starting_capital * goals.max_risk_per_trade_percent) / 100;
  let tradesWithinRisk = 0;
  let tradesExceedingRisk = 0;
  let riskExceededCost = 0;
  
  for (const trade of trades) {
    const tradeRisk = Math.abs(trade.pnl);
    if (trade.pnl < 0) {
      if (tradeRisk <= maxRiskAmount) {
        tradesWithinRisk++;
      } else {
        tradesExceedingRisk++;
        riskExceededCost += tradeRisk - maxRiskAmount;
      }
    } else {
      tradesWithinRisk++;
    }
  }
  
  adherence.push({
    goal_name: 'Max Risk Per Trade',
    goal_value: `${goals.max_risk_per_trade_percent}% (₹${maxRiskAmount.toLocaleString('en-IN')})`,
    times_followed: tradesWithinRisk,
    times_broken: tradesExceedingRisk,
    adherence_percent: calculateAdherencePercent(tradesWithinRisk, tradesExceedingRisk),
    cost_when_broken: riskExceededCost,
    trend: tradesExceedingRisk === 0 ? 'improving' : tradesExceedingRisk > 5 ? 'declining' : 'stable',
    trend_vs_last_week: 0,
  });
  
  // Stop loss adherence (based on patterns)
  const stopLossPatterns = patterns.filter((p) => p.type === 'no_stoploss');
  adherence.push({
    goal_name: 'Stop Loss Discipline',
    goal_value: goals.require_stoploss ? 'Required' : 'Recommended',
    times_followed: trades.length - stopLossPatterns.length,
    times_broken: stopLossPatterns.length,
    adherence_percent: calculateAdherencePercent(
      trades.length - stopLossPatterns.length,
      stopLossPatterns.length
    ),
    cost_when_broken: stopLossPatterns.reduce((sum, p) => sum + p.estimated_cost, 0),
    trend: stopLossPatterns.length === 0 ? 'improving' : 'stable',
    trend_vs_last_week: 0,
  });
  
  return adherence;
}

// ============================================
// HELPER FUNCTIONS
// ============================================

function generateInsight(
  patternType: PatternType,
  occurrences: number,
  totalCost: number,
  avgCost: number
): string {
  const costFormatted = `₹${totalCost.toLocaleString('en-IN')}`;
  const avgFormatted = `₹${avgCost.toLocaleString('en-IN')}`;
  
  switch (patternType) {
    case 'revenge_trading':
      return `Revenge trades cost ${costFormatted} total, averaging ${avgFormatted} each. That's typically 3x more than planned trades.`;
    case 'overtrading':
      return `Overtrading sessions cost ${costFormatted}. Win rate drops significantly after 5+ trades in quick succession.`;
    case 'position_sizing':
      return `Oversized positions cost ${costFormatted}. Smaller positions help maintain emotional discipline.`;
    case 'loss_aversion':
      return `Holding losers too long cost ${costFormatted}. Consider tighter stop losses to limit downside.`;
    case 'fomo':
      return `FOMO entries cost ${costFormatted}. Waiting for proper setup confirmation improves outcomes.`;
    case 'early_exit':
      return `Early exits left ${costFormatted} on the table. Consider trailing stops instead of fixed exits.`;
    case 'no_stoploss':
      return `Trading without stop losses cost ${costFormatted}. Always define your exit before entering.`;
    default:
      return `This pattern cost ${costFormatted} across ${occurrences} occurrences.`;
  }
}

function groupTradesByDay(trades: Trade[]): Map<string, Trade[]> {
  const grouped = new Map<string, Trade[]>();
  
  for (const trade of trades) {
    const date = new Date(trade.traded_at).toISOString().split('T')[0];
    const existing = grouped.get(date) || [];
    existing.push(trade);
    grouped.set(date, existing);
  }
  
  return grouped;
}

function calculateAdherencePercent(followed: number, broken: number): number {
  const total = followed + broken;
  if (total === 0) return 100;
  return Math.round((followed / total) * 100);
}

function calculateImprovementTrend(patterns: BehaviorPattern[]): number {
  // Simple trend calculation based on pattern frequency
  const now = new Date();
  const twoWeeksAgo = new Date(now.getTime() - 14 * 24 * 60 * 60 * 1000);
  const fourWeeksAgo = new Date(now.getTime() - 28 * 24 * 60 * 60 * 1000);
  
  const recentPatterns = patterns.filter(
    (p) => new Date(p.detected_at) >= twoWeeksAgo
  ).length;
  
  const olderPatterns = patterns.filter((p) => {
    const date = new Date(p.detected_at);
    return date >= fourWeeksAgo && date < twoWeeksAgo;
  }).length;
  
  if (olderPatterns === 0) return 0;
  
  const change = ((olderPatterns - recentPatterns) / olderPatterns) * 100;
  return Math.round(change);
}

// ============================================
// SUMMARY GENERATORS
// ============================================

export function generateEmotionalTaxSummary(tax: EmotionalTax): string {
  if (tax.total_cost_all_time === 0) {
    return "No emotional trading costs detected. You're trading with discipline!";
  }
  
  const worstPatternName = PATTERN_NAMES[tax.worst_pattern];
  const improvement = tax.improvement_vs_last_month;
  
  let summary = `Your emotional trading has cost ₹${tax.total_cost_all_time.toLocaleString('en-IN')} total. `;
  summary += `${worstPatternName} is your biggest area for improvement (₹${tax.worst_pattern_cost.toLocaleString('en-IN')}). `;
  
  if (improvement > 0) {
    summary += `Good news: You're ${improvement}% better than last month!`;
  } else if (improvement < 0) {
    summary += `This month has been ${Math.abs(improvement)}% costlier than last month.`;
  }
  
  return summary;
}

export function getTopRecommendations(tax: EmotionalTax, limit: number = 3): string[] {
  const recommendations: string[] = [];
  
  for (const breakdown of tax.breakdown.slice(0, limit)) {
    switch (breakdown.pattern_type) {
      case 'revenge_trading':
        recommendations.push('Take a 15-minute break after any loss over ₹500');
        break;
      case 'overtrading':
        recommendations.push('Set a maximum of 5 trades per 30-minute window');
        break;
      case 'position_sizing':
        recommendations.push('Cap position sizes at 5% of your capital');
        break;
      case 'loss_aversion':
        recommendations.push('Set stop losses at entry, not after the trade goes against you');
        break;
      case 'fomo':
        recommendations.push('Wait for 2 confirmations before entering after a big move');
        break;
      default:
        recommendations.push(`Address ${breakdown.pattern_name} to save ₹${breakdown.avg_cost_per_occurrence.toLocaleString('en-IN')} per occurrence`);
    }
  }
  
  return recommendations;
}
