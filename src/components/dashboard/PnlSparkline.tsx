import { CompletedTrade } from '@/types/api';

export function PnlSparkline({ closed, unrealized, positive }: {
  closed: CompletedTrade[];
  unrealized: number;
  positive: boolean;
}) {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const todayTrades = closed.filter(t => new Date(t.exit_time) >= today);

  const points: number[] = [0];
  let cum = 0;
  for (const t of todayTrades) { cum += t.realized_pnl; points.push(cum); }
  points.push(cum + unrealized);

  if (points.length < 2) {
    return <div className="flex-1 flex items-center justify-center text-[11px] text-muted-foreground/50">No data yet</div>;
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const W = 200; const H = 72;
  const toX = (i: number) => (i / (points.length - 1)) * W;
  const toY = (v: number) => H - ((v - min) / range) * (H * 0.85) - H * 0.075;
  const zeroY = toY(0);

  const linePath = points.map((v, i) => `${i === 0 ? 'M' : 'L'}${toX(i).toFixed(1)},${toY(v).toFixed(1)}`).join(' ');
  const areaPath = `${linePath} L${W},${zeroY.toFixed(1)} L0,${zeroY.toFixed(1)} Z`;

  const lineColor = positive ? 'var(--tm-profit, #16A34A)' : 'var(--tm-loss, #DC2626)';
  const gradId = `spk-${positive ? 'p' : 'l'}`;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="flex-1 w-full">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={lineColor} stopOpacity="0.18" />
          <stop offset="100%" stopColor={lineColor} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <line x1="0" y1={zeroY} x2={W} y2={zeroY} stroke="currentColor" strokeOpacity="0.12" strokeWidth="1" strokeDasharray="3 3" className="text-muted-foreground" />
      <path d={areaPath} fill={`url(#${gradId})`} />
      <path d={linePath} fill="none" stroke={lineColor} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={toX(points.length - 1)} cy={toY(points[points.length - 1])} r="3" fill={lineColor} />
    </svg>
  );
}
