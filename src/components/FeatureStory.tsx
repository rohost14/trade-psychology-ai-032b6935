import * as React from "react";
import { Check, AlertTriangle, Activity, TrendingDown, Eye, Shield, Brain } from "lucide-react";

export type Story = {
  eyebrow: string;
  title: string;
  body: string;
  bullets: string[];
  reverse?: boolean;
  visual: React.ReactNode;
};

export const FeatureStory = ({ story, id }: { story: Story; id?: string }) => (
  <section id={id} className="border-t border-border/60">
    <div className="max-w-[1180px] mx-auto px-6 py-20 lg:py-28">
      <div className={`grid lg:grid-cols-2 gap-12 lg:gap-16 items-center ${story.reverse ? "lg:[&>*:first-child]:order-2" : ""}`}>
        <div>
          <p className="text-[12px] font-medium uppercase tracking-[0.15em] text-primary mb-4">{story.eyebrow}</p>
          <h2 className="font-display text-[32px] lg:text-[44px] leading-[1.08] font-semibold text-foreground tracking-tight">
            {story.title}
          </h2>
          <p className="mt-5 text-[16px] leading-[1.6] text-muted-foreground max-w-[480px]">{story.body}</p>
          <ul className="mt-7 space-y-3">
            {story.bullets.map((b) => (
              <li key={b} className="flex items-start gap-2.5 text-[14.5px] text-foreground">
                <Check className="h-4 w-4 text-primary mt-0.5 shrink-0" strokeWidth={2.5} />
                <span>{b}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>{story.visual}</div>
      </div>
    </div>
  </section>
);

/* Visual: Alert feed mock */
export const AlertFeedMock = () => (
  <div className="relative rounded-2xl border border-border bg-card p-5 lg:p-6 shadow-sm">
    <div className="flex items-center justify-between mb-4">
      <span className="text-[13px] font-semibold text-foreground">Live behavioral feed</span>
      <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
        <span className="h-1.5 w-1.5 rounded-full bg-profit animate-pulse" />
        Watching
      </span>
    </div>
    <div className="space-y-2.5">
      {[
        { icon: AlertTriangle, color: "loss", title: "Revenge trade detected", note: "3rd entry on RELIANCE within 4 min after loss", time: "14:32", tint: true },
        { icon: Activity, color: "warning", title: "Overtrading pace", note: "7 trades · 2× your weekly average", time: "13:10" },
        { icon: TrendingDown, color: "warning", title: "Adding to a loser", note: "Position size up 60% on INFY (red 18min)", time: "12:47" },
        { icon: Eye, color: "muted", title: "Rule break: stop-loss removed", note: "TCS · stop pulled at −₹420", time: "11:48" },
      ].map((a, i) => {
        const Icon = a.icon;
        return (
          <div
            key={i}
            className={`flex items-start gap-3 rounded-lg px-3 py-3 ${a.tint ? "bg-loss/10 border border-loss/20" : "bg-muted/40"}`}
          >
            <div className={`h-7 w-7 rounded-md flex items-center justify-center shrink-0 ${a.color === "loss" ? "bg-loss/15 text-loss" : a.color === "warning" ? "bg-warning/15 text-warning" : "bg-muted text-muted-foreground"}`}>
              <Icon className="h-3.5 w-3.5" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <p className={`text-[13px] font-semibold ${a.color === "loss" ? "text-loss" : "text-foreground"}`}>{a.title}</p>
                <span className="text-[11px] text-muted-foreground font-mono shrink-0">{a.time}</span>
              </div>
              <p className="text-[12px] text-muted-foreground mt-0.5 leading-snug">{a.note}</p>
            </div>
          </div>
        );
      })}
    </div>
  </div>
);

/* Visual: Shield circuit breaker mock */
export const ShieldMock = () => (
  <div className="relative rounded-2xl border border-border bg-card p-5 lg:p-6 shadow-sm overflow-hidden">
    <div className="flex items-center justify-between mb-4">
      <span className="text-[13px] font-semibold text-foreground flex items-center gap-1.5">
        <Shield className="h-4 w-4 text-loss" />
        Blowup Shield
      </span>
      <span className="text-[10px] uppercase tracking-wider text-loss font-bold bg-loss/10 px-2 py-0.5 rounded">Active</span>
    </div>
    <div className="space-y-4">
      <div className="p-4 bg-muted/40 rounded-xl border border-border flex items-center justify-between">
        <div>
          <h4 className="text-sm font-semibold text-foreground">Daily Loss Limit</h4>
          <p className="text-xs text-muted-foreground mt-0.5">Threshold: −₹10,000</p>
        </div>
        <span className="text-sm font-mono text-loss font-bold">−₹9,820 hit</span>
      </div>
      <div className="p-4 bg-loss/5 rounded-xl border border-loss/20">
        <h4 className="text-xs font-semibold text-loss uppercase tracking-wider">Accountability Dispatch</h4>
        <p className="text-[12.5px] text-muted-foreground mt-1 leading-snug">
          "Rahul has crossed daily risk threshold. Cooldown period suggested."
        </p>
        <div className="mt-3 flex items-center gap-2 text-xs text-profit font-medium">
          <span className="h-1.5 w-1.5 rounded-full bg-profit animate-pulse" />
          WhatsApp alert sent to partner
        </div>
      </div>
    </div>
  </div>
);

/* Visual: Coach psychology mock */
export const CoachMock = () => (
  <div className="relative rounded-2xl border border-border bg-card p-5 lg:p-6 shadow-sm">
    <div className="flex items-center justify-between mb-4">
      <span className="text-[13px] font-semibold text-foreground flex items-center gap-1.5">
        <Brain className="h-4 w-4 text-primary" />
        AI Psychology Mirror
      </span>
      <span className="text-[11px] text-muted-foreground font-mono">Friday analysis</span>
    </div>
    <div className="space-y-3">
      <div className="p-4 bg-muted/40 rounded-xl border border-border">
        <p className="text-[13px] text-muted-foreground italic">"Why did I lose ₹14,000 on RELIANCE today?"</p>
      </div>
      <div className="p-4 bg-primary/5 rounded-xl border border-primary/20">
        <p className="text-[12.5px] text-foreground leading-relaxed">
          <strong>Coach:</strong> You entered RELIANCE 3 times within 8 minutes of a stop-out. Historical analysis shows your win rate drops to <strong>14%</strong> on such quick re-entries, costing you an average of <strong>₹8,400 per incident</strong>. You are trying to force a recovery rather than executing a setup.
        </p>
      </div>
    </div>
  </div>
);
