// Pattern Analysis Hook - Runs behavioral detection on trade data
// Manages detected patterns and triggers alerts

import { useState, useEffect, useCallback, useRef } from 'react';
import { toast } from 'sonner';
import { BehaviorPattern, PatternType, PatternSeverity } from '@/types/patterns';
import { Trade } from '@/types/api';
import { detectAllPatterns, getPatternStats } from '@/lib/patternDetector';
import { getGoals } from '@/lib/goalsManager';

interface AlertNotification {
  id: string;
  pattern: BehaviorPattern;
  shown_at: string;
  acknowledged: boolean;
}

interface UsePatternAnalysisOptions {
  trades: Trade[];
  enabled?: boolean;
  pollInterval?: number; // ms, 0 to disable
  showToasts?: boolean;
}

interface UsePatternAnalysisReturn {
  patterns: BehaviorPattern[];
  alerts: AlertNotification[];
  stats: {
    total: number;
    by_severity: Record<PatternSeverity, number>;
    by_type: Partial<Record<PatternType, number>>;
    total_cost: number;
  };
  isAnalyzing: boolean;
  lastAnalyzed: Date | null;
  acknowledgeAlert: (alertId: string) => void;
  acknowledgeAll: () => void;
  refresh: () => void;
}

// Storage key for persisted alerts
const ALERTS_STORAGE_KEY = 'tradementor_pattern_alerts';

// Get severity label for toast
const getSeverityLabel = (severity: PatternSeverity) => {
  switch (severity) {
    case 'critical': return '🚨 Critical';
    case 'high': return '⚠️ High Alert';
    case 'medium': return '⚡ Caution';
    case 'low': return 'ℹ️ Info';
  }
};

export function usePatternAnalysis({
  trades,
  enabled = true,
  pollInterval = 0,
  showToasts = true,
}: UsePatternAnalysisOptions): UsePatternAnalysisReturn {
  const [patterns, setPatterns] = useState<BehaviorPattern[]>([]);
  const [alerts, setAlerts] = useState<AlertNotification[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [lastAnalyzed, setLastAnalyzed] = useState<Date | null>(null);
  
  const shownPatternIds = useRef<Set<string>>(new Set());

  // Load persisted alerts on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(ALERTS_STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as AlertNotification[];
        setAlerts(parsed);
        // Mark these as already shown
        parsed.forEach(a => shownPatternIds.current.add(a.pattern.id));
      }
    } catch (e) {
      console.error('Error loading alerts:', e);
    }
  }, []);

  // Persist alerts when they change
  useEffect(() => {
    try {
      // Keep only last 50 alerts
      const toStore = alerts.slice(0, 50);
      localStorage.setItem(ALERTS_STORAGE_KEY, JSON.stringify(toStore));
    } catch (e) {
      console.error('Error saving alerts:', e);
    }
  }, [alerts]);

  const runAnalysis = useCallback(() => {
    if (!enabled || trades.length === 0) return;
    
    setIsAnalyzing(true);
    
    try {
      const goals = getGoals();
      const detected = detectAllPatterns(trades, goals.starting_capital);
      
      setPatterns(detected);
      setLastAnalyzed(new Date());
      
      // Find new patterns and create alerts
      const newAlerts: AlertNotification[] = [];
      
      for (const pattern of detected) {
        if (!shownPatternIds.current.has(pattern.id)) {
          shownPatternIds.current.add(pattern.id);
          
          const alert: AlertNotification = {
            id: `alert_${pattern.id}`,
            pattern,
            shown_at: new Date().toISOString(),
            acknowledged: false,
          };
          
          newAlerts.push(alert);
          
          // Show toast for important patterns
          if (showToasts && (pattern.severity === 'critical' || pattern.severity === 'high')) {
            toast.error(`${getSeverityLabel(pattern.severity)}: ${pattern.name}`, {
              description: pattern.description,
              duration: 8000,
              action: {
                label: 'View',
                onClick: () => {
                  // Could navigate to alerts or expand in UI
                  console.log('View alert:', pattern.id);
                },
              },
            });
          } else if (showToasts && pattern.severity === 'medium') {
            toast.warning(`${getSeverityLabel(pattern.severity)}: ${pattern.name}`, {
              description: pattern.description,
              duration: 5000,
            });
          }
        }
      }
      
      if (newAlerts.length > 0) {
        setAlerts(prev => [...newAlerts, ...prev].slice(0, 100));
      }
      
    } catch (error) {
      console.error('Pattern analysis error:', error);
    } finally {
      setIsAnalyzing(false);
    }
  }, [enabled, trades, showToasts]);

  // Run analysis when trades change
  useEffect(() => {
    runAnalysis();
  }, [runAnalysis]);

  // Set up polling if enabled
  useEffect(() => {
    if (pollInterval <= 0) return;
    
    const interval = setInterval(runAnalysis, pollInterval);
    return () => clearInterval(interval);
  }, [pollInterval, runAnalysis]);

  const acknowledgeAlert = useCallback((alertId: string) => {
    setAlerts(prev => 
      prev.map(a => a.id === alertId ? { ...a, acknowledged: true } : a)
    );
  }, []);

  const acknowledgeAll = useCallback(() => {
    setAlerts(prev => prev.map(a => ({ ...a, acknowledged: true })));
  }, []);

  const stats = patterns.length > 0 
    ? getPatternStats(patterns) 
    : { total: 0, by_severity: { critical: 0, high: 0, medium: 0, low: 0 }, by_type: {}, total_cost: 0 };

  return {
    patterns,
    alerts,
    stats,
    isAnalyzing,
    lastAnalyzed,
    acknowledgeAlert,
    acknowledgeAll,
    refresh: runAnalysis,
  };
}
