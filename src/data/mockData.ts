import { Position, Trade, Alert } from '@/types/api';

export interface MockRiskState {
  risk_state: 'safe' | 'caution' | 'danger';
  status_message: string;
  active_patterns: string[];
  unrealized_pnl: number;
  ai_recommendations: string[];
  last_synced: string;
}

export const mockRiskState: MockRiskState = {
  risk_state: 'danger',
  status_message: 'High Risk Zone',
  active_patterns: ['Revenge Trading', 'Overtrading'],
  unrealized_pnl: -4850,
  ai_recommendations: [
    'You\'ve taken 7 trades in 45 minutes. Consider pausing.',
    'Last 3 trades were after losses - revenge pattern detected.',
    'Position sizes are 2x your usual - slow down.',
  ],
  last_synced: 'Synced 30 seconds ago',
};

export const mockPositions: (Position & { instrument_type: string; unrealized_pnl: number; current_value: number })[] = [
  {
    id: 'pos1',
    tradingsymbol: 'NIFTY26FEB22000CE',
    exchange: 'NFO',
    instrument_type: 'OPTION',
    total_quantity: 100,
    average_entry_price: 185.50,
    average_exit_price: null,
    realized_pnl: 0,
    unrealized_pnl: -2340,
    current_value: 16210,
    status: 'open',
  },
  {
    id: 'pos2',
    tradingsymbol: 'BANKNIFTY26FEB48000PE',
    exchange: 'NFO',
    instrument_type: 'OPTION',
    total_quantity: 50,
    average_entry_price: 320.00,
    average_exit_price: null,
    realized_pnl: 0,
    unrealized_pnl: -1875,
    current_value: 14125,
    status: 'open',
  },
];

// Closed trades - only last 24 hours (for dashboard display)
export const mockClosedTrades: Trade[] = [
  {
    id: 'ct1',
    tradingsymbol: 'NIFTY26FEB21900PE',
    exchange: 'NFO',
    trade_type: 'SELL',
    quantity: 50,
    price: 145.50,
    pnl: -1850,
    traded_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(), // 1 hour ago
  },
  {
    id: 'ct2',
    tradingsymbol: 'NIFTY26FEB21900PE',
    exchange: 'NFO',
    trade_type: 'BUY',
    quantity: 100,
    price: 152.25,
    pnl: -2400,
    traded_at: new Date(Date.now() - 1.5 * 60 * 60 * 1000).toISOString(), // 1.5 hours ago (revenge trade)
  },
  {
    id: 'ct3',
    tradingsymbol: 'BANKNIFTY26FEB47800CE',
    exchange: 'NFO',
    trade_type: 'SELL',
    quantity: 25,
    price: 280.00,
    pnl: 875,
    traded_at: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(), // 3 hours ago
  },
  {
    id: 'ct4',
    tradingsymbol: 'NIFTY26FEB22100CE',
    exchange: 'NFO',
    trade_type: 'SELL',
    quantity: 50,
    price: 95.00,
    pnl: -1200,
    traded_at: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(), // 4 hours ago
  },
  {
    id: 'ct5',
    tradingsymbol: 'INFY26FEB1900CE',
    exchange: 'NFO',
    trade_type: 'SELL',
    quantity: 400,
    price: 18.50,
    pnl: 640,
    traded_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(), // 6 hours ago
  },
  {
    id: 'ct6',
    tradingsymbol: 'TCS26FEB4200PE',
    exchange: 'NFO',
    trade_type: 'SELL',
    quantity: 175,
    price: 32.00,
    pnl: -980,
    traded_at: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(), // 8 hours ago
  },
];

export const mockAlerts: (Alert & { pattern: string; description: string; why_it_matters?: string })[] = [
  {
    id: '1',
    pattern_name: 'Revenge Trading',
    pattern: 'Revenge Trading',
    severity: 'high',
    description: 'New position 3 min after ₹1,850 loss',
    message: 'Quick re-entry after significant loss',
    why_it_matters: 'Revenge trades have 40% lower win rate. Your last 5 revenge trades lost ₹8,200.',
    timestamp: new Date(Date.now() - 1.5 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: '2',
    pattern_name: 'Overtrading',
    pattern: 'Overtrading Session',
    severity: 'high',
    description: '7 trades in 45 min (limit: 5)',
    message: 'Excessive trading frequency',
    why_it_matters: 'Win rate drops from 58% to 31% after 5th trade. Lost ₹4,300 in overtrades today.',
    timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: '3',
    pattern_name: 'Position Sizing',
    pattern: 'Position Size OK',
    severity: 'positive',
    description: 'All positions within 5% limit',
    message: 'Proper risk management',
    why_it_matters: 'Keeping positions sized correctly reduces emotional decisions by 2x.',
    timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
  },
];
