/**
 * Admin → Partitions & Retention
 *
 * `orders` and `behavior_events` are partitioned by month. When the forward
 * window runs out nothing fails — rows quietly land in the DEFAULT partition and
 * the table stops being partitioned in practice. This page exists so that state
 * is visible while there is still time to act, which is the only reason the last
 * near-miss was caught at all.
 *
 * Three things it deliberately makes hard to misread:
 *   - runway is shown in months, against the threshold, not as a green tick
 *   - row counts are labelled as ESTIMATES, because they come from reltuples
 *   - a blocked month says WHY it is blocked, not just that it is
 *
 * There is no "delete this partition" button anywhere. Deletion happens only
 * through the maintenance job, behind the snapshot gate.
 */
import { useEffect, useState } from 'react';
import {
  AlertTriangle, Archive, CheckCircle2, Database, Play, Save, ShieldAlert, XCircle,
} from 'lucide-react';
import { adminApi } from '@/lib/adminApi';
import { AdminPage, AdminCard, ErrorBanner, LoadingBlock, RefreshButton, fmtNum } from './_ui';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

interface Partition {
  name: string;
  month: string | null;
  bounds: string;
  estimated_rows: number;
  size_bytes: number;
  state: 'past' | 'current' | 'future' | 'default';
  is_default: boolean;
}

interface Retention {
  months: number | null;
  source: 'code' | 'admin';
  code_default: number | null;
  updated_by: string | null;
  updated_at: string | null;
  floor_months: number;
  ceiling_months: number;
  snapshot_gated: boolean;
}

interface TableState {
  table: string;
  retention: Retention;
  partition_count: number;
  first_month: string | null;
  last_month: string | null;
  current_partition: string | null;
  next_partition: string | null;
  runway_months: number;
  min_runway_months: number;
  missing_months: string[];
  default_partition_rows: number | null;
  eligible_for_deletion: string[];
  total_size_bytes: number;
  estimated_rows: number;
  health: 'healthy' | 'warning' | 'critical';
  health_reason: string | null;
  partitions: Partition[];
}

interface Overview {
  tables: TableState[];
  months_ahead: number;
  max_drops_per_run: number;
  confirm_phrase: string;
  last_run: {
    at?: string; ok?: boolean; error?: string; by?: string;
    created?: string[]; dropped?: string[]; skipped?: string[];
  } | null;
}

interface MonthStatus {
  month: string;
  accounts_with_orders: number;
  snapshots_present: number;
  snapshots_verified: number;
  complete: boolean;
  partition: string;
  partition_expired: boolean;
  eligible_for_deletion: boolean;
  blocked_reason: string | null;
  pruned_at: string | null;
}

const fmtBytes = (n: number) => {
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(0)} kB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
};

const HEALTH_STYLE: Record<string, string> = {
  healthy:  'text-tm-profit border-tm-profit/25 bg-tm-profit/10',
  warning:  'text-amber-500 border-amber-500/25 bg-amber-500/10',
  critical: 'text-tm-loss border-tm-loss/25 bg-tm-loss/10',
};

function HealthBadge({ health, reason }: { health: string; reason: string | null }) {
  const Icon = health === 'healthy' ? CheckCircle2 : health === 'warning' ? AlertTriangle : XCircle;
  return (
    <div className="flex items-center gap-2">
      <span className={cn('inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-medium',
        HEALTH_STYLE[health])}>
        <Icon className="h-3 w-3" />
        {health}
      </span>
      {reason && <span className="text-[11px] text-muted-foreground">{reason}</span>}
    </div>
  );
}

export default function AdminPartitions() {
  const [data, setData]       = useState<Overview | null>(null);
  const [months, setMonths]   = useState<MonthStatus[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [busy, setBusy]       = useState<string | null>(null);
  const [note, setNote]       = useState<string | null>(null);

  // Retention editor state, keyed by table.
  const [draft, setDraft]     = useState<Record<string, string>>({});
  const [confirm, setConfirm] = useState('');

  const [dryRun, setDryRun] = useState<{
    would_create: string[]; would_drop: string[]; would_skip: string[];
  } | null>(null);

  const load = async () => {
    setLoading(true); setError('');
    try {
      const [ov, sn] = await Promise.all([
        adminApi.partitions(),
        adminApi.partitionSnapshots(),
      ]);
      setData(ov);
      setMonths(sn.months);
      setDraft(Object.fromEntries(
        ov.tables.map((t: TableState) => [t.table, t.retention.months === null ? '' : String(t.retention.months)]),
      ));
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const act = async (key: string, fn: () => Promise<unknown>, describe: (r: never) => string) => {
    setBusy(key); setError(''); setNote(null);
    try {
      const r = await fn();
      setNote(describe(r as never));
      await load();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(null); }
  };

  if (loading && !data) return <AdminPage title="Partitions & Retention"><LoadingBlock /></AdminPage>;

  return (
    <AdminPage
      title="Partitions & Retention"
      subtitle="Monthly partitions, retention windows, and the snapshot archive that gates deletion"
      actions={<RefreshButton onClick={load} loading={loading} />}
    >
      {error && <div className="mb-5"><ErrorBanner message={error} /></div>}
      {note && (
        <div className="mb-5 rounded-lg border border-border bg-muted/40 px-4 py-3 text-[13px] text-foreground">
          {note}
        </div>
      )}

      {/* ── job health ───────────────────────────────────────────────── */}
      <AdminCard
        title="Maintenance job"
        subtitle={`Creates ${data?.months_ahead} months ahead · drops at most ${data?.max_drops_per_run} partitions per run`}
        className="mb-5"
      >
        {data?.last_run ? (
          <div className="space-y-1.5 text-[13px]">
            <div className="flex items-center gap-2">
              {data.last_run.ok
                ? <CheckCircle2 className="h-4 w-4 text-tm-profit" />
                : <XCircle className="h-4 w-4 text-tm-loss" />}
              <span className="text-foreground">
                Last run {data.last_run.at ? new Date(data.last_run.at).toLocaleString() : 'unknown'}
                {data.last_run.by && ` · manually by ${data.last_run.by}`}
              </span>
            </div>
            {data.last_run.error && <p className="text-tm-loss">{data.last_run.error}</p>}
            <p className="text-muted-foreground">
              created {data.last_run.created?.length ?? 0} ·
              dropped {data.last_run.dropped?.length ?? 0} ·
              retained {data.last_run.skipped?.length ?? 0}
            </p>
            {!!data.last_run.skipped?.length && (
              <p className="text-amber-500">
                Retained pending snapshots: {data.last_run.skipped.join(', ')}
              </p>
            )}
          </div>
        ) : (
          /* Absence of a record is NOT a clean run, and must not read as one. */
          <p className="text-[13px] text-muted-foreground">
            No run recorded. The record lives in Redis and is lost on a flush, so this
            means unknown — not that the job has never run. Partition state below is read
            from the database and is authoritative regardless.
          </p>
        )}
        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            variant="outline" size="sm" className="gap-2"
            disabled={busy !== null}
            onClick={() => act('ensure', () => adminApi.ensurePartitions(),
              (r: { created: string[] }) => r.created.length
                ? `Created ${r.created.length} partition(s): ${r.created.join(', ')}`
                : 'Nothing to create — every month in the window already has a partition.')}
          >
            <Database className="h-4 w-4" />
            Create missing partitions
          </Button>
          <Button
            variant="outline" size="sm" className="gap-2"
            disabled={busy !== null}
            onClick={() => act('dry', () => adminApi.runPartitionMaintenance(true),
              (r: { would_create: string[]; would_drop: string[]; would_skip: string[] }) => {
                setDryRun(r);
                return `Dry run: would create ${r.would_create.length}, drop ${r.would_drop.length}, retain ${r.would_skip.length}.`;
              })}
          >
            <Play className="h-4 w-4" />
            Preview maintenance run
          </Button>
        </div>

        {dryRun && (
          <div className="mt-4 rounded-lg border border-border p-4 space-y-3">
            <p className="text-xs font-semibold text-foreground">Preview — nothing has changed</p>
            {(['would_create', 'would_drop', 'would_skip'] as const).map(k => (
              <div key={k} className="text-[13px]">
                <span className="text-muted-foreground">
                  {k === 'would_create' ? 'Create' : k === 'would_drop' ? 'Drop' : 'Retain (no verified snapshot)'}:
                </span>{' '}
                <span className={cn('font-mono text-xs',
                  k === 'would_drop' ? 'text-tm-loss' : k === 'would_skip' ? 'text-amber-500' : 'text-foreground')}>
                  {dryRun[k].length ? dryRun[k].join(', ') : 'nothing'}
                </span>
              </div>
            ))}
            {dryRun.would_drop.length > 0 && (
              <div className="pt-2 border-t border-border space-y-2">
                <p className="text-[13px] text-tm-loss flex items-start gap-2">
                  <ShieldAlert className="h-4 w-4 shrink-0 mt-0.5" />
                  A real run deletes the order-level detail for those months permanently.
                  Their monthly summaries are kept.
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <Input
                    value={confirm}
                    onChange={e => setConfirm(e.target.value)}
                    placeholder={data?.confirm_phrase}
                    className="max-w-xs font-mono text-xs"
                  />
                  <Button
                    variant="destructive" size="sm"
                    disabled={busy !== null || confirm !== data?.confirm_phrase}
                    onClick={() => act('run', () => adminApi.runPartitionMaintenance(false, confirm),
                      (r: { dropped: string[]; skipped: string[] }) => {
                        setConfirm(''); setDryRun(null);
                        return `Dropped ${r.dropped.length}, retained ${r.skipped.length}.`;
                      })}
                  >
                    Run maintenance
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </AdminCard>

      {/* ── per table ────────────────────────────────────────────────── */}
      {data?.tables.map(t => (
        <AdminCard
          key={t.table}
          title={t.table}
          subtitle={`${t.partition_count} partitions · ${t.first_month ?? '—'} to ${t.last_month ?? '—'}`}
          right={<HealthBadge health={t.health} reason={t.health_reason} />}
          className="mb-5"
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
            <div>
              <div className="tm-label mb-1">Runway</div>
              <div className={cn('text-lg font-bold tabular-nums',
                t.runway_months < t.min_runway_months ? 'text-tm-loss' : 'text-foreground')}>
                {t.runway_months} mo
              </div>
              <div className="text-[11px] text-muted-foreground">want ≥ {t.min_runway_months}</div>
            </div>
            <div>
              <div className="tm-label mb-1">Retention</div>
              <div className="text-lg font-bold tabular-nums text-foreground">
                {t.retention.months === null ? 'forever' : `${t.retention.months} mo`}
              </div>
              <div className="text-[11px] text-muted-foreground">
                {t.retention.source === 'code' ? 'code default' : `set by ${t.retention.updated_by ?? 'an admin'}`}
              </div>
            </div>
            <div>
              <div className="tm-label mb-1">Size</div>
              <div className="text-lg font-bold tabular-nums text-foreground">{fmtBytes(t.total_size_bytes)}</div>
              <div className="text-[11px] text-muted-foreground">~{fmtNum(t.estimated_rows)} rows (estimated)</div>
            </div>
            <div>
              <div className="tm-label mb-1">In DEFAULT</div>
              <div className={cn('text-lg font-bold tabular-nums',
                t.default_partition_rows ? 'text-tm-loss' : 'text-foreground')}>
                {t.default_partition_rows === null ? '—' : fmtNum(t.default_partition_rows)}
              </div>
              <div className="text-[11px] text-muted-foreground">
                {t.default_partition_rows ? 'window has lapsed' : 'rows outside every month'}
              </div>
            </div>
          </div>

          {t.missing_months.length > 0 && (
            <p className="mb-4 text-[13px] text-amber-500">
              Missing partitions: {t.missing_months.join(', ')}
            </p>
          )}

          {/* retention editor */}
          <div className="rounded-lg border border-border p-4 mb-5">
            <p className="text-xs font-semibold text-foreground mb-1">Retention policy</p>
            <p className="text-[12px] text-muted-foreground mb-3">
              Blank = keep indefinitely. Minimum {t.retention.floor_months} months —
              detectors still read inside that window.
              {t.retention.snapshot_gated
                ? ' A month is summarised and verified before its partition can be dropped.'
                : ' This table is NOT snapshot-gated; dropping a month here loses it outright.'}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Input
                value={draft[t.table] ?? ''}
                onChange={e => setDraft({ ...draft, [t.table]: e.target.value })}
                placeholder="months (blank = forever)"
                className="max-w-[200px]"
                inputMode="numeric"
              />
              <Input
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                placeholder={`${data.confirm_phrase} (only if shortening)`}
                className="max-w-xs font-mono text-xs"
              />
              <Button
                variant="outline" size="sm" className="gap-2"
                disabled={busy !== null}
                onClick={() => {
                  const raw = (draft[t.table] ?? '').trim();
                  return act(`ret-${t.table}`,
                    () => adminApi.setPartitionRetention({
                      table: t.table,
                      months: raw === '' ? null : Number(raw),
                      confirm: confirm || undefined,
                    }),
                    (r: { retention: Retention }) => {
                      setConfirm('');
                      return `${t.table} retention is now ${r.retention.months === null ? 'indefinite' : `${r.retention.months} months`}.`;
                    });
                }}
              >
                <Save className="h-4 w-4" />
                Save
              </Button>
              {t.retention.source === 'admin' && (
                <Button
                  variant="ghost" size="sm"
                  disabled={busy !== null}
                  onClick={() => act(`reset-${t.table}`,
                    () => adminApi.setPartitionRetention({
                      table: t.table, reset: true, confirm: confirm || undefined,
                    }),
                    () => { setConfirm(''); return `${t.table} is back on the code default.`; })}
                >
                  Reset to default
                </Button>
              )}
            </div>
          </div>

          <div className="overflow-x-auto -mx-5">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="text-[11px] uppercase tracking-wide text-muted-foreground border-b border-border">
                  <th className="text-left font-medium px-5 py-2">Partition</th>
                  <th className="text-left font-medium py-2">Range</th>
                  <th className="text-right font-medium py-2">Rows (est.)</th>
                  <th className="text-right font-medium py-2">Size</th>
                  <th className="text-right font-medium px-5 py-2">State</th>
                </tr>
              </thead>
              <tbody>
                {t.partitions.map(p => {
                  const doomed = t.eligible_for_deletion.includes(p.name);
                  return (
                    <tr key={p.name} className="border-b border-border/50 last:border-0">
                      <td className="px-5 py-2 font-mono text-xs text-foreground">{p.name}</td>
                      <td className="py-2 font-mono text-[11px] text-muted-foreground">{p.bounds}</td>
                      <td className="py-2 text-right tabular-nums">{fmtNum(p.estimated_rows)}</td>
                      <td className="py-2 text-right tabular-nums text-muted-foreground">{fmtBytes(p.size_bytes)}</td>
                      <td className="px-5 py-2 text-right">
                        <span className={cn('text-[11px]',
                          doomed ? 'text-tm-loss font-medium'
                            : p.state === 'current' ? 'text-tm-brand font-medium'
                            : p.is_default ? 'text-amber-500' : 'text-muted-foreground')}>
                          {doomed ? 'past retention' : p.state}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </AdminCard>
      ))}

      {/* ── snapshot archive ─────────────────────────────────────────── */}
      <AdminCard
        title="Monthly snapshot archive"
        subtitle="A month's orders cannot be dropped until every account in it has a verified summary"
      >
        {!months?.length ? (
          <p className="text-[13px] text-muted-foreground">No months with order activity yet.</p>
        ) : (
          <div className="overflow-x-auto -mx-5">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="text-[11px] uppercase tracking-wide text-muted-foreground border-b border-border">
                  <th className="text-left font-medium px-5 py-2">Month</th>
                  <th className="text-right font-medium py-2">Accounts</th>
                  <th className="text-right font-medium py-2">Verified</th>
                  <th className="text-left font-medium py-2 pl-6">Status</th>
                  <th className="text-right font-medium px-5 py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {months.map(m => (
                  <tr key={m.month} className="border-b border-border/50 last:border-0">
                    <td className="px-5 py-2 font-mono text-xs text-foreground">{m.month.slice(0, 7)}</td>
                    <td className="py-2 text-right tabular-nums">{m.accounts_with_orders}</td>
                    <td className="py-2 text-right tabular-nums">
                      {m.snapshots_verified}/{m.accounts_with_orders}
                    </td>
                    <td className="py-2 pl-6">
                      {m.pruned_at ? (
                        <span className="text-muted-foreground text-[12px]">
                          orders removed · summary kept
                        </span>
                      ) : m.eligible_for_deletion ? (
                        <span className="text-tm-loss text-[12px]">
                          past retention · preserved · will be dropped
                        </span>
                      ) : m.partition_expired ? (
                        <span className="text-amber-500 text-[12px]">
                          past retention · RETAINED — {m.blocked_reason}
                        </span>
                      ) : m.complete ? (
                        <span className="text-tm-profit text-[12px]">summarised</span>
                      ) : (
                        <span className="text-muted-foreground text-[12px]">
                          within retention · {m.blocked_reason}
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-2 text-right">
                      {!m.complete && !m.pruned_at && (
                        <Button
                          variant="ghost" size="sm" className="gap-1.5 h-7 text-xs"
                          disabled={busy !== null}
                          onClick={() => act(`snap-${m.month}`,
                            () => adminApi.snapshotMonth(m.month.slice(0, 7)),
                            (r: { written: string[]; failed: string[] }) =>
                              `${m.month.slice(0, 7)}: ${r.written.length} snapshot(s) written, ${r.failed.length} failed.`)}
                        >
                          <Archive className="h-3.5 w-3.5" />
                          Build
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </AdminCard>
    </AdminPage>
  );
}
