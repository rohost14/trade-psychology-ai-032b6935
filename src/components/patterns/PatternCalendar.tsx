import { useState, useEffect, useCallback } from 'react';
import { Loader2, AlertTriangle, CheckCircle2, Calendar } from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';

// ─── Types ────────────────────────────────────────────────────────────────────

interface AlertRecord {
  id: string;
  pattern_type: string;
  severity: string;
  message: string;
  detected_at: string;
  acknowledged_at: string | null;
}

type DaySeverity = 'no_data' | 'clean' | 'low' | 'medium' | 'high' | 'critical';

interface DayData {
  date: string; // YYYY-MM-DD IST
  alerts: AlertRecord[];
  severity: DaySeverity;
  isFuture: boolean;
  isToday: boolean;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const SEVERITY_ORDER: Record<string, number> = {
  low: 1, medium: 2, caution: 2, high: 3, danger: 3, critical: 4,
};

function worstSeverity(alerts: AlertRecord[]): DaySeverity {
  if (alerts.length === 0) return 'clean';
  let max = 0;
  for (const a of alerts) {
    max = Math.max(max, SEVERITY_ORDER[a.severity] ?? 0);
  }
  if (max >= 4) return 'critical';
  if (max >= 3) return 'high';
  if (max >= 2) return 'medium';
  return 'low';
}

// Returns YYYY-MM-DD in IST for a given UTC Date object
function toISTDateStr(d: Date): string {
  return d.toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });
}

const SEVERITY_CELL: Record<DaySeverity, string> = {
  no_data:  'bg-muted/20 border border-muted/30',
  clean:    'bg-green-500/80 dark:bg-green-500/70 border-0',
  low:      'bg-amber-300/80 dark:bg-amber-400/60 border-0',
  medium:   'bg-amber-500/80 dark:bg-amber-500/70 border-0',
  high:     'bg-orange-500/80 dark:bg-orange-500/70 border-0',
  critical: 'bg-red-600/85 dark:bg-red-600/75 border-0',
};

const WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

// ─── Build Calendar Grid ──────────────────────────────────────────────────────

function buildGrid(alertsByDate: Record<string, AlertRecord[]>): DayData[][] {
  const today = new Date();
  const todayStr = toISTDateStr(today);

  // Go back 90 days from today
  const start = new Date(today);
  start.setDate(start.getDate() - 90);

  // Rewind to Monday of that week
  const dayOfWeek = start.getDay(); // 0=Sun, 1=Mon, ...
  const daysToMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
  start.setDate(start.getDate() - daysToMonday);

  // Build weeks (columns), each with 7 days (Mon–Sun)
  const weeks: DayData[][] = [];
  const cursor = new Date(start);

  while (cursor <= today || weeks.length < 13) {
    const week: DayData[] = [];
    for (let d = 0; d < 7; d++) {
      const dateStr = toISTDateStr(cursor);
      const isFuture = dateStr > todayStr;
      const isToday = dateStr === todayStr;
      const alerts = alertsByDate[dateStr] ?? [];

      // Days before our 90-day window or future days show as no_data
      const isInRange = dateStr >= toISTDateStr(new Date(today.getTime() - 90 * 86400000));

      week.push({
        date: dateStr,
        alerts,
        severity: isFuture || !isInRange ? 'no_data' : alerts.length > 0 ? worstSeverity(alerts) : 'clean',
        isFuture,
        isToday,
      });
      cursor.setDate(cursor.getDate() + 1);
    }
    weeks.push(week);
    if (weeks.length >= 14 && cursor > today) break;
  }

  return weeks;
}

function getMonthLabels(weeks: DayData[][]): { col: number; label: string }[] {
  const labels: { col: number; label: string }[] = [];
  let lastMonth = '';
  weeks.forEach((week, col) => {
    const month = new Date(week[0].date).toLocaleDateString('en-IN', { month: 'short' });
    if (month !== lastMonth) {
      labels.push({ col, label: month });
      lastMonth = month;
    }
  });
  return labels;
}

// ─── Day Detail Panel ─────────────────────────────────────────────────────────

function DayDetail({ day, onClose }: { day: DayData; onClose: () => void }) {
  const date = new Date(day.date + 'T00:00:00');
  const label = date.toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' });

  return (
    <div className="bg-card border border-border rounded-xl p-4 mt-3 animate-fade-in-up">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-semibold text-foreground">{label}</p>
        <button onClick={onClose} className="text-xs text-muted-foreground hover:text-foreground transition-colors">
          Close
        </button>
      </div>

      {day.alerts.length === 0 ? (
        <div className="flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
          <CheckCircle2 className="h-4 w-4" />
          Clean day — no behavioral alerts
        </div>
      ) : (
        <div className="space-y-2">
          {day.alerts.map((alert, i) => (
            <div key={i} className={cn(
              'flex items-start gap-2.5 p-2.5 rounded-lg border text-sm',
              alert.severity === 'critical' || alert.severity === 'danger'
                ? 'bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800'
                : alert.severity === 'high'
                  ? 'bg-orange-50 dark:bg-orange-900/10 border-orange-200 dark:border-orange-800'
                  : 'bg-amber-50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-800'
            )}>
              <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0 text-muted-foreground" />
              <div className="min-w-0">
                <p className="font-medium text-foreground capitalize">
                  {alert.pattern_type?.replace(/_/g, ' ')}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{alert.message}</p>
                <p className="text-[10px] text-muted-foreground mt-1">
                  {new Date(alert.detected_at).toLocaleTimeString('en-IN', {
                    hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata',
                  })} IST
                  {alert.acknowledged_at ? ' · Acknowledged' : ''}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main Calendar Component ──────────────────────────────────────────────────

export default function PatternCalendar() {
  const [alertsByDate, setAlertsByDate] = useState<Record<string, AlertRecord[]>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [selectedDay, setSelectedDay] = useState<DayData | null>(null);

  const fetchAlerts = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await api.get('/api/risk/alerts', { params: { hours: 2160 } }); // 90 days
      const rawAlerts: AlertRecord[] = res.data.alerts || [];
      const byDate: Record<string, AlertRecord[]> = {};
      for (const alert of rawAlerts) {
        const dateStr = toISTDateStr(new Date(alert.detected_at));
        if (!byDate[dateStr]) byDate[dateStr] = [];
        byDate[dateStr].push(alert);
      }
      setAlertsByDate(byDate);
    } catch {
      // show empty grid
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const weeks = buildGrid(alertsByDate);
  const monthLabels = getMonthLabels(weeks);

  const totalAlertDays = Object.values(alertsByDate).filter(a => a.length > 0).length;
  const cleanDays = weeks.flat().filter(d => !d.isFuture && d.severity === 'clean').length;

  const handleCellClick = (day: DayData) => {
    if (day.isFuture || day.severity === 'no_data') return;
    setSelectedDay(prev => prev?.date === day.date ? null : day);
  };

  return (
    <div className="bg-card rounded-xl border border-border p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-foreground">Pattern Calendar</h3>
          <span className="text-xs text-muted-foreground">Last 90 days</span>
        </div>
        {!isLoading && (
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="text-green-600 dark:text-green-400 font-medium">{cleanDays} clean</span>
            <span className="text-red-600 dark:text-red-400 font-medium">{totalAlertDays} with alerts</span>
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-32">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="overflow-x-auto">
          <div className="inline-block min-w-full">
            {/* Month labels */}
            <div className="flex mb-1" style={{ paddingLeft: '28px' }}>
              {weeks.map((_, col) => {
                const label = monthLabels.find(m => m.col === col);
                return (
                  <div key={col} className="w-4 shrink-0 mr-1 text-[10px] text-muted-foreground">
                    {label?.label ?? ''}
                  </div>
                );
              })}
            </div>

            {/* Grid: 7 rows (Mon–Sun) × N columns (weeks) */}
            <div className="flex gap-0">
              {/* Weekday labels */}
              <div className="flex flex-col gap-1 mr-1 shrink-0">
                {WEEKDAY_LABELS.map((day, i) => (
                  <div key={i} className="h-4 w-6 text-[10px] text-muted-foreground flex items-center justify-end pr-1">
                    {i % 2 === 0 ? day.slice(0, 1) : ''}
                  </div>
                ))}
              </div>

              {/* Weeks */}
              <div className="flex gap-1">
                {weeks.map((week, col) => (
                  <div key={col} className="flex flex-col gap-1">
                    {week.map((day, row) => (
                      <button
                        key={row}
                        onClick={() => handleCellClick(day)}
                        disabled={day.isFuture || day.severity === 'no_data'}
                        title={day.severity !== 'no_data' ? `${day.date}: ${day.alerts.length} alert(s)` : day.date}
                        className={cn(
                          'w-4 h-4 rounded-sm transition-all focus:outline-none',
                          SEVERITY_CELL[day.severity],
                          day.isToday && 'ring-2 ring-primary ring-offset-1 ring-offset-background',
                          selectedDay?.date === day.date && 'ring-2 ring-foreground ring-offset-1 ring-offset-background',
                          !day.isFuture && day.severity !== 'no_data' && 'hover:opacity-80 cursor-pointer',
                          (day.isFuture || day.severity === 'no_data') && 'cursor-default',
                        )}
                      />
                    ))}
                  </div>
                ))}
              </div>
            </div>

            {/* Legend */}
            <div className="flex items-center gap-3 mt-3 flex-wrap" style={{ paddingLeft: '28px' }}>
              <span className="text-[10px] text-muted-foreground">Less</span>
              {(['clean', 'low', 'medium', 'high', 'critical'] as DaySeverity[]).map(s => (
                <div key={s} className={cn('w-3.5 h-3.5 rounded-sm', SEVERITY_CELL[s])} title={s} />
              ))}
              <span className="text-[10px] text-muted-foreground">More alerts</span>
            </div>
          </div>
        </div>
      )}

      {/* Selected day detail */}
      {selectedDay && (
        <DayDetail day={selectedDay} onClose={() => setSelectedDay(null)} />
      )}
    </div>
  );
}
