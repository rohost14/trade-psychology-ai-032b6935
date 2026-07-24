/**
 * Post-import recap — the "aha" after a tradebook import. Reuses the habits summary
 * (computed from the freshly-built completed trades) to show a one-screen recap.
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, TrendingUp, Clock, Trophy, CalendarRange } from 'lucide-react';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';

interface Summary {
  total_trades: number; gross_pnl: number; win_rate: number;
  date_from: string | null; date_to: string | null;
  worst_hour: string | null; best_instrument: string | null; worst_instrument: string | null;
}

const inr = (n: number) => (n < 0 ? '-' : '') + '₹' + Math.abs(Math.round(n)).toLocaleString('en-IN');
const d = (iso: string | null) => iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: '2-digit' }) : '—';

export default function ImportRecap({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const [s, setS] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/api/analytics/habits?days=3650')
      .then(res => setS(res.data?.summary ?? null))
      .catch(() => setS(null))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <div className="text-center">
        <div className="w-12 h-12 rounded-full bg-tm-profit/10 flex items-center justify-center mx-auto mb-2">
          <CheckCircle2 className="h-6 w-6 text-tm-profit" />
        </div>
        <h3 className="text-base font-semibold text-foreground">History imported — here's what we found</h3>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground text-center py-6">Crunching your trades…</p>
      ) : !s ? (
        <p className="text-sm text-muted-foreground text-center py-6">Your analytics are ready. Open Analytics to explore.</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3">
            <Stat icon={TrendingUp} label="Trades" value={s.total_trades.toLocaleString('en-IN')} />
            <Stat icon={Trophy} label="Win rate" value={`${s.win_rate}%`} />
            <Stat icon={CalendarRange} label="Period" value={`${d(s.date_from)} → ${d(s.date_to)}`} small />
            <Stat icon={TrendingUp} label="Gross P&L (raw)" value={inr(s.gross_pnl)} valueClass={s.gross_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss'} />
          </div>

          <div className="rounded-lg border border-border bg-muted/30 px-4 py-3 space-y-1.5 text-[13px]">
            {s.best_instrument && <p className="text-muted-foreground">Your strongest instrument: <span className="text-foreground font-medium">{s.best_instrument}</span></p>}
            {s.worst_instrument && s.worst_instrument !== s.best_instrument && <p className="text-muted-foreground">Where it leaks most: <span className="text-foreground font-medium">{s.worst_instrument}</span></p>}
            {s.worst_hour && <p className="text-muted-foreground flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /> Your weakest hour is around <span className="text-foreground font-medium">{s.worst_hour}</span></p>}
          </div>
        </>
      )}

      <div className="flex gap-2.5 justify-end pt-1">
        <Button variant="ghost" onClick={onClose}>Done</Button>
        <Button onClick={() => { onClose(); navigate('/analytics'); }}>Explore my analytics</Button>
      </div>
    </div>
  );
}

function Stat({ icon: Icon, label, value, small, valueClass }: { icon: React.ElementType; label: string; value: string; small?: boolean; valueClass?: string }) {
  return (
    <div className="tm-card p-3.5">
      <p className="text-[11px] text-muted-foreground uppercase tracking-wide flex items-center gap-1.5 mb-1"><Icon className="h-3 w-3" /> {label}</p>
      <p className={`${small ? 'text-[13px]' : 'text-xl'} font-bold tabular-nums text-foreground ${valueClass ?? ''}`}>{value}</p>
    </div>
  );
}
