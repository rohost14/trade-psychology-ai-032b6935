export const BROKER_ACCOUNT_ID = '550e8400-e29b-41d4-a716-446655440000';

export const RISK_COLORS = {
  safe: '#10b981',     // emerald-500
  caution: '#f59e0b',  // amber-500
  danger: '#ef4444',   // red-500
} as const;

export const RISK_STATES = {
  SAFE: 'safe',
  CAUTION: 'caution',
  DANGER: 'danger',
} as const;

export const POLLING_INTERVAL = 30000; // 30 seconds
export const INSIGHT_REFRESH_INTERVAL = 120000; // 2 minutes

export const SEVERITY_ORDER = {
  critical: 0,
  high: 1,
  medium: 2,
  positive: 3,
} as const;

export type RiskState = keyof typeof RISK_COLORS;
export type Severity = keyof typeof SEVERITY_ORDER;
