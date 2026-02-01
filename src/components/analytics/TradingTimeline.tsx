import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import { TimelineTrade, emotionColorMap } from '@/data/analyticsData';
import { formatCurrency } from '@/lib/formatters';

interface TradingTimelineProps {
  trades: TimelineTrade[];
}

const TradingTimeline = ({ trades }: TradingTimelineProps) => {
  const [selectedTrade, setSelectedTrade] = useState<TimelineTrade | null>(null);
  const [hoveredTrade, setHoveredTrade] = useState<TimelineTrade | null>(null);

  const getEmotionColors = (emotion: string) => {
    return emotionColorMap[emotion] || { bg: 'bg-muted', border: 'border-muted', text: 'text-muted-foreground' };
  };

  const getDotSize = (size: number) => {
    if (size < 30) return 'w-3 h-3';
    if (size < 60) return 'w-4 h-4';
    return 'w-5 h-5';
  };

  const isNegativeEmotion = (emotion: string) => {
    return ['Revenge', 'FOMO', 'Panic', 'Greedy', 'Overconfident'].includes(emotion);
  };

  return (
    <div className="relative">
      {/* Glassmorphism card */}
      <div className="relative overflow-hidden rounded-2xl border border-border/50 bg-card/80 backdrop-blur-xl p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-semibold text-foreground">Behavioral Timeline</h3>
            <p className="text-sm text-muted-foreground">Last 20 trades - hover to explore</p>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
              <span className="text-muted-foreground">Disciplined</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-red-500" />
              <span className="text-muted-foreground">Emotional</span>
            </div>
          </div>
        </div>

        {/* Timeline */}
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-gradient-to-r from-border via-border/50 to-border transform -translate-y-1/2" />

          {/* Red cluster indicator */}
          <div className="absolute top-1/2 left-[5%] w-[15%] h-8 bg-red-500/10 border border-red-500/20 rounded-lg transform -translate-y-1/2 flex items-center justify-center">
            <span className="text-[10px] text-red-400 font-medium">Tilt Zone</span>
          </div>

          {/* Scrollable timeline container */}
          <div className="overflow-x-auto pb-4 -mx-2 px-2">
            <div className="flex items-center gap-4 min-w-max py-8">
              {trades.map((trade, index) => {
                const colors = getEmotionColors(trade.emotion);
                const isNegative = isNegativeEmotion(trade.emotion);

                return (
                  <motion.div
                    key={trade.id}
                    initial={{ opacity: 0, scale: 0 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: index * 0.05, type: 'spring', stiffness: 300 }}
                    className="relative flex flex-col items-center cursor-pointer group"
                    onMouseEnter={() => setHoveredTrade(trade)}
                    onMouseLeave={() => setHoveredTrade(null)}
                    onClick={() => setSelectedTrade(trade)}
                  >
                    {/* Time label */}
                    <span className="text-[10px] text-muted-foreground mb-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      {trade.time}
                    </span>

                    {/* Dot */}
                    <motion.div
                      className={`
                        ${getDotSize(trade.size)} 
                        ${colors.bg} 
                        rounded-full 
                        border-2 
                        ${colors.border}
                        shadow-lg
                        transition-all
                        duration-200
                        group-hover:scale-125
                        ${isNegative ? 'group-hover:shadow-red-500/50' : 'group-hover:shadow-emerald-500/50'}
                      `}
                      animate={
                        hoveredTrade?.id === trade.id
                          ? { scale: [1, 1.2, 1], boxShadow: ['0 0 0 0 rgba(0,0,0,0)', '0 0 20px 5px rgba(255,255,255,0.3)', '0 0 0 0 rgba(0,0,0,0)'] }
                          : {}
                      }
                      transition={{ duration: 0.5, repeat: hoveredTrade?.id === trade.id ? Infinity : 0 }}
                    />

                    {/* Symbol label */}
                    <span className="text-[10px] font-medium text-muted-foreground mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      {trade.symbol}
                    </span>

                    {/* Hover tooltip */}
                    <AnimatePresence>
                      {hoveredTrade?.id === trade.id && (
                        <motion.div
                          initial={{ opacity: 0, y: 10, scale: 0.9 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          exit={{ opacity: 0, y: 10, scale: 0.9 }}
                          className="absolute bottom-full mb-8 z-20 min-w-[160px]"
                        >
                          <div className="bg-popover/95 backdrop-blur-lg border border-border rounded-xl p-3 shadow-xl">
                            <div className="text-xs space-y-1.5">
                              <div className="flex justify-between items-center">
                                <span className="text-muted-foreground">Symbol</span>
                                <span className="font-semibold text-foreground">{trade.symbol}</span>
                              </div>
                              <div className="flex justify-between items-center">
                                <span className="text-muted-foreground">Time</span>
                                <span className="font-medium text-foreground">{trade.time}</span>
                              </div>
                              <div className="flex justify-between items-center">
                                <span className="text-muted-foreground">P&L</span>
                                <span className={`font-mono font-semibold ${trade.pnl >= 0 ? 'text-success' : 'text-destructive'}`}>
                                  {trade.pnl >= 0 ? '+' : ''}{formatCurrency(trade.pnl)}
                                </span>
                              </div>
                              <div className="flex justify-between items-center">
                                <span className="text-muted-foreground">Emotion</span>
                                <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${colors.bg} ${colors.text}`}>
                                  {trade.emotion}
                                </span>
                              </div>
                            </div>
                            {/* Arrow */}
                            <div className="absolute left-1/2 -bottom-1.5 transform -translate-x-1/2 w-3 h-3 bg-popover border-r border-b border-border rotate-45" />
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Click hint */}
        <p className="text-xs text-muted-foreground text-center mt-2">
          Click any dot for full trade breakdown
        </p>
      </div>

      {/* Trade detail modal */}
      <AnimatePresence>
        {selectedTrade && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm"
            onClick={() => setSelectedTrade(null)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="relative w-full max-w-md bg-card border border-border rounded-2xl p-6 shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                onClick={() => setSelectedTrade(null)}
                className="absolute top-4 right-4 p-1 rounded-lg hover:bg-muted transition-colors"
              >
                <X className="w-5 h-5 text-muted-foreground" />
              </button>

              <h3 className="text-lg font-semibold text-foreground mb-4">Trade Details</h3>

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 rounded-lg bg-muted/50">
                    <span className="text-xs text-muted-foreground">Symbol</span>
                    <p className="text-base font-semibold text-foreground">{selectedTrade.symbol}</p>
                  </div>
                  <div className="p-3 rounded-lg bg-muted/50">
                    <span className="text-xs text-muted-foreground">Time</span>
                    <p className="text-base font-semibold text-foreground">{selectedTrade.time}</p>
                  </div>
                </div>

                <div className="p-4 rounded-lg bg-muted/50">
                  <span className="text-xs text-muted-foreground">Profit/Loss</span>
                  <p className={`text-2xl font-bold font-mono ${selectedTrade.pnl >= 0 ? 'text-success' : 'text-destructive'}`}>
                    {selectedTrade.pnl >= 0 ? '+' : ''}{formatCurrency(selectedTrade.pnl)}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 rounded-lg bg-muted/50">
                    <span className="text-xs text-muted-foreground">Emotion Detected</span>
                    <div className="mt-1">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${getEmotionColors(selectedTrade.emotion).bg} ${getEmotionColors(selectedTrade.emotion).text}`}>
                        {selectedTrade.emotion}
                      </span>
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-muted/50">
                    <span className="text-xs text-muted-foreground">Position Size</span>
                    <p className="text-base font-semibold text-foreground">{selectedTrade.size} lots</p>
                  </div>
                </div>

                {isNegativeEmotion(selectedTrade.emotion) && (
                  <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/20">
                    <p className="text-sm text-destructive">
                      ⚠️ This trade was flagged as emotionally-driven. Consider reviewing your entry criteria.
                    </p>
                  </div>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default TradingTimeline;
