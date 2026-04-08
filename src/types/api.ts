export interface RiskState {
  risk_state: 'safe' | 'caution' | 'danger';
  status_message: string;
  active_patterns: string[];
  last_updated: string;
}

export interface DashboardStats {
  total_pnl: number;
  win_rate: number;
  total_trades: number;
  max_drawdown: number;
}

export interface Position {
  id: string;
  tradingsymbol: string;
  exchange: string;
  instrument_type: string;
  total_quantity: number;
  average_entry_price: number;
  average_exit_price: number | null;
  realized_pnl: number;
  unrealized_pnl: number;
  // Backend returns `value`; frontend maps `last_price * qty` to `current_value` at fetch boundary
  value?: number;
  current_value: number;
  status: 'open' | 'closed';
  // P&L fields
  pnl?: number;
  day_pnl?: number;
  close_price?: number;
  buy_value?: number;
  sell_value?: number;
  // Kite-specific fields
  instrument_token?: number;
  overnight_quantity?: number;
  multiplier?: number;
  m2m?: number;
  day_buy_quantity?: number;
  day_sell_quantity?: number;
  day_buy_price?: number;
  day_sell_price?: number;
  day_buy_value?: number;
  day_sell_value?: number;
  last_price?: number;
  product?: string;
  // Timing
  first_entry_time?: string;
  last_exit_time?: string;
  holding_duration_minutes?: number;
  synced_at?: string;
}

export interface Trade {
  id: string;
  tradingsymbol: string;
  exchange: string;
  // Frontend mapped field (from `transaction_type`); used by patternDetector & AlertContext
  trade_type: 'BUY' | 'SELL';
  // Backend field name (raw API response uses this)
  transaction_type?: string;
  quantity: number;
  price: number;
  pnl: number;
  // Frontend mapped field (from `order_timestamp` or `fill_timestamp`)
  traded_at: string;
  order_id?: string;
  // Kite-specific fields
  kite_order_id?: string;
  exchange_order_id?: string;
  instrument_token?: number;
  validity?: 'DAY' | 'IOC' | 'TTL';
  variety?: 'regular' | 'amo' | 'co' | 'iceberg';
  disclosed_quantity?: number;
  parent_order_id?: string;
  tag?: string;
  guid?: string;
  fill_timestamp?: string;
  order_timestamp?: string;
  exchange_timestamp?: string;
  average_price?: number;
  trigger_price?: number;
  market_protection?: number;
  filled_quantity?: number;
  pending_quantity?: number;
  cancelled_quantity?: number;
  status?: string;
  status_message?: string;
  product?: string;
  order_type?: string;
  asset_class?: string;
  instrument_type?: string;
  created_at?: string;
  updated_at?: string;
}

// Flat-to-flat trade round (one complete decision lifecycle)
export interface CompletedTrade {
  id: string;
  broker_account_id: string;
  tradingsymbol: string;
  exchange: string;
  instrument_type: string;
  product: string;
  direction: 'LONG' | 'SHORT';
  total_quantity: number;
  num_entries: number;
  num_exits: number;
  avg_entry_price: number;
  avg_exit_price: number;
  realized_pnl: number;
  entry_time: string;
  exit_time: string;
  duration_minutes: number;
  closed_by_flip: boolean;
  entry_trade_ids: string[];
  exit_trade_ids: string[];
  status: string;
  created_at: string;
}

export interface Alert {
  id: string;
  // Frontend uses pattern_name; backend sends pattern_type (RiskAlertResponse includes both)
  pattern_name: string;
  pattern_type?: string;
  severity: 'critical' | 'high' | 'medium' | 'positive';
  // Frontend uses timestamp; backend sends detected_at (RiskAlertResponse includes both)
  timestamp: string;
  detected_at?: string;
  message: string;
  acknowledged?: boolean;
  acknowledged_at?: string;
  why_it_matters?: string;
  // Backend fields
  trigger_trade_id?: string;
  related_trade_ids?: string[];
  details?: Record<string, unknown>;
}

export interface CoachInsight {
  insight: string;
  risk_state: string;
  timestamp: string;
}

export interface MoneySaved {
  all_time: number;
  this_week: number;
  this_month: number;
  blowups_prevented: number;
}

export interface ShieldSummary {
  total_alerts: number;
  danger_count: number;
  caution_count: number;
  heeded_count: number;
  continued_count: number;
  /** Net P&L of all trades taken AFTER alerts were not heeded. Negative = additional losses. */
  post_alert_pnl_continued: number;
  heeded_streak: number;
  /** Days with ≥3 danger alerts — high-spiral sessions */
  spiral_sessions: number;
}

export interface ShieldTimelineItem {
  id: string;
  detected_at: string;
  pattern_type: string;
  severity: string;
  message: string;
  trigger_symbol: string;
  outcome: 'heeded' | 'continued';
  post_alert_trade_count: number;
  post_alert_pnl: number;
  post_alert_trades: {
    tradingsymbol: string;
    realized_pnl: number;
    exit_time: string | null;
  }[];
  narrative: string;
  details: Record<string, unknown> | null;
}

export interface PatternBreakdown {
  pattern_type: string;
  display_name: string;
  alerts: number;
  heeded: number;
  continued: number;
  heeded_pct: number;
  post_alert_pnl: number;
}

export interface TradingPersona {
  persona_type: string;
  description: string;
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
}

export interface BrokerConnection {
  is_connected: boolean;
  broker_name: string;
  last_sync: string | null;
  account_id: string | null;
  // Kite profile fields
  user_type?: string;
  exchanges?: string[];
  products?: string[];
  order_types?: string[];
  avatar_url?: string;
  demat_consent?: boolean;
  sync_status?: 'pending' | 'syncing' | 'complete' | 'error';
}

export interface Order {
  id: string;
  broker_account_id: string;
  kite_order_id: string;
  exchange_order_id?: string;
  status: 'OPEN' | 'COMPLETE' | 'CANCELLED' | 'REJECTED' | 'TRIGGER PENDING';
  status_message?: string;
  status_message_raw?: string;
  tradingsymbol: string;
  exchange: string;
  transaction_type: 'BUY' | 'SELL';
  order_type: 'MARKET' | 'LIMIT' | 'SL' | 'SL-M';
  product: 'CNC' | 'MIS' | 'NRML' | 'BO' | 'CO';
  variety: 'regular' | 'amo' | 'co' | 'iceberg';
  validity: 'DAY' | 'IOC' | 'TTL';
  quantity: number;
  disclosed_quantity?: number;
  pending_quantity?: number;
  cancelled_quantity?: number;
  filled_quantity?: number;
  price?: number;
  trigger_price?: number;
  average_price?: number;
  order_timestamp?: string;
  exchange_timestamp?: string;
  exchange_update_timestamp?: string;
  tag?: string;
  guid?: string;
  parent_order_id?: string;
  created_at: string;
  updated_at: string;
}

export interface Holding {
  id: string;
  broker_account_id: string;
  tradingsymbol: string;
  exchange: string;
  isin?: string;
  quantity: number;
  authorised_quantity?: number;
  t1_quantity?: number;
  collateral_quantity?: number;
  collateral_type?: string;
  average_price?: number;
  last_price?: number;
  close_price?: number;
  pnl?: number;
  day_change?: number;
  day_change_percentage?: number;
  instrument_token?: number;
  product?: string;
  created_at: string;
  updated_at: string;
}

export interface Instrument {
  id: string;
  instrument_token: number;
  exchange_token?: number;
  tradingsymbol: string;
  name?: string;
  last_price?: number;
  expiry?: string;
  strike?: number;
  tick_size?: number;
  lot_size: number;
  instrument_type?: 'EQ' | 'FUT' | 'CE' | 'PE';
  segment?: string;
  exchange: string;
}

export interface MarginData {
  equity: {
    enabled: boolean;
    net: number;
    available: {
      adhoc_margin: number;
      cash: number;
      opening_balance: number;
      live_balance: number;
      collateral: number;
      intraday_payin: number;
    };
    utilised: {
      debits: number;
      exposure: number;
      m2m_realised: number;
      m2m_unrealised: number;
      option_premium: number;
      payout: number;
      span: number;
      holding_sales: number;
      turnover: number;
    };
  };
  commodity: {
    enabled: boolean;
    net: number;
    available: {
      adhoc_margin: number;
      cash: number;
      opening_balance: number;
      live_balance: number;
      collateral: number;
      intraday_payin: number;
    };
    utilised: {
      debits: number;
      exposure: number;
      m2m_realised: number;
      m2m_unrealised: number;
      option_premium: number;
      payout: number;
      span: number;
      holding_sales: number;
      turnover: number;
    };
  };
}

export interface MarginStatus {
  equity: {
    available: number;
    used: number;
    total: number;
    utilization_pct: number;
    breakdown: {
      cash: number;
      collateral: number;
      intraday_payin: number;
      exposure: number;
      span: number;
      option_premium: number;
    };
  };
  commodity: {
    available: number;
    used: number;
    total: number;
    utilization_pct: number;
    breakdown: {
      cash: number;
      collateral: number;
      intraday_payin: number;
      exposure: number;
      span: number;
      option_premium: number;
    };
  };
  overall: {
    max_utilization_pct: number;
    risk_level: 'safe' | 'warning' | 'danger' | 'insolvent';
    risk_message: string;
    is_insolvent?: boolean;
  };
}

export interface MarginSnapshot {
  timestamp: string;
  equity_utilization: number;
  commodity_utilization: number;
  max_utilization: number;
  risk_level: 'safe' | 'warning' | 'danger' | 'insolvent';
}

export interface MarginHistory {
  has_data: boolean;
  period_days: number;
  snapshot_count: number;
  statistics: {
    avg_utilization: number;
    max_utilization: number;
    min_utilization: number;
    danger_occurrences: number;
    warning_occurrences: number;
  };
  snapshots: MarginSnapshot[];
}

export interface MarginInsight {
  type: 'positive' | 'warning' | 'danger' | 'info';
  title: string;
  message: string;
  action: string;
}

export interface MarginInsightsResponse {
  current_status: MarginStatus;
  history: MarginHistory;
  insights: MarginInsight[];
}

export interface OrderAnalytics {
  has_data: boolean;
  period_days: number;
  summary: {
    total_orders: number;
    completed: number;
    cancelled: number;
    rejected: number;
    fill_rate_pct: number;
  };
  metrics: {
    cancel_ratio_pct: number;
    modification_rate_pct: number;
    rejection_reasons: Record<string, number>;
  };
  timing: {
    hourly_distribution: Record<number, number>;
    peak_trading_hour: number | null;
    peak_hour_formatted: string | null;
  };
  insights: Array<{
    type: 'positive' | 'warning' | 'danger' | 'info';
    pattern: string;
    title: string;
    message: string;
    suggestion: string;
    severity: 'positive' | 'low' | 'medium' | 'high';
  }>;
}

export interface PriceUpdate {
  type: 'price';
  instrument: string;
  data: {
    last_price: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    change: number;
    change_percent: number;
    bid: number;
    ask: number;
    oi?: number;
    oi_change?: number;
  };
  timestamp: string;
}

export interface WebSocketMessage {
  type: 'price' | 'trade' | 'alert' | 'subscribed' | 'unsubscribed' | 'pong' | 'error';
  instrument?: string;
  instruments?: string[];
  data?: Record<string, unknown>;
  message?: string;
  timestamp?: string;
}

// =============================================================================
// Danger Zone & Rate Limiting Types
// =============================================================================

export type DangerLevel = 'safe' | 'caution' | 'warning' | 'danger' | 'critical';
export type InterventionType = 'none' | 'soft_warning' | 'notification' | 'soft_cooldown' | 'hard_cooldown' | 'trading_block';

export interface DangerZoneStatus {
  level: DangerLevel;
  intervention: InterventionType;
  triggers: string[];
  message: string;
  cooldown_active: boolean;
  cooldown_remaining_minutes: number;
  daily_loss_used_percent: number;
  trade_count_today: number;
  consecutive_losses: number;
  patterns_active: string[];
  recommendations: string[];
  checked_at: string;
}

export interface InterventionResult {
  success: boolean;
  cooldown_started: boolean;
  notification_sent: boolean;
  whatsapp_sent: boolean;
  alert_created: boolean;
}

export interface EscalationStatus {
  trigger: string;
  violation_count_24h: number;
  current_escalation_level: number;
  max_escalation_level: number;
  current_duration_minutes: number;
  next_duration_minutes: number;
  at_max_escalation: boolean;
}

export interface NotificationStats {
  total_24h: number;
  by_tier: {
    [tier: string]: {
      hourly: number;
      hourly_limit: number;
      daily: number;
      daily_limit: number;
    };
  };
  by_type: {
    [type: string]: number;
  };
}

export interface DangerZoneThresholds {
  loss_limits: {
    warning_percent: number;
    danger_percent: number;
    critical_percent: number;
  };
  trading_frequency: {
    trades_per_15min_warning: number;
    trades_per_15min_danger: number;
    trades_per_hour_warning: number;
    trades_per_hour_danger: number;
  };
  consecutive_losses: {
    warning: number;
    danger: number;
    critical: number;
  };
  time_based: {
    avoid_first_minutes: number;
    avoid_last_minutes: number;
  };
}

export interface DangerZoneSummary {
  current_status: {
    level: DangerLevel;
    intervention: InterventionType;
    triggers: string[];
    message: string;
    cooldown_active: boolean;
    cooldown_remaining_minutes: number;
  };
  metrics: {
    daily_loss_used_percent: number;
    trade_count_today: number;
    consecutive_losses: number;
    patterns_active: string[];
  };
  cooldown_history_7d: CooldownRecord[];
  notification_stats_24h: NotificationStats;
  recommendations: string[];
  checked_at: string;
}

// =============================================================================
// Cooldown Types
// =============================================================================

export interface CooldownRecord {
  id: string;
  broker_account_id: string;
  reason: string;
  duration_minutes: number;
  started_at: string;
  expires_at: string;
  is_active: boolean;
  remaining_minutes: number;
  remaining_seconds: number;
  can_skip: boolean;
  skipped: boolean;
  acknowledged: boolean;
  message: string | null;
  meta_data: Record<string, unknown>;
}

export interface CooldownCreateRequest {
  reason?: string;
  duration_minutes?: number;
  message?: string;
}

export interface PreTradeCheckRequest {
  symbol?: string;
  quantity?: number;
  direction?: 'BUY' | 'SELL';
  order_value?: number;
}

export interface PreTradeCheckResponse {
  action: 'allow' | 'warn' | 'cooldown';
  reasons: string[];
  recommendations: string[];
  cooldown: CooldownRecord | null;
  patterns_detected: string[];
  risk_level: 'low' | 'medium' | 'high';
  predictive_alert?: {
    type: string;
    message: string;
    severity: string;
  };
}
