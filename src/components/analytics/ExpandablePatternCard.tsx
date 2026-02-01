import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Flame,
  TrendingUp,
  Activity,
  Shield,
  Clock,
  Target,
  Scale,
  ChevronDown,
  Sparkles,
} from 'lucide-react';
import { ExpandablePattern } from '@/data/analyticsData';

interface ExpandablePatternCardProps {
  pattern: ExpandablePattern;
}

const iconMap: Record<string, React.ElementType> = {
  Flame,
  TrendingUp,
  Activity,
  Shield,
  Clock,
  Target,
  Scale,
};

const ExpandablePatternCard = ({ pattern }: ExpandablePatternCardProps) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const Icon = iconMap[pattern.icon] || Activity;

  const getSeverityStyles = () => {
    switch (pattern.severity) {
      case 'critical':
        return {
          border: 'border-red-500/30 hover:border-red-500/50',
          gradient: 'from-red-500/10 via-transparent to-transparent',
          badge: 'bg-red-500/20 text-red-400 border-red-500/30',
          iconBg: 'bg-red-500/20',
          iconColor: 'text-red-400',
        };
      case 'warning':
        return {
          border: 'border-amber-500/30 hover:border-amber-500/50',
          gradient: 'from-amber-500/10 via-transparent to-transparent',
          badge: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
          iconBg: 'bg-amber-500/20',
          iconColor: 'text-amber-400',
        };
      case 'positive':
        return {
          border: 'border-emerald-500/30 hover:border-emerald-500/50',
          gradient: 'from-emerald-500/10 via-transparent to-transparent',
          badge: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
          iconBg: 'bg-emerald-500/20',
          iconColor: 'text-emerald-400',
        };
    }
  };

  const styles = getSeverityStyles();

  const getSeverityLabel = () => {
    switch (pattern.severity) {
      case 'critical':
        return 'Critical';
      case 'warning':
        return 'Attention';
      case 'positive':
        return 'Strength';
    }
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={`
        relative overflow-hidden rounded-xl border bg-card/50 backdrop-blur-sm
        cursor-pointer transition-all duration-300
        ${styles.border}
      `}
      onClick={() => setIsExpanded(!isExpanded)}
    >
      {/* Background gradient */}
      <div className={`absolute inset-0 bg-gradient-to-br ${styles.gradient} opacity-50`} />

      <div className="relative z-10">
        {/* Collapsed header */}
        <div className="p-4 flex items-center gap-3">
          <motion.div
            className={`p-2.5 rounded-xl ${styles.iconBg}`}
            animate={
              pattern.severity === 'critical'
                ? { scale: [1, 1.1, 1] }
                : {}
            }
            transition={{ duration: 1.5, repeat: Infinity }}
          >
            <Icon className={`w-5 h-5 ${styles.iconColor}`} />
          </motion.div>

          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-foreground truncate">
              {pattern.name}
            </p>
            <p className="text-xs text-muted-foreground">
              {pattern.frequency}x this week
            </p>
          </div>

          <span className={`px-2 py-1 text-[10px] font-medium rounded-full border ${styles.badge}`}>
            {getSeverityLabel()}
          </span>

          <motion.div
            animate={{ rotate: isExpanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
          >
            <ChevronDown className="w-4 h-4 text-muted-foreground" />
          </motion.div>
        </div>

        {/* Expanded content */}
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3, ease: 'easeInOut' }}
              className="overflow-hidden"
            >
              <div className="px-4 pb-4 space-y-3">
                <div className="h-px bg-border" />

                {/* Description */}
                <p className="text-sm text-muted-foreground">
                  {pattern.description}
                </p>

                {/* Stats */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 rounded-lg bg-muted/30">
                    <span className="text-[10px] text-muted-foreground uppercase tracking-wide">
                      Last Detected
                    </span>
                    <p className="text-sm font-medium text-foreground mt-0.5">
                      {pattern.lastDetected}
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-muted/30">
                    <span className="text-[10px] text-muted-foreground uppercase tracking-wide">
                      Frequency
                    </span>
                    <p className="text-sm font-medium text-foreground mt-0.5">
                      {pattern.frequency} times/week
                    </p>
                  </div>
                </div>

                {/* AI Advice */}
                <div className={`p-3 rounded-lg border ${styles.border} bg-background/50`}>
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles className={`w-4 h-4 ${styles.iconColor}`} />
                    <span className="text-xs font-semibold text-foreground">AI Insight</span>
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {pattern.aiAdvice}
                  </p>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
};

export default ExpandablePatternCard;
