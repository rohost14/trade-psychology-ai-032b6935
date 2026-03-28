/**
 * Guest Mode Demo Data
 * Realistic F&O intraday demo for Indian traders.
 * Symbols match Zerodha format. Covers NIFTY/BANKNIFTY options, stock options, and intraday MIS.
 */
import type { CompletedTrade, Position } from '@/types/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function daysAgo(n: number, hour = 10, minute = 30): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
}

// ---------------------------------------------------------------------------
// Broker account (fake)
// ---------------------------------------------------------------------------
export const DEMO_ACCOUNT = {
  id: 'demo-account-id',
  broker_name: 'zerodha',
  broker_user_id: 'ZA1234',
  broker_email: 'demo@tradementor.ai',
  status: 'connected',
  connected_at: daysAgo(30),
  last_sync_at: daysAgo(0, 9, 16),
};

// ---------------------------------------------------------------------------
// Completed trades — realistic F&O scenarios
// ---------------------------------------------------------------------------
export const DEMO_COMPLETED_TRADES: CompletedTrade[] = [
  // NIFTY weekly PE (caught a fall, quick profit)
  {
    id: 'ct-001', broker_account_id: 'demo-account-id',
    tradingsymbol: 'NIFTY2531723200PE', exchange: 'NFO', instrument_type: 'PE',
    direction: 'LONG', total_quantity: 50, num_entries: 1, num_exits: 1,
    avg_entry_price: 125.5, avg_exit_price: 198.0,
    entry_time: daysAgo(1, 9, 22), exit_time: daysAgo(1, 10, 47),
    duration_minutes: 85, realized_pnl: 3625, product: 'MIS',
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [],
    status: 'closed', created_at: daysAgo(1, 9, 22),
  },
  // SOLARINDS intraday MIS (loss, held too long)
  {
    id: 'ct-002', broker_account_id: 'demo-account-id',
    tradingsymbol: 'SOLARINDS', exchange: 'NSE', instrument_type: 'EQ',
    direction: 'LONG', total_quantity: 100, num_entries: 1, num_exits: 1,
    avg_entry_price: 8420, avg_exit_price: 8290,
    entry_time: daysAgo(1, 11, 5), exit_time: daysAgo(1, 14, 22),
    duration_minutes: 197, realized_pnl: -13000, product: 'MIS',
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [],
    status: 'closed', created_at: daysAgo(1, 11, 5),
  },
  // Revenge trade after SOLARINDS loss — NIFTY CE quick flip (loss)
  {
    id: 'ct-003', broker_account_id: 'demo-account-id',
    tradingsymbol: 'NIFTY25MAR23000CE', exchange: 'NFO', instrument_type: 'CE',
    direction: 'LONG', total_quantity: 100, num_entries: 1, num_exits: 1,
    avg_entry_price: 88, avg_exit_price: 61,
    entry_time: daysAgo(1, 14, 35), exit_time: daysAgo(1, 15, 10),
    duration_minutes: 35, realized_pnl: -2700, product: 'MIS',
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [],
    status: 'closed', created_at: daysAgo(1, 14, 35),
  },
  // BANKNIFTY PE (won)
  {
    id: 'ct-004', broker_account_id: 'demo-account-id',
    tradingsymbol: 'BANKNIFTY2531748500PE', exchange: 'NFO', instrument_type: 'PE',
    direction: 'LONG', total_quantity: 15, num_entries: 1, num_exits: 1,
    avg_entry_price: 340, avg_exit_price: 490,
    entry_time: daysAgo(2, 9, 18), exit_time: daysAgo(2, 10, 5),
    duration_minutes: 47, realized_pnl: 2250, product: 'MIS',
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [],
    status: 'closed', created_at: daysAgo(2, 9, 18),
  },
  // FORTIS stock option (monthly, small profit)
  {
    id: 'ct-005', broker_account_id: 'demo-account-id',
    tradingsymbol: 'FORTIS25MAR960CE', exchange: 'NFO', instrument_type: 'CE',
    direction: 'LONG', total_quantity: 1100, num_entries: 1, num_exits: 1,
    avg_entry_price: 14.5, avg_exit_price: 19.2,
    entry_time: daysAgo(3, 10, 30), exit_time: daysAgo(3, 13, 15),
    duration_minutes: 165, realized_pnl: 5170, product: 'NRML',
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [],
    status: 'closed', created_at: daysAgo(3, 10, 30),
  },
  // SENSEX PE (oversized — behavioral flag)
  {
    id: 'ct-006', broker_account_id: 'demo-account-id',
    tradingsymbol: 'SENSEX25MAR75000PE', exchange: 'BFO', instrument_type: 'PE',
    direction: 'LONG', total_quantity: 20, num_entries: 1, num_exits: 1,
    avg_entry_price: 280, avg_exit_price: 195,
    entry_time: daysAgo(3, 11, 45), exit_time: daysAgo(3, 14, 30),
    duration_minutes: 165, realized_pnl: -1700, product: 'MIS',
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [],
    status: 'closed', created_at: daysAgo(3, 11, 45),
  },
  // NIFTY CE — good trade, disciplined exit
  {
    id: 'ct-007', broker_account_id: 'demo-account-id',
    tradingsymbol: 'NIFTY25MAR23000CE', exchange: 'NFO', instrument_type: 'CE',
    direction: 'LONG', total_quantity: 50, num_entries: 1, num_exits: 1,
    avg_entry_price: 102, avg_exit_price: 148,
    entry_time: daysAgo(5, 9, 25), exit_time: daysAgo(5, 11, 10),
    duration_minutes: 105, realized_pnl: 2300, product: 'MIS',
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [],
    status: 'closed', created_at: daysAgo(5, 9, 25),
  },
  // Big loss day — overtrading
  {
    id: 'ct-008', broker_account_id: 'demo-account-id',
    tradingsymbol: 'NIFTY2531723200PE', exchange: 'NFO', instrument_type: 'PE',
    direction: 'LONG', total_quantity: 150, num_entries: 1, num_exits: 1,
    avg_entry_price: 55, avg_exit_price: 30,
    entry_time: daysAgo(6, 9, 20), exit_time: daysAgo(6, 9, 48),
    duration_minutes: 28, realized_pnl: -3750, product: 'MIS',
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [],
    status: 'closed', created_at: daysAgo(6, 9, 20),
  },
  {
    id: 'ct-009', broker_account_id: 'demo-account-id',
    tradingsymbol: 'NIFTY2531723200CE', exchange: 'NFO', instrument_type: 'CE',
    direction: 'LONG', total_quantity: 100, num_entries: 1, num_exits: 1,
    avg_entry_price: 72, avg_exit_price: 45,
    entry_time: daysAgo(6, 10, 5), exit_time: daysAgo(6, 10, 35),
    duration_minutes: 30, realized_pnl: -2700, product: 'MIS',
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [],
    status: 'closed', created_at: daysAgo(6, 10, 5),
  },
  {
    id: 'ct-010', broker_account_id: 'demo-account-id',
    tradingsymbol: 'BANKNIFTY2531749000CE', exchange: 'NFO', instrument_type: 'CE',
    direction: 'LONG', total_quantity: 30, num_entries: 1, num_exits: 1,
    avg_entry_price: 120, avg_exit_price: 88,
    entry_time: daysAgo(6, 11, 15), exit_time: daysAgo(6, 11, 50),
    duration_minutes: 35, realized_pnl: -960, product: 'MIS',
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [],
    status: 'closed', created_at: daysAgo(6, 11, 15),
  },
  // Good week — 4 winners
  {
    id: 'ct-011', broker_account_id: 'demo-account-id',
    tradingsymbol: 'NIFTY25MAR23000CE', exchange: 'NFO', instrument_type: 'CE',
    direction: 'LONG', total_quantity: 50, num_entries: 1, num_exits: 1,
    avg_entry_price: 78, avg_exit_price: 115,
    entry_time: daysAgo(9, 9, 30), exit_time: daysAgo(9, 11, 45),
    duration_minutes: 135, realized_pnl: 1850, product: 'MIS',
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [],
    status: 'closed', created_at: daysAgo(9, 9, 30),
  },
  {
    id: 'ct-012', broker_account_id: 'demo-account-id',
    tradingsymbol: 'BANKNIFTY2531748500PE', exchange: 'NFO', instrument_type: 'PE',
    direction: 'LONG', total_quantity: 15, num_entries: 1, num_exits: 1,
    avg_entry_price: 410, avg_exit_price: 590,
    entry_time: daysAgo(10, 9, 20), exit_time: daysAgo(10, 10, 40),
    duration_minutes: 80, realized_pnl: 2700, product: 'MIS',
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [],
    status: 'closed', created_at: daysAgo(10, 9, 20),
  },
  {
    id: 'ct-013', broker_account_id: 'demo-account-id',
    tradingsymbol: 'FORTIS25MAR960CE', exchange: 'NFO', instrument_type: 'CE',
    direction: 'LONG', total_quantity: 1100, num_entries: 1, num_exits: 1,
    avg_entry_price: 8.5, avg_exit_price: 14.5,
    entry_time: daysAgo(12, 10, 0), exit_time: daysAgo(12, 14, 30),
    duration_minutes: 270, realized_pnl: 6600, product: 'NRML',
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [],
    status: 'closed', created_at: daysAgo(12, 10, 0),
  },
  {
    id: 'ct-014', broker_account_id: 'demo-account-id',
    tradingsymbol: 'SOLARINDS', exchange: 'NSE', instrument_type: 'EQ',
    direction: 'LONG', total_quantity: 50, num_entries: 1, num_exits: 1,
    avg_entry_price: 8150, avg_exit_price: 8280,
    entry_time: daysAgo(14, 9, 45), exit_time: daysAgo(14, 12, 20),
    duration_minutes: 155, realized_pnl: 6500, product: 'MIS',
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [],
    status: 'closed', created_at: daysAgo(14, 9, 45),
  },
  {
    id: 'ct-015', broker_account_id: 'demo-account-id',
    tradingsymbol: 'NIFTY25MAR23000PE', exchange: 'NFO', instrument_type: 'PE',
    direction: 'LONG', total_quantity: 50, num_entries: 1, num_exits: 1,
    avg_entry_price: 155, avg_exit_price: 95,
    entry_time: daysAgo(15, 13, 10), exit_time: daysAgo(15, 14, 55),
    duration_minutes: 105, realized_pnl: -3000, product: 'MIS',
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [],
    status: 'closed', created_at: daysAgo(15, 13, 10),
  },
];

// ---------------------------------------------------------------------------
// Open positions
// ---------------------------------------------------------------------------
export const DEMO_POSITIONS: Position[] = [
  {
    id: 'pos-001', tradingsymbol: 'NIFTY25MAR23000CE', exchange: 'NFO',
    instrument_type: 'CE', product: 'NRML',
    total_quantity: 50, average_entry_price: 108.5, average_exit_price: null,
    last_price: 124.2, pnl: 785, day_pnl: 785,
    realized_pnl: 0, unrealized_pnl: 785, current_value: 6210,
    status: 'open',
  },
  {
    id: 'pos-002', tradingsymbol: 'BANKNIFTY2531748500PE', exchange: 'NFO',
    instrument_type: 'PE', product: 'MIS',
    total_quantity: 15, average_entry_price: 385, average_exit_price: null,
    last_price: 362, pnl: -345, day_pnl: -345,
    realized_pnl: 0, unrealized_pnl: -345, current_value: 5430,
    status: 'open',
  },
];

// ---------------------------------------------------------------------------
// Risk state
// ---------------------------------------------------------------------------
export const DEMO_RISK_STATE = {
  state: 'caution',
  score: 62,
  factors: [
    { name: 'Daily P&L', status: 'caution', value: '-₹15,700', detail: '63% of daily limit used' },
    { name: 'Behavioral Alerts', status: 'danger', value: '3 alerts', detail: 'Revenge trading detected' },
    { name: 'Position Count', status: 'safe', value: '2 open', detail: 'Within normal range' },
  ],
  daily_pnl: -15700,
  daily_loss_limit: 25000,
  trades_today: 5,
  daily_trade_limit: 10,
};

// ---------------------------------------------------------------------------
// Risk alerts (behavioral)
// ---------------------------------------------------------------------------
export const DEMO_RISK_ALERTS = [
  {
    id: 'ra-001', pattern_type: 'revenge_trading', severity: 'high',
    message: 'You entered NIFTY23000CE just 25 minutes after a ₹13,000 loss on SOLARINDS. Revenge trading pattern detected.',
    created_at: daysAgo(1, 14, 36), acknowledged: false,
    estimated_cost: 2700,
  },
  {
    id: 'ra-002', pattern_type: 'overtrading', severity: 'medium',
    message: '5 trades placed in the last 3 hours. Your typical pace is 2-3. Slow down and be selective.',
    created_at: daysAgo(1, 13, 0), acknowledged: false,
    estimated_cost: 0,
  },
  {
    id: 'ra-003', pattern_type: 'loss_aversion', severity: 'medium',
    message: 'SOLARINDS held for 3h 17m while in loss. Consider setting a max hold time on losers.',
    created_at: daysAgo(1, 14, 22), acknowledged: true,
    estimated_cost: 4500,
  },
];

// ---------------------------------------------------------------------------
// Profile
// ---------------------------------------------------------------------------
export const DEMO_PROFILE = {
  id: 'demo-profile-id',
  broker_account_id: 'demo-account-id',
  display_name: 'Demo Trader',
  experience_level: 'intermediate',
  trading_style: 'intraday',
  risk_tolerance: 'moderate',
  preferred_instruments: ['NIFTY', 'BANKNIFTY', 'STOCKS'],
  daily_loss_limit: 25000,
  daily_trade_limit: 10,
  max_position_size: 150000,
  cooldown_after_loss: 15,
  onboarding_completed: true,
};

// ---------------------------------------------------------------------------
// Analytics: overview
// ---------------------------------------------------------------------------
const EQUITY_CURVE = (() => {
  let equity = 100000;
  const curve = [];
  const pnls = [2100, -800, 1500, 3200, -1200, 4800, -2100, 1800, 2250, -3750,
    -2700, -960, 1850, 2700, 6600, 6500, -3000, 3625, -13000, -2700];
  for (let i = pnls.length - 1; i >= 0; i--) {
    equity += pnls[i];
    const d = new Date();
    d.setDate(d.getDate() - (pnls.length - 1 - i));
    curve.push({ date: d.toISOString().split('T')[0], equity: Math.round(equity) });
  }
  return curve;
})();

export const DEMO_OVERVIEW = {
  has_data: true, period_days: 30,
  kpis: {
    total_pnl: 7990, trade_count: 15, win_rate: 60,
    winners: 9, losers: 6,
    avg_win: 3933, avg_loss: -4635,
    profit_factor: 1.28, expectancy: 533,
    max_win_streak: 4, max_loss_streak: 3,
    current_streak: 2, current_streak_type: 'loss',
    best_day: { date: daysAgo(12).split('T')[0], pnl: 9300 },
    worst_day: { date: daysAgo(1).split('T')[0], pnl: -16075 },
  },
  equity_curve: EQUITY_CURVE,
  daily_pnl: [
    { date: daysAgo(1).split('T')[0], pnl: -16075 },
    { date: daysAgo(2).split('T')[0], pnl: 2250 },
    { date: daysAgo(3).split('T')[0], pnl: 3470 },
    { date: daysAgo(5).split('T')[0], pnl: 2300 },
    { date: daysAgo(6).split('T')[0], pnl: -7410 },
    { date: daysAgo(9).split('T')[0], pnl: 1850 },
    { date: daysAgo(10).split('T')[0], pnl: 2700 },
    { date: daysAgo(12).split('T')[0], pnl: 9300 },
    { date: daysAgo(14).split('T')[0], pnl: 6500 },
    { date: daysAgo(15).split('T')[0], pnl: -3000 },
  ],
};

// ---------------------------------------------------------------------------
// Analytics: performance
// ---------------------------------------------------------------------------
export const DEMO_PERFORMANCE = {
  has_data: true,
  by_instrument: [
    { symbol: 'NIFTY options', pnl: 2225, trades: 7, win_rate: 57 },
    { symbol: 'BANKNIFTY options', pnl: 4950, trades: 3, win_rate: 67 },
    { symbol: 'FORTIS options', pnl: 11770, trades: 2, win_rate: 100 },
    { symbol: 'SOLARINDS', pnl: -6500, trades: 2, win_rate: 50 },
    { symbol: 'SENSEX options', pnl: -1700, trades: 1, win_rate: 0 },
  ],
  by_session: [
    { hour: 9, label: '09:00', pnl: 5100, trades: 5, win_rate: 80 },
    { hour: 10, label: '10:00', pnl: 1450, trades: 3, win_rate: 67 },
    { hour: 11, label: '11:00', pnl: 5210, trades: 3, win_rate: 33 },
    { hour: 12, label: '12:00', pnl: 0, trades: 0, win_rate: 0 },
    { hour: 13, label: '13:00', pnl: -2700, trades: 1, win_rate: 0 },
    { hour: 14, label: '14:00', pnl: -14270, trades: 3, win_rate: 0 },
  ],
  monthly_pnl: [
    { month: 'Jan', pnl: 24500 },
    { month: 'Feb', pnl: -8200 },
    { month: 'Mar', pnl: 7990 },
  ],
};

// ---------------------------------------------------------------------------
// Analytics: timing heatmap
// ---------------------------------------------------------------------------
export const DEMO_TIMING_HEATMAP = {
  has_data: true,
  heatmap: Array.from({ length: 5 }, (_, dayIdx) =>
    Array.from({ length: 14 }, (_, hourIdx) => ({
      day: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'][dayIdx],
      hour: hourIdx + 9,
      pnl: Math.round((Math.random() - 0.45) * 5000),
      trades: Math.floor(Math.random() * 4),
    }))
  ).flat(),
  best_hour: 9, worst_hour: 14,
  best_day: 'Wednesday', worst_day: 'Friday',
};

// ---------------------------------------------------------------------------
// Analytics: behavioral analysis
// ---------------------------------------------------------------------------
export const DEMO_BEHAVIORAL = {
  has_data: true,
  patterns: [
    {
      pattern_type: 'revenge_trading', frequency: 3, severity: 'high',
      estimated_cost: 8400,
      description: 'You entered positions within 30 min of a significant loss 3 times this month.',
      examples: ['NIFTY23000CE after SOLARINDS loss', 'NIFTY23200PE after BANKNIFTY loss'],
    },
    {
      pattern_type: 'loss_aversion', frequency: 2, severity: 'medium',
      estimated_cost: 9200,
      description: 'Held losing positions 2-4× longer than winners. Average loser held 185 min vs 97 min for winners.',
      examples: ['SOLARINDS: 197 min', 'SENSEX75000PE: 165 min'],
    },
    {
      pattern_type: 'overtrading', frequency: 1, severity: 'medium',
      estimated_cost: 3660,
      description: '5 trades on one day vs your average of 2.5. High-frequency days correlate with net losses.',
      examples: ['Day 6: 3 rapid-fire losses'],
    },
  ],
  summary: {
    total_behavioral_cost: 21260,
    clean_days: 7, flagged_days: 3,
    most_frequent_pattern: 'revenge_trading',
  },
};

// ---------------------------------------------------------------------------
// Analytics: journal correlation (stub — no real journal data in demo)
// ---------------------------------------------------------------------------
export const DEMO_JOURNAL_CORRELATION = {
  has_data: false,
  message: 'Journal your trades to unlock correlation insights.',
};

// ---------------------------------------------------------------------------
// Analytics: AI insights
// ---------------------------------------------------------------------------
export const DEMO_AI_INSIGHTS = {
  has_data: true,
  insights: [
    {
      type: 'pattern',
      title: 'Morning Edge is Real',
      body: 'Your 9–10 AM trades have a 80% win rate vs 33% after 2 PM. Consider restricting entries to pre-noon only.',
      severity: 'positive',
    },
    {
      type: 'warning',
      title: 'Afternoon Revenge Spiral',
      body: 'Every time you\'ve had a loss > ₹5,000 before 2 PM, your next trade has been a loser. Walk away instead.',
      severity: 'high',
    },
    {
      type: 'pattern',
      title: 'NIFTY options: Your best instrument',
      body: 'Consistent edge on NIFTY directional trades with defined risk. Lean into this strength.',
      severity: 'positive',
    },
  ],
};

// ---------------------------------------------------------------------------
// Analytics: AI summary
// ---------------------------------------------------------------------------
export const DEMO_AI_SUMMARY = {
  has_data: true,
  summary: `This month you traded 15 completed positions with a net P&L of ₹7,990. Your win rate is solid at 60%, but 3 revenge-trading incidents cost you ~₹8,400 that you didn't have to lose.

Your strongest edge is in morning NIFTY/BANKNIFTY options (9–10 AM), where you win 80% of the time. Your weakest period is 2–3:30 PM — especially after an earlier loss. Consider a hard rule: no new entries after 2 PM if you're down on the day.

The SOLARINDS trade stands out: you held a losing intraday position for 3+ hours and took a ₹13,000 hit. A simple max-hold rule (e.g., 90 min for MIS) would have limited the damage significantly.

One thing to build on: your FORTIS options trades were textbook — patient entry, clear thesis, disciplined exit.`,
};

// ---------------------------------------------------------------------------
// Analytics: progress
// ---------------------------------------------------------------------------
export const DEMO_PROGRESS = {
  this_week: {
    total_pnl: -16075, trade_count: 5, win_rate: 40,
    winners: 2, losers: 3, avg_win: 3625, avg_loss: -7800,
  },
  last_week: {
    total_pnl: 14050, trade_count: 5, win_rate: 80,
    winners: 4, losers: 1, avg_win: 4588, avg_loss: -1700,
  },
  comparison: {
    pnl:          { change: -30125, improved: false, percent: -214.4 },
    win_rate:     { change: -40,    improved: false, percent: -50 },
    trade_count:  { change: 0,      improved: true,  percent: 0 },
    danger_alerts:{ change: 2,      improved: false, percent: 200 },
  },
  alerts: { this_week: 3, last_week: 1 },
  streaks: { days_without_revenge: 2, current_streak: 2, best_streak: 7 },
};

// ---------------------------------------------------------------------------
// Analytics: risk metrics
// ---------------------------------------------------------------------------
export const DEMO_RISK_METRICS = {
  has_data: true,
  max_drawdown: -23110,
  max_drawdown_pct: -19.3,
  var_95: -9800,
  avg_daily_loss: -5500,
  largest_single_loss: -13000,
  risk_reward_ratio: 0.85,
  days_in_drawdown: 4,
  recovery_factor: 0.35,
};

// ---------------------------------------------------------------------------
// Analytics: risk score
// ---------------------------------------------------------------------------
export const DEMO_RISK_SCORE = {
  score: 62,
  label: 'Moderate Risk',
  components: {
    drawdown: 55, volatility: 70, behavioral: 65, discipline: 58,
  },
  trend: 'deteriorating',
};

// ---------------------------------------------------------------------------
// Analytics: critical trades
// ---------------------------------------------------------------------------
export const DEMO_CRITICAL_TRADES = {
  has_data: true,
  total_critical: 4,
  avg_loss_threshold: -3500,
  trades: [
    {
      id: 'ct-002', tradingsymbol: 'SOLARINDS', direction: 'LONG',
      entry_time: daysAgo(1, 11, 5), exit_time: daysAgo(1, 14, 22),
      duration_minutes: 197, realized_pnl: -13000,
      severity: 'critical',
      reasons: [
        { type: 'large_loss', label: '₹13,000 loss' },
        { type: 'behavioral_alert', label: 'Loss aversion: held 3h 17m', severity: 'high' },
      ],
    },
    {
      id: 'ct-003', tradingsymbol: 'NIFTY25MAR23000CE', direction: 'LONG',
      entry_time: daysAgo(1, 14, 35), exit_time: daysAgo(1, 15, 10),
      duration_minutes: 35, realized_pnl: -2700,
      severity: 'high',
      reasons: [
        { type: 'behavioral_alert', label: 'Revenge trade: 13 min after ₹13K loss', severity: 'high' },
        { type: 'quick_reentry', label: 'Re-entry < 30 min' },
      ],
    },
    {
      id: 'ct-008', tradingsymbol: 'NIFTY2531723200PE', direction: 'LONG',
      entry_time: daysAgo(6, 9, 20), exit_time: daysAgo(6, 9, 48),
      duration_minutes: 28, realized_pnl: -3750,
      severity: 'high',
      reasons: [
        { type: 'oversized', label: '3× normal size (150 lots)' },
        { type: 'large_loss', label: '₹3,750 loss' },
      ],
    },
    {
      id: 'ct-006', tradingsymbol: 'SENSEX25MAR75000PE', direction: 'LONG',
      entry_time: daysAgo(3, 11, 45), exit_time: daysAgo(3, 14, 30),
      duration_minutes: 165, realized_pnl: -1700,
      severity: 'medium',
      reasons: [
        { type: 'behavioral_alert', label: 'Overtrading day: 4th trade', severity: 'medium' },
      ],
    },
  ],
};

// ---------------------------------------------------------------------------
// Analytics: edge confidence
// ---------------------------------------------------------------------------
export const DEMO_EDGE_CONFIDENCE = {
  has_data: true,
  overall_edge: 52,
  confidence: 'moderate',
  instruments: [
    { symbol: 'NIFTY options', edge: 68, trades: 7, confidence: 'strong' },
    { symbol: 'BANKNIFTY options', edge: 71, trades: 3, confidence: 'strong' },
    { symbol: 'FORTIS options', edge: 95, trades: 2, confidence: 'limited_data' },
    { symbol: 'SOLARINDS', edge: 38, trades: 2, confidence: 'weak' },
    { symbol: 'SENSEX options', edge: 0, trades: 1, confidence: 'no_edge' },
  ],
};

// ---------------------------------------------------------------------------
// Analytics: conditional performance
// ---------------------------------------------------------------------------
export const DEMO_CONDITIONAL_PERFORMANCE = {
  has_data: true,
  conditions: [
    { condition: 'First trade of day', win_rate: 75, avg_pnl: 2850, trades: 8 },
    { condition: 'After a win', win_rate: 62, avg_pnl: 1200, trades: 8 },
    { condition: 'After a loss', win_rate: 30, avg_pnl: -4100, trades: 10 },
    { condition: 'Morning (9–11 AM)', win_rate: 77, avg_pnl: 2680, trades: 9 },
    { condition: 'Afternoon (2–4 PM)', win_rate: 25, avg_pnl: -6250, trades: 4 },
    { condition: 'More than 3 trades/day', win_rate: 22, avg_pnl: -3200, trades: 9 },
  ],
};

// ---------------------------------------------------------------------------
// Analytics: options behavior
// ---------------------------------------------------------------------------
export const DEMO_OPTIONS_BEHAVIOR = {
  has_data: true,
  ce_pnl: 8575, pe_pnl: 4175,
  buy_pnl: 12750, sell_pnl: 0,
  weekly_pnl: 3475, monthly_pnl: 9275,
  avg_hold_winner: 97, avg_hold_loser: 185,
  premium_decay_cost: 2100,
};

// ---------------------------------------------------------------------------
// Behavioral patterns (MyPatterns page)
// ---------------------------------------------------------------------------
export const DEMO_BEHAVIORAL_ANALYSIS = {
  has_data: true,
  time_window_days: 30,
  patterns_detected: [
    {
      pattern_type: 'revenge_trading', count: 3, severity: 'high',
      estimated_cost: 8400, last_seen: daysAgo(1, 14, 35),
      description: 'Quick re-entry after significant loss',
    },
    {
      pattern_type: 'loss_aversion', count: 2, severity: 'medium',
      estimated_cost: 9200, last_seen: daysAgo(1, 14, 22),
      description: 'Holding losers 2-4× longer than winners',
    },
    {
      pattern_type: 'overtrading', count: 1, severity: 'medium',
      estimated_cost: 3660, last_seen: daysAgo(6, 11, 50),
      description: 'High-frequency trading day correlated with net loss',
    },
  ],
  total_behavioral_cost: 21260,
  clean_days_pct: 70,
};
