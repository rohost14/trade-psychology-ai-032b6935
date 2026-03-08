import { useState } from 'react';
import { Download, FileText, Table, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from '@/components/ui/dropdown-menu';
import { toast } from 'sonner';
import { api } from '@/lib/api';

interface ExportReportButtonProps {
  brokerAccountId: string;
}

export default function ExportReportButton({ brokerAccountId }: ExportReportButtonProps) {
  const [isExporting, setIsExporting] = useState(false);

  const exportTradesCSV = async () => {
    try {
      setIsExporting(true);

      // Fetch trades
      const response = await api.get('/api/trades/', {
        params: { limit: 500 }
      });

      const trades = response.data.trades || [];
      if (trades.length === 0) {
        toast.error('No trades to export');
        return;
      }

      // Create CSV content
      const headers = [
        'Date',
        'Symbol',
        'Exchange',
        'Type',
        'Quantity',
        'Price',
        'P&L',
        'Status'
      ];

      const rows = trades.map((t: any) => [
        new Date(t.traded_at || t.order_timestamp).toLocaleString(),
        t.tradingsymbol,
        t.exchange,
        t.transaction_type,
        t.quantity,
        t.average_price || t.price,
        t.pnl || 0,
        t.status
      ]);

      const csvContent = [
        headers.join(','),
        ...rows.map((row: any[]) =>
          row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')
        )
      ].join('\n');

      // Download file
      downloadFile(csvContent, `trades-export-${new Date().toISOString().split('T')[0]}.csv`, 'text/csv');
      toast.success('Trades exported successfully');
    } catch (error) {
      console.error('Export failed:', error);
      toast.error('Failed to export trades');
    } finally {
      setIsExporting(false);
    }
  };

  const exportAnalyticsReport = async () => {
    try {
      setIsExporting(true);

      // Fetch all analytics data
      const [tradesRes, progressRes, patternsRes] = await Promise.all([
        api.get('/api/trades/', { params: { limit: 200 } }),
        api.get('/api/analytics/progress'),
        api.get('/api/behavioral/analysis', { params: { time_window_days: 30 } })
      ]);

      const trades = tradesRes.data.trades || [];
      const progress = progressRes.data;
      const patterns = patternsRes.data.patterns_detected || [];

      // Generate report content
      const report = generateTextReport(trades, progress, patterns);

      downloadFile(report, `trading-report-${new Date().toISOString().split('T')[0]}.txt`, 'text/plain');
      toast.success('Report exported successfully');
    } catch (error) {
      console.error('Export failed:', error);
      toast.error('Failed to export report');
    } finally {
      setIsExporting(false);
    }
  };

  const exportWeeklyReport = async () => {
    try {
      setIsExporting(true);

      const progressRes = await api.get('/api/analytics/progress');

      const progress = progressRes.data;
      const report = generateWeeklyReport(progress);

      downloadFile(report, `weekly-report-${new Date().toISOString().split('T')[0]}.txt`, 'text/plain');
      toast.success('Weekly report exported');
    } catch (error) {
      console.error('Export failed:', error);
      toast.error('Failed to export report');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" disabled={isExporting}>
          {isExporting ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Download className="h-4 w-4 mr-2" />
          )}
          Export
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuLabel>Export Options</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={exportTradesCSV}>
          <Table className="h-4 w-4 mr-2" />
          Trades (CSV)
        </DropdownMenuItem>
        <DropdownMenuItem onClick={exportWeeklyReport}>
          <FileText className="h-4 w-4 mr-2" />
          Weekly Summary
        </DropdownMenuItem>
        <DropdownMenuItem onClick={exportAnalyticsReport}>
          <FileText className="h-4 w-4 mr-2" />
          Full Report
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function downloadFile(content: string, filename: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function generateTextReport(trades: any[], progress: any, patterns: any[]): string {
  const lines: string[] = [];

  lines.push('═══════════════════════════════════════════════════════════');
  lines.push('                    TRADEMENTOR AI REPORT                   ');
  lines.push('═══════════════════════════════════════════════════════════');
  lines.push(`Generated: ${new Date().toLocaleString()}`);
  lines.push('');

  // This Week Summary
  if (progress?.this_week) {
    lines.push('─── THIS WEEK SUMMARY ───');
    lines.push(`Total P&L:     ₹${progress.this_week.total_pnl?.toFixed(2) || 0}`);
    lines.push(`Trade Count:   ${progress.this_week.trade_count || 0}`);
    lines.push(`Win Rate:      ${progress.this_week.win_rate?.toFixed(1) || 0}%`);
    lines.push(`Winners:       ${progress.this_week.winners || 0}`);
    lines.push(`Losers:        ${progress.this_week.losers || 0}`);
    lines.push('');
  }

  // Week Comparison
  if (progress?.comparison) {
    lines.push('─── WEEK-OVER-WEEK CHANGE ───');
    const comp = progress.comparison;
    lines.push(`P&L Change:    ${comp.pnl?.improved ? '↑' : '↓'} ${Math.abs(comp.pnl?.percent || 0).toFixed(1)}%`);
    lines.push(`Win Rate:      ${comp.win_rate?.improved ? '↑' : '↓'} ${Math.abs(comp.win_rate?.percent || 0).toFixed(1)}%`);
    lines.push(`Trade Count:   ${comp.trade_count?.change > 0 ? '+' : ''}${comp.trade_count?.change || 0}`);
    lines.push(`Danger Alerts: ${comp.danger_alerts?.change > 0 ? '+' : ''}${comp.danger_alerts?.change || 0}`);
    lines.push('');
  }

  // Behavioral Patterns
  if (patterns.length > 0) {
    lines.push('─── BEHAVIORAL PATTERNS DETECTED ───');
    patterns.forEach((p: any) => {
      lines.push(`• ${p.pattern_type || p.name}: ${p.severity || 'medium'} severity`);
      if (p.description) lines.push(`  ${p.description}`);
    });
    lines.push('');
  }

  // Discipline Streaks
  if (progress?.streaks) {
    lines.push('─── DISCIPLINE STREAKS ───');
    lines.push(`Days Without Revenge Trading: ${progress.streaks.days_without_revenge || 0}`);
    lines.push(`Current Streak: ${progress.streaks.current_streak || 0} days`);
    lines.push('');
  }

  // Trade Summary
  if (trades.length > 0) {
    lines.push('─── TRADE STATISTICS ───');
    const pnls = trades.map(t => t.pnl || 0);
    const winners = pnls.filter(p => p > 0);
    const losers = pnls.filter(p => p < 0);
    lines.push(`Total Trades:  ${trades.length}`);
    lines.push(`Total P&L:     ₹${pnls.reduce((a, b) => a + b, 0).toFixed(2)}`);
    lines.push(`Avg Win:       ₹${winners.length ? (winners.reduce((a, b) => a + b, 0) / winners.length).toFixed(2) : 0}`);
    lines.push(`Avg Loss:      ₹${losers.length ? (losers.reduce((a, b) => a + b, 0) / losers.length).toFixed(2) : 0}`);
    lines.push('');
  }

  lines.push('═══════════════════════════════════════════════════════════');
  lines.push('                   Powered by TradeMentor AI                ');
  lines.push('═══════════════════════════════════════════════════════════');

  return lines.join('\n');
}

function generateWeeklyReport(progress: any): string {
  const lines: string[] = [];

  lines.push('╔═══════════════════════════════════════╗');
  lines.push('║       WEEKLY TRADING SUMMARY          ║');
  lines.push('╚═══════════════════════════════════════╝');
  lines.push(`Week of: ${new Date().toLocaleDateString()}`);
  lines.push('');

  if (progress?.this_week) {
    const tw = progress.this_week;
    lines.push('📊 PERFORMANCE');
    lines.push(`   P&L:        ₹${tw.total_pnl?.toFixed(2) || 0}`);
    lines.push(`   Trades:     ${tw.trade_count || 0}`);
    lines.push(`   Win Rate:   ${tw.win_rate?.toFixed(1) || 0}%`);
    lines.push('');
  }

  if (progress?.comparison) {
    const c = progress.comparison;
    lines.push('📈 VS LAST WEEK');
    lines.push(`   P&L:        ${c.pnl?.improved ? '✅ Better' : '⚠️ Worse'} (${c.pnl?.percent?.toFixed(0) || 0}%)`);
    lines.push(`   Win Rate:   ${c.win_rate?.improved ? '✅ Better' : '⚠️ Worse'}`);
    lines.push(`   Alerts:     ${c.danger_alerts?.improved ? '✅ Fewer' : '⚠️ More'}`);
    lines.push('');
  }

  if (progress?.streaks) {
    lines.push('🔥 DISCIPLINE');
    lines.push(`   Streak:     ${progress.streaks.current_streak || 0} days clean`);
    lines.push('');
  }

  lines.push('─────────────────────────────────────────');
  lines.push('Keep trading with discipline!');
  lines.push('- TradeMentor AI');

  return lines.join('\n');
}
