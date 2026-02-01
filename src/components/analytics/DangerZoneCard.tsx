import { motion } from 'framer-motion';
import { Flame, TrendingUp, Activity, AlertTriangle } from 'lucide-react';
import { DangerPattern } from '@/data/analyticsData';

interface DangerZoneCardProps {
  dangers: DangerPattern[];
}

const iconMap: Record<string, React.ElementType> = {
  Flame,
  TrendingUp,
  Activity,
  AlertTriangle,
};

const DangerZoneCard = ({ dangers }: DangerZoneCardProps) => {
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="relative overflow-hidden rounded-2xl"
    >
      {/* Gradient background */}
      <div className="absolute inset-0 bg-gradient-to-br from-red-600 via-red-700 to-orange-700" />

      {/* Animated background pattern */}
      <div className="absolute inset-0 opacity-10">
        <div className="absolute top-0 left-0 w-32 h-32 bg-white rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-0 right-0 w-40 h-40 bg-orange-300 rounded-full blur-3xl animate-pulse delay-700" />
      </div>

      <div className="relative z-10 p-6">
        {/* Header */}
        <div className="flex items-center gap-3 mb-5">
          <motion.div
            animate={{ scale: [1, 1.1, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="p-2.5 rounded-xl bg-white/20 backdrop-blur-sm"
          >
            <AlertTriangle className="w-5 h-5 text-white" />
          </motion.div>
          <div>
            <h3 className="text-lg font-bold text-white">Danger Zone</h3>
            <p className="text-xs text-red-100/80">Critical patterns to address</p>
          </div>
        </div>

        {/* Patterns list */}
        <div className="space-y-3">
          {dangers.map((danger, index) => {
            const Icon = iconMap[danger.icon] || Flame;

            return (
              <motion.div
                key={danger.name}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 + index * 0.1 }}
                className="flex items-center gap-3 p-3 rounded-xl bg-white/10 backdrop-blur-sm border border-white/10 hover:bg-white/15 transition-colors"
              >
                <motion.div
                  animate={{ rotate: [0, 5, -5, 0] }}
                  transition={{ duration: 0.5, repeat: Infinity, repeatDelay: 2 }}
                  className="p-2 rounded-lg bg-red-500/30"
                >
                  <Icon className="w-4 h-4 text-red-100" />
                </motion.div>

                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-white truncate">{danger.name}</p>
                  <p className="text-xs text-red-100/70">
                    Detected {danger.count} times this week
                  </p>
                </div>

                <div className="text-right">
                  <p className="text-sm font-mono font-bold text-white">{danger.impact}</p>
                  <p className="text-[10px] text-red-100/60">impact</p>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Total impact */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="mt-4 pt-4 border-t border-white/20"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs text-red-100/80">Total weekly impact</span>
            <span className="text-lg font-bold font-mono text-white">₹26,200</span>
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
};

export default DangerZoneCard;
