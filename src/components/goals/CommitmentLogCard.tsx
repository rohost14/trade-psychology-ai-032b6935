import { History, Edit3, AlertOctagon, Award } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { CommitmentLogEntry } from '@/types/patterns';
import { cn } from '@/lib/utils';
import { format, parseISO, isToday, isYesterday } from 'date-fns';

interface CommitmentLogCardProps {
  log: CommitmentLogEntry[];
  maxItems?: number;
}

const ENTRY_CONFIG = {
  goal_set:         { icon: Edit3,        iconColor: 'text-tm-brand',   border: 'border-tm-brand/20',  bg: 'bg-teal-50/50 dark:bg-teal-900/10',   label: 'Set',       labelColor: 'text-tm-brand bg-teal-50 dark:bg-teal-900/20' },
  goal_modified:    { icon: Edit3,        iconColor: 'text-tm-obs',     border: 'border-tm-obs/20',    bg: 'bg-amber-50/50 dark:bg-amber-900/10', label: 'Modified',  labelColor: 'text-tm-obs bg-amber-50 dark:bg-amber-900/20' },
  goal_broken:      { icon: AlertOctagon, iconColor: 'text-tm-loss',    border: 'border-tm-loss/20',   bg: 'bg-red-50/50 dark:bg-red-900/10',     label: 'Broken',    labelColor: 'text-tm-loss bg-red-50 dark:bg-red-900/20' },
  streak_milestone: { icon: Award,        iconColor: 'text-tm-profit',  border: 'border-tm-profit/20', bg: 'bg-teal-50/50 dark:bg-teal-900/10',   label: 'Milestone', labelColor: 'text-tm-profit bg-teal-50 dark:bg-teal-900/20' },
};

const formatDate = (timestamp: string) => {
  const date = parseISO(timestamp);
  if (isToday(date)) return `Today, ${format(date, 'h:mm a')}`;
  if (isYesterday(date)) return `Yesterday, ${format(date, 'h:mm a')}`;
  return format(date, 'MMM d, h:mm a');
};

export function CommitmentLogCard({ log, maxItems = 20 }: CommitmentLogCardProps) {
  const displayLog = log.slice(0, maxItems);

  return (
    <div className="tm-card overflow-hidden">
      <div className="px-5 py-4 border-b border-border">
        <p className="text-sm font-semibold text-foreground flex items-center gap-1.5">
          <History className="h-4 w-4 text-muted-foreground" />
          Commitment Log
        </p>
      </div>
      <div className="p-5">
        {displayLog.length === 0 ? (
          <div className="text-center py-8">
            <History className="h-8 w-8 mx-auto mb-2 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">No commitment history yet</p>
            <p className="text-xs text-muted-foreground/70 mt-0.5">Goal changes and breaks will appear here</p>
          </div>
        ) : (
          <ScrollArea className="h-[300px] pr-4">
            <div className="space-y-3">
              {displayLog.map((entry) => {
                const cfg = ENTRY_CONFIG[entry.type] ?? ENTRY_CONFIG.goal_set;
                const Icon = cfg.icon;
                return (
                  <div
                    key={entry.id}
                    className={cn('flex gap-3 p-3 rounded-lg border', cfg.border, cfg.bg)}
                  >
                    <Icon className={cn('h-4 w-4 flex-shrink-0 mt-0.5', cfg.iconColor)} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={cn('text-[10px] font-semibold px-1.5 py-0.5 rounded', cfg.labelColor)}>
                          {cfg.label}
                        </span>
                        <span className="text-[10px] text-muted-foreground">
                          {formatDate(entry.timestamp)}
                        </span>
                      </div>
                      <p className="text-xs text-foreground">{entry.description}</p>
                      {entry.reason && (
                        <p className="text-[10px] text-muted-foreground mt-0.5">Reason: {entry.reason}</p>
                      )}
                      {entry.cost !== undefined && entry.cost > 0 && (
                        <p className="text-[10px] font-mono tabular-nums text-tm-loss mt-0.5">
                          Cost: ₹{entry.cost.toLocaleString('en-IN')}
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        )}
      </div>
    </div>
  );
}
