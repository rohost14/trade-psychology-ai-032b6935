// Alert Context Provider — Backend-only behavioral alerts
//
// Architecture:
//   - Single engine: backend BehaviorEngine is the ONLY detection engine.
//     Frontend patternDetector.ts has been removed.
//   - alerts (persistent)  = fetched from backend risk_alerts table
//   - WebSocket events     = trigger immediate refetch when new alert fires
//   - Toast on new alerts  = shown when WebSocket fires a new alert
//   - capital              = resolved from Kite margin (equity.total) or profile fallback
//
// Capital resolution priority:
//   1. profile.trading_capital (user-declared in Settings)
//   2. Kite equity.total (live margin data — automatically derived, zero user effort)
//   3. 100,000 hardcoded floor (cold start / not connected)

import { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import { PatternSeverity, PatternType } from '@/types/patterns';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { isMarketOpen } from '@/lib/exchangeConstants';

// Re-export hook for AlertContext internal use (avoids circular import issues)
function useWebSocketAlerts() {
  return useWebSocket();
}

const CAPITAL_FLOOR = 100_000; // Rs 1L floor — used only when nothing else is available

// Profile shape (6 user-declared fields; all others are backend-derived)
export interface UserProfileThresholds {
  daily_trade_limit?: number;
  cooldown_after_loss?: number;
  trading_capital?: number;
  max_position_size?: number;
  sl_percent_futures?: number;
  sl_percent_options?: number;
}

export interface AlertNotification {
  id: string;
  pattern: {
    id: string;
    type: PatternType;
    /** Original backend pattern_type string — use this for buildFacts / PATTERN_EXPLANATIONS lookups */
    backend_type: string;
    name: string;
    severity: PatternSeverity;
    description: string;
    detected_at: string | undefined;
    insight: unknown;
    historical_insight: unknown;
    estimated_cost: number;
    trades_involved: string[];
    frequency_this_week: number;
    frequency_this_month: number;
    /** Raw context dict from behavior_engine — e.g. gap_minutes, prior_loss, streak */
    details: Record<string, unknown>;
  };
  shown_at: string | undefined;
  acknowledged: boolean;
}

interface AlertContextValue {
  // Persistent alerts from backend risk_alerts table
  alerts: AlertNotification[];
  unacknowledgedCount: number;

  // User profile (6 fields) — still useful for Settings display
  traderProfile: UserProfileThresholds | null;

  // Resolved trading capital
  capital: number;

  // Actions
  acknowledgeAlert: (alertId: string) => void;
  acknowledgeAll: () => void;
  clearAllAlerts: () => void;
}

const AlertContext = createContext<AlertContextValue | undefined>(undefined);

// ---------------------------------------------------------------------------
// Backend pattern_type → frontend PatternType mapping
// ---------------------------------------------------------------------------
const BACKEND_TO_FRONTEND_TYPE: Record<string, string> = {
  'consecutive_loss':  'consecutive_losses',
  'revenge_sizing':    'revenge_trading',
  'tilt_loss_spiral':  'revenge_trading',
  'overtrading':       'overtrading',
  'fomo':              'fomo',
  'fomo_entry':        'fomo',
  'revenge_trade':     'revenge_trading',
  'martingale_behaviour': 'position_sizing',
  'size_escalation':   'position_sizing',
  'excess_exposure':   'position_sizing',
  'session_meltdown':  'capital_drawdown',
  'no_stoploss':       'no_stoploss',
  'early_exit':        'early_exit',
  'winning_streak_overconfidence': 'winning_streak_overconfidence',
  'panic_exit':        'early_exit',
  'rapid_reentry':     'same_instrument_chasing',
  'rapid_flip':        'same_instrument_chasing',
  'burst_trading':     'overtrading',
  'consecutive_loss_streak': 'consecutive_losses',
  'options_direction_confusion': 'options_direction_confusion',
  'options_premium_avg_down':    'options_premium_avg_down',
  'iv_crush_behavior':           'iv_crush_behavior',
  'expiry_day_overtrading':      'overtrading',
  'opening_5min_trap':           'opening_5min_trap',
  'end_of_session_mis_panic':    'end_of_session_mis_panic',
  'post_loss_recovery_bet':      'post_loss_recovery_bet',
  'profit_giveaway':             'profit_giveaway',
};

function formatPatternName(patternType: string): string {
  const names: Record<string, string> = {
    'consecutive_loss':              'Consecutive Loss Spiral',
    'consecutive_losses':            'Consecutive Losses',
    'consecutive_loss_streak':       'Consecutive Loss Streak',
    'revenge_sizing':                'Revenge Sizing',
    'revenge_trading':               'Revenge Trading',
    'revenge_trade':                 'Revenge Trade',
    'overtrading':                   'Overtrading',
    'burst_trading':                 'Burst Trading',
    'fomo':                          'FOMO Entry',
    'fomo_entry':                    'FOMO Entry',
    'tilt_loss_spiral':              'Tilt / Loss Spiral',
    'position_sizing':               'Oversized Position',
    'excess_exposure':               'Excess Exposure',
    'size_escalation':               'Size Escalation',
    'martingale_behaviour':          'Martingale / Averaging Down',
    'same_instrument_chasing':       'Instrument Chasing',
    'rapid_reentry':                 'Rapid Re-entry',
    'rapid_flip':                    'Rapid Direction Flip',
    'loss_aversion':                 'Loss Aversion',
    'early_exit':                    'Early Exit',
    'panic_exit':                    'Panic Exit',
    'no_stoploss':                   'No Stop-Loss',
    'winning_streak_overconfidence': 'Overconfidence (Win Streak)',
    'session_meltdown':              'Session Meltdown',
    'capital_drawdown':              'Capital Drawdown',
    'options_direction_confusion':   'Direction Confusion',
    'options_premium_avg_down':      'Premium Averaging Down',
    'iv_crush_behavior':             'IV Crush',
    'opening_5min_trap':             'Opening 5-Min Trap',
    'end_of_session_mis_panic':      'End-of-Session Panic',
    'post_loss_recovery_bet':        'Recovery Bet',
    'profit_giveaway':               'Profit Giveaway',
  };
  return names[patternType]
    || patternType.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

// Type for raw backend alert (what the API actually returns)
interface BackendAlert {
  id: string;
  pattern_type: string;
  severity: string;
  message: string;
  details?: Record<string, unknown>;
  detected_at?: string;
  created_at?: string;
  acknowledged_at?: string | null;
  acknowledged?: boolean; // present in demo data and some API responses
}

// Map backend severity strings to frontend PatternSeverity
function normalizeSeverity(s: string): PatternSeverity {
  const map: Record<string, PatternSeverity> = {
    danger:   'high',
    critical: 'critical',
    high:     'high',
    caution:  'medium',
    medium:   'medium',
    low:      'low',
  };
  return map[s.toLowerCase()] ?? 'medium';
}

function mapBackendAlert(a: BackendAlert): AlertNotification {
  const frontendType = (BACKEND_TO_FRONTEND_TYPE[a.pattern_type] || a.pattern_type) as PatternType;
  const detected_at = a.detected_at || a.created_at;
  return {
    id: String(a.id),
    pattern: {
      id:                  String(a.id),
      type:                frontendType,
      backend_type:        a.pattern_type,
      name:                formatPatternName(a.pattern_type),
      severity:            normalizeSeverity(a.severity),
      description:         a.message,
      detected_at,
      insight:             a.details?.insight || '',
      historical_insight:  a.details?.historical_insight || '',
      estimated_cost:      (a.details?.estimated_cost as number) ?? 0,
      trades_involved:     [],
      frequency_this_week:  0,
      frequency_this_month: 0,
      details:             (a.details as Record<string, unknown>) ?? {},
    },
    shown_at:     detected_at,
    acknowledged: a.acknowledged ?? (a.acknowledged_at != null),
  };
}

const SEVERITY_LABEL: Record<string, string> = {
  critical: '🚨 Danger',
  danger:   '🚨 Danger',
  high:     '⚠️ High Alert',
  medium:   '⚡ Caution',
  caution:  '⚡ Caution',
  low:      'ℹ️ Info',
};

export function AlertProvider({ children }: { children: ReactNode }) {
  const [alerts,        setAlerts]        = useState<AlertNotification[]>([]);
  const [traderProfile, setTraderProfile] = useState<UserProfileThresholds | null>(null);
  const [capital,       setCapital]       = useState<number>(CAPITAL_FLOOR);

  // Track IDs already toasted so we never double-toast the same alert
  const toastedIdsRef = useRef<Set<string>>(new Set());

  // ---------------------------------------------------------------------------
  // Capital resolution: profile.trading_capital → Kite equity.total → floor
  // ---------------------------------------------------------------------------
  useEffect(() => {
    async function resolveCapitalAndProfile() {
      try {
        const res = await api.get('/api/profile/');
        const profile = res.data?.profile as UserProfileThresholds | null;
        if (profile) setTraderProfile(profile);

        if (profile?.trading_capital && profile.trading_capital > 0) {
          setCapital(profile.trading_capital);
          return;
        }

        try {
          const mRes = await api.get('/api/zerodha/margins');
          const equityTotal: number = mRes.data?.equity?.total ?? 0;
          if (equityTotal > 0) {
            setCapital(equityTotal);
            return;
          }
        } catch {
          // Not connected or market closed — fall through
        }

        setCapital(CAPITAL_FLOOR);
      } catch {
        // Not authenticated yet — keep floor
      }
    }

    resolveCapitalAndProfile();
  }, []);

  // ---------------------------------------------------------------------------
  // Fetch alerts from backend — single source of truth
  // ---------------------------------------------------------------------------
  const fetchAlerts = useCallback(async (showToasts = false) => {
    try {
      const res = await api.get('/api/risk/alerts', { params: { hours: 48 } });
      const raw: BackendAlert[] = res.data.alerts || [];
      const mapped = raw.map(mapBackendAlert);
      setAlerts(mapped);

      if (showToasts) {
        for (let i = 0; i < mapped.length; i++) {
          const alert = mapped[i];
          const rawAlert = raw[i];
          if (!alert.acknowledged && !toastedIdsRef.current.has(alert.id)) {
            // Always mark as seen so we don't revisit on the next WebSocket event
            toastedIdsRef.current.add(alert.id);

            // Gate: only show real-time toast during market hours for this exchange.
            // Alert is always saved to DB and visible in Alerts history.
            // NSE/NFO/BSE/BFO close at 15:30; MCX runs until 23:30; CDS until 17:00.
            const exchange = (rawAlert.details?.exchange as string | undefined) ?? 'NSE';
            if (!isMarketOpen(exchange)) continue;

            const sev = alert.pattern.severity;
            const label = SEVERITY_LABEL[sev] ?? '⚠️ Alert';
            if (sev === 'critical' || sev === 'high') {
              toast.error(`${label}: ${alert.pattern.name}`, {
                description: alert.pattern.description,
                duration: 8000,
              });
            } else if (sev === 'medium') {
              toast.warning(`${label}: ${alert.pattern.name}`, {
                description: alert.pattern.description,
                duration: 5000,
              });
            }
          }
        }
      } else {
        // Seed toasted set from existing alerts (prevent re-toast on next WS event)
        mapped.forEach(a => toastedIdsRef.current.add(a.id));
      }
    } catch {
      // Non-fatal — user may not be authenticated yet
    }
  }, []);

  // Initial fetch — seed toasted IDs, no toasts
  useEffect(() => {
    fetchAlerts(false);
  }, [fetchAlerts]);

  // React to WebSocket alert events — refetch and toast new ones
  const { lastAlertEvent } = useWebSocketAlerts();
  useEffect(() => {
    if (lastAlertEvent) fetchAlerts(true);
  }, [lastAlertEvent]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------------------------------------------------------------------------
  // Alert actions
  // ---------------------------------------------------------------------------
  const acknowledgeAlert = useCallback(async (alertId: string) => {
    setAlerts(prev => prev.map(a => a.id === alertId ? { ...a, acknowledged: true } : a));
    try {
      await api.post(`/api/risk/alerts/${alertId}/acknowledge`);
    } catch {
      setAlerts(prev => prev.map(a => a.id === alertId ? { ...a, acknowledged: false } : a));
    }
  }, []);

  const acknowledgeAll = useCallback(() => {
    setAlerts(prev => prev.map(a => ({ ...a, acknowledged: true })));
  }, []);

  const clearAllAlerts = useCallback(() => {
    setAlerts([]);
  }, []);

  const unacknowledgedCount = alerts.filter(a => !a.acknowledged).length;

  return (
    <AlertContext.Provider value={{
      alerts,
      unacknowledgedCount,
      traderProfile,
      capital,
      acknowledgeAlert,
      acknowledgeAll,
      clearAllAlerts,
    }}>
      {children}
    </AlertContext.Provider>
  );
}

export function useAlerts() {
  const context = useContext(AlertContext);
  if (!context) throw new Error('useAlerts must be used within AlertProvider');
  return context;
}
