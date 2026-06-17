/**
 * Guest Mode — API intercept layer.
 * When guest mode is active, returns demo data instead of hitting the backend.
 */

import {
  DEMO_ACCOUNT, DEMO_COMPLETED_TRADES, DEMO_POSITIONS, DEMO_RISK_STATE,
  DEMO_RISK_ALERTS, DEMO_PROFILE, DEMO_OVERVIEW, DEMO_PERFORMANCE,
  DEMO_TIMING_HEATMAP, DEMO_BEHAVIORAL, DEMO_JOURNAL_CORRELATION,
  DEMO_AI_INSIGHTS, DEMO_AI_SUMMARY, DEMO_PROGRESS, DEMO_RISK_METRICS,
  DEMO_RISK_SCORE, DEMO_CRITICAL_TRADES, DEMO_EDGE_CONFIDENCE,
  DEMO_CONDITIONAL_PERFORMANCE, DEMO_OPTIONS_BEHAVIOR, DEMO_BEHAVIORAL_ANALYSIS,
  DEMO_PNL_PERCENT, DEMO_BTST, DEMO_PNL_ATTRIBUTION, DEMO_QUALITY_BREAKDOWN,
  DEMO_INSTRUMENT_NIFTY,
} from './demoData';

export const GUEST_MODE_KEY = 'tradementor_guest_mode';

export function isGuestMode(): boolean {
  return localStorage.getItem(GUEST_MODE_KEY) === 'true';
}

export function enableGuestMode(): void {
  localStorage.setItem(GUEST_MODE_KEY, 'true');
}

export function disableGuestMode(): void {
  localStorage.removeItem(GUEST_MODE_KEY);
}

// ---------------------------------------------------------------------------
// Route matcher — returns mock data for a given URL path + method.
// Returns `undefined` if the path is not mocked (falls through to real network).
// ---------------------------------------------------------------------------
export function getGuestResponse(url: string, method = 'GET'): unknown | undefined {
  const path = url.split('?')[0]; // strip query params
  const m = method.toUpperCase();

  // POST / DELETE — return success stubs silently
  if (m === 'POST' || m === 'DELETE' || m === 'PATCH') {
    // Specific cases
    if (path.includes('/api/profile/onboarding')) return { success: true };
    if (path.includes('/api/zerodha/sync')) return { message: 'Guest mode — no sync needed' };
    if (path.includes('/api/risk/alerts') && path.includes('/acknowledge')) return { success: true };
    if (path.includes('/api/journal')) return { id: 'demo-journal', success: true };
    // Generic POST stub
    return { success: true };
  }

  // GET routes
  if (path === '/api/zerodha/accounts') {
    return { accounts: [DEMO_ACCOUNT] };
  }
  if (path === '/api/zerodha/token/validate') {
    return { valid: true, needs_login: false };
  }
  if (path === '/api/zerodha/margins' || path === '/api/zerodha/margins/') {
    return {
      equity: { available: 250000, used: 87500, total: 250000, utilization_pct: 35,
        breakdown: { cash: 250000, collateral: 0, intraday_payin: 0, exposure: 60000, span: 27500, option_premium: 0 } },
      commodity: { available: 0, used: 0, total: 0, utilization_pct: 0, breakdown: {} },
      overall: { max_utilization_pct: 35, risk_level: 'safe', risk_message: 'Margin levels are healthy.' },
    };
  }
  if (path.includes('/api/zerodha/margins/insights')) {
    return { current_status: null, history: { has_data: false, snapshots: [] }, insights: [] };
  }
  if (path === '/api/zerodha/holdings' || path.includes('/api/zerodha/holdings')) {
    return { holdings: [] };
  }
  if (path === '/api/positions/' || path === '/api/positions') {
    return { positions: DEMO_POSITIONS };
  }
  if (path === '/api/trades/completed' || path === '/api/trades/') {
    return { trades: DEMO_COMPLETED_TRADES, total: DEMO_COMPLETED_TRADES.length };
  }
  if (path === '/api/risk/state') return DEMO_RISK_STATE;
  if (path === '/api/risk/alerts') return { alerts: DEMO_RISK_ALERTS };
  if (path === '/api/profile/' || path === '/api/profile') return DEMO_PROFILE;

  // Analytics
  if (path === '/api/analytics/overview') return DEMO_OVERVIEW;
  if (path === '/api/analytics/performance') return DEMO_PERFORMANCE;
  if (path === '/api/analytics/timing-heatmap') return DEMO_TIMING_HEATMAP;
  if (path === '/api/analytics/progress') return DEMO_PROGRESS;
  if (path === '/api/analytics/risk-metrics') return DEMO_RISK_METRICS;
  if (path === '/api/analytics/risk-score') return DEMO_RISK_SCORE;
  if (path === '/api/analytics/critical-trades') {
    // Normalize demo data: backend uses flag_reasons, demo uses reasons
    return {
      ...DEMO_CRITICAL_TRADES,
      trades: DEMO_CRITICAL_TRADES.trades.map((t: any) => ({
        ...t,
        flag_reasons: t.flag_reasons ?? t.reasons ?? [],
      })),
    };
  }
  if (path === '/api/analytics/edge-confidence') return DEMO_EDGE_CONFIDENCE;
  if (path === '/api/analytics/conditional-performance') return DEMO_CONDITIONAL_PERFORMANCE;
  if (path === '/api/analytics/options-behavior') return DEMO_OPTIONS_BEHAVIOR;
  if (path === '/api/analytics/journal-correlation') return DEMO_JOURNAL_CORRELATION;
  if (path === '/api/analytics/ai-insights') return DEMO_AI_INSIGHTS;
  if (path === '/api/analytics/ai-summary') return DEMO_AI_SUMMARY;
  if (path === '/api/analytics/dashboard-stats') {
    return {
      total_pnl: 7990, win_rate: 60, trade_count: 15,
      money_saved: 45840, behavioral_alerts: 7,
    };
  }
  if (path === '/api/analytics/unrealized-pnl') {
    return { unrealized_pnl: 440, positions_count: 2 };
  }
  if (path === '/api/analytics/pnl-percent') return DEMO_PNL_PERCENT;
  if (path === '/api/analytics/btst') return DEMO_BTST;
  if (path === '/api/analytics/pnl-attribution') return DEMO_PNL_ATTRIBUTION;
  if (path === '/api/analytics/quality-breakdown') return DEMO_QUALITY_BREAKDOWN;
  if (path === '/api/analytics/expiry-pattern') {
    return {
      has_data: true,
      period_days: 90,
      expiry: { trade_count: 18, win_rate: 44.4, avg_pnl: -320, total_pnl: -5760 },
      non_expiry: { trade_count: 47, win_rate: 61.7, avg_pnl: 285, total_pnl: 13395 },
      by_hour: [
        { hour: 9,  label: '09:00', expiry_count: 4, expiry_avg_pnl: -180, non_expiry_count: 8,  non_expiry_avg_pnl: 210 },
        { hour: 10, label: '10:00', expiry_count: 6, expiry_avg_pnl: -420, non_expiry_count: 12, non_expiry_avg_pnl: 340 },
        { hour: 11, label: '11:00', expiry_count: 3, expiry_avg_pnl: 150,  non_expiry_count: 9,  non_expiry_avg_pnl: 280 },
        { hour: 14, label: '14:00', expiry_count: 5, expiry_avg_pnl: -580, non_expiry_count: 10, non_expiry_avg_pnl: 190 },
        { hour: 15, label: '15:00', expiry_count: 0, expiry_avg_pnl: 0,    non_expiry_count: 8,  non_expiry_avg_pnl: 310 },
      ],
      worst_expiry_trades: [
        { symbol: 'NIFTY25JUN24200PE', pnl: -2400, hour: 14 },
        { symbol: 'BANKNIFTY25JUN50000PE', pnl: -1800, hour: 10 },
      ],
      by_expiry_week_dow: [
        { day: 'Mon', trade_count: 12, win_rate: 58.3, avg_pnl: 240,  total_pnl: 2880  },
        { day: 'Tue', trade_count: 18, win_rate: 55.6, avg_pnl: 180,  total_pnl: 3240  },
        { day: 'Wed', trade_count: 22, win_rate: 50.0, avg_pnl: 80,   total_pnl: 1760  },
        { day: 'Thu', trade_count: 28, win_rate: 39.3, avg_pnl: -420, total_pnl: -11760 },
        { day: 'Fri', trade_count: 8,  win_rate: 62.5, avg_pnl: 310,  total_pnl: 2480  },
      ],
    };
  }
  if (path === '/api/analytics/trade-sequence') {
    return {
      has_data: true,
      period_days: 90,
      baseline_win_rate: 58.5,
      baseline_avg_pnl: 220,
      sequence: [
        { ordinal: 1, label: '#1', trade_count: 52, win_rate: 67.3, avg_pnl: 380, delta_win_rate: 8.8 },
        { ordinal: 2, label: '#2', trade_count: 48, win_rate: 62.5, avg_pnl: 290, delta_win_rate: 4.0 },
        { ordinal: 3, label: '#3', trade_count: 42, win_rate: 59.5, avg_pnl: 210, delta_win_rate: 1.0 },
        { ordinal: 4, label: '#4', trade_count: 35, win_rate: 54.3, avg_pnl: 140, delta_win_rate: -4.2 },
        { ordinal: 5, label: '#5', trade_count: 28, win_rate: 46.4, avg_pnl: -80, delta_win_rate: -12.1 },
        { ordinal: 6, label: '#6', trade_count: 18, win_rate: 38.9, avg_pnl: -210, delta_win_rate: -19.6 },
        { ordinal: 7, label: '#7', trade_count: 12, win_rate: 33.3, avg_pnl: -390, delta_win_rate: -25.2 },
      ],
    };
  }
  if (path === '/api/analytics/instrument') {
    // Return NIFTY data for any underlying in demo
    return DEMO_INSTRUMENT_NIFTY;
  }
  if (path === '/api/analytics/discipline-summary') {
    return {
      has_data: true,
      score: 52,
      max_score: 100,
      week_start: new Date(Date.now() - 6 * 86_400_000).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }),
      danger_alerts: 3,
      caution_alerts: 4,
      trades_this_week: 5,
      revenge_free_days: 1,
      weekly_trend: [72, 81, 55, 52],
      breakdown: { alerts_score: 22, quality_score: 30 },
    };
  }

  // Behavioral
  if (path === '/api/behavioral/analysis') return DEMO_BEHAVIORAL_ANALYSIS;
  if (path === '/api/behavioral/patterns') {
    return { patterns: DEMO_BEHAVIORAL_ANALYSIS.patterns_detected };
  }

  // Dashboard predictive warnings
  if (path.includes('/api/dashboard/warnings') || path.includes('/api/risk/warnings')) {
    return {
      warnings: [
        { id: 'w1', message: 'You\'re 63% into your daily loss limit.', severity: 'caution', pattern_type: 'daily_limit' },
        { id: 'w2', message: 'Last 3 afternoon trades: all losers. Close early today.', severity: 'high', pattern_type: 'time_pattern' },
      ],
    };
  }

  // Portfolio radar
  if (path.includes('/api/portfolio-radar') || path.includes('/api/portfolio_radar')) {
    return {
      has_data: true,
      concentration_score: 68,
      top_holding: 'NIFTY options',
      warnings: ['NIFTY options represent 55% of open risk'],
      positions: DEMO_POSITIONS,
    };
  }

  // Reports
  if (path.includes('/api/reports')) {
    return { reports: [], has_data: false };
  }

  // Personalization
  if (path.includes('/api/personalization/insights')) {
    return {
      has_data: true,
      last_updated: new Date(Date.now() - 3600_000).toISOString(),
      trades_analyzed: 87,
      insights: [
        { type: 'danger_time',    icon: '⏰', title: 'Your Danger Hour',   value: '14:00',  detail: '28% win rate', recommendation: 'Avoid trading at 14:00 — historically your worst hour' },
        { type: 'best_time',      icon: '✨', title: 'Your Best Hour',     value: '09:00',  detail: '68% win rate', recommendation: 'Focus your high-conviction trades at market open' },
        { type: 'problem_symbol', icon: '🚫', title: 'Avoid This',         value: 'BANKNIFTY', detail: '24% win rate', recommendation: 'Consider removing BANKNIFTY from your watchlist' },
        { type: 'strong_symbol',  icon: '💪', title: 'Your Edge',          value: 'NIFTY',  detail: '62% win rate', recommendation: 'Focus more on NIFTY — consistent edge detected' },
        { type: 'revenge_window', icon: '⏱️', title: 'Your Revenge Window', value: '8 min', detail: 'Typical re-entry after a loss', recommendation: 'Set cooldown to at least 12 minutes to break the pattern' },
      ],
      predictive_alerts: [
        { type: 'time_warning',   message: 'Heads up: 14:00–15:00 is historically your weakest hour (28% win rate)', severity: 'caution' },
        { type: 'symbol_warning', message: 'Warning: Your win rate on BANKNIFTY is only 24%. Consider avoiding or reducing size.', severity: 'danger' },
      ],
    };
  }
  if (path.includes('/api/personalization/learn') || path.includes('/api/personalization')) {
    return { success: true };
  }

  // AI Coach — return a canned demo message
  if (path.includes('/api/coach')) {
    return {
      message: 'Welcome to TradeMentor demo! Connect your Zerodha account to get personalized coaching based on your actual trades.',
      session_id: 'demo-session',
    };
  }

  // Journal entries
  if (path.includes('/api/journal')) {
    return { entries: [], total: 0 };
  }

  // Goals
  if (path.includes('/api/goals')) {
    return { goals: [], streaks: {} };
  }

  // Alerts page
  if (path === '/api/behavioral/alerts' || path.includes('/api/alerts')) {
    return { alerts: DEMO_RISK_ALERTS, total: DEMO_RISK_ALERTS.length };
  }

  // Notification status
  if (path.includes('/api/profile/notification-status')) {
    return {
      whatsapp: { twilio_configured: false, phone_set: false },
      push: { enabled: false },
      email: { smtp_configured: false },
    };
  }

  // Blowup Shield — must match ShieldSummary interface
  if (path.includes('/api/shield/summary')) {
    return {
      total_alerts: 22, danger_count: 8, caution_count: 14,
      heeded_count: 15, continued_count: 7, post_alert_pnl_continued: -4120,
      heeded_streak: 4, spiral_sessions: 1,
    };
  }
  if (path.includes('/api/shield/timeline')) {
    return { timeline: [], total: 0 };
  }
  if (path.includes('/api/shield/patterns')) {
    return { patterns: [] };
  }

  // GTT / orders
  if (path.includes('/api/gtt') || path.includes('/api/orders')) {
    return { orders: [], gtt: [] };
  }

  // Catch-all: any unmocked GET route returns {} to prevent 401s from the real
  // backend (guest mode has no auth token). Add a specific stub above for any
  // endpoint that should render demo data instead of a blank state.
  if (import.meta.env.DEV) {
    // eslint-disable-next-line no-console
    console.warn(`[GuestMode] No stub for ${m} ${path} — add one in getGuestResponse() to show demo data`);
  }
  return {};
}
