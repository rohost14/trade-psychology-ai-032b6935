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

// Default detection thresholds — overridden by buildPatternConfig() from user profile
const DEFAULT_CONFIG: PatternDetectionConfig = {
  overtrading_trades_per_30min: 8,
  overtrading_trades_per_hour: 12,
  revenge_max_time_after_loss_minutes: 10,
  revenge_min_loss_to_trigger: 500,
  fomo_rapid_entry_after_big_move_minutes: 2,
  fomo_big_move_threshold_percent: 1,
  position_max_percent_of_capital: 10,
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
  consecutive_losses: 'Consecutive Losses',
  capital_drawdown: 'Capital Drawdown',
  same_instrument_chasing: 'Same Instrument Chasing',
  all_loss_session: 'All-Loss Session',
};

// Generate deterministic ID based on pattern data
// This ensures the same pattern doesn't create duplicate alerts
function generatePatternId(type: PatternType, tradeIds: string[], timestamp: string): string {
  const sortedIds = [...tradeIds].sort().join('_');
  // Create a stable hash from the pattern signature
  const signature = `${type}_${sortedIds}_${timestamp.slice(0, 10)}`; // Use date portion only
  return signature;
}

// ---------------------------------------------------------------------------
// Session boundary helper — filter to today's trades in IST
// This prevents cross-day pattern accumulation (consecutive_losses, etc.)
// ---------------------------------------------------------------------------
function getTodayTradesIST(trades: Trade[]): Trade[] {
  const todayIST = new Date().toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' });
  return trades.filter(t =>
    new Date(t.traded_at).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' }) === todayIST
  );
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
  // Track which trades have already been included in a detected cluster
  // to avoid overlapping windows generating near-duplicate patterns
  const usedTradeIndices = new Set<number>();

  for (let i = 0; i < sortedTrades.length; i++) {
    // Skip trades already part of a detected cluster
    if (usedTradeIndices.has(i)) continue;

    const windowStart = new Date(sortedTrades[i].traded_at).getTime();
    const windowEnd = windowStart + 30 * 60 * 1000; // 30 minutes

    const tradesInWindow: Trade[] = [];
    const indicesInWindow: number[] = [];
    for (let j = i; j < sortedTrades.length; j++) {
      const tradeTime = new Date(sortedTrades[j].traded_at).getTime();
      if (tradeTime >= windowStart && tradeTime <= windowEnd) {
        tradesInWindow.push(sortedTrades[j]);
        indicesInWindow.push(j);
      }
    }

    if (tradesInWindow.length >= config.overtrading_trades_per_30min) {
      // Mark all trades in this cluster as used so subsequent windows don't re-detect them
      for (const idx of indicesInWindow) usedTradeIndices.add(idx);

      {
        const pnlInWindow = tradesInWindow.reduce((sum, t) => sum + t.pnl, 0);
        const severity = getSeverity(tradesInWindow.length, [
          config.overtrading_trades_per_30min,
          Math.ceil(config.overtrading_trades_per_30min * 1.4),
          Math.ceil(config.overtrading_trades_per_30min * 2),
        ]);

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
          frequency_this_week: 0, // Computed in detectAllPatterns from historicalPatterns
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

        // Fix 3: Always factual insight — no misleading ₹0 from entry pnl
        const historicalInsight = `Re-entered ${timeDiff.toFixed(1)} min after a ₹${Math.abs(currentTrade.pnl).toLocaleString('en-IN')} loss`;

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
          historical_insight: historicalInsight,
          frequency_this_week: 0,
          frequency_this_month: 0,
          estimated_cost: Math.abs(currentTrade.pnl) * 0.5, // attribute 50% to revenge behavior
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
    // Use latest trade timestamp (not new Date()) to keep ID deterministic across calls
    const latestTimestamp = trades.reduce((latest, t) => {
      const tt = new Date(t.traded_at).getTime();
      return tt > latest ? tt : latest;
    }, 0);
    patterns.push({
      id: generatePatternId('loss_aversion', tradeIds, new Date(latestTimestamp).toISOString()),
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
    // Fix 2: Instrument-aware capital-at-risk estimation
    // Options buyers: price IS the premium — that's the exact capital at risk
    // Futures/options sellers: use ~10% SPAN margin approximation
    const isOption = trade.instrument_type?.includes('CE') || trade.instrument_type?.includes('PE');
    const isFuture = trade.instrument_type === 'FUT' || (!isOption && !trade.instrument_type?.includes('EQ'));

    let positionValue: number;
    if (isOption) {
      positionValue = trade.price * trade.quantity; // premium paid — exact for buyers
    } else if (isFuture) {
      positionValue = trade.price * trade.quantity * 0.1; // ~10% SPAN margin estimate
    } else {
      positionValue = trade.price * trade.quantity; // delivery equity — use full notional
    }

    const percentOfCapital = (positionValue / capital) * 100;

    if (percentOfCapital > config.position_max_percent_of_capital) {
      patterns.push({
        id: generatePatternId('position_sizing', [trade.id], trade.traded_at),
        type: 'position_sizing',
        name: PATTERN_NAMES.position_sizing,
        severity: getSeverity(percentOfCapital, [
          config.position_max_percent_of_capital,
          config.position_max_percent_of_capital * 2,
          config.position_max_percent_of_capital * 4,
        ]),
        detected_at: trade.traded_at,
        description: `Position size was ${percentOfCapital.toFixed(1)}% of capital`,
        evidence: {
          trades_involved: [trade.id],
          time_window_minutes: 0,
          trigger_condition: `Position > ${config.position_max_percent_of_capital}% of capital`,
          threshold_exceeded_by: ((percentOfCapital - config.position_max_percent_of_capital) / config.position_max_percent_of_capital) * 100,
        },
        // Fix 4: Always factual position context (not pnl which is 0 for entries)
        historical_insight: `This position was ${percentOfCapital.toFixed(1)}% of your capital (₹${positionValue.toLocaleString('en-IN')})`,
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
// CONSECUTIVE LOSSES DETECTION
// ============================================

export function detectConsecutiveLosses(trades: Trade[]): BehaviorPattern[] {
  const patterns: BehaviorPattern[] = [];

  // Fix 7: Treat breakeven trades (|pnl| < ₹50) as neutral — exclude from streak
  // Filter to exit events only and ignore scratch trades
  const exits = trades.filter((t) => Math.abs(t.pnl) > 50);
  if (exits.length < 3) return patterns;

  // Sort by time (oldest first)
  const sorted = [...exits].sort(
    (a, b) => new Date(a.traded_at).getTime() - new Date(b.traded_at).getTime()
  );

  // Count consecutive losses from most recent
  let streak = 0;
  const losingIds: string[] = [];
  let totalLoss = 0;

  for (let i = sorted.length - 1; i >= 0; i--) {
    if (sorted[i].pnl < 0) {
      streak++;
      losingIds.push(sorted[i].id);
      totalLoss += Math.abs(sorted[i].pnl);
    } else {
      break;
    }
  }

  if (streak >= 3) {
    const severity = getSeverity(streak, [3, 4, 5]);

    patterns.push({
      id: generatePatternId('consecutive_losses', losingIds, sorted[sorted.length - 1].traded_at),
      type: 'consecutive_losses',
      name: PATTERN_NAMES.consecutive_losses,
      severity,
      detected_at: sorted[sorted.length - 1].traded_at,
      description: `${streak} consecutive losing trades, total loss ₹${totalLoss.toLocaleString('en-IN')}`,
      evidence: {
        trades_involved: losingIds,
        time_window_minutes: 0,
        trigger_condition: `${streak} consecutive losses (threshold: 3)`,
        threshold_exceeded_by: ((streak - 3) / 3) * 100,
      },
      historical_insight: `Loss spiral: ${streak} trades in a row lost a combined ₹${totalLoss.toLocaleString('en-IN')}`,
      frequency_this_week: 0,
      frequency_this_month: 0,
      estimated_cost: totalLoss,
      insight: 'After 3+ consecutive losses, win rate typically drops further. Consider taking a break to reset mentally.',
    });
  }

  return patterns;
}

// ============================================
// CAPITAL DRAWDOWN DETECTION
// ============================================

export function detectCapitalDrawdown(
  trades: Trade[],
  capital: number
): BehaviorPattern[] {
  const patterns: BehaviorPattern[] = [];

  if (capital <= 0) return patterns;

  // Filter to exit events only (pnl !== 0)
  const exits = trades.filter((t) => t.pnl !== 0);
  if (exits.length === 0) return patterns;

  // Sum session P&L
  const sessionPnl = exits.reduce((sum, t) => sum + t.pnl, 0);

  // Only trigger on losses
  if (sessionPnl >= 0) return patterns;

  const drawdownPercent = (Math.abs(sessionPnl) / capital) * 100;

  if (drawdownPercent >= 10) {
    const severity = getSeverity(drawdownPercent, [10, 25, 40]);
    const tradeIds = exits.filter((t) => t.pnl < 0).map((t) => t.id);
    const latestTimestamp = exits.reduce((latest, t) => {
      const tt = new Date(t.traded_at).getTime();
      return tt > latest ? tt : latest;
    }, 0);

    patterns.push({
      id: generatePatternId('capital_drawdown', tradeIds, new Date(latestTimestamp).toISOString()),
      type: 'capital_drawdown',
      name: PATTERN_NAMES.capital_drawdown,
      severity,
      detected_at: new Date(latestTimestamp).toISOString(),
      description: `Session drawdown: ₹${Math.abs(sessionPnl).toLocaleString('en-IN')} (${drawdownPercent.toFixed(1)}% of capital)`,
      evidence: {
        trades_involved: tradeIds,
        time_window_minutes: 0,
        trigger_condition: `Session loss > 10% of capital (current: ${drawdownPercent.toFixed(1)}%)`,
        threshold_exceeded_by: ((drawdownPercent - 10) / 10) * 100,
      },
      historical_insight: `You've lost ${drawdownPercent.toFixed(1)}% of your capital in this session`,
      frequency_this_week: 0,
      frequency_this_month: 0,
      estimated_cost: Math.abs(sessionPnl),
      insight: 'Protecting capital is priority #1. Professional traders rarely risk more than 2% per trade or 6% per day.',
    });
  }

  return patterns;
}

// ============================================
// SAME INSTRUMENT CHASING DETECTION
// ============================================

export function detectSameInstrumentChasing(trades: Trade[]): BehaviorPattern[] {
  const patterns: BehaviorPattern[] = [];

  // Filter to exit events only (pnl !== 0)
  const exits = trades.filter((t) => t.pnl !== 0);
  if (exits.length < 2) return patterns;

  // Fix 6: Only count losses on same symbol within last 3 hours
  const threeHoursAgo = Date.now() - 3 * 3600 * 1000;
  const recentExits = exits.filter(t => new Date(t.traded_at).getTime() > threeHoursAgo);

  // Group losses by tradingsymbol
  const lossesBySymbol = new Map<string, Trade[]>();
  for (const t of recentExits) {
    if (t.pnl < 0) {
      const existing = lossesBySymbol.get(t.tradingsymbol) || [];
      existing.push(t);
      lossesBySymbol.set(t.tradingsymbol, existing);
    }
  }

  for (const [symbol, lossTrades] of lossesBySymbol) {
    if (lossTrades.length >= 2) {
      const severity = getSeverity(lossTrades.length, [2, 3, 4]);
      const totalLoss = lossTrades.reduce((sum, t) => sum + Math.abs(t.pnl), 0);
      const tradeIds = lossTrades.map((t) => t.id);
      const latestTimestamp = lossTrades.reduce((latest, t) => {
        const tt = new Date(t.traded_at).getTime();
        return tt > latest ? tt : latest;
      }, 0);

      patterns.push({
        id: generatePatternId('same_instrument_chasing', tradeIds, new Date(latestTimestamp).toISOString()),
        type: 'same_instrument_chasing',
        name: PATTERN_NAMES.same_instrument_chasing,
        severity,
        detected_at: new Date(latestTimestamp).toISOString(),
        description: `${lossTrades.length} losing trades on ${symbol} in the last 3 hours, total loss ₹${totalLoss.toLocaleString('en-IN')}`,
        evidence: {
          trades_involved: tradeIds,
          time_window_minutes: 180,
          trigger_condition: `${lossTrades.length} losses on same instrument in 3h (threshold: 2)`,
          threshold_exceeded_by: ((lossTrades.length - 2) / 2) * 100,
        },
        historical_insight: `You keep going back to ${symbol} despite losses. This is a common fixation pattern.`,
        frequency_this_week: 0,
        frequency_this_month: 0,
        estimated_cost: totalLoss,
        insight: 'Repeatedly losing on the same instrument suggests fixation. Consider moving to a different setup.',
      });
    }
  }

  return patterns;
}

// ============================================
// ALL-LOSS SESSION DETECTION
// ============================================

export function detectAllLossSession(trades: Trade[]): BehaviorPattern[] {
  const patterns: BehaviorPattern[] = [];

  // Filter to exit events only (pnl !== 0)
  const exits = trades.filter((t) => t.pnl !== 0);
  if (exits.length < 3) return patterns;

  const winners = exits.filter((t) => t.pnl > 0);
  const losers = exits.filter((t) => t.pnl < 0);

  // Trigger only if 0 winners and 3+ losers
  if (winners.length > 0 || losers.length < 3) return patterns;

  const severity = getSeverity(losers.length, [3, 5, 7]);
  const totalLoss = losers.reduce((sum, t) => sum + Math.abs(t.pnl), 0);
  const tradeIds = losers.map((t) => t.id);
  const latestTimestamp = losers.reduce((latest, t) => {
    const tt = new Date(t.traded_at).getTime();
    return tt > latest ? tt : latest;
  }, 0);

  patterns.push({
    id: generatePatternId('all_loss_session', tradeIds, new Date(latestTimestamp).toISOString()),
    type: 'all_loss_session',
    name: PATTERN_NAMES.all_loss_session,
    severity,
    detected_at: new Date(latestTimestamp).toISOString(),
    description: `All ${losers.length} trades lost today — zero winners. Total loss ₹${totalLoss.toLocaleString('en-IN')}`,
    evidence: {
      trades_involved: tradeIds,
      time_window_minutes: 0,
      trigger_condition: `${losers.length} exits, 0 winners (threshold: 3+ exits, 0 wins)`,
      threshold_exceeded_by: ((losers.length - 3) / 3) * 100,
    },
    historical_insight: `Zero-win sessions are a strong signal that your edge is absent today`,
    frequency_this_week: 0,
    frequency_this_month: 0,
    estimated_cost: totalLoss,
    insight: 'When every trade loses, the market or your setup is against you today. Stop trading and review tomorrow.',
  });

  return patterns;
}

// ============================================
// MAIN DETECTION FUNCTION
// ============================================

export function detectAllPatterns(
  trades: Trade[],
  capital: number = 100000,
  config: PatternDetectionConfig = DEFAULT_CONFIG,
  historicalPatterns: Array<{ type: PatternType; detected_at: string }> = [],
): BehaviorPattern[] {
  // Fix 1: Session boundary — filter to today's IST trades before detection
  // This prevents cross-day accumulation (consecutive_losses, same_instrument_chasing, etc.)
  const todayTrades = getTodayTradesIST(trades);

  const allPatterns: BehaviorPattern[] = [];

  // Run all detectors on today's trades only
  allPatterns.push(...detectOvertrading(todayTrades, config));
  allPatterns.push(...detectRevengeTading(todayTrades, config));
  allPatterns.push(...detectLossAversion(todayTrades));
  allPatterns.push(...detectPositionSizing(todayTrades, capital, config));
  allPatterns.push(...detectConsecutiveLosses(todayTrades));
  allPatterns.push(...detectCapitalDrawdown(todayTrades, capital));
  allPatterns.push(...detectSameInstrumentChasing(todayTrades));
  allPatterns.push(...detectAllLossSession(todayTrades));

  // Fix 5: Compute frequency_this_week and frequency_this_month from historicalPatterns
  const weekAgo = Date.now() - 7 * 86400000;
  const monthAgo = Date.now() - 30 * 86400000;

  const patternsWithFrequency = allPatterns.map(p => ({
    ...p,
    frequency_this_week: historicalPatterns.filter(h =>
      h.type === p.type && new Date(h.detected_at).getTime() > weekAgo
    ).length,
    frequency_this_month: historicalPatterns.filter(h =>
      h.type === p.type && new Date(h.detected_at).getTime() > monthAgo
    ).length,
  }));

  // Sort by severity (critical first) then by time (recent first)
  const severityOrder: Record<PatternSeverity, number> = {
    critical: 0,
    high: 1,
    medium: 2,
    low: 3,
  };

  patternsWithFrequency.sort((a, b) => {
    const severityDiff = severityOrder[a.severity] - severityOrder[b.severity];
    if (severityDiff !== 0) return severityDiff;
    return new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime();
  });

  return patternsWithFrequency;
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

// Get stats for a list of patterns
export function getPatternStats(patterns: BehaviorPattern[]) {
  const by_severity: Record<PatternSeverity, number> = {
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
  };

  const by_type: Partial<Record<PatternType, number>> = {};
  let total_cost = 0;

  for (const pattern of patterns) {
    by_severity[pattern.severity]++;
    by_type[pattern.type] = (by_type[pattern.type] || 0) + 1;
    total_cost += pattern.estimated_cost || 0;
  }

  return {
    total: patterns.length,
    by_severity,
    by_type,
    total_cost,
  };
}
