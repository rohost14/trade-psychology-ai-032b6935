import { motion } from 'framer-motion';
import { ArrowLeft, Shield, TrendingUp, AlertTriangle, CheckCircle2, Info, Calculator } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { formatCurrency, formatRelativeTime } from '@/lib/formatters';

interface SavedTrade {
  id: string;
  date: string;
  pattern: string;
  symbol: string;
  intervention: string;
  estimatedLoss: number;
  actualOutcome: number;
  saved: number;
  confidence: 'high' | 'medium' | 'low';
}

const savedTrades: SavedTrade[] = [
  {
    id: '1',
    date: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    pattern: 'Revenge Trading',
    symbol: 'NIFTY26FEB22000CE',
    intervention: 'Alert sent after 3 rapid losses. You paused trading.',
    estimatedLoss: 8500,
    actualOutcome: 0,
    saved: 8500,
    confidence: 'high',
  },
  {
    id: '2',
    date: new Date(Date.now() - 4 * 24 * 60 * 60 * 1000).toISOString(),
    pattern: 'Overtrading',
    symbol: 'BANKNIFTY Options',
    intervention: 'Trade limit warning at 8 trades. You stopped at 9.',
    estimatedLoss: 4200,
    actualOutcome: -800,
    saved: 3400,
    confidence: 'medium',
  },
  {
    id: '3',
    date: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
    pattern: 'FOMO Entry',
    symbol: 'RELIANCE26FEB2800CE',
    intervention: 'Late entry warning. You waited for pullback.',
    estimatedLoss: 2800,
    actualOutcome: 1200,
    saved: 4000,
    confidence: 'high',
  },
  {
    id: '4',
    date: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString(),
    pattern: 'Position Sizing',
    symbol: 'NIFTY Weekly Options',
    intervention: 'Size warning at 5% capital. You reduced to 3%.',
    estimatedLoss: 6000,
    actualOutcome: -1800,
    saved: 4200,
    confidence: 'medium',
  },
  {
    id: '5',
    date: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString(),
    pattern: 'Account Blowup Risk',
    symbol: 'Multiple Positions',
    intervention: 'Margin warning at 85%. You closed 2 positions.',
    estimatedLoss: 15000,
    actualOutcome: -2400,
    saved: 12600,
    confidence: 'high',
  },
];

const methodologySteps = [
  {
    title: 'Pattern Detection',
    description: 'We analyze your trade history to identify behavioral patterns like revenge trading, FOMO, and overtrading.',
  },
  {
    title: 'Historical Comparison',
    description: 'We compare against your own history. When you showed similar patterns before without intervention, what was the average loss?',
  },
  {
    title: 'Intervention Impact',
    description: 'We measure what happened after you received an alert. Did you pause? Reduce size? Exit early?',
  },
  {
    title: 'Conservative Estimate',
    description: 'We use your historical average loss for the pattern, minus any actual loss you incurred. We never overestimate.',
  },
];

export default function MoneySavedPage() {
  const totalSaved = savedTrades.reduce((sum, t) => sum + t.saved, 0);
  const totalInterventions = savedTrades.length;
  const avgSavedPerIntervention = totalSaved / totalInterventions;

  return (
    <div className="max-w-4xl mx-auto pb-12">
      {/* Back Button */}
      <Link 
        to="/dashboard" 
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Dashboard
      </Link>

      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 rounded-lg bg-success/10">
            <TrendingUp className="h-6 w-6 text-success" />
          </div>
          <h1 className="text-2xl font-bold text-foreground">Money Saved</h1>
        </div>
        <p className="text-muted-foreground">
          A transparent breakdown of how we calculate prevented losses
        </p>
      </motion.div>

      {/* Summary Stats */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8"
      >
        <div className="bg-card rounded-lg border border-border p-5 border-l-4 border-l-success">
          <p className="text-sm text-muted-foreground mb-1">Total Saved</p>
          <p className="text-3xl font-bold font-mono text-success">{formatCurrency(totalSaved)}</p>
        </div>
        <div className="bg-card rounded-lg border border-border p-5">
          <p className="text-sm text-muted-foreground mb-1">Interventions</p>
          <p className="text-3xl font-bold font-mono text-foreground">{totalInterventions}</p>
        </div>
        <div className="bg-card rounded-lg border border-border p-5">
          <p className="text-sm text-muted-foreground mb-1">Avg Saved / Alert</p>
          <p className="text-3xl font-bold font-mono text-foreground">{formatCurrency(avgSavedPerIntervention)}</p>
        </div>
      </motion.div>

      {/* Methodology Section */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="bg-card rounded-lg border border-border mb-8"
      >
        <div className="px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Calculator className="h-5 w-5 text-primary" />
            <h2 className="text-base font-semibold text-foreground">How We Calculate</h2>
          </div>
        </div>
        <div className="p-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {methodologySteps.map((step, idx) => (
              <div key={idx} className="flex gap-3">
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center">
                  <span className="text-xs font-bold text-primary">{idx + 1}</span>
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">{step.title}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{step.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </motion.div>

      {/* Trade-by-Trade Breakdown */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="bg-card rounded-lg border border-border"
      >
        <div className="px-5 py-4 border-b border-border">
          <h2 className="text-base font-semibold text-foreground">Intervention History</h2>
          <p className="text-sm text-muted-foreground">Each time we helped you avoid a loss</p>
        </div>
        
        <div className="divide-y divide-border">
          {savedTrades.map((trade, idx) => (
            <motion.div
              key={trade.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4 + idx * 0.05 }}
              className="p-5"
            >
              <div className="flex items-start justify-between gap-4 mb-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={cn(
                      'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                      trade.pattern === 'Account Blowup Risk' 
                        ? 'bg-red-100 text-red-700'
                        : trade.pattern === 'Revenge Trading'
                        ? 'bg-orange-100 text-orange-700'
                        : 'bg-amber-100 text-amber-700'
                    )}>
                      {trade.pattern}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {formatRelativeTime(trade.date)}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-foreground">{trade.symbol}</p>
                  <p className="text-xs text-muted-foreground mt-1">{trade.intervention}</p>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="text-lg font-bold font-mono text-success">+{formatCurrency(trade.saved)}</p>
                  <p className="text-xs text-muted-foreground">saved</p>
                </div>
              </div>

              {/* Calculation Breakdown */}
              <div className="bg-muted/30 rounded-lg p-3 text-xs">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-muted-foreground">Estimated loss if continued:</span>
                  <span className="font-mono text-destructive">-{formatCurrency(trade.estimatedLoss)}</span>
                </div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-muted-foreground">Actual outcome:</span>
                  <span className={cn(
                    'font-mono',
                    trade.actualOutcome >= 0 ? 'text-success' : 'text-destructive'
                  )}>
                    {trade.actualOutcome >= 0 ? '+' : ''}{formatCurrency(trade.actualOutcome)}
                  </span>
                </div>
                <div className="flex items-center justify-between pt-1 border-t border-border">
                  <span className="text-foreground font-medium">Amount saved:</span>
                  <span className="font-mono font-bold text-success">+{formatCurrency(trade.saved)}</span>
                </div>
                <div className="flex items-center gap-1 mt-2">
                  <Info className="h-3 w-3 text-muted-foreground" />
                  <span className="text-muted-foreground">
                    Confidence: {trade.confidence === 'high' ? 'High (based on your exact history)' : 'Medium (based on pattern averages)'}
                  </span>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </motion.div>

      {/* Disclaimer */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6 }}
        className="mt-6 p-4 bg-muted/30 rounded-lg border border-border"
      >
        <div className="flex items-start gap-3">
          <Info className="h-5 w-5 text-muted-foreground flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-foreground mb-1">About these estimates</p>
            <p className="text-xs text-muted-foreground">
              These are conservative estimates based on your personal trading history. We use your actual past losses 
              in similar situations to calculate what you likely would have lost without intervention. We never 
              include hypothetical gains or speculative scenarios. The actual amount saved may be higher.
            </p>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
