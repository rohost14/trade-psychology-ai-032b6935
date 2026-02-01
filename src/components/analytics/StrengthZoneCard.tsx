import { motion } from 'framer-motion';
import { Shield, Clock, Target, CheckCircle2 } from 'lucide-react';
import { StrengthPattern } from '@/data/analyticsData';

interface StrengthZoneCardProps {
  strengths: StrengthPattern[];
}

const iconMap: Record<string, React.ElementType> = {
  Shield,
  Clock,
  Target,
  CheckCircle2,
};

const StrengthZoneCard = ({ strengths }: StrengthZoneCardProps) => {
  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="relative overflow-hidden rounded-2xl"
    >
      {/* Gradient background */}
      <div className="absolute inset-0 bg-gradient-to-br from-emerald-600 via-emerald-700 to-teal-700" />

      {/* Animated background pattern */}
      <div className="absolute inset-0 opacity-10">
        <div className="absolute top-0 right-0 w-32 h-32 bg-white rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-0 left-0 w-40 h-40 bg-teal-300 rounded-full blur-3xl animate-pulse delay-700" />
      </div>

      <div className="relative z-10 p-6">
        {/* Header */}
        <div className="flex items-center gap-3 mb-5">
          <motion.div
            animate={{ scale: [1, 1.05, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="p-2.5 rounded-xl bg-white/20 backdrop-blur-sm"
          >
            <CheckCircle2 className="w-5 h-5 text-white" />
          </motion.div>
          <div>
            <h3 className="text-lg font-bold text-white">Strength Zone</h3>
            <p className="text-xs text-emerald-100/80">Your winning patterns</p>
          </div>
        </div>

        {/* Patterns list */}
        <div className="space-y-3">
          {strengths.map((strength, index) => {
            const Icon = iconMap[strength.icon] || Shield;

            return (
              <motion.div
                key={strength.name}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 + index * 0.1 }}
                className="flex items-center gap-3 p-3 rounded-xl bg-white/10 backdrop-blur-sm border border-white/10 hover:bg-white/15 transition-colors"
              >
                <motion.div
                  animate={{ scale: [1, 1.1, 1] }}
                  transition={{ duration: 1.5, repeat: Infinity, repeatDelay: 1 }}
                  className="p-2 rounded-lg bg-emerald-500/30"
                >
                  <Icon className="w-4 h-4 text-emerald-100" />
                </motion.div>

                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-white truncate">{strength.name}</p>
                  <p className="text-xs text-emerald-100/70">
                    Active in {strength.count} trades
                  </p>
                </div>

                <div className="text-right">
                  <p className="text-sm font-mono font-bold text-white">{strength.impact}</p>
                  <p className="text-[10px] text-emerald-100/60">saved</p>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Total saved */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="mt-4 pt-4 border-t border-white/20"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs text-emerald-100/80">Total money protected</span>
            <span className="text-lg font-bold font-mono text-white">₹16,100</span>
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
};

export default StrengthZoneCard;
