// Commitment Log Card - Accountability trail of goal changes
// Shows history of modifications and breaks

import { History, Edit3, AlertOctagon, Award } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { CommitmentLogEntry } from '@/types/patterns';
import { cn } from '@/lib/utils';
import { format, parseISO, isToday, isYesterday } from 'date-fns';

interface CommitmentLogCardProps {
  log: CommitmentLogEntry[];
  maxItems?: number;
}

export function CommitmentLogCard({ log, maxItems = 20 }: CommitmentLogCardProps) {
  const displayLog = log.slice(0, maxItems);
  
  const getIcon = (type: CommitmentLogEntry['type']) => {
    switch (type) {
      case 'goal_set':
        return <Edit3 className="h-4 w-4 text-primary" />;
      case 'goal_modified':
        return <Edit3 className="h-4 w-4 text-warning" />;
      case 'goal_broken':
        return <AlertOctagon className="h-4 w-4 text-destructive" />;
      case 'streak_milestone':
        return <Award className="h-4 w-4 text-success" />;
      default:
        return <History className="h-4 w-4 text-muted-foreground" />;
    }
  };
  
  const getTypeLabel = (type: CommitmentLogEntry['type']) => {
    switch (type) {
      case 'goal_set':
        return { label: 'Set', variant: 'default' as const };
      case 'goal_modified':
        return { label: 'Modified', variant: 'secondary' as const };
      case 'goal_broken':
        return { label: 'Broken', variant: 'destructive' as const };
      case 'streak_milestone':
        return { label: 'Milestone', variant: 'default' as const };
      default:
        return { label: 'Event', variant: 'secondary' as const };
    }
  };
  
  const formatDate = (timestamp: string) => {
    const date = parseISO(timestamp);
    if (isToday(date)) return `Today, ${format(date, 'h:mm a')}`;
    if (isYesterday(date)) return `Yesterday, ${format(date, 'h:mm a')}`;
    return format(date, 'MMM d, h:mm a');
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <History className="h-5 w-5 text-muted-foreground" />
          Commitment Log
        </CardTitle>
      </CardHeader>
      <CardContent>
        {displayLog.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <History className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No commitment history yet</p>
            <p className="text-xs">Your goal changes and breaks will appear here</p>
          </div>
        ) : (
          <ScrollArea className="h-[300px] pr-4">
            <div className="space-y-3">
              {displayLog.map((entry) => {
                const typeInfo = getTypeLabel(entry.type);
                return (
                  <div
                    key={entry.id}
                    className={cn(
                      "flex gap-3 p-3 rounded-lg border",
                      entry.type === 'goal_broken' && "border-destructive/30 bg-destructive/5",
                      entry.type === 'streak_milestone' && "border-success/30 bg-success/5",
                      entry.type === 'goal_modified' && "border-warning/30 bg-warning/5",
                      entry.type === 'goal_set' && "border-primary/30 bg-primary/5"
                    )}
                  >
                    <div className="flex-shrink-0 mt-0.5">
                      {getIcon(entry.type)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant={typeInfo.variant} className="text-xs">
                          {typeInfo.label}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {formatDate(entry.timestamp)}
                        </span>
                      </div>
                      <p className="text-sm">{entry.description}</p>
                      {entry.reason && (
                        <p className="text-xs text-muted-foreground mt-1">
                          Reason: {entry.reason}
                        </p>
                      )}
                      {entry.cost !== undefined && entry.cost > 0 && (
                        <p className="text-xs font-mono text-destructive mt-1">
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
      </CardContent>
    </Card>
  );
}
