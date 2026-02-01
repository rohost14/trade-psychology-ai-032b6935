// Alert Context Provider - Global state for behavioral alerts
// Provides pattern analysis across the app

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { BehaviorPattern, PatternSeverity, PatternType } from '@/types/patterns';
import { Trade } from '@/types/api';
import { detectAllPatterns, getPatternStats } from '@/lib/patternDetector';
import { getGoals } from '@/lib/goalsManager';
import { toast } from 'sonner';

export interface AlertNotification {
  id: string;
  pattern: BehaviorPattern;
  shown_at: string;
  acknowledged: boolean;
}

interface AlertContextValue {
  // Patterns
  patterns: BehaviorPattern[];
  
  // Alerts
  alerts: AlertNotification[];
  unacknowledgedCount: number;
  
  // Stats
  stats: {
    total: number;
    by_severity: Record<PatternSeverity, number>;
    by_type: Partial<Record<PatternType, number>>;
    total_cost: number;
  };
  
  // State
  isAnalyzing: boolean;
  lastAnalyzed: Date | null;
  
  // Actions
  runAnalysis: (trades: Trade[]) => void;
  acknowledgeAlert: (alertId: string) => void;
  acknowledgeAll: () => void;
  clearAllAlerts: () => void;
}

const AlertContext = createContext<AlertContextValue | undefined>(undefined);

const ALERTS_STORAGE_KEY = 'tradementor_pattern_alerts';
const SHOWN_PATTERNS_KEY = 'tradementor_shown_patterns';

const getSeverityLabel = (severity: PatternSeverity) => {
  switch (severity) {
    case 'critical': return '🚨 Critical';
    case 'high': return '⚠️ High Alert';
    case 'medium': return '⚡ Caution';
    case 'low': return 'ℹ️ Info';
  }
};

export function AlertProvider({ children }: { children: ReactNode }) {
  const [patterns, setPatterns] = useState<BehaviorPattern[]>([]);
  const [alerts, setAlerts] = useState<AlertNotification[]>([]);
  const [shownPatternIds, setShownPatternIds] = useState<Set<string>>(new Set());
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [lastAnalyzed, setLastAnalyzed] = useState<Date | null>(null);

  // Load persisted data on mount
  useEffect(() => {
    try {
      const storedAlerts = localStorage.getItem(ALERTS_STORAGE_KEY);
      if (storedAlerts) {
        setAlerts(JSON.parse(storedAlerts));
      }
      
      const storedShown = localStorage.getItem(SHOWN_PATTERNS_KEY);
      if (storedShown) {
        setShownPatternIds(new Set(JSON.parse(storedShown)));
      }
    } catch (e) {
      console.error('Error loading alert data:', e);
    }
  }, []);

  // Persist alerts
  useEffect(() => {
    try {
      localStorage.setItem(ALERTS_STORAGE_KEY, JSON.stringify(alerts.slice(0, 100)));
    } catch (e) {
      console.error('Error saving alerts:', e);
    }
  }, [alerts]);

  // Persist shown pattern IDs
  useEffect(() => {
    try {
      localStorage.setItem(SHOWN_PATTERNS_KEY, JSON.stringify([...shownPatternIds]));
    } catch (e) {
      console.error('Error saving shown patterns:', e);
    }
  }, [shownPatternIds]);

  const runAnalysis = useCallback((trades: Trade[]) => {
    if (trades.length === 0 || isAnalyzing) return;
    
    setIsAnalyzing(true);
    
    try {
      const goals = getGoals();
      const detected = detectAllPatterns(trades, goals.starting_capital);
      
      setPatterns(detected);
      setLastAnalyzed(new Date());
      
      // Find new patterns (not already shown)
      const newAlerts: AlertNotification[] = [];
      const newShownIds = new Set(shownPatternIds);
      
      for (const pattern of detected) {
        // Check if this exact pattern was already shown
        if (!shownPatternIds.has(pattern.id)) {
          newShownIds.add(pattern.id);
          
          const alert: AlertNotification = {
            id: `alert_${pattern.id}`,
            pattern,
            shown_at: new Date().toISOString(),
            acknowledged: false,
          };
          
          newAlerts.push(alert);
          
          // Show toast for high-severity patterns (only for NEW patterns)
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
      
      if (newAlerts.length > 0) {
        setAlerts(prev => [...newAlerts, ...prev].slice(0, 100));
        setShownPatternIds(newShownIds);
      }
      
    } catch (error) {
      console.error('Pattern analysis error:', error);
    } finally {
      setIsAnalyzing(false);
    }
  }, [shownPatternIds, isAnalyzing]);

  const acknowledgeAlert = useCallback((alertId: string) => {
    setAlerts(prev => 
      prev.map(a => a.id === alertId ? { ...a, acknowledged: true } : a)
    );
  }, []);

  const acknowledgeAll = useCallback(() => {
    setAlerts(prev => prev.map(a => ({ ...a, acknowledged: true })));
  }, []);

  const clearAllAlerts = useCallback(() => {
    setAlerts([]);
    setShownPatternIds(new Set());
    localStorage.removeItem(ALERTS_STORAGE_KEY);
    localStorage.removeItem(SHOWN_PATTERNS_KEY);
  }, []);

  const unacknowledgedCount = alerts.filter(a => !a.acknowledged).length;
  
  const stats = patterns.length > 0 
    ? getPatternStats(patterns) 
    : { total: 0, by_severity: { critical: 0, high: 0, medium: 0, low: 0 }, by_type: {}, total_cost: 0 };

  return (
    <AlertContext.Provider
      value={{
        patterns,
        alerts,
        unacknowledgedCount,
        stats,
        isAnalyzing,
        lastAnalyzed,
        runAnalysis,
        acknowledgeAlert,
        acknowledgeAll,
        clearAllAlerts,
      }}
    >
      {children}
    </AlertContext.Provider>
  );
}

export function useAlerts() {
  const context = useContext(AlertContext);
  if (!context) {
    throw new Error('useAlerts must be used within AlertProvider');
  }
  return context;
}
