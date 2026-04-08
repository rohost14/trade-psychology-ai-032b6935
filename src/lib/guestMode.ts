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
  if (path === '/api/analytics/critical-trades') return DEMO_CRITICAL_TRADES;
  if (path === '/api/analytics/edge-confidence') return DEMO_EDGE_CONFIDENCE;
  if (path === '/api/analytics/conditional-performance') return DEMO_CONDITIONAL_PERFORMANCE;
  if (path === '/api/analytics/options-behavior') return DEMO_OPTIONS_BEHAVIOR;
  if (path === '/api/analytics/journal-correlation') return DEMO_JOURNAL_CORRELATION;
  if (path === '/api/analytics/ai-insights') return DEMO_AI_INSIGHTS;
  if (path === '/api/analytics/ai-summary') return DEMO_AI_SUMMARY;
  if (path === '/api/analytics/dashboard-stats') {
    return {
      total_pnl: 7990, win_rate: 60, trade_count: 15,
      money_saved: 21260, behavioral_alerts: 6,
    };
  }
  if (path === '/api/analytics/unrealized-pnl') {
    return { unrealized_pnl: 440, positions_count: 2 };
  }

  // Behavioral
  if (path === '/api/behavioral/analysis') return DEMO_BEHAVIORAL_ANALYSIS;
  if (path === '/api/behavioral/patterns') {
    return { patterns: DEMO_BEHAVIORAL_ANALYSIS.patterns_detected };
  }

  // Money saved
  if (path.includes('/api/analytics/money-saved')) {
    return { total_saved: 21260, alerts_count: 3, period_days: 30 };
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

  // Catch-all: any unmocked route in guest mode returns empty success
  // Prevents 401s from hitting the real backend (which would fire token-expired events)
  return {};
}
