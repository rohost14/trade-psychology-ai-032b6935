import { useEffect, useState } from "react";
import { Play, RotateCcw, Pause } from "lucide-react";

type Step = {
  id: number;
  time: string;
  action: string;
  detail: string;
  emotion: string;
  thought: string;
  delta: number; // cumulative pnl after this step
};

const STEPS: Step[] = [
  {
    id: 1,
    time: "09:21",
    action: "RELIANCE · long 50 @ 2,487",
    detail: "Stopped out −₹2,100. Within plan. You should've been done.",
    emotion: "Annoyed",
    thought: "\"Market just shook me out. Let me get it back.\"",
    delta: -2100,
  },
  {
    id: 2,
    time: "09:27",
    action: "RELIANCE · re-entry 80 @ 2,492",
    detail: "1.6× size. No setup. 6 minutes after the loss.",
    emotion: "Tilted",
    thought: "\"This one has to work. I saw the move coming.\"",
    delta: -5400,
  },
  {
    id: 3,
    time: "09:34",
    action: "RELIANCE · stop pulled, added 40",
    detail: "Original SL removed. Position doubled. Hope replaced the plan.",
    emotion: "Desperate",
    thought: "\"I can't take another loss. It'll come back.\"",
    delta: -11200,
  },
  {
    id: 4,
    time: "09:41",
    action: "Forced exit at market",
    detail: "Panic close. One bad trade became the worst day of the month.",
    emotion: "Blown out",
    thought: "\"Why do I keep doing this?\"",
    delta: -18400,
  },
];

const emotionColor = (e: string) =>
  ({
    Annoyed: "text-warning",
    Tilted: "text-warning",
    Desperate: "text-loss",
    "Blown out": "text-loss",
  }[e] ?? "text-muted-foreground");

const LossSpiralSimulator = ({ id }: { id?: string }) => {
  const [active, setActive] = useState(0); // index of current step (0..STEPS.length)
  const [playing, setPlaying] = useState(true);
  const [animatedPnl, setAnimatedPnl] = useState(0);

  // Auto-play
  useEffect(() => {
    if (!playing) return;
    const idInterval = setInterval(() => {
      setActive((a) => {
        if (a >= STEPS.length) {
          return a; // hold at end
        }
        return a + 1;
      });
    }, 2200);
    return () => clearInterval(idInterval);
  }, [playing]);

  // Animate the headline P&L toward target
  useEffect(() => {
    const target = active === 0 ? 0 : STEPS[active - 1].delta;
    const start = animatedPnl;
    const duration = 700;
    const t0 = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setAnimatedPnl(Math.round(start + (target - start) * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  const replay = () => {
    setActive(0);
    setAnimatedPnl(0);
    setPlaying(true);
  };

  const finalLoss = STEPS[STEPS.length - 1].delta;
  const pctOfDayLimit = Math.min(100, Math.abs(animatedPnl) / Math.abs(finalLoss) * 100);

  return (
    <section id={id} className="border-t border-border/60 bg-background">
      <div className="max-w-[1180px] mx-auto px-6 py-20 lg:py-28">
        <div className="grid lg:grid-cols-[1fr_1.15fr] gap-12 lg:gap-16 items-start">
          {/* Left — copy */}
          <div className="lg:sticky lg:top-24">
            <p className="text-[12px] font-medium uppercase tracking-[0.15em] text-loss mb-4">
              Why traders actually blow up
            </p>
            <h2 className="font-display text-[32px] lg:text-[44px] leading-[1.05] font-semibold text-foreground tracking-tight">
              It's never one bad trade.
              <br />
              It's the next four.
            </h2>
            <p className="mt-5 text-[16px] leading-[1.6] text-muted-foreground max-w-[480px]">
              Watch a real revenge-trading spiral play out — the kind that turns a planned −₹2,000 stop into a −₹18,400 wipeout in twenty minutes. If this feels familiar, you're not alone. It's the same loop happening to ~90% of retail traders, every single day.
            </p>
            <p className="mt-5 text-[15px] leading-[1.6] text-foreground font-medium max-w-[460px]">
              TradeMentor sits between step 1 and step 2 — and refuses to let you click.
            </p>
            <div className="mt-7 flex items-center gap-2">
              <button
                onClick={() => setPlaying((p) => !p)}
                className="inline-flex items-center gap-2 h-9 px-4 rounded-lg border border-border bg-card text-[13px] font-medium text-foreground hover:bg-muted transition-colors"
              >
                {playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                {playing ? "Pause" : "Play"}
              </button>
              <button
                onClick={replay}
                className="inline-flex items-center gap-2 h-9 px-4 rounded-lg border border-border bg-card text-[13px] font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              >
                <RotateCcw className="h-3.5 w-3.5" /> Replay
              </button>
            </div>
          </div>

          {/* Right — simulator */}
          <div className="rounded-lg border border-border bg-card overflow-hidden shadow-[0_30px_80px_-30px_hsl(226_28%_30%/0.25)]">
            {/* Headline P&L */}
            <div className="px-5 pt-5 pb-4 border-b border-border bg-loss-muted/50">
              <div className="flex items-center justify-between">
                <span className="text-[10.5px] uppercase tracking-[0.1em] font-medium text-muted-foreground">
                  Account P&L · simulated session
                </span>
                <span className="text-[10.5px] font-tabular text-muted-foreground">
                  step {Math.min(active, STEPS.length)} / {STEPS.length}
                </span>
              </div>
              <div className="mt-1.5 flex items-baseline gap-3">
                <span className="font-display text-[40px] sm:text-[48px] font-semibold tracking-tight text-loss font-tabular tabular-nums">
                  {animatedPnl === 0
                    ? "₹0"
                    : `−₹${Math.abs(animatedPnl).toLocaleString("en-IN")}`}
                </span>
                {active > 0 && (
                  <span className="text-[12px] font-tabular text-loss">
                    ▼ {((Math.abs(animatedPnl) / 50000) * 100).toFixed(2)}% of capital
                  </span>
                )}
              </div>
              <div className="mt-3 h-1.5 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full bg-loss transition-[width] duration-700 ease-out"
                  style={{ width: `${pctOfDayLimit}%` }}
                />
              </div>
              <div className="mt-1.5 flex items-center justify-between text-[10.5px] text-muted-foreground font-tabular">
                <span>Planned stop · −₹2,000</span>
                <span>Actual blow · −₹18,400</span>
              </div>
            </div>

            {/* Timeline */}
            <ol className="divide-y divide-border">
              {STEPS.map((s, i) => {
                const reached = active > i;
                const isCurrent = active === i + 1;
                return (
                  <li
                    key={s.id}
                    className={`flex gap-4 px-5 py-4 transition-all duration-500 ${
                      reached ? "opacity-100" : "opacity-30"
                    } ${isCurrent ? "bg-loss-muted/40" : ""}`}
                  >
                    <div className="shrink-0 flex flex-col items-center">
                      <div
                        className={`h-7 w-7 rounded-full flex items-center justify-center text-[11px] font-bold font-tabular border-2 transition-colors ${
                          reached
                            ? "bg-loss text-primary-foreground border-loss"
                            : "bg-muted text-muted-foreground border-border"
                        }`}
                      >
                        {s.id}
                      </div>
                      {i < STEPS.length - 1 && (
                        <div className={`w-px flex-1 mt-1 ${reached ? "bg-loss/40" : "bg-border"}`} />
                      )}
                    </div>
                    <div className="flex-1 min-w-0 pb-1">
                      <div className="flex items-baseline justify-between gap-3 flex-wrap">
                        <p className="text-[13px] font-semibold text-foreground">{s.action}</p>
                        <span className="text-[10.5px] font-tabular text-muted-foreground">{s.time}</span>
                      </div>
                      <p className="text-[12px] text-muted-foreground mt-0.5 leading-snug">{s.detail}</p>
                      {reached && (
                        <div className="mt-2 flex items-center gap-2 flex-wrap animate-fade-in">
                          <span
                            className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-[3px] bg-loss/10 ${emotionColor(
                              s.emotion,
                            )}`}
                          >
                            {s.emotion}
                          </span>
                          <span className="text-[11.5px] italic text-foreground/80">{s.thought}</span>
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
            </ol>

            {/* Footer */}
            <div className="px-5 py-4 border-t border-border bg-muted/40 flex items-center justify-between gap-3">
              <p className="text-[12px] text-muted-foreground">
                With TradeMentor, step 2 never happens.{" "}
                <span className="text-foreground font-semibold">−₹16,300 saved.</span>
              </p>
              <span className="text-[10.5px] uppercase tracking-wider text-muted-foreground font-medium">
                simulated
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default LossSpiralSimulator;
