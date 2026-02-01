// Pattern Detection Engine for TradeMentor AI
// Detects behavioral patterns from trade data
// Philosophy: Show facts, not restrictions

import { Trade } from '@/types/api';
import {
  BehaviorPattern,
  PatternType,
  PatternSeverity,
  PatternDetectionConfig,
} from '@/types/patterns';

// Default detection thresholds
const DEFAULT_CONFIG: PatternDetectionConfig = {
  overtrading_trades_per_30min: 5,
  overtrading_trades_per_hour: 8,
  revenge_max_time_after_loss_minutes: 5,
  revenge_min_loss_to_trigger: 500,
  fomo_rapid_entry_after_big_move_minutes: 2,
  fomo_big_move_threshold_percent: 1,
  position_max_percent_of_capital: 5,
  early_exit_min_profit_missed_percent: 50,
};

// Pattern name mappings
const PATTERN_NAMES: Record<PatternType, string> = {
  overtrading: 'Overtrading',
  revenge_trading: 'Revenge Trading',
  fomo: 'FOMO Entry',
  no_stoploss: 'No Stop Loss',
  early_exit: 'Early Exit',
  position_sizing: 'Position Size Warning',
  loss_aversion: 'Loss Aversion',
  winning_streak_overconfidence: 'Overconfidence',
};

// Generate deterministic ID based on pattern data
// This ensures the same pattern doesn't create duplicate alerts
function generatePatternId(type: PatternType, tradeIds: string[], timestamp: string): string {
  const sortedIds = [...tradeIds].sort().join('_');
  // Create a stable hash from the pattern signature
  const signature = `${type}_${sortedIds}_${timestamp.slice(0, 10)}`; // Use date portion only
  return signature;
}

// ============================================
// OVERTRADING DETECTION
// ============================================

export function detectOvertrading(
  trades: Trade[],
  config: PatternDetectionConfig = DEFAULT_CONFIG
): BehaviorPattern[] {
  const patterns: BehaviorPattern[] = [];
  
  if (trades.length < 3) return patterns;
  
  // Sort trades by time
  const sortedTrades = [...trades].sort(
    (a, b) => new Date(a.traded_at).getTime() - new Date(b.traded_at).getTime()
  );
  
  // Check for clusters of trades within 30 minutes
  for (let i = 0; i < sortedTrades.length; i++) {
    const windowStart = new Date(sortedTrades[i].traded_at).getTime();
    const windowEnd = windowStart + 30 * 60 * 1000; // 30 minutes
    
    const tradesInWindow = sortedTrades.filter((t) => {
      const tradeTime = new Date(t.traded_at).getTime();
      return tradeTime >= windowStart && tradeTime <= windowEnd;
    });
    
    if (tradesInWindow.length >= config.overtrading_trades_per_30min) {
      // Check if we already detected this cluster
      const existingPattern = patterns.find((p) => {
        const existingStart = new Date(p.detected_at).getTime();
        return Math.abs(existingStart - windowStart) < 30 * 60 * 1000;
      });
      
      if (!existingPattern) {
        const pnlInWindow = tradesInWindow.reduce((sum, t) => sum + t.pnl, 0);
        const severity = getSeverity(tradesInWindow.length, [5, 7, 10]);
        
        const tradeIds = tradesInWindow.map((t) => t.id);
        patterns.push({
          id: generatePatternId('overtrading', tradeIds, sortedTrades[i].traded_at),
          type: 'overtrading',
          name: PATTERN_NAMES.overtrading,
          severity,
          detected_at: sortedTrades[i].traded_at,
          description: `${tradesInWindow.length} trades executed in 30 minutes`,
          evidence: {
            trades_involved: tradesInWindow.map((t) => t.id),
            time_window_minutes: 30,
            trigger_condition: `${tradesInWindow.length} trades in 30 minutes (threshold: ${config.overtrading_trades_per_30min})`,
            threshold_exceeded_by: ((tradesInWindow.length - config.overtrading_trades_per_30min) / config.overtrading_trades_per_30min) * 100,
          },
          historical_insight: pnlInWindow < 0
            ? `This session resulted in a loss of ₹${Math.abs(pnlInWindow).toLocaleString('en-IN')}`
            : `This session had a profit of ₹${pnlInWindow.toLocaleString('en-IN')}`,
          frequency_this_week: 0, // Will be calculated separately
          frequency_this_month: 0,
          estimated_cost: pnlInWindow < 0 ? Math.abs(pnlInWindow) : 0,
          insight: 'Data shows win rate typically drops after 5+ trades in quick succession. Consider pausing between trades.',
        });
      }
    }
  }
  
  return patterns;
}

// ============================================
// REVENGE TRADING DETECTION
// ============================================

export function detectRevengeTading(
  trades: Trade[],
  config: PatternDetectionConfig = DEFAULT_CONFIG
): BehaviorPattern[] {
  const patterns: BehaviorPattern[] = [];
  
  if (trades.length < 2) return patterns;
  
  const sortedTrades = [...trades].sort(
    (a, b) => new Date(a.traded_at).getTime() - new Date(b.traded_at).getTime()
  );
  
  for (let i = 0; i < sortedTrades.length - 1; i++) {
    const currentTrade = sortedTrades[i];
    const nextTrade = sortedTrades[i + 1];
    
    // Check if current trade was a significant loss
    if (currentTrade.pnl < -config.revenge_min_loss_to_trigger) {
      const timeDiff = (new Date(nextTrade.traded_at).getTime() - new Date(currentTrade.traded_at).getTime()) / (60 * 1000);
      
      // Quick re-entry after loss = revenge trading
      if (timeDiff <= config.revenge_max_time_after_loss_minutes) {
        const severity = getSeverity(Math.abs(currentTrade.pnl), [500, 2000, 5000]);
        
        const tradeIds = [currentTrade.id, nextTrade.id];
        patterns.push({
          id: generatePatternId('revenge_trading', tradeIds, nextTrade.traded_at),
          type: 'revenge_trading',
          name: PATTERN_NAMES.revenge_trading,
          severity,
          detected_at: nextTrade.traded_at,
          description: `New trade ${timeDiff.toFixed(1)} minutes after ₹${Math.abs(currentTrade.pnl).toLocaleString('en-IN')} loss`,
          evidence: {
            trades_involved: [currentTrade.id, nextTrade.id],
            time_window_minutes: timeDiff,
            trigger_condition: `Trade within ${config.revenge_max_time_after_loss_minutes}min after loss > ₹${config.revenge_min_loss_to_trigger}`,
            threshold_exceeded_by: ((config.revenge_max_time_after_loss_minutes - timeDiff) / config.revenge_max_time_after_loss_minutes) * 100,
          },
          historical_insight: nextTrade.pnl < 0
            ? `This revenge trade also lost ₹${Math.abs(nextTrade.pnl).toLocaleString('en-IN')}`
            : `This trade recovered ₹${nextTrade.pnl.toLocaleString('en-IN')}`,
          frequency_this_week: 0,
          frequency_this_month: 0,
          estimated_cost: nextTrade.pnl < 0 ? Math.abs(nextTrade.pnl) : 0,
          insight: 'Revenge trades historically have a 40% lower win rate. Taking a 15-minute break helps reset decision-making.',
        });
      }
    }
  }
  
  return patterns;
}

// ============================================
// LOSS AVERSION DETECTION
// ============================================

export function detectLossAversion(trades: Trade[]): BehaviorPattern[] {
  const patterns: BehaviorPattern[] = [];
  
  if (trades.length < 5) return patterns;
  
  // Calculate average hold time for winners vs losers
  // This would need entry/exit times - using PnL ratio as proxy
  
  const winners = trades.filter((t) => t.pnl > 0);
  const losers = trades.filter((t) => t.pnl < 0);
  
  if (winners.length === 0 || losers.length === 0) return patterns;
  
  const avgWinSize = winners.reduce((sum, t) => sum + t.pnl, 0) / winners.length;
  const avgLossSize = Math.abs(losers.reduce((sum, t) => sum + t.pnl, 0) / losers.length);
  
  // If average loss is significantly larger than average win = loss aversion
  // (holding losers too long, cutting winners too early)
  const ratio = avgLossSize / avgWinSize;
  
  if (ratio > 1.5) {
    const totalExcessLoss = losers.reduce((sum, t) => {
      const excessLoss = Math.abs(t.pnl) - avgWinSize;
      return sum + (excessLoss > 0 ? excessLoss : 0);
    }, 0);
    
    const tradeIds = losers.map((t) => t.id);
    patterns.push({
      id: generatePatternId('loss_aversion', tradeIds, new Date().toISOString()),
      type: 'loss_aversion',
      name: PATTERN_NAMES.loss_aversion,
      severity: getSeverity(ratio, [1.5, 2, 3]),
      detected_at: new Date().toISOString(),
      description: `Average loss (₹${avgLossSize.toLocaleString('en-IN')}) is ${ratio.toFixed(1)}x larger than average win (₹${avgWinSize.toLocaleString('en-IN')})`,
      evidence: {
        trades_involved: losers.map((t) => t.id),
        time_window_minutes: 0,
        trigger_condition: `Loss/Win ratio > 1.5 (current: ${ratio.toFixed(2)})`,
        threshold_exceeded_by: ((ratio - 1.5) / 1.5) * 100,
      },
      historical_insight: `This pattern suggests holding losers too long or cutting winners too early`,
      frequency_this_week: 0,
      frequency_this_month: 0,
      estimated_cost: totalExcessLoss,
      insight: 'Consider setting symmetric stop-loss and take-profit levels to maintain balanced risk-reward.',
    });
  }
  
  return patterns;
}

// ============================================
// POSITION SIZING DETECTION
// ============================================

export function detectPositionSizing(
  trades: Trade[],
  capital: number,
  config: PatternDetectionConfig = DEFAULT_CONFIG
): BehaviorPattern[] {
  const patterns: BehaviorPattern[] = [];
  
  if (capital <= 0) return patterns;
  
  for (const trade of trades) {
    const tradeValue = trade.price * trade.quantity;
    const percentOfCapital = (tradeValue / capital) * 100;
    
    if (percentOfCapital > config.position_max_percent_of_capital) {
      patterns.push({
        id: generatePatternId('position_sizing', [trade.id], trade.traded_at),
        type: 'position_sizing',
        name: PATTERN_NAMES.position_sizing,
        severity: getSeverity(percentOfCapital, [5, 10, 20]),
        detected_at: trade.traded_at,
        description: `Position size was ${percentOfCapital.toFixed(1)}% of capital`,
        evidence: {
          trades_involved: [trade.id],
          time_window_minutes: 0,
          trigger_condition: `Position > ${config.position_max_percent_of_capital}% of capital`,
          threshold_exceeded_by: ((percentOfCapital - config.position_max_percent_of_capital) / config.position_max_percent_of_capital) * 100,
        },
        historical_insight: trade.pnl < 0
          ? `This oversized position lost ₹${Math.abs(trade.pnl).toLocaleString('en-IN')}`
          : `Position was profitable: ₹${trade.pnl.toLocaleString('en-IN')}`,
        frequency_this_week: 0,
        frequency_this_month: 0,
        estimated_cost: trade.pnl < 0 ? Math.abs(trade.pnl) * 0.5 : 0, // Attribute 50% to sizing
        insight: 'Large positions correlate with 2x more emotional decisions. Keeping positions smaller helps maintain discipline.',
      });
    }
  }
  
  return patterns;
}

// ============================================
// MAIN DETECTION FUNCTION
// ============================================

export function detectAllPatterns(
  trades: Trade[],
  capital: number = 100000,
  config: PatternDetectionConfig = DEFAULT_CONFIG
): BehaviorPattern[] {
  const allPatterns: BehaviorPattern[] = [];
  
  // Run all detectors
  allPatterns.push(...detectOvertrading(trades, config));
  allPatterns.push(...detectRevengeTading(trades, config));
  allPatterns.push(...detectLossAversion(trades));
  allPatterns.push(...detectPositionSizing(trades, capital, config));
  
  // Sort by severity (critical first) then by time (recent first)
  const severityOrder: Record<PatternSeverity, number> = {
    critical: 0,
    high: 1,
    medium: 2,
    low: 3,
  };
  
  allPatterns.sort((a, b) => {
    const severityDiff = severityOrder[a.severity] - severityOrder[b.severity];
    if (severityDiff !== 0) return severityDiff;
    return new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime();
  });
  
  return allPatterns;
}

// ============================================
// HELPER FUNCTIONS
// ============================================

function getSeverity(value: number, thresholds: [number, number, number]): PatternSeverity {
  if (value >= thresholds[2]) return 'critical';
  if (value >= thresholds[1]) return 'high';
  if (value >= thresholds[0]) return 'medium';
  return 'low';
}

// Calculate pattern frequency in a time window
export function calculatePatternFrequency(
  patterns: BehaviorPattern[],
  days: number
): Map<PatternType, number> {
  const frequency = new Map<PatternType, number>();
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - days);
  
  for (const pattern of patterns) {
    if (new Date(pattern.detected_at) >= cutoffDate) {
      const current = frequency.get(pattern.type) || 0;
      frequency.set(pattern.type, current + 1);
    }
  }
  
  return frequency;
}

// Get pattern statistics
export function getPatternStats(patterns: BehaviorPattern[]): {
  total: number;
  by_severity: Record<PatternSeverity, number>;
  by_type: Record<PatternType, number>;
  total_cost: number;
} {
  const stats = {
    total: patterns.length,
    by_severity: { critical: 0, high: 0, medium: 0, low: 0 } as Record<PatternSeverity, number>,
    by_type: {} as Record<PatternType, number>,
    total_cost: 0,
  };
  
  for (const pattern of patterns) {
    stats.by_severity[pattern.severity]++;
    stats.by_type[pattern.type] = (stats.by_type[pattern.type] || 0) + 1;
    stats.total_cost += pattern.estimated_cost;
  }
  
  return stats;
}
