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
  // ── Today's session ───────────────────────────────────────────────────────
  // The Dashboard filters closed trades to the current session window, and
  // every fixture below used to be dated a day or more back, so Closed
  // Positions always rendered empty in demo mode. These five sit in today's
  // session and cover the cases the table has to handle: a win, a loss, a
  // multi-leg round trip, an equity position and a fast scratch.
  {
    id: 'ct-t01', broker_account_id: 'demo-account-id',
    tradingsymbol: 'NIFTY2580724500CE', exchange: 'NFO', instrument_type: 'CE',
    direction: 'LONG', total_quantity: 75, num_entries: 1, num_exits: 1,
    avg_entry_price: 142.1, avg_exit_price: 161.5,
    entry_time: daysAgo(0, 9, 18), exit_time: daysAgo(0, 9, 40),
    duration_minutes: 22, realized_pnl: 1455, product: 'NRML',
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [],
    status: 'closed', created_at: daysAgo(0, 9, 18),
  },
  {
    id: 'ct-t02', broker_account_id: 'demo-account-id',
    tradingsymbol: 'BANKNIFTY2580750800CE', exchange: 'NFO', instrument_type: 'CE',
    direction: 'LONG', total_quantity: 50, num_entries: 2, num_exits: 1,
    avg_entry_price: 388.4, avg_exit_price: 372.9,
    entry_time: daysAgo(0, 11, 8), exit_time: daysAgo(0, 12, 12),
    duration_minutes: 64, realized_pnl: -775, product: 'NRML',
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [],
    status: 'closed', created_at: daysAgo(0, 11, 8),
  },
  {
    id: 'ct-t03', broker_account_id: 'demo-account-id',
    tradingsymbol: 'FINNIFTY2580719800PE', exchange: 'NFO', instrument_type: 'PE',
    direction: 'SHORT', total_quantity: 40, num_entries: 1, num_exits: 2,
    avg_entry_price: 96.25, avg_exit_price: 88.4,
    entry_time: daysAgo(0, 12, 30), exit_time: daysAgo(0, 13, 5),
    duration_minutes: 35, realized_pnl: 314, product: 'MIS',
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [],
    status: 'closed', created_at: daysAgo(0, 12, 30),
  },
  {
    id: 'ct-t04', broker_account_id: 'demo-account-id',
    tradingsymbol: 'MAXHEALTH', exchange: 'NSE', instrument_type: 'EQ',
    direction: 'LONG', total_quantity: 2100, num_entries: 2, num_exits: 2,
    avg_entry_price: 9.31, avg_exit_price: 11.01,
    entry_time: daysAgo(0, 10, 4), exit_time: daysAgo(0, 12, 43),
    duration_minutes: 159, realized_pnl: 3570, product: 'NRML',
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [],
    status: 'closed', created_at: daysAgo(0, 10, 4),
  },
  {
    id: 'ct-t05', broker_account_id: 'demo-account-id',
    tradingsymbol: 'SENSEX2580781400PE', exchange: 'BFO', instrument_type: 'PE',
    direction: 'LONG', total_quantity: 100, num_entries: 1, num_exits: 1,
    avg_entry_price: 24.12, avg_exit_price: 10.28,
    entry_time: daysAgo(0, 13, 51), exit_time: daysAgo(0, 14, 7),
    duration_minutes: 16, realized_pnl: -1384, product: 'NRML',
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [],
    status: 'closed', created_at: daysAgo(0, 13, 51),
  },
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
    entry_price_source: 'ledger',
    last_price: 124.2, pnl: 785, day_pnl: 785,
    realized_pnl: 0, unrealized_pnl: 785, current_value: 6210,
    status: 'open',
  },
  {
    id: 'pos-002', tradingsymbol: 'BANKNIFTY2531748500PE', exchange: 'NFO',
    instrument_type: 'PE', product: 'MIS',
    total_quantity: 15, average_entry_price: 385, average_exit_price: null,
    entry_price_source: 'broker',
    last_price: 362, pnl: -345, day_pnl: -345,
    realized_pnl: 0, unrealized_pnl: -345, current_value: 5430,
    status: 'open',
  },
];

// ---------------------------------------------------------------------------
// Risk state
// ---------------------------------------------------------------------------
export const DEMO_RISK_STATE = {
  state: 'danger',
  score: 76,
  factors: [
    { name: 'Daily P&L', status: 'caution', value: '-₹15,700', detail: '63% of daily limit used' },
    { name: 'Behavioral Alerts', status: 'danger', value: '7 alerts', detail: '3 high-severity unacknowledged' },
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
    id: 'ra-001', pattern_type: 'revenge_trade', severity: 'danger',
    message: 'NIFTY23000CE entry came 25 min after ₹13,000 loss on SOLARINDS. Re-entering under active loss stress.',
    created_at: daysAgo(1, 14, 36), acknowledged: false,
    details: {
      gap_minutes: 25,
      prior_loss: 13000,
      prior_symbol: 'SOLARINDS',
      danger_window: 20,
      estimated_cost: 2700,
    },
  },
  {
    id: 'ra-002', pattern_type: 'overtrading_burst', severity: 'caution',
    message: '5 trades in the last 3 hours. Typical pace is 2–3. Each additional trade this session has been a loss.',
    created_at: daysAgo(1, 13, 0), acknowledged: false,
    details: {
      daily_count: 5,
      declared_limit: 4,
      trades_in_window: 5,
      estimated_cost: 0,
    },
  },
  {
    id: 'ra-003', pattern_type: 'martingale_behaviour', severity: 'caution',
    message: 'BANKNIFTY lot size went 1 → 1 → 3 across three consecutive losses. Total session exposure has tripled.',
    created_at: daysAgo(1, 14, 22), acknowledged: true,
    details: {
      underlying: 'BANKNIFTY',
      size_sequence: [1, 1, 3],
      max_ratio: 3,
      consecutive_losses: 3,
      estimated_cost: 4500,
    },
  },
  {
    id: 'ra-004', pattern_type: 'size_escalation', severity: 'critical',
    message: 'BANKNIFTY 45500 PE entry at 100 lots — 4× your average size — 8 min after ₹2,600 loss. Win rate on oversized entries: 28% vs 60% baseline.',
    created_at: daysAgo(0, 10, 51), acknowledged: false,
    details: {
      underlying: 'BANKNIFTY',
      symbol: 'BANKNIFTY45500PE',
      lots: 100,
      avg_lots: 25,
      ratio: 4,
      prior_loss: 2600,
      win_rate_oversized: 0.28,
      win_rate_normal: 0.60,
      estimated_cost: 4200,
    },
  },
  {
    id: 'ra-005', pattern_type: 'early_exit', severity: 'caution',
    message: 'NIFTY CE exited at +₹820 after 8 min. Position continued to +₹2,100. You exit 42% early on average — ₹7,680 in unrealised gains left behind this month.',
    created_at: daysAgo(0, 9, 38), acknowledged: false,
    details: {
      symbol: 'NIFTY23000CE',
      exit_pnl: 820,
      continued_to: 2100,
      avg_early_exit_pct: 42,
      monthly_cost: 7680,
      times_this_month: 6,
      estimated_cost: 1280,
    },
  },
  {
    id: 'ra-006', pattern_type: 'no_stoploss', severity: 'danger',
    message: 'FINNIFTY 19800 CE open 47 min with no stop-loss. Unrealised loss: ₹3,200. Positions without stop-loss average 3× larger final loss for you.',
    created_at: daysAgo(0, 9, 15), acknowledged: false,
    details: {
      symbol: 'FINNIFTY19800CE',
      open_minutes: 47,
      unrealised_loss: 3200,
      loss_multiplier: 3,
      estimated_cost: 5800,
    },
  },
  {
    id: 'ra-007', pattern_type: 'opening_5min_trap', severity: 'caution',
    message: 'NIFTY CE entry at 09:17 — within opening 5-min window. Your win rate on opening entries is 19% vs 54% after 09:30. This pattern cost ₹9,400 last month.',
    created_at: daysAgo(1, 9, 20), acknowledged: true,
    details: {
      symbol: 'NIFTY23000CE',
      entry_time: '09:17',
      win_rate_opening: 0.19,
      win_rate_after_open: 0.54,
      monthly_cost: 9400,
      estimated_cost: 1800,
    },
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
// Mirrors the /api/analytics/overview equity_curve item shape:
// { date, cumulative_pnl, trade_count } — chronological (oldest first).
const EQUITY_CURVE = (() => {
  const pnls = [2100, -800, 1500, 3200, -1200, 4800, -2100, 1800, 2250, -3750,
    -2700, -960, 1850, 2700, 6600, 6500, -3000, 3625, -13000, -2700];
  let cumulative = 0;
  const curve = [];
  for (let i = 0; i < pnls.length; i++) {
    cumulative += pnls[i];
    const d = new Date();
    d.setDate(d.getDate() - (pnls.length - 1 - i)); // oldest first, ends today
    curve.push({
      date: d.toISOString().split('T')[0],
      cumulative_pnl: Math.round(cumulative),
      trade_count: 1 + (i % 3),
    });
  }
  return curve;
})();

// Mirrors GET /api/analytics/overview response shape
export const DEMO_OVERVIEW = {
  has_data: true, period_days: 30,
  kpis: {
    total_pnl: 7990, total_trades: 15, win_rate: 60,
    winners: 9, losers: 6,
    avg_win: 3933, avg_loss: -4635,
    profit_factor: 1.28, expectancy: 533,
    max_win_streak: 4, max_loss_streak: 3,
    current_streak: 2, current_streak_type: 'loss',
    best_day: { date: daysAgo(12).split('T')[0], pnl: 9300, trades: 2, win_rate: 100 },
    worst_day: { date: daysAgo(1).split('T')[0], pnl: -16075, trades: 3, win_rate: 33.3 },
    avg_duration_min: 118,
    max_drawdown: -23110,
    win_days: 6, loss_days: 4, trading_days: 10,
    largest_win: 6600, largest_loss: -13000,
  },
  equity_curve: EQUITY_CURVE,
  daily_pnl: [
    { date: daysAgo(15).split('T')[0], pnl: -3000,  trades: 1, win_rate: 0 },
    { date: daysAgo(14).split('T')[0], pnl: 6500,   trades: 1, win_rate: 100 },
    { date: daysAgo(12).split('T')[0], pnl: 9300,   trades: 2, win_rate: 100 },
    { date: daysAgo(10).split('T')[0], pnl: 2700,   trades: 1, win_rate: 100 },
    { date: daysAgo(9).split('T')[0],  pnl: 1850,   trades: 1, win_rate: 100 },
    { date: daysAgo(6).split('T')[0],  pnl: -7410,  trades: 3, win_rate: 0 },
    { date: daysAgo(5).split('T')[0],  pnl: 2300,   trades: 1, win_rate: 100 },
    { date: daysAgo(3).split('T')[0],  pnl: 3470,   trades: 2, win_rate: 50 },
    { date: daysAgo(2).split('T')[0],  pnl: 2250,   trades: 1, win_rate: 100 },
    { date: daysAgo(1).split('T')[0],  pnl: -16075, trades: 3, win_rate: 33.3 },
  ],
};

// ---------------------------------------------------------------------------
// Analytics: performance
// ---------------------------------------------------------------------------
// Mirrors GET /api/analytics/performance response shape
export const DEMO_PERFORMANCE = {
  has_data: true,
  period_days: 30,
  total_trades: 15,
  by_instrument: [
    { symbol: 'NIFTY25MAR23000CE',     trades: 4, pnl: 3750,   win_rate: 75,  avg_pnl: 938,   avg_duration_min: 78 },
    { symbol: 'BANKNIFTY2531748500PE', trades: 2, pnl: 4950,   win_rate: 100, avg_pnl: 2475,  avg_duration_min: 64 },
    { symbol: 'NIFTY2531723200PE',     trades: 2, pnl: -125,   win_rate: 50,  avg_pnl: -63,   avg_duration_min: 57 },
    { symbol: 'FORTIS25MAR960CE',      trades: 2, pnl: 11770,  win_rate: 100, avg_pnl: 5885,  avg_duration_min: 218 },
    { symbol: 'SOLARINDS',             trades: 2, pnl: -6500,  win_rate: 50,  avg_pnl: -3250, avg_duration_min: 176 },
    { symbol: 'NIFTY2531723200CE',     trades: 1, pnl: -2700,  win_rate: 0,   avg_pnl: -2700, avg_duration_min: 30 },
    { symbol: 'BANKNIFTY2531749000CE', trades: 1, pnl: -960,   win_rate: 0,   avg_pnl: -960,  avg_duration_min: 35 },
    { symbol: 'SENSEX25MAR75000PE',    trades: 1, pnl: -1700,  win_rate: 0,   avg_pnl: -1700, avg_duration_min: 165 },
  ],
  by_direction: {
    LONG:  { trades: 13, pnl: 9690,  win_rate: 61.5 },
    SHORT: { trades: 2,  pnl: -1700, win_rate: 50 },
  },
  by_product: {
    MIS:  { trades: 11, pnl: 1490, wins: 6, losses: 5, win_rate: 54.5, avg_pnl: 135 },
    NRML: { trades: 4,  pnl: 6500, wins: 3, losses: 1, win_rate: 75,   avg_pnl: 1625 },
  },
  by_hour: [
    { hour: 9,  label: '9:00',  trades: 5, pnl: 5100,   win_rate: 80 },
    { hour: 10, label: '10:00', trades: 3, pnl: 1450,   win_rate: 67 },
    { hour: 11, label: '11:00', trades: 3, pnl: 5210,   win_rate: 33 },
    { hour: 13, label: '13:00', trades: 1, pnl: -2700,  win_rate: 0 },
    { hour: 14, label: '14:00', trades: 3, pnl: -14270, win_rate: 0 },
  ],
  by_day_of_week: [
    { day: 0, name: 'Monday',    trades: 3, pnl: 4200,  win_rate: 67 },
    { day: 1, name: 'Tuesday',   trades: 4, pnl: 6350,  win_rate: 75 },
    { day: 2, name: 'Wednesday', trades: 3, pnl: 5850,  win_rate: 67 },
    { day: 3, name: 'Thursday',  trades: 4, pnl: -7410, win_rate: 25 },
    { day: 4, name: 'Friday',    trades: 1, pnl: -1000, win_rate: 0 },
  ],
  size_analysis: [
    { bucket: 'Small (<0.7x)',    trades: 3, pnl: 2850,  win_rate: 67, avg_pnl: 950 },
    { bucket: 'Medium (0.7-1.3x)',trades: 9, pnl: 12890, win_rate: 67, avg_pnl: 1432 },
    { bucket: 'Large (>1.3x)',    trades: 3, pnl: -7750, win_rate: 33, avg_pnl: -2583 },
  ],
};

// ---------------------------------------------------------------------------
// Analytics: timing heatmap
// ---------------------------------------------------------------------------
// Mirrors GET /api/analytics/timing-heatmap response shape
export const DEMO_TIMING_HEATMAP = {
  has_data: true,
  cells: [
    { hour: 9,  day: 0, day_name: 'Mon', hour_label: '9:00',  trades: 2, pnl: 3200,  avg_pnl: 1600,  win_rate: 100 },
    { hour: 10, day: 0, day_name: 'Mon', hour_label: '10:00', trades: 1, pnl: 1000,  avg_pnl: 1000,  win_rate: 100 },
    { hour: 9,  day: 1, day_name: 'Tue', hour_label: '9:00',  trades: 2, pnl: 1900,  avg_pnl: 950,   win_rate: 50 },
    { hour: 11, day: 1, day_name: 'Tue', hour_label: '11:00', trades: 2, pnl: 4450,  avg_pnl: 2225,  win_rate: 100 },
    { hour: 9,  day: 2, day_name: 'Wed', hour_label: '9:00',  trades: 1, pnl: 0,     avg_pnl: 0,     win_rate: 0 },
    { hour: 10, day: 2, day_name: 'Wed', hour_label: '10:00', trades: 2, pnl: 5850,  avg_pnl: 2925,  win_rate: 100 },
    { hour: 11, day: 3, day_name: 'Thu', hour_label: '11:00', trades: 1, pnl: 760,   avg_pnl: 760,   win_rate: 100 },
    { hour: 13, day: 3, day_name: 'Thu', hour_label: '13:00', trades: 1, pnl: -2700, avg_pnl: -2700, win_rate: 0 },
    { hour: 14, day: 3, day_name: 'Thu', hour_label: '14:00', trades: 2, pnl: -5470, avg_pnl: -2735, win_rate: 0 },
    { hour: 14, day: 4, day_name: 'Fri', hour_label: '14:00', trades: 1, pnl: -1000, avg_pnl: -1000, win_rate: 0 },
  ],
  by_hour: [
    { hour: 9,  label: '9:00',  trades: 5, pnl: 5100,  win_rate: 60 },
    { hour: 10, label: '10:00', trades: 3, pnl: 6850,  win_rate: 100 },
    { hour: 11, label: '11:00', trades: 3, pnl: 5210,  win_rate: 100 },
    { hour: 13, label: '13:00', trades: 1, pnl: -2700, win_rate: 0 },
    { hour: 14, label: '14:00', trades: 3, pnl: -6470, win_rate: 0 },
  ],
  by_day: [
    { day: 0, name: 'Mon', trades: 3, pnl: 4200,  win_rate: 100 },
    { day: 1, name: 'Tue', trades: 4, pnl: 6350,  win_rate: 75 },
    { day: 2, name: 'Wed', trades: 3, pnl: 5850,  win_rate: 67 },
    { day: 3, name: 'Thu', trades: 4, pnl: -7410, win_rate: 25 },
    { day: 4, name: 'Fri', trades: 1, pnl: -1000, win_rate: 0 },
  ],
};

// ---------------------------------------------------------------------------
// Analytics: behavioral analysis
// ---------------------------------------------------------------------------
export const DEMO_BEHAVIORAL = {
  has_data: true,
  patterns: [
    {
      pattern_type: 'revenge_trade', frequency: 3, severity: 'danger',
      estimated_cost: 8400,
      description: 'You entered positions within 30 min of a significant loss 3 times this month.',
      examples: ['NIFTY23000CE after SOLARINDS loss', 'NIFTY23200PE after BANKNIFTY loss'],
    },
    {
      pattern_type: 'holding_loser', frequency: 2, severity: 'caution',
      estimated_cost: 9200,
      description: 'Held losing positions 2-4× longer than winners. Average loser held 185 min vs 97 min for winners.',
      examples: ['SOLARINDS: 197 min', 'SENSEX75000PE: 165 min'],
    },
    {
      pattern_type: 'daily_overtrading', frequency: 1, severity: 'caution',
      estimated_cost: 3660,
      description: '5 trades on one day vs your average of 2.5. High-frequency days correlate with net losses.',
      examples: ['Day 6: 3 rapid-fire losses'],
    },
  ],
  summary: {
    total_behavioral_cost: 45840,
    clean_days: 5, flagged_days: 5,
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
  summary: `This month you traded 15 completed positions with a net P&L of ₹7,990. Your win rate is 60%, but 7 behavioral patterns have cost you an estimated ₹45,840 — meaning your clean trades made ₹53,830 and habits gave most of it back.

Three patterns stand out: revenge trading (3 incidents, ₹8,400), early exits leaving ₹7,680 on the table across 6 trades, and opening 5-min entries with a 19% win rate. You also have 2 open positions without stop-losses right now.

Your strongest edge is 9–10 AM NIFTY/BANKNIFTY (80% win rate). Your worst period is 2 PM onward — every afternoon loss this month followed a morning drawdown. Consider a rule: no new entries after 2 PM if you're already down.

One thing to build on: FORTIS options — both trades were textbook. Patient entry, defined hold time, clean exit.`,
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
  alerts: { this_week: 7, last_week: 1 },
  streaks: { days_without_revenge: 2, current_streak: 2, best_streak: 7 },
};

// ---------------------------------------------------------------------------
// Analytics: risk metrics
// ---------------------------------------------------------------------------
// Mirrors GET /api/analytics/risk-metrics response shape
export const DEMO_RISK_METRICS = {
  has_data: true,
  period_days: 30,
  max_drawdown: { amount: -23110, start_date: daysAgo(6).split('T')[0], end_date: daysAgo(1).split('T')[0] },
  drawdown_periods: [],
  daily_volatility: 7420,
  var_95: -9800,
  risk_reward_ratio: 0.85,
  consecutive_max: { wins: 4, losses: 3 },
  alerts_summary: [
    { pattern_type: 'revenge_trade',           count: 3, last_detected: daysAgo(1, 14, 40) },
    { pattern_type: 'daily_overtrading',             count: 2, last_detected: daysAgo(6, 11, 55) },
    { pattern_type: 'no_stoploss',             count: 2, last_detected: daysAgo(3, 12, 10) },
    { pattern_type: 'opening_5min_trap',       count: 1, last_detected: daysAgo(6, 9, 18) },
    { pattern_type: 'constitution_violation', count: 1, last_detected: daysAgo(1, 15, 5) },
  ],
  recent_alerts: [],
};

// ---------------------------------------------------------------------------
// Analytics: risk score
// ---------------------------------------------------------------------------
export const DEMO_RISK_SCORE = {
  score: 76,
  label: 'High Risk',
  components: {
    drawdown: 60, volatility: 70, behavioral: 84, discipline: 52,
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
// Mirrors GET /api/analytics/edge-confidence (Wilson interval) response shape
export const DEMO_EDGE_CONFIDENCE = {
  has_data: true,
  n: 15,
  wins: 9,
  observed_win_rate: 60.0,
  ci_lower: 35.7,
  ci_upper: 80.2,
  ci_center: 58.6,
  verdict: 'too_few',
  message: 'Only 15 trades — need at least 20 for a reliable reading.',
  is_reliable: false,
};

// ---------------------------------------------------------------------------
// Analytics: conditional performance
// ---------------------------------------------------------------------------
// Mirrors GET /api/analytics/conditional-performance response shape
export const DEMO_CONDITIONAL_PERFORMANCE = {
  has_data: true,
  total_trades: 15,
  baseline_win_rate: 60.0,
  baseline_avg_pnl: 533,
  conditions: [
    {
      key: 'after_loss', label: 'After a loss',
      win_rate: 30.0, avg_pnl: -4100, trade_count: 10, delta_vs_baseline: -30.0,
      narrative: 'Your win rate drops to 30% after a loss (vs 60% baseline) across 10 trades.',
    },
    {
      key: 'first_30min', label: 'Opening 30 minutes',
      win_rate: 40.0, avg_pnl: -1850, trade_count: 5, delta_vs_baseline: -20.0,
      narrative: 'In the opening 30 minutes your win rate drops to 40% (vs 60% baseline) across 5 trades.',
    },
    {
      key: 'expiry_day', label: 'Expiry day',
      win_rate: 44.4, avg_pnl: -320, trade_count: 9, delta_vs_baseline: -15.6,
      narrative: 'On expiry days your win rate drops to 44.4% (vs 60% baseline) across 9 trades.',
    },
    {
      key: 'quick_reentry', label: 'Quick re-entry (<20 min)',
      win_rate: 28.6, avg_pnl: -2870, trade_count: 7, delta_vs_baseline: -31.4,
      narrative: 'Quick re-entries (<20 min) show win rate drops to 28.6% (vs 60% baseline) across 7 trades.',
    },
  ],
};

// ---------------------------------------------------------------------------
// Analytics: options behavior
// ---------------------------------------------------------------------------
// Mirrors GET /api/analytics/options-behavior response shape
// (old flat ce_pnl/pe_pnl shape crashed OptionsBehaviorCard in guest mode)
export const DEMO_OPTIONS_BEHAVIOR = {
  period_days: 30,
  has_data: true,
  direction_confusion: {
    count: 2,
    underlying_breakdown: { NIFTY: 2 },
    avg_flip_minutes: 11.5,
  },
  premium_avg_down: {
    count: 1,
    total_re_entry_premium: 6750,
    avg_worst_loss_pct: -34.2,
  },
  iv_crush: {
    count: 1,
    total_loss: 2700,
    avg_hold_minutes: 165,
    avg_loss_pct: -30.4,
  },
};

// ---------------------------------------------------------------------------
// Analytics: pnl-percent (% Return tab)
// ---------------------------------------------------------------------------
export const DEMO_PNL_PERCENT = {
  has_data: true,
  avg_win_pct: 42.9,
  avg_loss_pct: -30.2,
  rr_ratio: 1.42,
  win_count: 9,
  loss_count: 6,
  avg_win_hold_minutes: 97,
  avg_loss_hold_minutes: 185,
  disposition_ratio: 1.9,
  by_hold_time: [
    { bucket: '<30m',   avg_pct: -45.5, count: 1, avg_win_pct: 0,    avg_loss_pct: -45.5 },
    { bucket: '30–60m', avg_pct: -12.7, count: 4, avg_win_pct: 44.1, avg_loss_pct: -31.6 },
    { bucket: '1–2h',   avg_pct: 27.1,  count: 4, avg_win_pct: 48.9, avg_loss_pct: -38.7 },
    { bucket: '2–4h',   avg_pct: 9.9,   count: 5, avg_win_pct: 32.5, avg_loss_pct: -16.0 },
    { bucket: '4h+',    avg_pct: 70.6,  count: 1, avg_win_pct: 70.6, avg_loss_pct: 0     },
  ],
  trades: [
    { tradingsymbol: 'NIFTY2531723200PE',   instrument_type: 'PE', direction: 'LONG', pnl_pct: 57.8,   realized_pnl: 3625,   duration_minutes: 85,  exit_time: daysAgo(1, 10, 47) },
    { tradingsymbol: 'SOLARINDS',           instrument_type: 'EQ', direction: 'LONG', pnl_pct: -1.5,   realized_pnl: -13000, duration_minutes: 197, exit_time: daysAgo(1, 14, 22) },
    { tradingsymbol: 'NIFTY25MAR23000CE',   instrument_type: 'CE', direction: 'LONG', pnl_pct: -30.7,  realized_pnl: -2700,  duration_minutes: 35,  exit_time: daysAgo(1, 15, 10) },
    { tradingsymbol: 'BANKNIFTY2531748500PE',instrument_type: 'PE', direction: 'LONG', pnl_pct: 44.1,  realized_pnl: 2250,   duration_minutes: 47,  exit_time: daysAgo(2, 10, 5)  },
    { tradingsymbol: 'FORTIS25MAR960CE',    instrument_type: 'CE', direction: 'LONG', pnl_pct: 32.4,   realized_pnl: 5170,   duration_minutes: 165, exit_time: daysAgo(3, 13, 15) },
    { tradingsymbol: 'SENSEX25MAR75000PE',  instrument_type: 'PE', direction: 'LONG', pnl_pct: -30.4,  realized_pnl: -1700,  duration_minutes: 165, exit_time: daysAgo(3, 14, 30) },
    { tradingsymbol: 'NIFTY25MAR23000CE',   instrument_type: 'CE', direction: 'LONG', pnl_pct: 45.1,   realized_pnl: 2300,   duration_minutes: 105, exit_time: daysAgo(5, 11, 10) },
    { tradingsymbol: 'NIFTY2531723200PE',   instrument_type: 'PE', direction: 'LONG', pnl_pct: -45.5,  realized_pnl: -3750,  duration_minutes: 28,  exit_time: daysAgo(6, 9, 48)  },
    { tradingsymbol: 'NIFTY2531723200CE',   instrument_type: 'CE', direction: 'LONG', pnl_pct: -37.5,  realized_pnl: -2700,  duration_minutes: 30,  exit_time: daysAgo(6, 10, 35) },
    { tradingsymbol: 'BANKNIFTY2531749000CE',instrument_type: 'CE', direction: 'LONG', pnl_pct: -26.7, realized_pnl: -960,   duration_minutes: 35,  exit_time: daysAgo(6, 11, 50) },
    { tradingsymbol: 'NIFTY25MAR23000CE',   instrument_type: 'CE', direction: 'LONG', pnl_pct: 47.4,   realized_pnl: 1850,   duration_minutes: 135, exit_time: daysAgo(9, 11, 45) },
    { tradingsymbol: 'BANKNIFTY2531748500PE',instrument_type: 'PE', direction: 'LONG', pnl_pct: 43.9,  realized_pnl: 2700,   duration_minutes: 80,  exit_time: daysAgo(10, 10, 40)},
    { tradingsymbol: 'FORTIS25MAR960CE',    instrument_type: 'CE', direction: 'LONG', pnl_pct: 70.6,   realized_pnl: 6600,   duration_minutes: 270, exit_time: daysAgo(12, 14, 30)},
    { tradingsymbol: 'SOLARINDS',           instrument_type: 'EQ', direction: 'LONG', pnl_pct: 1.6,    realized_pnl: 6500,   duration_minutes: 155, exit_time: daysAgo(14, 12, 20)},
    { tradingsymbol: 'NIFTY25MAR23000PE',   instrument_type: 'PE', direction: 'LONG', pnl_pct: -38.7,  realized_pnl: -3000,  duration_minutes: 105, exit_time: daysAgo(15, 14, 55)},
  ],
};

// ---------------------------------------------------------------------------
// Analytics: btst (BTST tab)
// ---------------------------------------------------------------------------
export const DEMO_BTST = {
  has_data: true,
  period_days: 30,
  total_btst_trades: 3,
  btst_win_rate: 67,
  btst_total_pnl: 4850,
  overnight_reversals: 1,
  reversal_pnl_lost: -2200,
  trades: [
    {
      id: 'btst-001', tradingsymbol: 'NIFTY25MAR23000CE',
      instrument_type: 'CE', direction: 'LONG',
      entry_time: daysAgo(4, 15, 15), exit_time: daysAgo(3, 9, 32),
      realized_pnl: 4200, avg_entry_price: 95, overnight_close_price: 142,
      was_profitable_at_eod: true, is_reversal: false,
      duration_minutes: 1097, hold_type: 'overnight' as const,
    },
    {
      id: 'btst-002', tradingsymbol: 'BANKNIFTY2531748500PE',
      instrument_type: 'PE', direction: 'LONG',
      entry_time: daysAgo(11, 15, 5), exit_time: daysAgo(10, 9, 41),
      realized_pnl: 2850, avg_entry_price: 290, overnight_close_price: 385,
      was_profitable_at_eod: true, is_reversal: false,
      duration_minutes: 1116, hold_type: 'overnight' as const,
    },
    {
      id: 'btst-003', tradingsymbol: 'NIFTY25MAR23000PE',
      instrument_type: 'PE', direction: 'LONG',
      entry_time: daysAgo(18, 15, 20), exit_time: daysAgo(17, 9, 38),
      realized_pnl: -2200, avg_entry_price: 180, overnight_close_price: 210,
      was_profitable_at_eod: true, is_reversal: true,
      duration_minutes: 1098, hold_type: 'overnight' as const,
    },
  ],
};

// ---------------------------------------------------------------------------
// Analytics: pnl-attribution (AttributionCard in SummaryTab)
// ---------------------------------------------------------------------------
export const DEMO_PNL_ATTRIBUTION = {
  has_data: true,
  total_pnl: 7990,
  clean_pnl: 30155,
  clean_count: 11,
  clean_wr: 73,
  clean_avg_pnl: 2741,
  flagged_pnl: -22165,
  flagged_count: 4,
  flagged_wr: 25,
  flagged_avg_pnl: -5541,
};

// ---------------------------------------------------------------------------
// Analytics: quality-breakdown (TradesTab quality scores)
// ---------------------------------------------------------------------------
// Mirrors GET /api/analytics/edge-leak response shape
export const DEMO_EDGE_LEAK = {
  has_data: true,
  period_days: 30,
  min_trades: 5,
  edges: [
    { dimension: 'Time',       label: '9 AM-10 AM',  trades: 5, pnl: 5100,  win_rate: 80 },
    { dimension: 'Instrument', label: 'BANKNIFTY',   trades: 5, pnl: 4950,  win_rate: 67 },
    { dimension: 'Type',       label: 'Call buys',   trades: 8, pnl: 3750,  win_rate: 63 },
  ],
  leaks: [
    { dimension: 'Time', label: '2 PM-3 PM', trades: 5, pnl: -14270, win_rate: 0 },
    { dimension: 'Day',  label: 'Thursday',  trades: 6, pnl: -7410,  win_rate: 33 },
  ],
};

// Mirrors GET /api/analytics/strategy-performance response shape
export const DEMO_STRATEGY_PERFORMANCE = {
  has_data: true,
  period_days: 30,
  strategies: [
    { kind: 'single_leg', key: 'Call buys', label: 'Call buys', trades: 8, pnl: 3750,  win_rate: 63,  avg_pnl: 469 },
    { kind: 'single_leg', key: 'Put buys',  label: 'Put buys',  trades: 5, pnl: 4175,  win_rate: 60,  avg_pnl: 835 },
    { kind: 'single_leg', key: 'Equity',    label: 'Equity',    trades: 2, pnl: -6500, win_rate: 50,  avg_pnl: -3250 },
    { kind: 'multi_leg',  key: 'straddle_buy', label: 'Straddle (buy)', trades: 1, pnl: -1200, win_rate: 0, avg_pnl: -1200 },
  ],
};

// Mirrors GET /api/analytics/quality-breakdown response shape
// (behavioural quality score 0–8; tiers high 7–8 / mid 5–6 / low 0–4)
export const DEMO_QUALITY_BREAKDOWN = {
  has_data: true,
  avg_score: 5.4,
  max_score: 8,
  tiers: {
    high: { count: 5, avg_pnl: 3634,  win_rate: 100,  total_pnl: 18170 },
    mid:  { count: 6, avg_pnl: 372,   win_rate: 66.7, total_pnl: 2230 },
    low:  { count: 4, avg_pnl: -3103, win_rate: 0,    total_pnl: -12410 },
  },
  per_trade: [
    { trade_id: 'ct-013', tradingsymbol: 'FORTIS25MAR960CE',      realized_pnl: 6600,   entry_time: daysAgo(12, 10, 0),  exit_time: daysAgo(12, 14, 30), score: 8, tier: 'high' },
    { trade_id: 'ct-001', tradingsymbol: 'NIFTY2531723200PE',     realized_pnl: 3625,   entry_time: daysAgo(1, 9, 22),   exit_time: daysAgo(1, 10, 47),  score: 7, tier: 'high' },
    { trade_id: 'ct-005', tradingsymbol: 'FORTIS25MAR960CE',      realized_pnl: 5170,   entry_time: daysAgo(3, 10, 30),  exit_time: daysAgo(3, 13, 15),  score: 7, tier: 'high' },
    { trade_id: 'ct-012', tradingsymbol: 'BANKNIFTY2531748500PE', realized_pnl: 2700,   entry_time: daysAgo(10, 9, 20),  exit_time: daysAgo(10, 10, 40), score: 7, tier: 'high' },
    { trade_id: 'ct-011', tradingsymbol: 'NIFTY25MAR23000CE',     realized_pnl: 1850,   entry_time: daysAgo(9, 9, 30),   exit_time: daysAgo(9, 11, 45),  score: 7, tier: 'high' },
    { trade_id: 'ct-004', tradingsymbol: 'BANKNIFTY2531748500PE', realized_pnl: 2250,   entry_time: daysAgo(2, 9, 18),   exit_time: daysAgo(2, 10, 5),   score: 6, tier: 'mid' },
    { trade_id: 'ct-007', tradingsymbol: 'NIFTY25MAR23000CE',     realized_pnl: 2300,   entry_time: daysAgo(5, 9, 25),   exit_time: daysAgo(5, 11, 10),  score: 6, tier: 'mid' },
    { trade_id: 'ct-014', tradingsymbol: 'SOLARINDS',             realized_pnl: 6500,   entry_time: daysAgo(14, 9, 45),  exit_time: daysAgo(14, 12, 20), score: 6, tier: 'mid' },
    { trade_id: 'ct-006', tradingsymbol: 'SENSEX25MAR75000PE',    realized_pnl: -1700,  entry_time: daysAgo(3, 11, 45),  exit_time: daysAgo(3, 14, 30),  score: 5, tier: 'mid' },
    { trade_id: 'ct-010', tradingsymbol: 'BANKNIFTY2531749000CE', realized_pnl: -960,   entry_time: daysAgo(6, 11, 15),  exit_time: daysAgo(6, 11, 50),  score: 5, tier: 'mid' },
    { trade_id: 'ct-015', tradingsymbol: 'NIFTY25MAR23000PE',     realized_pnl: -3000,  entry_time: daysAgo(15, 13, 10), exit_time: daysAgo(15, 14, 55), score: 5, tier: 'mid' },
    { trade_id: 'ct-002', tradingsymbol: 'SOLARINDS',             realized_pnl: -13000, entry_time: daysAgo(1, 11, 5),   exit_time: daysAgo(1, 14, 22),  score: 4, tier: 'low' },
    { trade_id: 'ct-003', tradingsymbol: 'NIFTY25MAR23000CE',     realized_pnl: -2700,  entry_time: daysAgo(1, 14, 35),  exit_time: daysAgo(1, 15, 10),  score: 2, tier: 'low' },
    { trade_id: 'ct-008', tradingsymbol: 'NIFTY2531723200PE',     realized_pnl: -3750,  entry_time: daysAgo(6, 9, 20),   exit_time: daysAgo(6, 9, 48),   score: 3, tier: 'low' },
    { trade_id: 'ct-009', tradingsymbol: 'NIFTY2531723200CE',     realized_pnl: -2700,  entry_time: daysAgo(6, 10, 5),   exit_time: daysAgo(6, 10, 35),  score: 3, tier: 'low' },
  ],
};

// ---------------------------------------------------------------------------
// Analytics: instrument drill-down (InstrumentPanel)
// ---------------------------------------------------------------------------
export const DEMO_INSTRUMENT_NIFTY = {
  has_data: true,
  underlying: 'NIFTY',
  total_trades: 8,
  total_pnl: 5275,
  win_rate: 62,
  profit_factor: 1.84,
  avg_hold_min: 94,
  avg_win: 2886,
  avg_loss: -2788,
  by_option_type: {
    CE: { trades: 5, pnl: 3050, win_rate: 60, avg_pnl: 610 },
    PE: { trades: 3, pnl: 2225, win_rate: 67, avg_pnl: 742 },
  },
  by_hour: [
    { hour: 9, label: '09:00', trades: 3, pnl: 6325, win_rate: 100 },
    { hour: 10, label: '10:00', trades: 1, pnl: -2700, win_rate: 0 },
    { hour: 11, label: '11:00', trades: 2, pnl: 4150, win_rate: 50 },
    { hour: 14, label: '14:00', trades: 1, pnl: -3000, win_rate: 0 },
    { hour: 15, label: '15:00', trades: 1, pnl: 2700, win_rate: 100 },
  ],
  equity_curve: (() => {
    const points = [3625, -2700, 2300, -3750, -2700, 1850, 2700, -3000];
    let cum = 0;
    return points.map((p, i) => {
      cum += p;
      const d = new Date();
      d.setDate(d.getDate() - (15 - i * 2));
      return { date: d.toISOString().split('T')[0], cumulative_pnl: cum };
    });
  })(),
  trades: [
    { id: 'ct-001', tradingsymbol: 'NIFTY2531723200PE',  direction: 'LONG', total_quantity: 50,  avg_entry_price: 125.5, avg_exit_price: 198.0, realized_pnl: 3625,  duration_minutes: 85,  exit_time: daysAgo(1, 10, 47),  option_type: 'PE' },
    { id: 'ct-003', tradingsymbol: 'NIFTY25MAR23000CE',  direction: 'LONG', total_quantity: 100, avg_entry_price: 88,    avg_exit_price: 61,    realized_pnl: -2700, duration_minutes: 35,  exit_time: daysAgo(1, 15, 10),  option_type: 'CE' },
    { id: 'ct-007', tradingsymbol: 'NIFTY25MAR23000CE',  direction: 'LONG', total_quantity: 50,  avg_entry_price: 102,   avg_exit_price: 148,   realized_pnl: 2300,  duration_minutes: 105, exit_time: daysAgo(5, 11, 10),  option_type: 'CE' },
    { id: 'ct-008', tradingsymbol: 'NIFTY2531723200PE',  direction: 'LONG', total_quantity: 150, avg_entry_price: 55,    avg_exit_price: 30,    realized_pnl: -3750, duration_minutes: 28,  exit_time: daysAgo(6, 9, 48),   option_type: 'PE' },
    { id: 'ct-009', tradingsymbol: 'NIFTY2531723200CE',  direction: 'LONG', total_quantity: 100, avg_entry_price: 72,    avg_exit_price: 45,    realized_pnl: -2700, duration_minutes: 30,  exit_time: daysAgo(6, 10, 35),  option_type: 'CE' },
    { id: 'ct-011', tradingsymbol: 'NIFTY25MAR23000CE',  direction: 'LONG', total_quantity: 50,  avg_entry_price: 78,    avg_exit_price: 115,   realized_pnl: 1850,  duration_minutes: 135, exit_time: daysAgo(9, 11, 45),  option_type: 'CE' },
    { id: 'ct-015', tradingsymbol: 'NIFTY25MAR23000PE',  direction: 'LONG', total_quantity: 50,  avg_entry_price: 155,   avg_exit_price: 95,    realized_pnl: -3000, duration_minutes: 105, exit_time: daysAgo(15, 14, 55), option_type: 'PE' },
  ],
};

// ---------------------------------------------------------------------------
// Behavioral patterns (MyPatterns page)
// ---------------------------------------------------------------------------
export const DEMO_BEHAVIORAL_ANALYSIS = {
  has_data: true,
  time_window_days: 30,
  patterns_detected: [
    {
      pattern_type: 'revenge_trade', count: 3, severity: 'danger',
      estimated_cost: 8400, last_seen: daysAgo(1, 14, 35),
      description: 'Quick re-entry after significant loss',
    },
    {
      pattern_type: 'holding_loser', count: 2, severity: 'caution',
      estimated_cost: 9200, last_seen: daysAgo(1, 14, 22),
      description: 'Holding losers 2-4× longer than winners',
    },
    {
      pattern_type: 'daily_overtrading', count: 1, severity: 'caution',
      estimated_cost: 3660, last_seen: daysAgo(6, 11, 50),
      description: 'High-frequency trading day correlated with net loss',
    },
    {
      pattern_type: 'size_escalation', count: 2, severity: 'danger',
      estimated_cost: 6300, last_seen: daysAgo(0, 10, 51),
      description: 'Position size 3–4× average after consecutive losses',
    },
    {
      pattern_type: 'early_exit', count: 6, severity: 'caution',
      estimated_cost: 7680, last_seen: daysAgo(0, 9, 38),
      description: 'Exiting profitable positions 42% before their peak on average',
    },
    {
      pattern_type: 'no_stoploss', count: 2, severity: 'danger',
      estimated_cost: 5800, last_seen: daysAgo(0, 9, 15),
      description: 'Open positions held 40+ min with no stop-loss defined',
    },
    {
      pattern_type: 'opening_5min_trap', count: 3, severity: 'caution',
      estimated_cost: 4800, last_seen: daysAgo(1, 9, 20),
      description: 'Entries within opening 5-min window — 19% win rate vs 54% baseline',
    },
  ],
  total_behavioral_cost: 45840,
  clean_days_pct: 52,
};

// ---------------------------------------------------------------------------
// Analytics: habits
// ---------------------------------------------------------------------------
// Mirrors GET /api/analytics/habits. Added because there was no fixture at all,
// so guest mode fell through to the `{}` catch-all: `has_data` read undefined,
// the tab rendered its locked state permanently, and it announced a 5-trade
// unlock gate directly beneath an Overview reporting 15 trades for the same
// period. Numbers below are consistent with DEMO_OVERVIEW / DEMO_PERFORMANCE.
//
// Bucket rows must carry `key` and `net_pnl` — the field names habits_service.py
// emits and HabitsTab reads. An earlier version of this fixture called the figure
// `pnl`, so every bar read Math.round(undefined) === NaN: the label printed "₹NaN",
// `net_pnl >= 0` was false so every bar rendered in the loss colour, and the NaN%
// width was rejected by CSS, leaving the bar's `inset: 0` to stretch it full width.
// A winning hour and a losing hour were indistinguishable. Renaming a mock field is
// not cosmetic — these fixtures are the only smoke test of the response shape.
export const DEMO_HABITS = {
  has_data: true,
  sample: 15,
  min_sample: 5,
  by_hour: [
    { key: 9,  label: '09:00', trades: 5, net_pnl: 5100,   win_rate: 80 },
    { key: 10, label: '10:00', trades: 3, net_pnl: 1450,   win_rate: 67 },
    { key: 11, label: '11:00', trades: 3, net_pnl: 5210,   win_rate: 33 },
    { key: 13, label: '13:00', trades: 1, net_pnl: -2700,  win_rate: 0  },
    { key: 14, label: '14:00', trades: 3, net_pnl: -14270, win_rate: 0  },
  ],
  by_day_of_week: [
    { key: 0, label: 'Mon', trades: 3, net_pnl: 4200,  win_rate: 67 },
    { key: 1, label: 'Tue', trades: 4, net_pnl: 6350,  win_rate: 75 },
    { key: 2, label: 'Wed', trades: 3, net_pnl: 5850,  win_rate: 67 },
    { key: 3, label: 'Thu', trades: 4, net_pnl: -7410, win_rate: 25 },
    { key: 4, label: 'Fri', trades: 1, net_pnl: -1000, win_rate: 0  },
  ],
  // Ascending net_pnl — worst first, matching habits_service.py's inst_rows sort.
  by_instrument: [
    { key: 'SOLARINDS', label: 'SOLARINDS', trades: 2, net_pnl: -6500, win_rate: 50  },
    { key: 'SENSEX',    label: 'SENSEX',    trades: 1, net_pnl: -1700, win_rate: 0   },
    { key: 'NIFTY',     label: 'NIFTY',     trades: 7, net_pnl: 925,   win_rate: 57  },
    { key: 'BANKNIFTY', label: 'BANKNIFTY', trades: 3, net_pnl: 3990,  win_rate: 67  },
    { key: 'FORTIS',    label: 'FORTIS',    trades: 2, net_pnl: 11770, win_rate: 100 },
  ],
  after_loss_size: {
    overall_avg_notional: 186_000,
    after_loss_avg_notional: 244_000,
    ratio: 1.31,
    after_loss_count: 6,
    min_bucket: 3,
  },
  summary: {
    total_trades: 15,
    gross_pnl: 7990,
    win_rate: 60,
    worst_hour: '14:00',
    best_hour: '09:00',
    worst_instrument: 'SOLARINDS',
    best_instrument: 'FORTIS',
  },
};

// ---------------------------------------------------------------------------
// Analytics: session log
// ---------------------------------------------------------------------------
// Mirrors GET /api/analytics/session-log. SessionLog renders INSIDE the Habits
// tab, so with no fixture it fell through to the `{}` catch-all: `has_data` read
// undefined and the component returned null. It vanished silently rather than
// erroring, which is the failure mode that makes this bug class hard to notice.
//
// Days reconcile exactly with DEMO_HABITS.by_day_of_week, because the two render
// on the same screen: Mon +4,200/3 · Tue +6,350/4 · Wed +5,850/3 (−2,700 and
// +8,550) · Thu −7,410/4 · Fri −1,000/1. Totals 15 trades and +₹7,990, matching
// DEMO_HABITS.summary. The 5 Aug day also matches DEMO_JOURNAL_ENTRIES.
//
// `insight` is not hand-written — it is what the endpoint's own rule produces
// from these days: the three losing days are −7,410 (revenge), −2,700 (revenge)
// and −1,000 (overtrading), so revenge wins 2 of 3.
export const DEMO_SESSION_LOG = {
  has_data: true,
  period_days: 60,
  days: [
    { date: '2026-08-05', pnl: -2700, trades: 1, alerts: 2,
      tag: 'revenge',     top_patterns: ['revenge_trade', 'no_stoploss'] },
    { date: '2026-08-04', pnl: 6350,  trades: 4, alerts: 1,
      tag: 'flagged',     top_patterns: ['early_exit'] },
    { date: '2026-08-03', pnl: 4200,  trades: 3, alerts: 0,
      tag: 'clean',       top_patterns: [] },
    { date: '2026-07-31', pnl: -1000, trades: 1, alerts: 1,
      tag: 'overtrading', top_patterns: ['overtrading'] },
    { date: '2026-07-30', pnl: -7410, trades: 4, alerts: 5,
      tag: 'revenge',     top_patterns: ['revenge_trade', 'size_escalation', 'rapid_reentry'] },
    { date: '2026-07-29', pnl: 8550,  trades: 2, alerts: 0,
      tag: 'clean',       top_patterns: [] },
  ],
  insight: { tag: 'revenge', count: 2, of: 3 },
};

// ---------------------------------------------------------------------------
// Analytics: behaviour → realized money
// ---------------------------------------------------------------------------
// Mirrors GET /api/analytics/behaviour-cost. FACTUAL framing throughout: these
// are the raw realized P&L of the exact completed trades each alert or rule
// breach fired on, never an estimate or a counterfactual. Added because there
// was no fixture, so the ranked cost leak rendered nothing in demo.
// Pattern P&L sums to the −₹14,270 the 2 PM-3 PM leak already reports.
export const DEMO_BEHAVIOUR_COST = {
  has_data: true,
  patterns: [
    { pattern_type: 'revenge_trade',   alert_count: 3, trade_count: 3, realized_pnl: -13000 },
    { pattern_type: 'size_escalation', alert_count: 2, trade_count: 2, realized_pnl: -6450  },
    { pattern_type: 'daily_overtrading',     alert_count: 2, trade_count: 4, realized_pnl: -3750  },
    { pattern_type: 'no_stoploss',     alert_count: 2, trade_count: 2, realized_pnl: -1700  },
    { pattern_type: 'early_exit',      alert_count: 1, trade_count: 1, realized_pnl: 820    },
  ],
  pattern_totals: { trade_count: 12, realized_pnl: -24080 },
  rules: [
    { rule: 'max_trades_per_day',  breach_count: 2, trade_count: 3, realized_pnl: -4610 },
    { rule: 'daily_loss_limit',    breach_count: 1, trade_count: 2, realized_pnl: -3000 },
    { rule: 'cooldown_after_loss', breach_count: 3, trade_count: 3, realized_pnl: -2700 },
  ],
  rule_totals: { trade_count: 8, realized_pnl: -10310 },
};

// Mirrors GET /api/risk/alert-response-stats — how the trader actually responds
// to their own alerts. Missing fixture crashed the Alerts Patterns tab.
export const DEMO_ALERT_RESPONSE_STATS = {
  total_took_anyway: 12,
  total_stopped: 3,
  total_ignored: 40,
  total_not_useful: 3,
  total_planned: 4,
  patterns: [
    { pattern: 'revenge_trade',   total: 9, ignored: 6, stopped: 1, took_anyway: 5,
      not_useful: 1, planned: 0, not_useful_rate: 0.11, ack_rate: 0.33 },
    { pattern: 'size_escalation', total: 7, ignored: 5, stopped: 1, took_anyway: 4,
      not_useful: 0, planned: 3, not_useful_rate: 0, ack_rate: 0.29 },
    { pattern: 'no_stoploss',     total: 6, ignored: 4, stopped: 1, took_anyway: 3,
      not_useful: 2, planned: 1, not_useful_rate: 0.33, ack_rate: 0.33 },
  ],
};

// ---------------------------------------------------------------------------
// Reports: saved morning briefs, EOD reports and weekly summaries
// ---------------------------------------------------------------------------
// Mirrors GET /api/reports/saved. Added because there was no fixture, so the
// page rendered "No reports yet" in demo — a misleading empty state rather
// than a crash, which is the harder version of the same bug. Figures line up
// with DEMO_OVERVIEW so the two screens do not contradict each other.
export const DEMO_SAVED_REPORTS = {
  total: 5,
  reports: [
    {
      id: 'rep-001', report_type: 'post_market', report_date: daysAgo(0, 15, 40).slice(0, 10),
      generated_at: daysAgo(0, 15, 40), sent_via: 'whatsapp',
      total_pnl: -8455, total_trades: 8, win_rate: 50,
    },
    {
      id: 'rep-002', report_type: 'morning_briefing', report_date: daysAgo(0, 8, 45).slice(0, 10),
      generated_at: daysAgo(0, 8, 45), sent_via: 'whatsapp',
      readiness_score: 62, watch_out_count: 2,
    },
    {
      id: 'rep-003', report_type: 'weekly_summary', report_date: daysAgo(2, 18, 0).slice(0, 10),
      generated_at: daysAgo(2, 18, 0), sent_via: null,
      total_pnl: 7990, total_trades: 15, win_rate: 60,
    },
    {
      id: 'rep-004', report_type: 'post_market', report_date: daysAgo(3, 15, 40).slice(0, 10),
      generated_at: daysAgo(3, 15, 40), sent_via: 'whatsapp',
      total_pnl: 3625, total_trades: 4, win_rate: 75,
    },
    {
      id: 'rep-005', report_type: 'morning_briefing', report_date: daysAgo(3, 8, 45).slice(0, 10),
      generated_at: daysAgo(3, 8, 45), sent_via: 'whatsapp',
      readiness_score: 78, watch_out_count: 1,
    },
  ],
};

// ---------------------------------------------------------------------------
// Journal entries
// ---------------------------------------------------------------------------
// The guest stub deliberately returned an empty list, so the page could only
// ever be seen in its empty state. These mirror GET /api/journal and reference
// the same trades as DEMO_RISK_ALERTS, so an entry and the alert that prompted
// it describe the same event.
export const DEMO_JOURNAL_ENTRIES = {
  total: 5,
  entries: [
    // Today's day-level entry, so the Today block renders written rather than
    // only ever showing its empty prompt.
    {
      id: 'je-000', trade_id: null, emotion_tags: ['focused'],
      followed_plan: null, deviation_reason: null, exit_reason: null,
      setup_quality: null, would_repeat: null, market_condition: 'choppy',
      notes: 'Only A+ breakouts. Nothing before 10am.',
      lessons: 'Five minutes off the screen after any stopout.',
      trade_symbol: null, trade_type: null, trade_pnl: null,
      entry_type: 'day', created_at: daysAgo(0, 8, 50), updated_at: daysAgo(0, 8, 50),
    },
    {
      id: 'je-001', trade_id: 'ct-t01', emotion_tags: ['revenge', 'anxious'],
      followed_plan: 'no', deviation_reason: 'Re-entered 25 min after the SOLARINDS loss',
      exit_reason: 'stopped_out', setup_quality: 3, would_repeat: 'no',
      market_condition: 'choppy',
      notes: 'Took NIFTY23000CE straight after the big loss. Knew it was wrong while placing it.',
      lessons: 'One loss ends the day when I am tired, it does not start a streak.',
      trade_symbol: 'NIFTY23000CE', trade_type: 'MIS', trade_pnl: '-2700',
      entry_type: 'trade', created_at: daysAgo(0, 14, 40), updated_at: daysAgo(0, 14, 40),
    },
    {
      id: 'je-002', trade_id: 'ct-t02', emotion_tags: ['calm'],
      followed_plan: 'yes', deviation_reason: null,
      exit_reason: 'target_hit', setup_quality: 8, would_repeat: 'yes',
      market_condition: 'trending',
      notes: 'Waited for the retest, sized normally, took the target without moving it.',
      trade_symbol: 'FORTIS25MAR960CE', trade_type: 'NRML', trade_pnl: '6600',
      entry_type: 'trade', created_at: daysAgo(1, 10, 15), updated_at: daysAgo(1, 10, 15),
    },
    {
      id: 'je-003', trade_id: 'ct-t03', emotion_tags: ['fomo'],
      followed_plan: 'partial', deviation_reason: 'Entered late, chased the move',
      exit_reason: 'manual', setup_quality: 4, would_repeat: 'no',
      market_condition: 'volatile',
      notes: 'Saw it running and jumped in without waiting for a pullback.',
      trade_symbol: 'BANKNIFTY2531748500CE', trade_type: 'MIS', trade_pnl: '2700',
      entry_type: 'trade', created_at: daysAgo(2, 9, 25), updated_at: daysAgo(2, 9, 25),
    },
    {
      id: 'je-004', trade_id: null, emotion_tags: ['overconfident'],
      followed_plan: null, deviation_reason: null, exit_reason: null,
      setup_quality: null, would_repeat: null, market_condition: null,
      notes: 'Three green days running. Watch the size tomorrow — that is usually when it slips.',
      lessons: 'Plan-only days are my best days. Do more of them.',
      trade_symbol: null, trade_type: null, trade_pnl: null,
      entry_type: 'note', created_at: daysAgo(3, 16, 5), updated_at: daysAgo(3, 16, 5),
    },
  ],
};

// ---------------------------------------------------------------------------
// My Rules — the trading constitution
// ---------------------------------------------------------------------------
// Mirrors the four /api/constitution/* endpoints. Added because none were
// stubbed, so the page rendered "Could not load your rules. Connect your broker
// and complete onboarding first." — a failure message shown to a demo user who
// has no broker to connect. Limits line up with DEMO_RISK_STATE.
export const DEMO_CONSTITUTION = {
  rules: {
    daily_loss_limit: 25000,
    daily_trade_limit: 5,
    max_position_size: 200000,
    cooldown_after_loss: 15,
    max_consecutive_losses: 3,
    restricted_windows: ['09:15-09:30'],
  },
  pending: null,
  accepted_at: daysAgo(21, 19, 30),
};

export const DEMO_CONSTITUTION_STATUS = {
  status: [
    { rule: 'daily_loss',            current: 8455, limit: 25000, ratio: 0.34 },
    { rule: 'daily_trades',          current: 9,    limit: 5,     ratio: 1.8  },
    { rule: 'max_position_size',     current: 186000, limit: 200000, ratio: 0.93 },
    { rule: 'cooldown_after_loss',   active: true,  remaining_min: 7, limit_min: 15 },
    { rule: 'max_consecutive_losses', current: 2,   limit: 3,     ratio: 0.67 },
    { rule: 'restricted_windows',    windows: ['09:15-09:30'] },
  ],
};

export const DEMO_CONSTITUTION_VIOLATIONS = {
  today: [
    { rule: 'daily_trade_limit',   severity: 'danger',  message: '9 trades today against a limit of 5.',            detected_at: daysAgo(0, 14, 22) },
    { rule: 'cooldown_after_loss', severity: 'caution', message: 'Re-entered 6 min after a loss; cooldown is 15.',   detected_at: daysAgo(0, 13, 40) },
  ],
  total: 11,
  by_rule: {
    daily_trade_limit: 5,
    cooldown_after_loss: 4,
    max_position_size: 2,
  },
};

// Mirrors GET /api/risk/patterns. A subset of the real catalogue, byte-identical
// in shape to what the endpoint returns — guest fixtures double as smoke
// fixtures, and every past divergence between a mock and its endpoint shipped
// as a live bug. `count` is the real total; the list is trimmed to the patterns
// the demo alerts actually use.
export const DEMO_PATTERN_CATALOGUE = {
  "patterns": [
    {
      "pattern_type": "martingale_behaviour",
      "label": "Averaging down",
      "observes": "Position size increasing after consecutive losses on the same instrument.",
      "explanation": "Each step raises the total at risk in the session, not just the cost of this trade.",
      "nature": "risk",
      "disposition": "alerting",
      "trigger": "exit",
      "guardian_eligible": false,
      "version": "1.1.0"
    },
    {
      "pattern_type": "overtrading_burst",
      "label": "Burst of trades",
      "observes": "Positions opened inside a 30-minute window, counting a multi-leg structure as one.",
      "explanation": "Trades taken minutes apart share one state of mind rather than separate assessments.",
      "nature": "emotional",
      "disposition": "alerting",
      "trigger": "exit",
      "guardian_eligible": false,
      "version": "2.0.0"
    },
    {
      "pattern_type": "early_exit",
      "label": "Early exit",
      "observes": "Winning positions closed well short of your usual holding time.",
      "explanation": "Winners cut short while losers run is the asymmetry that quietly caps a strategy.",
      "nature": "performance",
      "disposition": "analytics",
      "trigger": "session",
      "guardian_eligible": false,
      "version": "2.0.0"
    },
    {
      "pattern_type": "daily_overtrading",
      "label": "Heavy day",
      "observes": "Total positions opened today, counting a multi-leg structure as one.",
      "explanation": "Past a certain count the day stops being a series of decisions and becomes momentum.",
      "nature": null,
      "disposition": "alerting",
      "trigger": "position",
      "guardian_eligible": false,
      "version": "2.0.0"
    },
    {
      "pattern_type": "rapid_reentry",
      "label": "Immediate re-entry",
      "observes": "Re-entering the same instrument shortly after closing it at a loss.",
      "explanation": "The setup that just failed has not changed in those few minutes. The re-entry is a second attempt at the same idea at a worse moment.",
      "nature": "emotional",
      "disposition": "analytics",
      "trigger": "exit",
      "guardian_eligible": false,
      "version": "2.0.0"
    },
    {
      "pattern_type": "no_stoploss",
      "label": "No stop-loss on record",
      "observes": "Whether a stop-loss order was on the position when it was exited.",
      "explanation": "A pre-defined exit is decided before the position moves. Without one, the exit is decided while it is moving.",
      "nature": "risk",
      "disposition": "alerting",
      "trigger": "exit",
      "guardian_eligible": false,
      "version": "1.0.0"
    },
    {
      "pattern_type": "opening_5min_trap",
      "label": "Opening-minutes entry",
      "observes": "Entries in the first minutes after open that closed quickly at a loss, or lost heavily.",
      "explanation": "Spreads are widest and option premiums least settled while the market is still finding its level.",
      "nature": "emotional",
      "disposition": "analytics",
      "trigger": "exit",
      "guardian_eligible": false,
      "version": "2.0.0"
    },
    {
      "pattern_type": "premium_loss_event",
      "label": "Premium destruction",
      "observes": "Percentage of the premium paid that has been lost on a long option.",
      "explanation": "Beyond a point the position needs a move it was never sized for. Time is on the other side.",
      "nature": "risk",
      "disposition": "alerting",
      "trigger": "exit",
      "guardian_eligible": false,
      "version": "2.0.0"
    },
    {
      "pattern_type": "post_loss_recovery_bet",
      "label": "Recovery bet",
      "observes": "A position materially larger than your average, entered after a loss on the same underlying.",
      "explanation": "If this one also loses, the combined loss exceeds everything it was meant to recover.",
      "nature": "risk",
      "disposition": "alerting",
      "trigger": "exit",
      "guardian_eligible": false,
      "version": "1.1.0"
    },
    {
      "pattern_type": "size_escalation",
      "label": "Rising position size",
      "observes": "Quantity across consecutive trades on the same underlying while losing.",
      "explanation": "Larger size on an instrument that is already losing compounds the drawdown rather than recovering it.",
      "nature": "emotional",
      "disposition": "alerting",
      "trigger": "exit",
      "guardian_eligible": false,
      "version": "1.1.0"
    },
    {
      "pattern_type": "constitution_violation",
      "label": "Rule breach",
      "observes": "Your own limits — loss cap, trade count, cooldown, no-trade windows, position size — against what you actually did.",
      "explanation": "These are your numbers, written when the session was not running.",
      "nature": "discipline",
      "disposition": "alerting",
      "trigger": "exit",
      "guardian_eligible": true,
      "version": "1.0.0"
    },
    {
      "pattern_type": "session_meltdown",
      "label": "Session breakdown",
      "observes": "Session P&L against your daily loss limit, together with the pace of trading.",
      "explanation": "A session that is both deep in loss and accelerating is the shape a bad day takes before it becomes the worst one.",
      "nature": "risk",
      "disposition": "alerting",
      "trigger": "exit",
      "guardian_eligible": true,
      "version": "1.0.0"
    },
    {
      "pattern_type": "revenge_trade",
      "label": "Trade straight after a loss",
      "observes": "How soon a new position follows a losing exit, and how its size compares to your average.",
      "explanation": "A decision taken while the previous loss is still fresh is being made against that loss rather than on its own terms.",
      "nature": "emotional",
      "disposition": "alerting",
      "trigger": "exit",
      "guardian_eligible": false,
      "version": "2.0.0"
    }
  ],
  "count": 33,
  "severity_order": [
    "info",
    "caution",
    "danger",
    "critical"
  ]
};

// Mirrors GET /api/positions/structures. The demo positions are two unrelated
// single legs, so there is no structure to report — an empty list is the honest
// fixture, and it exercises the path where the table renders flat rows.
export const DEMO_OPEN_STRUCTURES = { structures: [], count: 0 };

// Mirrors GET /api/risk/patterns/{pattern_type}/my-record — the trader's own
// history with a pattern, which replaced the invented population statistics
// that used to sit in the alert panel. `enough` gates the display: below
// min_sample the UI says so rather than showing a number built from 3 trades.
export const DEMO_PATTERN_RECORD = {
  pattern_type: 'revenge_trade',
  window_days: 180,
  times_fired: 11,
  last_seen: daysAgo(4, 11, 20),
  trades_measured: 9,
  win_rate: 22.2,
  wins: 2,
  losses: 7,
  pnl: -18400,
  avg_pnl: -2044.44,
  best: 1250,
  worst: -6800,
  enough: true,
  min_sample: 5,
};

// Mirrors GET /api/constitution/suggestions exactly — field names included.
// Guest fixtures double as smoke fixtures, and every past divergence between a
// mock and its endpoint shipped as a live bug.
export const DEMO_RULE_SUGGESTIONS = {
  suggestions: [
    {
      field: 'daily_loss_limit',
      current_value: 25000,
      suggested_value: 12000,
      headline: 'Set your daily loss limit to ₹12,000',
      evidence: [
        { label: 'Red sessions in this window', value: '14 of 38 · median ₹7,400' },
        { label: 'Sessions that reached ₹12,000', value: '4 · deepest ₹31,200' },
      ],
      confidence: 'high',
      sample: { sessions: 38, red_sessions: 14, window_days: 90 },
    },
    {
      field: 'max_consecutive_losses',
      current_value: 3,
      suggested_value: 2,
      headline: 'Stop after 2 consecutive losses',
      evidence: [
        { label: 'Your next trade after 2 losses in a row', value: 'won 3 of 19 · 16%' },
        { label: 'Your win rate the rest of the time', value: '47% across 214 trades' },
      ],
      confidence: 'medium',
      sample: { trades: 214, sessions: 38, window_days: 90 },
    },
  ],
  status: 'ok',
  reason: null,
  withheld: [],
  context: {
    window_days: 90,
    trades: 214,
    sessions: 38,
    min_sessions: 10,
    min_trades: 30,
    multi_leg_detected: false,
  },
};

export const DEMO_CONSTITUTION_HISTORY = {
  history: [
    {
      changed_at: daysAgo(4, 20, 10), change_type: 'tighten',
      changes: { daily_trade_limit: { old: 8, new: 5 } },
    },
    {
      changed_at: daysAgo(12, 21, 5), change_type: 'loosen',
      changes: { daily_loss_limit: { old: 20000, new: 25000 } },
    },
  ],
};

// Mirrors GET /api/constitution/effective — declared vs enforced, with the
// reason they differ. Deliberately includes an overridden rule: the trader
// declared 50 trades a day, their own baseline says 6, so 6 is enforced. That
// is the case the old page displayed as "50" with nothing said about it.
export const DEMO_CONSTITUTION_EFFECTIVE = {
  has_baseline: true,
  rules: {
    daily_trade_limit:      { declared: 50,     effective: 6,      source: 'learned',  overridden: true  },
    cooldown_after_loss:    { declared: 15,     effective: 15,     source: 'declared', overridden: false },
    daily_loss_limit:       { declared: 25000,  effective: 25000,  source: 'declared', overridden: false },
    max_position_size:      { declared: 200000, effective: 200000, source: 'declared', overridden: false },
    max_consecutive_losses: { declared: null,   effective: 3,      source: 'default',  overridden: false },
  },
  ungoverned: {
    burst_trades_per_30min_caution: 4,
    burst_trades_per_30min_danger: 7,
    consecutive_loss_caution: 3,
    consecutive_loss_danger: 5,
    revenge_window_caution_min: 12,
    daily_trade_danger: 9,
  },
};
