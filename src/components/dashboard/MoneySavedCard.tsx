import { ArrowRight, Sparkles, PiggyBank, TrendingUp, Zap } from 'lucide-react';
import { Link } from 'react-router-dom';
import { formatCurrency } from '@/lib/formatters';
import type { MoneySaved } from '@/types/api';

interface MoneySavedCardProps {
  data: MoneySaved;
}

export default function MoneySavedCard({ data }: MoneySavedCardProps) {
  return (
    <div className="card-premium hover-glow-success overflow-hidden transition-transform duration-200 hover:scale-[1.008]">
      {/* Decorative gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-br from-success/8 via-transparent to-primary/5 pointer-events-none" />

      {/* Floating particles effect */}
      <div className="absolute top-4 right-4 opacity-20">
        <div className="animate-float">
          <Sparkles className="h-8 w-8 text-success" />
        </div>
      </div>

      <div className="relative p-6">
        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <div className="p-3.5 rounded-2xl bg-gradient-to-br from-success/25 to-success/10 border border-success/20 shadow-lg transition-transform duration-200 hover:scale-[1.08] hover:rotate-[5deg]">
            <PiggyBank className="h-6 w-6 text-success" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-foreground">Money Saved</h3>
            <p className="text-sm text-muted-foreground">Prevented losses</p>
          </div>
        </div>

        {/* Main Amount */}
        <div className="mb-6 animate-fade-in-up" style={{ animationDelay: '80ms' }}>
          <p className="stat-value-lg text-success">
            {formatCurrency(data.all_time)}
          </p>
          <p className="text-sm text-muted-foreground mt-2 flex items-center gap-2">
            <TrendingUp className="h-3.5 w-3.5 text-success" />
            All time total
          </p>
        </div>

        {/* This Week */}
        <div
          className="p-4 rounded-xl border border-success/25 mb-6 relative overflow-hidden animate-fade-in-up"
          style={{ animationDelay: '140ms' }}
        >
          <div className="absolute inset-0 bg-gradient-to-r from-success/12 via-success/6 to-transparent" />
          <div className="relative flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-1.5 rounded-lg bg-success/20 animate-zap-pulse">
                <Zap className="h-4 w-4 text-success" />
              </div>
              <span className="text-[15px] text-foreground font-medium">This Week</span>
            </div>
            <span className="text-lg font-mono text-success font-medium animate-fade-in" style={{ animationDelay: '200ms' }}>
              +{formatCurrency(data.this_week)}
            </span>
          </div>
        </div>

        {/* Link to Details */}
        <Link
          to="/money-saved"
          className="flex items-center justify-between p-4 rounded-xl bg-muted/40 hover:bg-muted/60 border border-border/50 transition-all duration-300 group"
        >
          <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors font-medium">
            See breakdown
          </span>
          <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-1 transition-all duration-200" />
        </Link>
      </div>
    </div>
  );
}
