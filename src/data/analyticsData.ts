// Mock data for Analytics page

export interface RadarScores {
  discipline: number;
  patience: number;
  riskControl: number;
  emotionalControl: number;
  entryTiming: number;
  exitTiming: number;
  overall: number;
}

export interface TimelineTrade {
  id: number;
  time: string;
  symbol: string;
  pnl: number;
  emotion: 'Revenge' | 'FOMO' | 'Disciplined' | 'Panic' | 'Greedy' | 'Patient' | 'Overconfident';
  size: number;
}

export interface DangerPattern {
  name: string;
  count: number;
  impact: string;
  icon: string;
}

export interface StrengthPattern {
  name: string;
  count: number;
  impact: string;
  icon: string;
}

export interface HourlyPnl {
  hour: string;
  pnl: number;
  trades: number;
  wins: number;
  losses: number;
}

export interface ExpandablePattern {
  id: string;
  name: string;
  severity: 'critical' | 'warning' | 'positive';
  description: string;
  lastDetected: string;
  frequency: number;
  aiAdvice: string;
  icon: string;
}

export const radarScores: RadarScores = {
  discipline: 45,
  patience: 38,
  riskControl: 72,
  emotionalControl: 41,
  entryTiming: 65,
  exitTiming: 58,
  overall: 53,
};

export const personaMap: Record<string, { name: string; description: string }> = {
  low: { name: 'Impulsive Maverick', description: 'High risk tolerance, needs structure' },
  medium: { name: 'Evolving Trader', description: 'Building discipline, room to grow' },
  high: { name: 'Calculated Strategist', description: 'Methodical approach, strong control' },
};

export const getPersona = (score: number) => {
  if (score < 40) return personaMap.low;
  if (score < 70) return personaMap.medium;
  return personaMap.high;
};

export const timelineTrades: TimelineTrade[] = [
  { id: 1, time: '9:25 AM', symbol: 'NIFTY', pnl: -340, emotion: 'Revenge', size: 50 },
  { id: 2, time: '9:32 AM', symbol: 'NIFTY', pnl: -120, emotion: 'FOMO', size: 75 },
  { id: 3, time: '10:15 AM', symbol: 'BANKNIFTY', pnl: 520, emotion: 'Disciplined', size: 25 },
  { id: 4, time: '10:45 AM', symbol: 'RELIANCE', pnl: 180, emotion: 'Patient', size: 30 },
  { id: 5, time: '11:02 AM', symbol: 'NIFTY', pnl: -450, emotion: 'Overconfident', size: 100 },
  { id: 6, time: '11:18 AM', symbol: 'NIFTY', pnl: -220, emotion: 'Revenge', size: 80 },
  { id: 7, time: '11:35 AM', symbol: 'HDFC', pnl: 340, emotion: 'Disciplined', size: 40 },
  { id: 8, time: '12:00 PM', symbol: 'BANKNIFTY', pnl: 890, emotion: 'Patient', size: 35 },
  { id: 9, time: '12:30 PM', symbol: 'INFY', pnl: -80, emotion: 'FOMO', size: 45 },
  { id: 10, time: '1:15 PM', symbol: 'TCS', pnl: 420, emotion: 'Disciplined', size: 25 },
  { id: 11, time: '1:45 PM', symbol: 'NIFTY', pnl: -560, emotion: 'Panic', size: 90 },
  { id: 12, time: '2:00 PM', symbol: 'BANKNIFTY', pnl: 280, emotion: 'Patient', size: 30 },
  { id: 13, time: '2:20 PM', symbol: 'NIFTY', pnl: -180, emotion: 'Greedy', size: 60 },
  { id: 14, time: '2:35 PM', symbol: 'RELIANCE', pnl: 150, emotion: 'Disciplined', size: 20 },
  { id: 15, time: '2:50 PM', symbol: 'NIFTY', pnl: -320, emotion: 'Revenge', size: 85 },
  { id: 16, time: '3:00 PM', symbol: 'BANKNIFTY', pnl: 620, emotion: 'Patient', size: 40 },
  { id: 17, time: '3:10 PM', symbol: 'NIFTY', pnl: 180, emotion: 'Disciplined', size: 25 },
  { id: 18, time: '3:20 PM', symbol: 'HDFC', pnl: -90, emotion: 'FOMO', size: 35 },
  { id: 19, time: '3:25 PM', symbol: 'NIFTY', pnl: 240, emotion: 'Patient', size: 30 },
  { id: 20, time: '3:28 PM', symbol: 'BANKNIFTY', pnl: -150, emotion: 'Panic', size: 50 },
];

export const dangerPatterns: DangerPattern[] = [
  { name: 'Revenge Trading', count: 7, impact: '₹12,400', icon: 'Flame' },
  { name: 'FOMO Entries', count: 5, impact: '₹8,200', icon: 'TrendingUp' },
  { name: 'Overtrading', count: 12, impact: '₹5,600', icon: 'Activity' },
];

export const strengthPatterns: StrengthPattern[] = [
  { name: 'Stop Loss Discipline', count: 18, impact: '₹8,200', icon: 'Shield' },
  { name: 'Patient Entries', count: 9, impact: '₹4,100', icon: 'Clock' },
  { name: 'Risk Consistency', count: 15, impact: '₹3,800', icon: 'Target' },
];

export const hourlyPnlData: HourlyPnl[] = [
  { hour: '9:15', pnl: -460, trades: 3, wins: 0, losses: 3 },
  { hour: '10:00', pnl: 180, trades: 2, wins: 2, losses: 0 },
  { hour: '11:00', pnl: -330, trades: 3, wins: 1, losses: 2 },
  { hour: '12:00', pnl: 810, trades: 2, wins: 2, losses: 0 },
  { hour: '1:00', pnl: -140, trades: 2, wins: 1, losses: 1 },
  { hour: '2:00', pnl: 250, trades: 4, wins: 3, losses: 1 },
  { hour: '3:00', pnl: 800, trades: 4, wins: 3, losses: 1 },
];

export const expandablePatterns: ExpandablePattern[] = [
  {
    id: '1',
    name: 'Revenge Trading',
    severity: 'critical',
    description: 'Trading immediately after a loss to recover, often leading to larger losses.',
    lastDetected: '2 hours ago',
    frequency: 7,
    aiAdvice: 'Take a 15-minute break after any loss exceeding ₹500. Your win rate drops 40% when revenge trading.',
    icon: 'Flame',
  },
  {
    id: '2',
    name: 'FOMO Entries',
    severity: 'warning',
    description: 'Entering trades late in a move due to fear of missing out.',
    lastDetected: '4 hours ago',
    frequency: 5,
    aiAdvice: 'Wait for a pullback. FOMO entries have a 23% lower success rate in your history.',
    icon: 'TrendingUp',
  },
  {
    id: '3',
    name: 'Stop Loss Discipline',
    severity: 'positive',
    description: 'Consistently honoring pre-set stop losses without moving them.',
    lastDetected: '30 minutes ago',
    frequency: 18,
    aiAdvice: 'Excellent discipline! This habit has prevented an estimated ₹8,200 in additional losses.',
    icon: 'Shield',
  },
  {
    id: '4',
    name: 'Overtrading',
    severity: 'critical',
    description: 'Taking too many trades, often from boredom or overconfidence.',
    lastDetected: '1 hour ago',
    frequency: 12,
    aiAdvice: 'Limit to 5 trades per day. Your win rate drops from 58% to 34% after the 5th trade.',
    icon: 'Activity',
  },
  {
    id: '5',
    name: 'Patient Entries',
    severity: 'positive',
    description: 'Waiting for optimal entry points based on your trading plan.',
    lastDetected: '1 hour ago',
    frequency: 9,
    aiAdvice: 'Great pattern! Patient entries have a 72% success rate vs 45% for impulsive ones.',
    icon: 'Clock',
  },
  {
    id: '6',
    name: 'Position Sizing',
    severity: 'warning',
    description: 'Occasionally exceeding recommended position sizes.',
    lastDetected: '3 hours ago',
    frequency: 4,
    aiAdvice: 'Keep positions under 3% of capital. Large positions correlate with 2x more emotional decisions.',
    icon: 'Scale',
  },
];

export const emotionColorMap: Record<string, { bg: string; border: string; text: string }> = {
  Revenge: { bg: 'bg-red-500', border: 'border-red-400', text: 'text-red-100' },
  FOMO: { bg: 'bg-orange-500', border: 'border-orange-400', text: 'text-orange-100' },
  Panic: { bg: 'bg-red-600', border: 'border-red-500', text: 'text-red-100' },
  Greedy: { bg: 'bg-amber-500', border: 'border-amber-400', text: 'text-amber-100' },
  Overconfident: { bg: 'bg-orange-600', border: 'border-orange-500', text: 'text-orange-100' },
  Disciplined: { bg: 'bg-emerald-500', border: 'border-emerald-400', text: 'text-emerald-100' },
  Patient: { bg: 'bg-teal-500', border: 'border-teal-400', text: 'text-teal-100' },
};
