// Alert History Sheet - View all behavioral pattern alerts
// Accessible from header bell icon

import { useState } from 'react';
import { Bell, Check, CheckCheck, AlertCircle, AlertTriangle, XCircle, CheckCircle2, Trash2 } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { BehaviorPattern, PatternSeverity } from '@/types/patterns';
import { cn } from '@/lib/utils';
import { format, parseISO, isToday, isYesterday } from 'date-fns';

interface AlertNotification {
  id: string;
  pattern: BehaviorPattern;
  shown_at: string;
  acknowledged: boolean;
}

interface AlertHistorySheetProps {
  alerts: AlertNotification[];
  unacknowledgedCount: number;
  onAcknowledge: (alertId: string) => void;
  onAcknowledgeAll: () => void;
  onClearAll?: () => void;
}

const severityConfig: Record<PatternSeverity, {
  icon: typeof AlertCircle;
  color: string;
  bg: string;
  border: string;
}> = {
  critical: {
    icon: XCircle,
    color: 'text-destructive',
    bg: 'bg-destructive/10',
    border: 'border-l-destructive',
  },
  high: {
    icon: AlertCircle,
    color: 'text-destructive',
    bg: 'bg-destructive/10',
    border: 'border-l-destructive',
  },
  medium: {
    icon: AlertTriangle,
    color: 'text-warning',
    bg: 'bg-warning/10',
    border: 'border-l-warning',
  },
  low: {
    icon: CheckCircle2,
    color: 'text-muted-foreground',
    bg: 'bg-muted',
    border: 'border-l-muted-foreground',
  },
};

export function AlertHistorySheet({
  alerts,
  unacknowledgedCount,
  onAcknowledge,
  onAcknowledgeAll,
  onClearAll,
}: AlertHistorySheetProps) {
  const [open, setOpen] = useState(false);
  
  const unacknowledgedAlerts = alerts.filter(a => !a.acknowledged);
  const acknowledgedAlerts = alerts.filter(a => a.acknowledged);
  
  const formatDate = (timestamp: string) => {
    const date = parseISO(timestamp);
    if (isToday(date)) return `Today, ${format(date, 'h:mm a')}`;
    if (isYesterday(date)) return `Yesterday, ${format(date, 'h:mm a')}`;
    return format(date, 'MMM d, h:mm a');
  };

  const renderAlert = (alert: AlertNotification) => {
    const config = severityConfig[alert.pattern.severity];
    const Icon = config.icon;
    
    return (
      <div
        key={alert.id}
        className={cn(
          'p-4 rounded-lg border-l-4 transition-colors',
          config.border,
          config.bg,
          alert.acknowledged && 'opacity-60'
        )}
      >
        <div className="flex items-start gap-3">
          <Icon className={cn('h-5 w-5 mt-0.5', config.color)} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <Badge variant={alert.pattern.severity === 'critical' || alert.pattern.severity === 'high' ? 'destructive' : 'secondary'} className="text-xs">
                {alert.pattern.severity}
              </Badge>
              <span className="text-xs text-muted-foreground">
                {formatDate(alert.shown_at)}
              </span>
            </div>
            <p className="font-medium text-sm">{alert.pattern.name}</p>
            <p className="text-sm text-muted-foreground mt-1">
              {alert.pattern.description}
            </p>
            {alert.pattern.estimated_cost > 0 && (
              <p className="text-xs font-mono text-destructive mt-1">
                Est. cost: ₹{alert.pattern.estimated_cost.toLocaleString('en-IN')}
              </p>
            )}
            {!alert.acknowledged && (
              <Button
                variant="ghost"
                size="sm"
                className="mt-2 h-8 text-xs"
                onClick={() => onAcknowledge(alert.id)}
              >
                <Check className="h-3 w-3 mr-1" />
                Acknowledge
              </Button>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="relative h-9 w-9">
          <Bell className="h-4 w-4" />
          {unacknowledgedCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[10px] font-bold text-destructive-foreground">
              {unacknowledgedCount > 9 ? '9+' : unacknowledgedCount}
            </span>
          )}
        </Button>
      </SheetTrigger>
      <SheetContent className="w-full sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Behavioral Alerts
          </SheetTitle>
          <SheetDescription>
            Pattern detections and trading behavior notifications
          </SheetDescription>
        </SheetHeader>
        
        <div className="mt-6">
          <Tabs defaultValue="unread" className="w-full">
            <div className="flex items-center justify-between mb-4">
              <TabsList>
                <TabsTrigger value="unread" className="gap-1">
                  Unread
                  {unacknowledgedCount > 0 && (
                    <Badge variant="destructive" className="ml-1 h-5 w-5 p-0 flex items-center justify-center text-[10px]">
                      {unacknowledgedCount}
                    </Badge>
                  )}
                </TabsTrigger>
                <TabsTrigger value="all">All</TabsTrigger>
              </TabsList>
              
              {unacknowledgedCount > 0 && (
                <Button variant="ghost" size="sm" onClick={onAcknowledgeAll} className="text-xs">
                  <CheckCheck className="h-3 w-3 mr-1" />
                  Mark all read
                </Button>
              )}
            </div>
            
            <TabsContent value="unread" className="mt-0">
              <ScrollArea className="h-[calc(100vh-280px)]">
                {unacknowledgedAlerts.length > 0 ? (
                  <div className="space-y-3 pr-4">
                    {unacknowledgedAlerts.map(renderAlert)}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <div className="p-3 rounded-full bg-success/10 mb-3">
                      <CheckCircle2 className="h-6 w-6 text-success" />
                    </div>
                    <p className="font-medium text-sm">All caught up!</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      No unread alerts
                    </p>
                  </div>
                )}
              </ScrollArea>
            </TabsContent>
            
            <TabsContent value="all" className="mt-0">
              <ScrollArea className="h-[calc(100vh-280px)]">
                {alerts.length > 0 ? (
                  <div className="space-y-3 pr-4">
                    {alerts.map(renderAlert)}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <div className="p-3 rounded-full bg-muted mb-3">
                      <Bell className="h-6 w-6 text-muted-foreground" />
                    </div>
                    <p className="font-medium text-sm">No alerts yet</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Pattern detections will appear here
                    </p>
                  </div>
                )}
              </ScrollArea>
              
              {alerts.length > 0 && onClearAll && (
                <div className="pt-4 border-t mt-4">
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="w-full text-xs text-muted-foreground"
                    onClick={onClearAll}
                  >
                    <Trash2 className="h-3 w-3 mr-1" />
                    Clear all alerts
                  </Button>
                </div>
              )}
            </TabsContent>
          </Tabs>
        </div>
      </SheetContent>
    </Sheet>
  );
}
