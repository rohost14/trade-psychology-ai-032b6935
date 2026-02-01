import { motion } from 'framer-motion';
import { Flame, TrendingUp, Activity, Shield, Clock, Target, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface BehavioralPattern {
  id: string;
  name: string;
  type: 'danger' | 'strength';
  count: number;
  impact: string;
  description: string;
  trend: 'up' | 'down' | 'stable';
}

interface BehavioralInsightsCardProps {
  patterns: BehavioralPattern[];
}

const iconMap: Record<string, any> = {
  Flame,
  TrendingUp,
  Activity,
  Shield,
  Clock,
  Target,
};

export default function BehavioralInsightsCard({ patterns }: BehavioralInsightsCardProps) {
  const dangers = patterns.filter(p => p.type === 'danger');
  const strengths = patterns.filter(p => p.type === 'strength');

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="grid grid-cols-1 md:grid-cols-2 gap-4"
    >
      {/* Danger Patterns */}
      <div className="bg-card rounded-lg border border-border shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-border bg-destructive/5 border-l-4 border-l-destructive">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-destructive" />
            <h3 className="text-sm font-semibold text-foreground">Areas to Improve</h3>
          </div>
        </div>
        <div className="divide-y divide-border">
          {dangers.length > 0 ? dangers.map((pattern) => {
            const Icon = iconMap[pattern.name.includes('Revenge') ? 'Flame' : pattern.name.includes('FOMO') ? 'TrendingUp' : 'Activity'] || Activity;
            return (
              <div key={pattern.id} className="p-4 hover:bg-muted/20 transition-colors">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-lg bg-destructive/10">
                      <Icon className="h-4 w-4 text-destructive" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-foreground">{pattern.name}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">{pattern.description}</p>
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-sm font-mono font-medium text-destructive">{pattern.impact}</p>
                    <p className="text-xs text-muted-foreground">{pattern.count}x this week</p>
                  </div>
                </div>
              </div>
            );
          }) : (
            <div className="p-6 text-center">
              <CheckCircle2 className="h-8 w-8 text-success mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">No concerning patterns detected</p>
            </div>
          )}
        </div>
      </div>

      {/* Strength Patterns */}
      <div className="bg-card rounded-lg border border-border shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-border bg-success/5 border-l-4 border-l-success">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-success" />
            <h3 className="text-sm font-semibold text-foreground">Your Strengths</h3>
          </div>
        </div>
        <div className="divide-y divide-border">
          {strengths.length > 0 ? strengths.map((pattern) => {
            const Icon = iconMap[pattern.name.includes('Stop') ? 'Shield' : pattern.name.includes('Patient') ? 'Clock' : 'Target'] || Target;
            return (
              <div key={pattern.id} className="p-4 hover:bg-muted/20 transition-colors">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-lg bg-success/10">
                      <Icon className="h-4 w-4 text-success" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-foreground">{pattern.name}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">{pattern.description}</p>
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-sm font-mono font-medium text-success">{pattern.impact}</p>
                    <p className="text-xs text-muted-foreground">{pattern.count}x this week</p>
                  </div>
                </div>
              </div>
            );
          }) : (
            <div className="p-6 text-center">
              <AlertTriangle className="h-8 w-8 text-warning mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">Keep trading to build your strengths</p>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
