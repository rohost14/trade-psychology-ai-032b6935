// Alert History Sheet — bell icon in Layout header
// Tabs: Unread | All  |  drill-in via AlertDetailSheet

import { useState } from 'react';
import { Bell, Check, CheckCheck, CheckCircle2, Trash2, ChevronRight } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { format, parseISO, isToday, isYesterday } from 'date-fns';
import { AlertNotification } from '@/contexts/AlertContext';
import AlertDetailSheet from '@/components/alerts/AlertDetailSheet';
import { severityDotClass } from '@/lib/alertSeverity';

interface AlertHistorySheetProps {
  alerts: AlertNotification[];
  unacknowledgedCount: number;
  onAcknowledge: (alertId: string) => void;
  onAcknowledgeAll: () => void;
  onClearAll?: () => void;
}

function formatDate(timestamp: string): string {
  const date = parseISO(timestamp);
  if (isToday(date)) return `Today, ${format(date, 'h:mm a')}`;
  if (isYesterday(date)) return `Yesterday, ${format(date, 'h:mm a')}`;
  return format(date, 'MMM d, h:mm a');
}

export function AlertHistorySheet({
  alerts,
  unacknowledgedCount,
  onAcknowledge,
  onAcknowledgeAll,
  onClearAll,
}: AlertHistorySheetProps) {
  const [open, setOpen] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<AlertNotification | null>(null);

  const unacknowledgedAlerts = alerts.filter(a => !a.acknowledged);
  const acknowledgedAlerts   = alerts.filter(a =>  a.acknowledged);

  const renderAlert = (alert: AlertNotification) => {
    const sev = alert.pattern.severity;
    return (
      <button
        key={alert.id}
        onClick={() => setSelectedAlert(alert)}
        className={cn(
          'w-full text-left flex items-start gap-3 px-4 py-3 rounded-lg border border-border',
          'hover:bg-muted/40 transition-colors',
          alert.acknowledged && 'opacity-50',
        )}
      >
        {/* Dot */}
        <span
          className={cn('mt-1.5 shrink-0 rounded-full', severityDotClass(sev))}
          style={{ width: 7, height: 7, minWidth: 7 }}
        />

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              {sev}
            </span>
            <span className="text-[11px] text-muted-foreground font-mono">
              {formatDate(alert.shown_at)}
            </span>
          </div>
          <p className="text-[13px] font-medium text-foreground leading-snug">{alert.pattern.name}</p>
          <p className="text-[12px] text-muted-foreground mt-0.5 leading-snug line-clamp-2">
            {alert.pattern.description}
          </p>
          {(alert.pattern.estimated_cost ?? 0) > 0 && (
            <p className="text-[11px] font-mono text-tm-loss mt-1">
              Est. cost: ₹{(alert.pattern.estimated_cost as number).toLocaleString('en-IN')}
            </p>
          )}
        </div>

        {/* Chevron / ack check */}
        <div className="shrink-0 pt-1">
          {alert.acknowledged
            ? <Check className="h-3.5 w-3.5 text-tm-profit" />
            : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/50" />
          }
        </div>
      </button>
    );
  };

  return (
    <>
      {/* Bell trigger */}
      <button
        onClick={() => setOpen(true)}
        className="relative h-9 w-9 flex items-center justify-center rounded-lg hover:bg-muted transition-colors"
      >
        <Bell className="h-4 w-4 text-muted-foreground" />
        {unacknowledgedCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-tm-loss text-[10px] font-bold text-white">
            {unacknowledgedCount > 9 ? '9+' : unacknowledgedCount}
          </span>
        )}
      </button>

      {/* History sheet */}
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent className="w-full sm:max-w-md p-0 flex flex-col overflow-hidden">
          <SheetHeader className="px-5 py-4 border-b border-border">
            <SheetTitle className="flex items-center gap-2 text-[15px]">
              <Bell className="h-4 w-4" />
              Behavioral Alerts
            </SheetTitle>
          </SheetHeader>

          <div className="flex-1 overflow-hidden flex flex-col px-4 pt-4">
            <Tabs defaultValue="unread" className="flex-1 flex flex-col">
              <div className="flex items-center justify-between mb-3">
                <TabsList className="h-8">
                  <TabsTrigger value="unread" className="text-[12px] h-7 px-3">
                    Unread
                    {unacknowledgedCount > 0 && (
                      <span className="ml-1.5 inline-flex items-center justify-center h-4 min-w-4 px-1 rounded-full bg-tm-loss text-white text-[10px] font-bold">
                        {unacknowledgedCount}
                      </span>
                    )}
                  </TabsTrigger>
                  <TabsTrigger value="all" className="text-[12px] h-7 px-3">All</TabsTrigger>
                </TabsList>

                {unacknowledgedCount > 0 && (
                  <button
                    onClick={onAcknowledgeAll}
                    className="flex items-center gap-1 text-[12px] text-tm-brand hover:underline"
                  >
                    <CheckCheck className="h-3 w-3" />
                    Mark all read
                  </button>
                )}
              </div>

              <TabsContent value="unread" className="mt-0 flex-1">
                <ScrollArea className="h-[calc(100vh-220px)]">
                  {unacknowledgedAlerts.length > 0 ? (
                    <div className="space-y-2 pr-2 pb-4">
                      {unacknowledgedAlerts.map(renderAlert)}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-16 text-center">
                      <CheckCircle2 className="h-8 w-8 text-tm-profit/30 mb-2.5" />
                      <p className="text-sm font-medium text-foreground">All caught up</p>
                      <p className="text-[13px] text-muted-foreground mt-0.5">No unread alerts</p>
                    </div>
                  )}
                </ScrollArea>
              </TabsContent>

              <TabsContent value="all" className="mt-0 flex-1">
                <ScrollArea className="h-[calc(100vh-220px)]">
                  {alerts.length > 0 ? (
                    <>
                      <div className="space-y-2 pr-2 pb-4">
                        {alerts.map(renderAlert)}
                      </div>
                      {onClearAll && (
                        <div className="pt-3 border-t border-border pb-4">
                          <button
                            onClick={onClearAll}
                            className="w-full flex items-center justify-center gap-1.5 py-2 text-[12px] text-muted-foreground hover:text-foreground transition-colors"
                          >
                            <Trash2 className="h-3 w-3" />
                            Clear all alerts
                          </button>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-16 text-center">
                      <Bell className="h-8 w-8 text-muted-foreground/20 mb-2.5" />
                      <p className="text-sm font-medium text-foreground">No alerts yet</p>
                      <p className="text-[13px] text-muted-foreground mt-0.5">Pattern detections will appear here</p>
                    </div>
                  )}
                </ScrollArea>
              </TabsContent>
            </Tabs>
          </div>
        </SheetContent>
      </Sheet>

      {/* Drill-in detail sheet */}
      <AlertDetailSheet
        alert={selectedAlert}
        open={selectedAlert !== null}
        onClose={() => setSelectedAlert(null)}
        onAcknowledge={(id) => { onAcknowledge(id); setSelectedAlert(null); }}
      />
    </>
  );
}
