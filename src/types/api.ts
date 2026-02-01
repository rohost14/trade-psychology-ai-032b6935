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
  current_value: number;
  status: 'open' | 'closed';
}

export interface Trade {
  id: string;
  tradingsymbol: string;
  exchange: string;
  trade_type: 'BUY' | 'SELL';
  quantity: number;
  price: number;
  pnl: number;
  traded_at: string;
  order_id?: string;
}

export interface Alert {
  id: string;
  pattern_name: string;
  severity: 'critical' | 'high' | 'medium' | 'positive';
  timestamp: string;
  message: string;
  acknowledged?: boolean;
  why_it_matters?: string;
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
}
