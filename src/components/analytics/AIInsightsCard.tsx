import { motion } from 'framer-motion';
import { Lightbulb, ArrowRight } from 'lucide-react';

interface Insight {
  id: string;
  title: string;
  description: string;
  action: string;
  priority: 'high' | 'medium' | 'low';
}

interface AIInsightsCardProps {
  insights: Insight[];
}

export default function AIInsightsCard({ insights }: AIInsightsCardProps) {
  const priorityStyles = {
    high: 'border-l-destructive bg-destructive/5',
    medium: 'border-l-warning bg-warning/5',
    low: 'border-l-success bg-success/5',
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
      className="bg-card rounded-lg border border-border shadow-sm"
    >
      <div className="px-6 py-4 border-b border-border">
        <div className="flex items-center gap-2">
          <Lightbulb className="h-5 w-5 text-primary" />
          <h3 className="text-base font-semibold text-foreground">AI Coach Insights</h3>
        </div>
        <p className="text-sm text-muted-foreground mt-1">Personalized recommendations based on your patterns</p>
      </div>

      <div className="divide-y divide-border">
        {insights.map((insight, idx) => (
          <motion.div
            key={insight.id}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.4 + idx * 0.1 }}
            className={`p-4 border-l-4 ${priorityStyles[insight.priority]}`}
          >
            <h4 className="text-sm font-medium text-foreground mb-1">{insight.title}</h4>
            <p className="text-sm text-muted-foreground mb-3">{insight.description}</p>
            <div className="flex items-center gap-2 text-primary text-sm font-medium">
              <ArrowRight className="h-4 w-4" />
              <span>{insight.action}</span>
            </div>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
