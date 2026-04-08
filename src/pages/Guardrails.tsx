import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Shield, Plus, Trash2, Pause, Play, Bell, BellOff,
  AlertTriangle, CheckCircle2, Clock, TrendingDown, TrendingUp, Info
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import api, { apiDetailString } from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────────────

interface GuardrailRule {
  id: string;
  name: string;
  target_symbols: string[] | null;
  condition_type: "loss_threshold" | "loss_range_time" | "total_pnl_drop" | "profit_target";
  condition_value: number;
  notify_whatsapp: boolean;
  notify_push: boolean;
  status: "active" | "paused" | "triggered";
  triggered_at: string | null;
  trigger_count: number;
  expires_at: string | null;
  is_expired: boolean;
}

const CONDITION_META = {
  loss_threshold: {
    label: "Position Loss Limit",
    icon: TrendingDown,
    description: "Alert when a position's unrealized loss exceeds a threshold",
    placeholder: "e.g. -5000",
    suffix: "₹",
    hint: "Enter negative amount (e.g. -5000 = alert if loss > ₹5,000)",
  },
  loss_range_time: {
    label: "Continuous Loss Duration",
    icon: Clock,
    description: "Alert when a position stays in loss for more than N minutes",
    placeholder: "e.g. 30",
    suffix: "min",
    hint: "Enter minutes (e.g. 30 = alert if losing for 30+ minutes continuously)",
  },
  total_pnl_drop: {
    label: "Portfolio P&L Floor",
    icon: AlertTriangle,
    description: "Alert when your total open P&L drops below a level",
    placeholder: "e.g. -10000",
    suffix: "₹",
    hint: "Enter negative amount (e.g. -10000 = alert when portfolio hits -₹10,000)",
  },
  profit_target: {
    label: "Profit Target Reached",
    icon: TrendingUp,
    description: "Alert when a position's unrealized profit hits your target",
    placeholder: "e.g. 8000",
    suffix: "₹",
    hint: "Enter positive amount (e.g. 8000 = alert when profit reaches ₹8,000)",
  },
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function conditionLabel(rule: GuardrailRule): string {
  const val = Math.abs(rule.condition_value);
  switch (rule.condition_type) {
    case "loss_threshold":
      return `Alert if loss exceeds ₹${val.toLocaleString("en-IN")}`;
    case "loss_range_time":
      return `Alert if in loss for ${val} min`;
    case "total_pnl_drop":
      return `Alert if portfolio hits -₹${val.toLocaleString("en-IN")}`;
    case "profit_target":
      return `Alert when profit reaches ₹${val.toLocaleString("en-IN")}`;
  }
}

function statusBadge(rule: GuardrailRule) {
  if (rule.is_expired)
    return <span className="text-[10px] font-medium px-1.5 py-0.5 rounded border border-border text-muted-foreground">Expired</span>;
  if (rule.status === "triggered")
    return <span className="text-[10px] font-medium px-1.5 py-0.5 rounded border border-tm-brand/20 bg-teal-50/50 dark:bg-teal-900/10 text-tm-brand">Triggered</span>;
  if (rule.status === "paused")
    return <span className="text-[10px] font-medium px-1.5 py-0.5 rounded border border-tm-obs/20 bg-amber-50/50 dark:bg-amber-900/10 text-tm-obs">Paused</span>;
  return <span className="text-[10px] font-medium px-1.5 py-0.5 rounded border border-tm-profit/20 bg-teal-50/50 dark:bg-teal-900/10 text-tm-profit">Active</span>;
}

// ── Add Rule Dialog ──────────────────────────────────────────────────────────

function AddRuleDialog({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [conditionType, setConditionType] = useState<keyof typeof CONDITION_META>("loss_threshold");
  const [conditionValue, setConditionValue] = useState("");
  const [targetSymbols, setTargetSymbols] = useState("");
  const [notifyWhatsapp, setNotifyWhatsapp] = useState(true);
  const [notifyPush, setNotifyPush] = useState(true);
  const { toast } = useToast();

  const meta = CONDITION_META[conditionType];

  const mutation = useMutation({
    mutationFn: async () => {
      const symbols = targetSymbols.trim()
        ? targetSymbols.split(",").map(s => s.trim().toUpperCase()).filter(Boolean)
        : null;
      await api.post("/api/guardrails/", {
        name: name.trim(),
        condition_type: conditionType,
        condition_value: parseFloat(conditionValue),
        target_symbols: symbols,
        notify_whatsapp: notifyWhatsapp,
        notify_push: notifyPush,
      });
    },
    onSuccess: () => {
      toast({ title: "Guardrail created", description: "Rule is now active." });
      setOpen(false);
      setName("");
      setConditionValue("");
      setTargetSymbols("");
      onCreated();
    },
    onError: (e: any) => {
      toast({
        title: "Failed to create rule",
        description: apiDetailString(e.response?.data?.detail, "Please check your inputs."),
        variant: "destructive",
      });
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" className="gap-2 bg-tm-brand hover:bg-tm-brand/90 text-white">
          <Plus className="h-4 w-4" /> Add Rule
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>New Guardrail Rule</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          {/* Name */}
          <div className="space-y-1.5">
            <Label>Rule Name</Label>
            <Input
              placeholder="e.g. Protect NIFTY trade"
              value={name}
              onChange={e => setName(e.target.value)}
            />
          </div>

          {/* Condition type */}
          <div className="space-y-1.5">
            <Label>Condition</Label>
            <Select value={conditionType} onValueChange={(v: any) => setConditionType(v)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(CONDITION_META).map(([key, m]) => (
                  <SelectItem key={key} value={key}>
                    <div className="flex items-center gap-2">
                      <m.icon className="h-3.5 w-3.5" />
                      {m.label}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">{meta.description}</p>
          </div>

          {/* Value */}
          <div className="space-y-1.5">
            <Label>Threshold ({meta.suffix})</Label>
            <Input
              type="number"
              placeholder={meta.placeholder}
              value={conditionValue}
              onChange={e => setConditionValue(e.target.value)}
            />
            <p className="text-xs text-muted-foreground flex gap-1">
              <Info className="h-3 w-3 mt-0.5 shrink-0" /> {meta.hint}
            </p>
          </div>

          {/* Target symbols */}
          <div className="space-y-1.5">
            <Label>Target Symbols <span className="text-muted-foreground">(optional)</span></Label>
            <Input
              placeholder="e.g. NIFTY24D19500PE, BANKNIFTY... (blank = all)"
              value={targetSymbols}
              onChange={e => setTargetSymbols(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Leave blank to watch all open positions
            </p>
          </div>

          {/* Notifications */}
          <div className="space-y-2 rounded-lg border p-3">
            <p className="text-sm font-medium">Notify via</p>
            <div className="flex items-center justify-between">
              <Label className="font-normal">WhatsApp</Label>
              <Switch checked={notifyWhatsapp} onCheckedChange={setNotifyWhatsapp} />
            </div>
            <div className="flex items-center justify-between">
              <Label className="font-normal">Push Notification</Label>
              <Switch checked={notifyPush} onCheckedChange={setNotifyPush} />
            </div>
          </div>

          <Button
            className="w-full bg-tm-brand hover:bg-tm-brand/90 text-white"
            disabled={!name.trim() || !conditionValue || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? "Creating..." : "Create Rule"}
          </Button>

        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Rule Card ────────────────────────────────────────────────────────────────

function RuleCard({ rule, onRefresh }: { rule: GuardrailRule; onRefresh: () => void }) {
  const { toast } = useToast();
  const meta = CONDITION_META[rule.condition_type];
  const Icon = meta.icon;

  const pauseMutation = useMutation({
    mutationFn: () => api.patch(`/api/guardrails/${rule.id}/pause`),
    onSuccess: onRefresh,
    onError: () => toast({ title: "Failed", variant: "destructive" }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.delete(`/api/guardrails/${rule.id}`),
    onSuccess: () => { toast({ title: "Rule deleted" }); onRefresh(); },
    onError: () => toast({ title: "Failed to delete", variant: "destructive" }),
  });

  const isInactive = rule.status === "triggered" || rule.is_expired;

  return (
    <div className={`tm-card overflow-hidden p-4 ${isInactive ? "opacity-60" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <div className="mt-0.5 rounded-lg bg-muted p-2 shrink-0">
            <Icon className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium text-sm">{rule.name}</span>
              {statusBadge(rule)}
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              {conditionLabel(rule)}
            </p>
            {rule.target_symbols?.length ? (
              <p className="text-xs text-muted-foreground">
                Watching: {rule.target_symbols.join(", ")}
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">Watching all open positions</p>
            )}
            <div className="flex gap-2 mt-1">
              {rule.notify_whatsapp ? (
                <span className="text-[10px] text-tm-profit flex items-center gap-0.5">
                  <Bell className="h-2.5 w-2.5" /> WhatsApp
                </span>
              ) : null}
              {rule.notify_push ? (
                <span className="text-[10px] text-tm-brand flex items-center gap-0.5">
                  <Bell className="h-2.5 w-2.5" /> Push
                </span>
              ) : null}
            </div>
            {rule.triggered_at && (
              <p className="text-[10px] text-muted-foreground mt-1">
                Triggered at {new Date(rule.triggered_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })} IST
              </p>
            )}
          </div>
        </div>

        {!isInactive && (
          <div className="flex gap-1 shrink-0">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              title={rule.status === "paused" ? "Resume" : "Pause"}
              disabled={pauseMutation.isPending}
              onClick={() => pauseMutation.mutate()}
            >
              {rule.status === "paused" ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-tm-loss hover:text-tm-loss"
              title="Delete"
              disabled={deleteMutation.isPending}
              onClick={() => deleteMutation.mutate()}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function Guardrails() {
  const queryClient = useQueryClient();

  const { data: rules = [], isLoading } = useQuery<GuardrailRule[]>({
    queryKey: ["guardrails"],
    queryFn: async () => {
      const r = await api.get("/api/guardrails/");
      return r.data;
    },
    refetchInterval: 30_000, // Refresh every 30s to see triggered state
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["guardrails"] });

  const active = rules.filter(r => r.status === "active" && !r.is_expired);
  const paused = rules.filter(r => r.status === "paused" && !r.is_expired);
  const done = rules.filter(r => r.status === "triggered" || r.is_expired);

  return (
    <div className="px-4 sm:px-6 py-6 max-w-2xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Position Guardrails</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Alert rules on your open positions. Fire once, never repeat.
          </p>
        </div>
        <AddRuleDialog onCreated={refresh} />
      </div>

      {/* Info banner */}
      <div className="rounded-lg border border-tm-brand/20 bg-teal-50/40 dark:bg-teal-900/10 px-4 py-3 text-sm text-muted-foreground flex gap-2">
        <Info className="h-4 w-4 mt-0.5 shrink-0 text-tm-brand" />
        <span>
          Rules expire at <strong className="text-foreground">15:30 IST</strong> daily. Each rule fires once — create a new one
          the next day. No automatic order execution — you act manually.
        </span>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map(i => <Skeleton key={i} className="h-24 w-full rounded-lg" />)}
        </div>
      ) : rules.length === 0 ? (
        <div className="tm-card overflow-hidden">
          <div className="py-12 text-center px-5">
            <Shield className="h-10 w-10 mx-auto text-muted-foreground/40 mb-3" />
            <p className="text-sm font-medium">No guardrail rules yet</p>
            <p className="text-sm text-muted-foreground mt-1">
              Add rules before market opens to protect your positions.
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Active */}
          {active.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
                Active ({active.length})
              </h2>
              {active.map(r => <RuleCard key={r.id} rule={r} onRefresh={refresh} />)}
            </section>
          )}

          {/* Paused */}
          {paused.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
                Paused ({paused.length})
              </h2>
              {paused.map(r => <RuleCard key={r.id} rule={r} onRefresh={refresh} />)}
            </section>
          )}

          {/* Triggered / Expired */}
          {done.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
                Completed Today ({done.length})
              </h2>
              {done.map(r => <RuleCard key={r.id} rule={r} onRefresh={refresh} />)}
            </section>
          )}
        </div>
      )}
    </div>
  );
}
