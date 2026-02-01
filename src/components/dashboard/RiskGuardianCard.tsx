import { RefreshCw, Shield, AlertTriangle, CheckCircle2, Activity, Zap, TrendingUp, Target } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { motion } from 'framer-motion';

interface RiskGuardianData {
  risk_state: 'safe' | 'caution' | 'danger';
  status_message: string;
  active_patterns: string[];
  unrealized_pnl: number;
  ai_recommendations: string[];
  last_synced: string;
}

interface RiskGuardianStats {
  trades_today?: number;
  win_rate?: number;
  max_drawdown?: number;
  risk_used?: number;
}

interface RiskGuardianCardProps {
  data: RiskGuardianData;
  stats?: RiskGuardianStats;
  onSync?: () => void;
  isLoading?: boolean;
}

const riskStateConfig = {
  safe: {
    borderClass: 'border-l-success',
    badgeClass: 'bg-success/15 text-success border border-success/25',
    bgGradient: 'from-success/10 via-success/5 to-transparent',
    iconBg: 'bg-gradient-to-br from-success/25 to-success/10',
    label: 'SAFE',
    icon: CheckCircle2,
    glowClass: 'hover-glow-success',
    dotColor: 'bg-success',
  },
  caution: {
    borderClass: 'border-l-warning',
    badgeClass: 'bg-warning/15 text-warning border border-warning/25',
    bgGradient: 'from-warning/10 via-warning/5 to-transparent',
    iconBg: 'bg-gradient-to-br from-warning/25 to-warning/10',
    label: 'CAUTION',
    icon: AlertTriangle,
    glowClass: 'hover-glow-warning',
    dotColor: 'bg-warning',
  },
  danger: {
    borderClass: 'border-l-destructive',
    badgeClass: 'bg-destructive/15 text-destructive border border-destructive/25',
    bgGradient: 'from-destructive/10 via-destructive/5 to-transparent',
    iconBg: 'bg-gradient-to-br from-destructive/25 to-destructive/10',
    label: 'DANGER',
    icon: AlertTriangle,
    glowClass: 'hover-glow-danger',
    dotColor: 'bg-destructive',
  },
};

export default function RiskGuardianCard({ data, stats: propStats, onSync, isLoading }: RiskGuardianCardProps) {
  const config = riskStateConfig[data.risk_state];
  const pnlColor = data.unrealized_pnl >= 0 ? 'text-success' : 'text-destructive';
  const StateIcon = config.icon;

  const stats = {
    trades: propStats?.trades_today ?? 0,
    winRate: propStats?.win_rate ?? 0,
    drawdown: propStats?.max_drawdown ?? 0,
    riskUsed: propStats?.risk_used ?? 0,
  };

  const statItems = [
    { label: 'Trades Today', value: stats.trades, color: 'text-foreground', icon: Target },
    { label: 'Win Rate', value: `${stats.winRate}%`, color: stats.winRate >= 50 ? 'text-success' : 'text-destructive', icon: TrendingUp },
    { label: 'Max Drawdown', value: formatCurrencyWithSign(stats.drawdown), color: 'text-destructive', icon: Activity },
    { label: 'Risk Budget', value: `${stats.riskUsed}%`, color: stats.riskUsed > 80 ? 'text-destructive' : stats.riskUsed > 60 ? 'text-warning' : 'text-success', icon: Zap },
  ];

  return (
    <motion.div 
      className={cn(
        'card-hero overflow-hidden',
        'border-l-4',
        config.borderClass,
        config.glowClass
      )}
      whileHover={{ scale: 1.003 }}
      transition={{ type: 'spring', stiffness: 300, damping: 25 }}
    >
      {/* Decorative mesh gradient */}
      <div className="absolute inset-0 bg-gradient-mesh opacity-40 pointer-events-none" />
      
      {/* Header with gradient */}
      <div className={cn('relative px-8 py-7 bg-gradient-to-r', config.bgGradient)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-5">
            <motion.div 
              className={cn('p-4 rounded-2xl border border-border/30 shadow-lg', config.iconBg)}
              whileHover={{ scale: 1.08, rotate: 5 }}
              transition={{ type: 'spring', stiffness: 300 }}
            >
              <Shield className="h-7 w-7 text-primary" />
            </motion.div>
            <div>
              <div className="flex items-center gap-3 flex-wrap">
                <h2 className="text-xl font-semibold text-foreground">Risk Guardian</h2>
                <motion.span 
                  className={cn('badge-premium', config.badgeClass)}
                  initial={{ scale: 0.8, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: 0.2, type: 'spring' }}
                >
                  <StateIcon className="h-3.5 w-3.5" />
                  {config.label}
                </motion.span>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 border border-primary/20 backdrop-blur-sm">
                  <motion.div 
                    className={cn('status-dot', config.dotColor)}
                    animate={{ opacity: [1, 0.6, 1] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  />
                  <span className="text-xs font-semibold text-primary tracking-wide">LIVE</span>
                </div>
              </div>
              <p className="text-[15px] text-muted-foreground mt-2 max-w-md">
                {data.status_message || 'Monitoring your trading behavior in real-time'}
                {data.last_synced && (
                  <span className="ml-2 text-xs text-muted-foreground/70">• {data.last_synced}</span>
                )}
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-8">
            <div className="text-right">
              <p className="text-sm text-muted-foreground mb-1.5 font-medium">Session P&L</p>
              <motion.p 
                className={cn('stat-value-lg', pnlColor)}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3, type: 'spring', stiffness: 100 }}
              >
                {formatCurrencyWithSign(data.unrealized_pnl)}
              </motion.p>
            </div>
            <Button
              variant="outline"
              size="icon"
              onClick={onSync}
              disabled={isLoading}
              className="h-12 w-12 rounded-xl border-border/50 bg-card/50 backdrop-blur-sm hover:bg-muted/80 transition-all duration-300 shadow-sm"
            >
              <RefreshCw className={cn('h-5 w-5', isLoading && 'animate-spin')} />
            </Button>
          </div>
        </div>
      </div>

      {/* Stats Row */}
      <div className="relative grid grid-cols-2 lg:grid-cols-4 divide-x divide-y lg:divide-y-0 divide-border/40">
        {statItems.map((stat, i) => (
          <motion.div 
            key={stat.label}
            className="px-8 py-6 group hover:bg-muted/40 transition-all duration-300 cursor-default"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + i * 0.06, type: 'spring', stiffness: 120 }}
          >
            <div className="flex items-center gap-2 mb-2">
              <stat.icon className="h-3.5 w-3.5 text-muted-foreground" />
              <p className="stat-label">{stat.label}</p>
            </div>
            <motion.p 
              className={cn('stat-value', stat.color)}
              whileHover={{ scale: 1.02 }}
              transition={{ type: 'spring', stiffness: 400 }}
            >
              {stat.value}
            </motion.p>
          </motion.div>
        ))}
      </div>

      {/* Risk Capacity Bar */}
      <div className="relative px-8 py-5 bg-gradient-to-r from-muted/50 to-muted/20 border-t border-border/40">
        <div className="flex items-center justify-between text-sm mb-3">
          <span className="text-muted-foreground font-medium flex items-center gap-2">
            <Zap className="h-4 w-4" />
            Risk Capacity
          </span>
          <motion.span 
            className={cn(
              'font-semibold',
              stats.riskUsed > 80 ? 'text-destructive' : stats.riskUsed > 60 ? 'text-warning' : 'text-success'
            )}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
          >
            {100 - stats.riskUsed}% remaining
          </motion.span>
        </div>
        <div className="h-3 bg-muted/80 rounded-full overflow-hidden shadow-inner">
          <motion.div 
            className={cn(
              'h-full rounded-full relative',
              stats.riskUsed > 80 ? 'bg-gradient-to-r from-destructive to-destructive/80' : 
              stats.riskUsed > 60 ? 'bg-gradient-to-r from-warning to-warning/80' : 
              'bg-gradient-to-r from-success to-success/80'
            )}
            initial={{ width: 0 }}
            animate={{ width: `${stats.riskUsed}%` }}
            transition={{ duration: 1.2, delay: 0.4, ease: [0.16, 1, 0.3, 1] }}
          >
            {/* Shimmer effect on bar */}
            <motion.div 
              className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent"
              initial={{ x: '-100%' }}
              animate={{ x: '200%' }}
              transition={{ duration: 2, delay: 1.5, repeat: Infinity, repeatDelay: 4 }}
            />
          </motion.div>
        </div>
      </div>
    </motion.div>
  );
}
