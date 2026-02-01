import { ArrowRight, Sparkles, PiggyBank, TrendingUp, Zap } from 'lucide-react';
import { Link } from 'react-router-dom';
import { formatCurrency } from '@/lib/formatters';
import { motion } from 'framer-motion';
import type { MoneySaved } from '@/types/api';

interface MoneySavedCardProps {
  data: MoneySaved;
}

export default function MoneySavedCard({ data }: MoneySavedCardProps) {
  return (
    <motion.div 
      className="card-premium hover-glow-success overflow-hidden"
      whileHover={{ scale: 1.008 }}
      transition={{ type: 'spring', stiffness: 300, damping: 25 }}
    >
      {/* Decorative gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-br from-success/8 via-transparent to-primary/5 pointer-events-none" />
      
      {/* Floating particles effect */}
      <div className="absolute top-4 right-4 opacity-20">
        <motion.div
          animate={{ y: [-5, 5, -5], rotate: [0, 10, 0] }}
          transition={{ duration: 4, repeat: Infinity }}
        >
          <Sparkles className="h-8 w-8 text-success" />
        </motion.div>
      </div>
      
      <div className="relative p-6">
        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <motion.div 
            className="p-3.5 rounded-2xl bg-gradient-to-br from-success/25 to-success/10 border border-success/20 shadow-lg"
            whileHover={{ scale: 1.08, rotate: 5 }}
            transition={{ type: 'spring', stiffness: 300 }}
          >
            <PiggyBank className="h-6 w-6 text-success" />
          </motion.div>
          <div>
            <h3 className="text-lg font-semibold text-foreground">Money Saved</h3>
            <p className="text-sm text-muted-foreground">Prevented losses</p>
          </div>
        </div>

        {/* Main Amount with animation */}
        <div className="mb-6">
          <motion.p 
            className="stat-value-lg text-success"
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ delay: 0.2, type: 'spring', stiffness: 100 }}
          >
            {formatCurrency(data.all_time)}
          </motion.p>
          <p className="text-sm text-muted-foreground mt-2 flex items-center gap-2">
            <TrendingUp className="h-3.5 w-3.5 text-success" />
            All time total
          </p>
        </div>

        {/* This Week with premium styling */}
        <motion.div 
          className="p-4 rounded-xl border border-success/25 mb-6 relative overflow-hidden"
          initial={{ opacity: 0, x: -15 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3, type: 'spring' }}
        >
          {/* Gradient background */}
          <div className="absolute inset-0 bg-gradient-to-r from-success/12 via-success/6 to-transparent" />
          
          <div className="relative flex items-center justify-between">
            <div className="flex items-center gap-3">
              <motion.div
                className="p-1.5 rounded-lg bg-success/20"
                animate={{ rotate: [0, 15, -15, 0], scale: [1, 1.1, 1] }}
                transition={{ duration: 3, repeat: Infinity, repeatDelay: 2 }}
              >
                <Zap className="h-4 w-4 text-success" />
              </motion.div>
              <span className="text-[15px] text-foreground font-medium">This Week</span>
            </div>
            <motion.span 
              className="text-lg font-mono text-success font-medium"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.4 }}
            >
              +{formatCurrency(data.this_week)}
            </motion.span>
          </div>
        </motion.div>

        {/* Link to Details */}
        <Link 
          to="/money-saved"
          className="flex items-center justify-between p-4 rounded-xl bg-muted/40 hover:bg-muted/60 border border-border/50 transition-all duration-300 group"
        >
          <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors font-medium">
            See breakdown
          </span>
          <motion.div
            whileHover={{ x: 6 }}
            transition={{ type: 'spring', stiffness: 400 }}
          >
            <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
          </motion.div>
        </Link>
      </div>
    </motion.div>
  );
}
