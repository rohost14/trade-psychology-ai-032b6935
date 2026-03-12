// Alert Context Provider — Single source of truth for behavioral alerts
//
// Architecture:
//   - alerts (persistent)  = fetched from backend risk_alerts table (polled every 60s)
//   - patterns (ephemeral) = computed client-side for real-time session toasts ONLY
//   - localStorage         = completely removed — backend is the persistent store
//   - capital              = resolved from Kite margin (equity.total) or profile fallback
//
// Capital resolution priority:
//   1. profile.trading_capital (user-declared in Settings)
//   2. Kite equity.total (live margin data — automatically derived, zero user effort)
//   3. 100,000 hardcoded floor (cold start / not connected)

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { BehaviorPattern, PatternSeverity, PatternType } from '@/types/patterns';
import { Trade } from '@/types/api';
import { detectAllPatterns, getPatternStats } from '@/lib/patternDetector';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { buildPatternConfig, UserProfileThresholds } from '@/lib/patternConfig';
import { useWebSocket } from '@/contexts/WebSocketContext';

// Re-export hook for AlertContext internal use (avoids circular import issues)
function useWebSocketAlerts() {
  return useWebSocket();
}

const CAPITAL_FLOOR = 100_000; // Rs 1L floor — used only when nothing else is available

export interface AlertNotification {
  id: string;
  pattern: BehaviorPattern;
  shown_at: string;
  acknowledged: boolean;
}

interface AlertContextValue {
  // Ephemeral session patterns (client-side, for stats + real-time detection)
  patterns: BehaviorPattern[];

  // Persistent alerts from backend risk_alerts table
  alerts: AlertNotification[];
  unacknowledgedCount: number;

  // Stats (from session patterns)
  stats: {
    total: number;
    by_severity: Record<PatternSeverity, number>;
    by_type: Partial<Record<PatternType, number>>;
    total_cost: number;
  };

  // State
  isAnalyzing: boolean;
  lastAnalyzed: Date | null;
  traderProfile: UserProfileThresholds | null;

  // Resolved trading capital — use this everywhere instead of traderProfile.trading_capital
  // Source: profile.trading_capital → Kite equity.total → 100,000 floor
  capital: number;

  // Actions
  runAnalysis: (trades: Trade[]) => void;
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
};

function formatPatternName(patternType: string): string {
  const names: Record<string, string> = {
    'consecutive_loss':              'Consecutive Loss Spiral',
    'consecutive_losses':            'Consecutive Losses',
    'revenge_sizing':                'Revenge Sizing',
    'revenge_trading':               'Revenge Trading',
    'overtrading':                   'Overtrading Burst',
    'fomo':                          'FOMO Entry',
    'tilt_loss_spiral':              'Tilt / Loss Spiral',
    'position_sizing':               'Oversized Position',
    'same_instrument_chasing':       'Same Instrument Chasing',
    'loss_aversion':                 'Loss Aversion',
    'early_exit':                    'Early Exit',
    'no_stoploss':                   'No Stop-Loss',
    'winning_streak_overconfidence': 'Winning Streak Overconfidence',
  };
  return names[patternType]
    || patternType.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

// Type for raw backend alert (what the API actually returns)
interface BackendAlert {
  id: string;
  pattern_type: string;
  severity: string;  // 'danger' | 'caution' | 'high' | 'medium' | 'low' | 'critical'
  message: string;
  details?: Record<string, unknown>;
  detected_at?: string;
  created_at?: string;
  acknowledged_at?: string | null;
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
      name:                formatPatternName(a.pattern_type),
      severity:            normalizeSeverity(a.severity),
      description:         a.message,
      detected_at,
      insight:             a.details?.insight || '',
      historical_insight:  a.details?.historical_insight || '',
      estimated_cost:      a.details?.estimated_cost ?? 0,
      trades_involved:     [],
      frequency_this_week:  0,
      frequency_this_month: 0,
    },
    shown_at:     detected_at,
    acknowledged: a.acknowledged_at != null,
  };
}

const getSeverityLabel = (severity: string) => {
  switch (severity) {
    case 'critical':
    case 'danger':   return '🚨 Danger';
    case 'high':     return '⚠️ High Alert';
    case 'medium':
    case 'caution':  return '⚡ Caution';
    case 'low':      return 'ℹ️ Info';
    default:         return '⚠️ Alert';
  }
};

export function AlertProvider({ children }: { children: ReactNode }) {
  const [patterns,           setPatterns]           = useState<BehaviorPattern[]>([]);
  const [alerts,             setAlerts]             = useState<AlertNotification[]>([]);
  const [isAnalyzing,        setIsAnalyzing]        = useState(false);
  const [lastAnalyzed,       setLastAnalyzed]       = useState<Date | null>(null);
  const [traderProfile,      setTraderProfile]      = useState<UserProfileThresholds | null>(null);
  const [capital,            setCapital]            = useState<number>(CAPITAL_FLOOR);
  const [lastTradeSignature, setLastTradeSignature] = useState<string>('');

  // Session-only set — tracks pattern_type+date combos already shown as toasts.
  // Seeded from backend alerts on load so we never re-toast a known alert.
  const [shownPatternKeys, setShownPatternKeys] = useState<Set<string>>(new Set());

  // ---------------------------------------------------------------------------
  // Capital resolution: profile.trading_capital → Kite equity.total → floor
  // Called once on mount. If profile has manual capital, no margin call needed.
  // ---------------------------------------------------------------------------
  useEffect(() => {
    async function resolveCapitalAndProfile() {
      try {
        const res = await api.get('/api/profile/');
        const profile = res.data?.profile as UserProfileThresholds | null;
        if (profile) setTraderProfile(profile);

        if (profile?.trading_capital && profile.trading_capital > 0) {
          // Tier 1: user has explicitly set their capital — trust it
          setCapital(profile.trading_capital);
          return;
        }

        // Tier 2: derive from live Kite equity margin (zero user effort)
        try {
          const mRes = await api.get('/api/zerodha/margins');
          const equityTotal: number = mRes.data?.equity?.total ?? 0;
          if (equityTotal > 0) {
            setCapital(equityTotal);
            return;
          }
        } catch {
          // Margins not available (not connected, market closed, etc.) — fall through
        }

        // Tier 3: floor — user is not connected or hasn't traded yet
        setCapital(CAPITAL_FLOOR);
      } catch {
        // Profile fetch failed (not authenticated yet) — keep floor
      }
    }

    resolveCapitalAndProfile();
  }, []);

  // ---------------------------------------------------------------------------
  // Backend alert polling — risk_alerts is the ONLY persistent alert store
  // ---------------------------------------------------------------------------
  const fetchAlerts = useCallback(async () => {
    try {
      const res = await api.get('/api/risk/alerts', { params: { hours: 48 } });
      const raw: any[] = res.data.alerts || [];
      setAlerts(raw.map(mapBackendAlert));

      // Seed shownPatternKeys from today's backend alerts so runAnalysis won't re-toast them
      const today = new Date().toDateString();
      setShownPatternKeys(prev => {
        const next = new Set(prev);
        raw.forEach(a => {
          const alertDate = new Date(a.detected_at || a.created_at).toDateString();
          if (alertDate === today) {
            const fType = BACKEND_TO_FRONTEND_TYPE[a.pattern_type] || a.pattern_type;
            next.add(`${fType}_${today}`);
          }
        });
        return next;
      });
    } catch {
      // Non-fatal — user may not be authenticated yet
    }
  }, []);

  // Initial fetch on mount
  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  // React to WebSocket alert events — replaces 60s polling.
  // When BehaviorEngine creates a new alert, Celery publishes to Redis,
  // FastAPI forwards via WebSocket, lastAlertEvent changes here.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const { lastAlertEvent } = useWebSocketAlerts();
  useEffect(() => {
    if (lastAlertEvent) fetchAlerts();
  }, [lastAlertEvent]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------------------------------------------------------------------------
  // runAnalysis — client-side real-time detection
  // PURPOSE: toasts only. Does NOT update `alerts` (backend owns that).
  // Uses resolved `capital` (from Kite or profile) — never a hardcoded guess.
  // ---------------------------------------------------------------------------
  const runAnalysis = useCallback((trades: Trade[]) => {
    if (trades.length === 0 || isAnalyzing) return;

    // Signature check — skip if same trade set as last run
    const latestTrade = trades[0];
    const signature = `${trades.length}_${latestTrade?.id}_${latestTrade?.traded_at}`;
    if (signature === lastTradeSignature) return;

    setIsAnalyzing(true);
    setLastTradeSignature(signature);

    try {
      const config   = buildPatternConfig(traderProfile);
      const detected = detectAllPatterns(trades, capital, config);

      setPatterns(detected);
      setLastAnalyzed(new Date());

      // Toast for patterns not yet in backend (real-time gap before next sync)
      const today  = new Date().toDateString();
      const newKeys = new Set(shownPatternKeys);

      for (const pattern of detected) {
        const key = `${pattern.type}_${today}`;
        if (!newKeys.has(key)) {
          newKeys.add(key);
          if (pattern.severity === 'critical' || pattern.severity === 'high') {
            toast.error(`${getSeverityLabel(pattern.severity)}: ${pattern.name}`, {
              description: pattern.description,
              duration: 8000,
            });
          } else if (pattern.severity === 'medium') {
            toast.warning(`${getSeverityLabel(pattern.severity)}: ${pattern.name}`, {
              description: pattern.description,
              duration: 5000,
            });
          }
        }
      }

      // Cap session set size to prevent memory leak on very long sessions
      if (newKeys.size > 500) {
        const iter = newKeys.values();
        for (let i = 0; i < newKeys.size - 500; i++) newKeys.delete(iter.next().value);
      }
      setShownPatternKeys(newKeys);

    } catch (error) {
      console.error('Pattern analysis error:', error);
    } finally {
      setIsAnalyzing(false);
    }
  }, [isAnalyzing, lastTradeSignature, traderProfile, capital, shownPatternKeys]);

  // ---------------------------------------------------------------------------
  // Alert actions
  // ---------------------------------------------------------------------------
  const acknowledgeAlert = useCallback(async (alertId: string) => {
    // Optimistic local update + backend persist
    setAlerts(prev => prev.map(a => a.id === alertId ? { ...a, acknowledged: true } : a));
    try {
      await api.post(`/api/risk/alerts/${alertId}/acknowledge`);
    } catch {
      // Revert optimistic update on failure
      setAlerts(prev => prev.map(a => a.id === alertId ? { ...a, acknowledged: false } : a));
    }
  }, []);

  const acknowledgeAll = useCallback(() => {
    setAlerts(prev => prev.map(a => ({ ...a, acknowledged: true })));
  }, []);

  const clearAllAlerts = useCallback(() => {
    setAlerts([]);
    setShownPatternKeys(new Set());
  }, []);

  const unacknowledgedCount = alerts.filter(a => !a.acknowledged).length;

  const stats = patterns.length > 0
    ? getPatternStats(patterns)
    : { total: 0, by_severity: { critical: 0, high: 0, medium: 0, low: 0 }, by_type: {}, total_cost: 0 };

  return (
    <AlertContext.Provider value={{
      patterns,
      alerts,
      unacknowledgedCount,
      stats,
      isAnalyzing,
      lastAnalyzed,
      traderProfile,
      capital,
      runAnalysis,
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
