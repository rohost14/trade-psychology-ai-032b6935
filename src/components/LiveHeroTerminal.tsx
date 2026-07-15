import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Activity, TrendingDown, Bell } from "lucide-react";
import Sparkline from "@/components/ui/Sparkline";
import FlashCell from "@/components/ui/FlashCell";
import { useTickStream, getHistory } from "@/hooks/useTickStream";

type Alert = {
  id: string;
  tone: "loss" | "warning" | "info";
  icon: typeof AlertTriangle;
  title: string;
  body: string;
  ts: number;
};

const QUEUE: Omit<Alert, "id" | "ts">[] = [
  {
    tone: "loss",
    icon: AlertTriangle,
    title: "Revenge trade detected",
    body: "3rd RELIANCE entry within 4 min after a stop-out.",
  },
  {
    tone: "warning",
    icon: Activity,
    title: "Overtrading pace",
    body: "7 trades in 22 min — 2.1× your weekly average.",
  },
  {
    tone: "warning",
    icon: TrendingDown,
    title: "Adding to a loser",
    body: "INFY position up 60%. Down 18 minutes straight.",
  },
  {
    tone: "loss",
    icon: Bell,
    title: "Stop-loss pulled",
    body: "TCS · SL removed at −₹420. Cooldown suggested.",
  },
];

const tone = (t: Alert["tone"]) =>
  t === "loss"
    ? { dot: "bg-loss", text: "text-loss", chip: "bg-loss/12", border: "border-loss/30" }
    : t === "warning"
    ? { dot: "bg-warning", text: "text-warning", chip: "bg-warning/12", border: "border-warning/30" }
    : { dot: "bg-primary", text: "text-primary", chip: "bg-primary/12", border: "border-primary/30" };

const timeAgo = (ts: number) => {
  const s = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (s < 3) return "just now";
  if (s < 60) return `${s}s ago`;
  return `${Math.floor(s / 60)}m ago`;
};

const LiveHeroTerminal = () => {
  const ticks = useTickStream();
  const [alerts, setAlerts] = useState<Alert[]>(() => [
    { ...QUEUE[0], id: "seed-0", ts: Date.now() - 1500 },
  ]);
  const idx = useRef(1);
  const [, setNow] = useState(Date.now());

  // Drip a new alert every ~5s
  useEffect(() => {
    const drip = setInterval(() => {
      const q = QUEUE[idx.current % QUEUE.length];
      setAlerts((prev) => [{ ...q, id: `a-${Date.now()}`, ts: Date.now() }, ...prev].slice(0, 3));
      idx.current += 1;
    }, 5000);
    const clock = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      clearInterval(drip);
      clearInterval(clock);
    };
  }, []);

  const nifty = ticks["NIFTY"];
  const reliance = ticks["RELIANCE"];
  const infy = ticks["INFY"];

  // Live P&L driven by ticks
  const pnl = useMemo(() => {
    const r = reliance?.changePct ?? 0;
    const i = infy?.changePct ?? 0;
    return Math.round(-1850 + r * 700 + i * 520);
  }, [reliance, infy]);

  const positions = [
    { sym: "RELIANCE", qty: 50, tick: reliance, entry: 2487.4 },
    { sym: "INFY", qty: 40, tick: infy, entry: 1521.6 },
  ];

  return (
    <div className="relative">
      {/* Terminal card */}
      <div className="rounded-2xl border border-border bg-card overflow-hidden shadow-[0_30px_80px_-30px_hsl(226_28%_30%/0.25)]">
        {/* Title bar */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-muted/40">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-loss/70" />
            <span className="h-2 w-2 rounded-full bg-warning/70" />
            <span className="h-2 w-2 rounded-full bg-profit/70" />
            <span className="ml-2 text-[11px] font-medium text-muted-foreground tracking-wide">
              tradementor · live session
            </span>
          </div>
          <span className="flex items-center gap-1.5 text-[10.5px] text-muted-foreground uppercase tracking-wider">
            <span className="h-1.5 w-1.5 rounded-full bg-profit animate-pulse" />
            streaming
          </span>
        </div>

        {/* NIFTY strip */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-border">
          <div className="flex items-baseline gap-2">
            <span className="text-[10.5px] uppercase tracking-wider text-muted-foreground font-medium">NIFTY 50</span>
            <FlashCell
              value={nifty?.last ?? 22486}
              format={(n) => n.toFixed(2)}
              className="text-[13px] font-semibold text-foreground"
            />
            <span className={`text-[11px] font-tabular ${(nifty?.changePct ?? 0) >= 0 ? "text-profit" : "text-loss"}`}>
              {(nifty?.changePct ?? 0) >= 0 ? "+" : ""}
              {(nifty?.changePct ?? 0).toFixed(2)}%
            </span>
          </div>
          <Sparkline data={getHistory("NIFTY").length ? getHistory("NIFTY") : [1, 1.2, 0.9, 1.4, 1.1, 1.5]} width={88} height={22} />
        </div>

        {/* Intraday P&L focal */}
        <div className="px-4 pt-4 pb-3">
          <div className="flex items-center justify-between">
            <span className="text-[10.5px] uppercase tracking-[0.1em] text-muted-foreground font-medium">
              Intraday P&L
            </span>
            <span className="text-[10.5px] text-muted-foreground font-tabular">2 positions · NSE</span>
          </div>
          <div className="mt-1 flex items-baseline gap-3">
            <FlashCell
              value={pnl}
              format={(n) => `${n >= 0 ? "+" : "−"}₹${Math.abs(n).toLocaleString("en-IN")}`}
              className={`font-display text-[34px] sm:text-[40px] font-semibold tracking-tight ${pnl >= 0 ? "text-profit" : "text-loss"}`}
            />
            <span className={`text-[12px] font-tabular ${pnl >= 0 ? "text-profit" : "text-loss"}`}>
              {pnl >= 0 ? "▲" : "▼"} {Math.abs((pnl / 1850) * 100).toFixed(1)}%
            </span>
          </div>
          <div className="mt-1 text-[11px] text-muted-foreground">
            Down day · 4 of last 5 entries flagged behaviorally.
          </div>
        </div>

        {/* Positions table */}
        <div className="border-t border-border">
          <div className="grid grid-cols-[1fr_56px_82px_70px] px-4 py-1.5 text-[10px] uppercase tracking-wider text-muted-foreground font-medium border-b border-border">
            <span>Position</span>
            <span className="text-right">Qty</span>
            <span className="text-right">LTP</span>
            <span className="text-right">P&L</span>
          </div>
          {positions.map((p) => {
            const ltp = p.tick?.last ?? p.entry;
            const pl = (ltp - p.entry) * p.qty;
            const up = pl >= 0;
            const hist = getHistory(p.sym);
            return (
              <div
                key={p.sym}
                className="grid grid-cols-[1fr_56px_82px_70px] items-center gap-2 px-4 py-2 border-b border-border last:border-b-0 text-[12px]"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <Sparkline data={hist.length ? hist : [1, 1.1, 0.95, 1.2]} width={36} height={16} />
                  <span className="font-semibold text-foreground truncate">{p.sym}</span>
                </div>
                <span className="text-right font-tabular text-muted-foreground">{p.qty}</span>
                <FlashCell value={ltp} format={(n) => n.toFixed(2)} className="text-right text-foreground" />
                <FlashCell
                  value={pl}
                  format={(n) => `${n >= 0 ? "+" : "−"}₹${Math.abs(Math.round(n)).toLocaleString("en-IN")}`}
                  className={`text-right font-semibold ${up ? "text-profit" : "text-loss"}`}
                />
              </div>
            );
          })}
        </div>

        {/* Alert stream */}
        <div className="border-t border-border bg-muted/30 px-3 py-3 space-y-2 min-h-[170px]">
          {alerts.map((a, i) => {
            const t = tone(a.tone);
            const Icon = a.icon;
            const isNew = Date.now() - a.ts < 600;
            return (
              <div
                key={a.id}
                className={`flex items-start gap-2.5 rounded-lg border ${t.border} bg-card px-3 py-2.5 ${
                  isNew ? "animate-fade-in" : ""
                } ${i === 0 ? "shadow-[0_4px_14px_-6px_hsl(var(--loss)/0.35)]" : "opacity-90"}`}
              >
                <div className={`h-7 w-7 rounded-md ${t.chip} ${t.text} flex items-center justify-center shrink-0`}>
                  <Icon className="h-3.5 w-3.5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-2">
                    <p className={`text-[12.5px] font-semibold ${t.text}`}>{a.title}</p>
                    <span className="text-[10.5px] text-muted-foreground font-tabular shrink-0">
                      {timeAgo(a.ts)}
                    </span>
                  </div>
                  <p className="text-[11.5px] text-muted-foreground mt-0.5 leading-snug">{a.body}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Floating "saved" pill */}
      <div className="hidden sm:flex absolute -right-4 -bottom-5 items-center gap-3 bg-background border border-border rounded-xl px-4 py-2.5 shadow-[0_18px_50px_-20px_hsl(226_28%_30%/0.35)]">
        <div className="h-8 w-8 rounded-lg bg-profit/12 text-profit flex items-center justify-center">
          <Bell className="h-4 w-4" />
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
            Cooldown enforced
          </p>
          <p className="text-[13px] font-semibold text-profit font-tabular">+₹6,400 protected</p>
        </div>
      </div>
    </div>
  );
};

export default LiveHeroTerminal;
