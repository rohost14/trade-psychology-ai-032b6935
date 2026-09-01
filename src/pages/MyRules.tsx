import { useCallback, useEffect, useState } from 'react';
import { Scale, Pencil, X, Check, History, ShieldAlert, Clock, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useApiQuery } from '@/hooks/useApiQuery';
import ErrorState from '@/components/ErrorState';
import EnforcedRules from '@/components/rules/EnforcedRules';
import RuleSuggestions from '@/components/rules/RuleSuggestions';
import { formatCurrency } from '@/lib/formatters';
import { cn } from '@/lib/utils';

interface Rules {
  daily_loss_limit: number | null;
  per_trade_loss_limit: number | null;
  daily_trade_limit: number | null;
  max_position_size: number | null;
  cooldown_after_loss: number | null;
  max_consecutive_losses: number | null;
  restricted_windows: string[];
}

interface StatusRow {
  rule: string;
  current?: number;
  limit?: number | null;
  ratio?: number | null;
  active?: boolean;
  remaining_min?: number;
  limit_min?: number | null;
  windows?: string[];
}

interface Violation {
  rule: string | null;
  severity: string;
  message: string;
  detected_at: string | null;
}

interface HistoryRow {
  changed_at: string | null;
  change_type: string;
  changes: Record<string, { old: unknown; new: unknown }>;
  effective_at: string | null;
  during_market_hours: boolean;
  override: boolean;
}

interface ConstitutionResponse {
  rules: Rules | null;
  pending: Record<string, unknown> | null;
  accepted_at: string | null;
}

interface ViolationsResponse {
  today: Violation[];
  total: number;
  by_rule: Record<string, number>;
}

const RULE_LABELS: Record<string, string> = {
  daily_loss: 'Daily loss limit',
  daily_loss_limit: 'Daily loss limit',
  per_trade_loss_limit: 'Per-trade loss limit',
  daily_trades: 'Max trades per day',
  daily_trade_limit: 'Max trades per day',
  max_consecutive_losses: 'Stop after consecutive losses',
  cooldown: 'Cooldown after a loss',
  cooldown_after_loss: 'Cooldown after a loss',
  max_trade_risk: 'Max risk per trade',
  max_position_size: 'Max risk per trade',
  restricted_window: 'No-trade window',
  restricted_windows: 'No-trade windows',
};

function ratioColor(ratio: number | null | undefined): string {
  if (ratio == null) return 'bg-muted';
  if (ratio >= 1) return 'bg-tm-loss';
  if (ratio >= 0.8) return 'bg-tm-obs';
  return 'bg-tm-profit';
}

export default function MyRules() {
  // Four independent reads, cached and deduped. Previously one Promise.all behind
  // eight useState calls: any single failure blanked the whole page, and leaving
  // and returning re-ran all four.
  const constitution = useApiQuery<ConstitutionResponse>(['constitution'], '/api/constitution/');
  const statusQ = useApiQuery<{ status: StatusRow[] }>(['constitution', 'status'], '/api/constitution/status');
  const violationsQ = useApiQuery<ViolationsResponse>(
    ['constitution', 'violations'], '/api/constitution/violations', { params: { days: 30 } },
  );
  const historyQ = useApiQuery<{ history: HistoryRow[] }>(
    ['constitution', 'history'], '/api/constitution/history', { params: { limit: 20 } },
  );

  const rules = constitution.data?.rules ?? null;
  const pending = constitution.data?.pending ?? null;
  const acceptedAt = constitution.data?.accepted_at ?? null;
  const status = statusQ.data?.status ?? [];
  const violationsToday = violationsQ.data?.today ?? [];
  const violations30d = violationsQ.data?.total ?? 0;
  const byRule = violationsQ.data?.by_rule ?? {};
  const history = historyQ.data?.history ?? [];

  // Only the constitution itself gates the page. The other three enrich it, and a
  // failed violations feed should not hide the rules a trader came here to read.
  const isLoading = constitution.isPending;
  const loadError = constitution.error;

  // All four queries are keyed under 'constitution', so one invalidation refreshes
  // the set. Calling .refetch() on each would work too, but the query objects are
  // new every render, which makes any useCallback around them pointless.
  const queryClient = useQueryClient();
  const load = useCallback(
    () => { queryClient.invalidateQueries({ queryKey: ['constitution'] }); },
    [queryClient],
  );

  // Edit state
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Partial<Rules>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [overrideFields, setOverrideFields] = useState<string[] | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  const startEdit = () => {
    if (!rules) return;
    setDraft({ ...rules });
    setEditing(true);
  };

  const save = async (overrideConfirmed = false) => {
    setIsSaving(true);
    try {
      const payload: Record<string, unknown> = { ...draft, override_confirmed: overrideConfirmed };
      const res = await api.put('/api/constitution/', payload);
      const outcome = res.data;
      if (outcome.pending && Object.keys(outcome.pending).length > 0) {
        toast.info('Relaxed rules queued. They take effect next session, after market close.');
      } else if (outcome.change_type === 'tighten') {
        toast.success('Rules tightened. Effective immediately.');
      } else if (outcome.change_type !== 'none') {
        toast.success('Rules updated.');
      } else {
        // NO SILENT SUCCESS. Before 2026-09-02 a save that changed nothing fell
        // through this chain without a word - which is how "clear a rule" looked
        // like it worked while the API was dropping the null.
        toast.info('No changes to save.');
      }
      setEditing(false);
      setOverrideFields(null);
      await load();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (err?.response?.status === 409 && detail?.code === 'override_required') {
        setOverrideFields(detail.loosening_fields || []);
      } else {
        toast.error('Failed to update rules.');
      }
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto space-y-4 pb-12">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 rounded-lg" />
        <Skeleton className="h-40 rounded-lg" />
      </div>
    );
  }

  // A failed request and "you have no rules yet" are different situations with
  // different fixes. These used to share one message that told the user to
  // complete onboarding — so a 500 sent an already-onboarded trader off to redo
  // setup they had finished, while their real rules sat safe on the server.
  if (loadError) {
    return (
      <div className="max-w-3xl mx-auto pb-12">
        <ErrorState
          error={loadError}
          onRetry={load}
          message="We couldn't load your rules. They're still saved and the engine is still enforcing them — this is only a display problem."
        />
      </div>
    );
  }

  if (!rules) {
    return (
      <div className="max-w-3xl mx-auto pb-12">
        <div className="tm-card overflow-hidden p-8 text-center">
          <Scale className="h-8 w-8 mx-auto text-muted-foreground mb-3" />
          <p className="text-sm font-medium text-foreground">No rules set yet</p>
          <p className="text-[13px] text-muted-foreground mt-1 max-w-sm mx-auto">
            Your trading constitution is created during onboarding. Complete it and your
            limits will appear here.
          </p>
        </div>
      </div>
    );
  }

  const numericStatus = status.filter(s => ['daily_loss', 'daily_trades', 'max_consecutive_losses'].includes(s.rule));
  const cooldownStatus = status.find(s => s.rule === 'cooldown');
  const windowStatus = status.find(s => s.rule === 'restricted_windows');

  return (
    <div className="max-w-3xl mx-auto space-y-5 pb-12">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="t-heading-lg text-foreground">My Rules</h1>
          <p className="text-sm text-muted-foreground">
            Your trading constitution. You wrote these rules. The system holds you to them.
          </p>
        </div>
        {!editing && (
          <Button variant="outline" size="sm" onClick={startEdit}>
            <Pencil className="h-3.5 w-3.5 mr-1.5" />
            Edit rules
          </Button>
        )}
      </div>

      {/* Pending loosening banner */}
      {pending && Object.keys(pending).filter(k => !k.startsWith('_')).length > 0 && (
        <div className="flex items-start gap-2.5 rounded-lg border border-tm-obs/30 bg-tm-obs/10 px-4 py-3">
          <Clock className="h-4 w-4 text-tm-obs mt-0.5 shrink-0" />
          <p className="text-sm text-tm-obs">
            Relaxed rules pending. They apply next session:
            {' '}
            <span className="font-medium">
              {Object.entries(pending)
                .filter(([k]) => !k.startsWith('_'))
                .map(([k, v]) => `${RULE_LABELS[k] || k}: ${String(v)}`)
                .join(' · ')}
            </span>
          </p>
        </div>
      )}

      <EnforcedRules status={status} />

      <RuleSuggestions />

      {/* Violations */}
      <div className="tm-card overflow-hidden">
        <div className="px-5 py-3.5 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-tm-loss" />
            Rule violations
          </h2>
          <span className="text-[11px] text-muted-foreground">{violations30d} in last 30 days</span>
        </div>
        <div className="p-5">
          {violationsToday.length === 0 ? (
            <p className="text-sm text-muted-foreground flex items-center gap-2">
              <Check className="h-4 w-4 text-tm-profit" />
              No violations today. Rules held.
            </p>
          ) : (
            <ul className="space-y-2.5">
              {violationsToday.map((v, i) => (
                <li key={i} className="flex items-start gap-2.5">
                  <span className={cn(
                    'mt-1 h-2 w-2 rounded-full shrink-0',
                    v.severity === 'critical' ? 'bg-tm-loss' :
                    v.severity === 'danger' ? 'bg-tm-loss/70' : 'bg-tm-obs'
                  )} />
                  <div className="min-w-0">
                    <p className="text-sm text-foreground">{v.message}</p>
                    <p className="text-[11px] text-muted-foreground">
                      {RULE_LABELS[v.rule || ''] || v.rule}
                      {v.detected_at && ' · ' + new Date(v.detected_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
          {Object.keys(byRule).length > 0 && (
            <div className="mt-4 pt-4 border-t border-border flex flex-wrap gap-2">
              {Object.entries(byRule).map(([rule, count]) => (
                <span key={rule} className="text-[11px] px-2 py-1 rounded-md bg-muted text-muted-foreground">
                  {RULE_LABELS[rule] || rule}: {count}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* History */}
      <div className="tm-card overflow-hidden">
        <button
          onClick={() => setShowHistory(h => !h)}
          className="w-full px-5 py-3.5 flex items-center justify-between hover:bg-muted/60 transition-colors"
        >
          <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <History className="h-4 w-4 text-muted-foreground" />
            Rule history
          </h2>
          <span className="text-[11px] text-muted-foreground">{history.length} changes</span>
        </button>
        {showHistory && (
          <div className="px-5 pb-5 pt-1 border-t border-border">
            {history.length === 0 ? (
              <p className="text-sm text-muted-foreground pt-3">No changes yet.</p>
            ) : (
              <ul className="space-y-3 pt-3">
                {history.map((h, i) => (
                  <li key={i} className="text-sm">
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        'text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded',
                        h.change_type === 'tighten' ? 'bg-tm-profit/10 text-tm-profit' :
                        h.change_type === 'loosen' ? 'bg-tm-loss/10 text-tm-loss' :
                        'bg-muted text-muted-foreground'
                      )}>
                        {h.change_type}
                      </span>
                      <span className="text-[11px] text-muted-foreground">
                        {h.changed_at && new Date(h.changed_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
                        {h.during_market_hours && ' · during market hours'}
                      </span>
                    </div>
                    <p className="text-muted-foreground text-[13px] mt-1">
                      {Object.entries(h.changes || {}).map(([f, c]) =>
                        `${RULE_LABELS[f] || f}: ${c.old ?? 'none'} to ${c.new ?? 'none'}`
                      ).join(' · ')}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {/* Edit dialog */}
      <Dialog open={editing} onOpenChange={(o) => { if (!o) { setEditing(false); setOverrideFields(null); } }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Edit your rules</DialogTitle>
            <DialogDescription>
              Tightening applies immediately. Relaxing a rule needs confirmation, and during
              market hours it only takes effect next session.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            {([
              ['daily_loss_limit', 'Daily loss limit (₹)', 100],
              ['per_trade_loss_limit', 'Per-trade loss limit (₹)', 100],
              ['daily_trade_limit', 'Max trades per day', 1],
              ['max_position_size', 'Max risk per trade (% of capital)', 0.5],
              ['max_consecutive_losses', 'Stop after consecutive losses', 1],
            ] as const).map(([field, label, step]) => (
              <div key={field}>
                <label className="text-xs font-medium text-muted-foreground">{label}</label>
                <Input
                  type="number"
                  step={step}
                  value={draft[field] ?? ''}
                  onChange={(e) => setDraft(d => ({
                    ...d,
                    [field]: e.target.value === '' ? null : Number(e.target.value),
                  }))}
                  className="mt-1"
                />
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEditing(false)} disabled={isSaving}>
              Cancel
            </Button>
            <Button onClick={() => save(false)} disabled={isSaving}>
              {isSaving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Save rules
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Override friction dialog */}
      <Dialog open={overrideFields !== null} onOpenChange={(o) => { if (!o) setOverrideFields(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldAlert className="h-5 w-5 text-tm-loss" />
              You are relaxing your own rules
            </DialogTitle>
            <DialogDescription className="space-y-2 pt-1">
              <span className="block">
                These rules exist because you set them when you were thinking clearly:
              </span>
              <span className="block font-medium text-foreground">
                {(overrideFields || []).map(f => RULE_LABELS[f] || f).join(', ')}
              </span>
              <span className="block">
                This override will be recorded. If the market is open right now, the change
                only takes effect next session.
              </span>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOverrideFields(null)} disabled={isSaving}>
              <X className="h-4 w-4 mr-1.5" />
              Keep my rules
            </Button>
            <Button variant="destructive" onClick={() => save(true)} disabled={isSaving}>
              {isSaving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Override and relax
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
