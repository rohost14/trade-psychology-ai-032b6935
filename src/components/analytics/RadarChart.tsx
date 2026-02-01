import { useEffect, useState, useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import {
  Radar,
  RadarChart as RechartsRadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from 'recharts';
import { RadarScores, getPersona } from '@/data/analyticsData';

interface RadarChartProps {
  scores: RadarScores;
}

const RadarChart = ({ scores }: RadarChartProps) => {
  const [animatedScores, setAnimatedScores] = useState<RadarScores>({
    discipline: 0,
    patience: 0,
    riskControl: 0,
    emotionalControl: 0,
    entryTiming: 0,
    exitTiming: 0,
    overall: 0,
  });
  const [displayScore, setDisplayScore] = useState(0);
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  useEffect(() => {
    if (isInView) {
      // Animate scores when in view
      const timer = setTimeout(() => {
        setAnimatedScores(scores);
      }, 200);

      // Animate center score
      const duration = 1500;
      const steps = 60;
      const increment = scores.overall / steps;
      let current = 0;
      const interval = setInterval(() => {
        current += increment;
        if (current >= scores.overall) {
          setDisplayScore(scores.overall);
          clearInterval(interval);
        } else {
          setDisplayScore(Math.floor(current));
        }
      }, duration / steps);

      return () => {
        clearTimeout(timer);
        clearInterval(interval);
      };
    }
  }, [isInView, scores]);

  const persona = getPersona(scores.overall);

  const chartData = [
    { subject: 'Discipline', value: animatedScores.discipline, fullMark: 100 },
    { subject: 'Patience', value: animatedScores.patience, fullMark: 100 },
    { subject: 'Risk Control', value: animatedScores.riskControl, fullMark: 100 },
    { subject: 'Emotional Control', value: animatedScores.emotionalControl, fullMark: 100 },
    { subject: 'Entry Timing', value: animatedScores.entryTiming, fullMark: 100 },
    { subject: 'Exit Timing', value: animatedScores.exitTiming, fullMark: 100 },
  ];

  const getScoreColor = (score: number) => {
    if (score < 40) return 'hsl(var(--destructive))';
    if (score < 70) return 'hsl(var(--warning))';
    return 'hsl(var(--success))';
  };

  const getScoreGradient = (score: number) => {
    if (score < 40) return 'from-red-500/30 to-orange-500/10';
    if (score < 70) return 'from-amber-500/30 to-yellow-500/10';
    return 'from-emerald-500/30 to-teal-500/10';
  };

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 20 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.6, ease: 'easeOut' }}
      className="relative w-full"
    >
      {/* Glassmorphism card */}
      <div className="relative overflow-hidden rounded-2xl border border-border/50 bg-card/80 backdrop-blur-xl p-6 md:p-8">
        {/* Background gradient */}
        <div
          className={`absolute inset-0 bg-gradient-to-br ${getScoreGradient(scores.overall)} opacity-50`}
        />

        {/* Pulsing rings animation */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          {[1, 2, 3].map((i) => (
            <motion.div
              key={i}
              className="absolute rounded-full border border-primary/20"
              initial={{ width: 100, height: 100, opacity: 0 }}
              animate={
                isInView
                  ? {
                      width: [100, 300 + i * 50],
                      height: [100, 300 + i * 50],
                      opacity: [0.5, 0],
                    }
                  : {}
              }
              transition={{
                duration: 3,
                delay: i * 0.5,
                repeat: Infinity,
                repeatDelay: 1,
              }}
            />
          ))}
        </div>

        <div className="relative z-10">
          {/* Header */}
          <div className="text-center mb-4">
            <motion.h2
              initial={{ opacity: 0, y: -10 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: 0.3 }}
              className="text-lg md:text-xl font-semibold text-foreground"
            >
              Your Trading Psychology Profile
            </motion.h2>
          </div>

          {/* Radar Chart */}
          <div className="relative h-[280px] md:h-[350px]">
            <ResponsiveContainer width="100%" height="100%">
              <RechartsRadarChart data={chartData} cx="50%" cy="50%" outerRadius="70%">
                <PolarGrid
                  stroke="hsl(var(--border))"
                  strokeOpacity={0.5}
                />
                <PolarAngleAxis
                  dataKey="subject"
                  tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                  tickLine={false}
                />
                <PolarRadiusAxis
                  angle={90}
                  domain={[0, 100]}
                  tick={false}
                  axisLine={false}
                />
                <Radar
                  name="Score"
                  dataKey="value"
                  stroke={getScoreColor(scores.overall)}
                  fill={getScoreColor(scores.overall)}
                  fillOpacity={0.3}
                  strokeWidth={2}
                  animationDuration={1500}
                  animationEasing="ease-out"
                />
              </RechartsRadarChart>
            </ResponsiveContainer>

            {/* Center score overlay */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <motion.div
                initial={{ scale: 0.5, opacity: 0 }}
                animate={isInView ? { scale: 1, opacity: 1 } : {}}
                transition={{ delay: 0.5, type: 'spring', stiffness: 200 }}
                className="flex flex-col items-center"
              >
                <span
                  className="text-4xl md:text-5xl font-bold font-mono"
                  style={{ color: getScoreColor(scores.overall) }}
                >
                  {displayScore}
                </span>
                <span className="text-xs text-muted-foreground mt-1">out of 100</span>
              </motion.div>
            </div>
          </div>

          {/* Persona badge */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.8 }}
            className="text-center mt-4"
          >
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-background/50 border border-border/50">
              <span className="text-sm text-muted-foreground">You trade like a</span>
              <span
                className="font-semibold text-sm"
                style={{ color: getScoreColor(scores.overall) }}
              >
                {persona.name}
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-2">{persona.description}</p>
          </motion.div>
        </div>
      </div>
    </motion.div>
  );
};

export default RadarChart;
