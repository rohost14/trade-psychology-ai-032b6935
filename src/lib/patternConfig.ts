/**
 * Pattern Detection Configuration Builder
 *
 * Builds PatternDetectionConfig from UserProfile using 3-tier threshold system:
 * Tier 1: User-declared values in profile (highest priority)
 * Tier 2: Universal cold-start defaults (style labels removed — same trader can scalp
 *         on expiry day and hold overnight on slow days; labeling is inaccurate)
 * Tier 3: Universal floors (never fire below these)
 */

import { PatternDetectionConfig } from '@/types/patterns';

export interface UserProfileThresholds {
  daily_trade_limit?: number;
  cooldown_after_loss?: number;
  trading_capital?: number;
  max_position_size?: number;
  sl_percent_futures?: number;
  sl_percent_options?: number;
}

// Tier 2: Universal cold-start defaults for all traders
const COLD_START_DEFAULTS = {
  overtrading_trades_per_30min: 8,
  revenge_max_time_minutes: 10,
};

export function buildPatternConfig(profile: UserProfileThresholds | null): PatternDetectionConfig {
  // Overtrading threshold: user daily_trade_limit → half of that = 30-min burst proxy
  const overtrading_trades_per_30min = profile?.daily_trade_limit
    ? Math.ceil(profile.daily_trade_limit / 2)
    : COLD_START_DEFAULTS.overtrading_trades_per_30min;

  // Revenge window from user cooldown_after_loss, else universal default
  const revenge_max_time_after_loss_minutes =
    profile?.cooldown_after_loss ?? COLD_START_DEFAULTS.revenge_max_time_minutes;

  // Minimum loss to trigger revenge alert: 0.5% of capital (not hardcoded ₹500)
  const revenge_min_loss_to_trigger = profile?.trading_capital
    ? profile.trading_capital * 0.005
    : 500;

  // Position sizing: if user has capital + max_position_size → derive %
  // max_position_size in Settings is stored as % of capital (e.g., 10.0 = 10%)
  const position_max_percent_of_capital = profile?.max_position_size != null
    ? profile.max_position_size        // already stored as %
    : 10;                              // default 10% (not 5% notional)

  return {
    overtrading_trades_per_30min,
    overtrading_trades_per_hour: Math.ceil(overtrading_trades_per_30min * 1.5),
    revenge_max_time_after_loss_minutes,
    revenge_min_loss_to_trigger,
    fomo_rapid_entry_after_big_move_minutes: 2,  // not user-adjustable yet
    fomo_big_move_threshold_percent: 1,           // not user-adjustable yet
    position_max_percent_of_capital,
    early_exit_min_profit_missed_percent: 50,     // not user-adjustable yet
  };
}
