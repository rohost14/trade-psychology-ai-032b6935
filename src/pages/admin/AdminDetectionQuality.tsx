import { useCallback, useEffect, useState } from 'react';
import { adminApi } from '@/lib/adminApi';
import {
  AdminPage, AdminCard, KpiCard, SectionHeader,
  ErrorBanner, LoadingBlock, EmptyState, RefreshButton, fmtNum,
} from './_ui';
import { cn } from '@/lib/utils';

/**
 * Is the engine any good?
 *
 * Insights answers what the engine DID. This answers whether it was right, and
 * how fast — the questions the product could not answer at all until Phase 4.
 * That absence is why two real defects survived for months: every WhatsApp
 * alert falling back to generic text, and the most common alert opening an
 * empty detail panel, are both invisible without an instrument.
 *
 * The screen's job is to make three things impossible to misread:
 *   - a gate with no data is not a passing gate
 *   - a rate off three alerts is not a finding
 *   - "we were wrong" and "I meant to do that" are different answers
 */

interface LatencySummary {
  alerts_measured: number;
  alerts_excluded_live: number;
  p50_seconds: number | null;
  p95_seconds: number | null;
  max_seconds: number | null;
  gate_seconds: number;
  over_gate: number;
  meets_gate: boolean | null;
}

interface PrecisionRow {
  detector: string;
  alerts: number;
  not_useful: number;
  planned: number;
  acknowledged: number;
  muted_by_accounts: number;
  not_useful_rate: number | null;
  planned_rate: number | null;
  mute_rate: number | null;
  significant: boolean;
}

interface ShadowRow {
  detector: string;
  events: number;
  would_have_alerted: number;
  severities: Record<string, number>;
}

interface QualityData {
  window_days: number;
  alerts_in_window: number;
  accounts_seen: number;
  min_alerts_for_rate: number;
  latency: LatencySummary;
  precision: PrecisionRow[];
  shadow: { detectors_in_shadow: number; events: number; would_have_alerted: number; by_detector: ShadowRow[] };
}

const secs = (v: number | null) => (v == null ? '—' : `${v < 1 ? v.toFixed(2) : v.toFixed(1)}s`);
const rate = (v: number | null) => (v == null ? '—' : `${Math.round(v * 100)}%`);

function GateVerdict({ latency }: { latency: LatencySummary }) {
  // Three states, not two. `null` means the sample was empty — which has said
  // nothing about the gate, and must never be painted as passing it. A metric
  // that reports success on no data is how a broken pipeline looks healthy.
  if (latency.meets_gate === null) {
    return (
      <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-muted border border-border text-muted-foreground">
        no data
      </span>
    );
  }
  return (
    <span className={cn(
      'text-[11px] font-semibold px-2 py-0.5 rounded-full border',
      latency.meets_gate
        ? 'bg-tm-profit/10 border-tm-profit/30 text-tm-profit'
        : 'bg-tm-loss/10 border-tm-loss/30 text-tm-loss',
    )}>
      {latency.meets_gate ? 'within gate' : `${latency.over_gate} over gate`}
    </span>
  );
}

function Latency({ latency }: { latency: LatencySummary }) {
  return (
    <AdminCard
      title="Detection latency"
      subtitle={`trade close → alert written · gate ${latency.gate_seconds}s`}
      right={<GateVerdict latency={latency} />}
    >
      {latency.alerts_measured === 0 ? (
        <EmptyState>
          Nothing measurable in this window.
          {latency.alerts_excluded_live > 0 && (
            <> {fmtNum(latency.alerts_excluded_live)} live alerts were excluded — they are
            raised while the position is open, so their latency is zero by construction.</>
          )}
        </EmptyState>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-3 mb-3">
            {([['p50', latency.p50_seconds], ['p95', latency.p95_seconds],
               ['max', latency.max_seconds]] as const).map(([label, value]) => (
              <div key={label}>
                <div className="tm-label mb-1">{label}</div>
                <div className={cn(
                  'text-[20px] font-bold tabular-nums leading-none',
                  value != null && value > latency.gate_seconds ? 'text-tm-loss' : 'text-foreground',
                )}>
                  {secs(value)}
                </div>
              </div>
            ))}
          </div>
          <p className="text-[11px] text-muted-foreground">
            {fmtNum(latency.alerts_measured)} alerts measured
            {latency.alerts_excluded_live > 0 && (
              <>, {fmtNum(latency.alerts_excluded_live)} live alerts excluded</>
            )}
          </p>
        </>
      )}
    </AdminCard>
  );
}

function Precision({ rows, minAlerts }: { rows: PrecisionRow[]; minAlerts: number }) {
  return (
    <AdminCard
      title="Where we were wrong"
      subtitle="the trader telling us, not us marking our own work"
    >
      {rows.length === 0 ? <EmptyState>No alerts in this window</EmptyState> : (
        <div className="overflow-x-auto -mx-1">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-left text-muted-foreground">
                <th className="font-medium pb-2 pl-1">Detector</th>
                <th className="font-medium pb-2 text-right">Alerts</th>
                <th className="font-medium pb-2 text-right" title="Trader said the detection itself was wrong">
                  Not useful
                </th>
                <th className="font-medium pb-2 text-right" title="Detection correct, concern already accounted for">
                  Planned
                </th>
                <th className="font-medium pb-2 text-right pr-1" title="Accounts that silenced this pattern outright">
                  Muted
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.detector} className="border-t border-border">
                  <td className="py-2 pl-1">
                    <span className="font-mono text-[11px] text-foreground">{r.detector}</span>
                    {/* A 100% not-useful rate off one alert is not a finding.
                        Saying so beside the number is the only way a reader
                        cannot mistake it for one. */}
                    {!r.significant && (
                      <span className="ml-2 text-[10px] text-muted-foreground">
                        &lt;{minAlerts} alerts
                      </span>
                    )}
                  </td>
                  <td className="py-2 text-right tabular-nums text-muted-foreground">{fmtNum(r.alerts)}</td>
                  <td className={cn('py-2 text-right tabular-nums font-medium',
                    r.significant && (r.not_useful_rate ?? 0) > 0.2 ? 'text-tm-loss' : 'text-foreground')}>
                    {rate(r.not_useful_rate)}
                  </td>
                  <td className="py-2 text-right tabular-nums text-foreground">{rate(r.planned_rate)}</td>
                  <td className={cn('py-2 text-right tabular-nums pr-1 font-medium',
                    (r.mute_rate ?? 0) > 0.2 ? 'text-tm-loss' : 'text-foreground')}>
                    {rate(r.mute_rate)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[11px] text-muted-foreground mt-3 leading-relaxed">
            <span className="font-medium">Not useful</span> means the detection was wrong.
            {' '}<span className="font-medium">Planned</span> means it was right and the trader
            had already accounted for it — accurate but redundant, which needs a different fix.
            {' '}<span className="font-medium">Muted</span> is the strongest signal: same one tap,
            but it means never show me this again.
          </p>
        </div>
      )}
    </AdminCard>
  );
}

function Shadow({ shadow }: { shadow: QualityData['shadow'] }) {
  return (
    <AdminCard
      title="Running in shadow"
      subtitle="what a detector would have raised if it were live"
    >
      {shadow.by_detector.length === 0 ? (
        <EmptyState>
          Nothing in shadow. Detectors ship as shadow and promote once their output holds
          up — this is the evidence for that decision.
        </EmptyState>
      ) : (
        <div className="flex flex-col gap-2.5">
          {shadow.by_detector.map(r => (
            <div key={r.detector} className="flex items-center justify-between gap-3">
              <span className="font-mono text-[11px] text-foreground truncate">{r.detector}</span>
              <div className="flex items-center gap-4 shrink-0 tabular-nums text-[12px]">
                <span className="text-muted-foreground">{fmtNum(r.events)} events</span>
                <span className="font-semibold text-foreground min-w-[90px] text-right">
                  {fmtNum(r.would_have_alerted)} would alert
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </AdminCard>
  );
}

export default function AdminDetectionQuality() {
  const [data, setData] = useState<QualityData | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await adminApi.detectionQuality(days));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load detection quality');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => { load(); }, [load]);

  return (
    <AdminPage
      title="Detection quality"
      subtitle="Is the engine right, and is it fast?"
      actions={
        <div className="flex items-center gap-2">
          <select
            value={days}
            onChange={e => setDays(Number(e.target.value))}
            className="h-8 rounded-lg border border-border bg-background text-[12px] px-2 text-foreground"
          >
            {[7, 30, 90].map(d => <option key={d} value={d}>{d} days</option>)}
          </select>
          <RefreshButton onClick={load} loading={loading} />
        </div>
      }
    >
      {error && <ErrorBanner message={error} />}
      {loading && !data ? <LoadingBlock /> : data && (
        <>
          <div className="grid gap-4 md:grid-cols-3 mb-5">
            <KpiCard label="Alerts in window" value={data.alerts_in_window}
                     sub={`${fmtNum(data.accounts_seen)} accounts saw one`} />
            <KpiCard label="Median latency" value={secs(data.latency.p50_seconds)}
                     sub={`p95 ${secs(data.latency.p95_seconds)}`}
                     accent={data.latency.meets_gate === false ? 'loss' : undefined} />
            <KpiCard label="Shadow detectors" value={data.shadow.detectors_in_shadow}
                     sub={`${fmtNum(data.shadow.would_have_alerted)} would have alerted`} />
          </div>

          <SectionHeader title="Speed" />
          <div className="mb-5"><Latency latency={data.latency} /></div>

          <SectionHeader title="Accuracy" />
          <div className="mb-5">
            <Precision rows={data.precision} minAlerts={data.min_alerts_for_rate} />
          </div>

          <SectionHeader title="Shadow" />
          <Shadow shadow={data.shadow} />
        </>
      )}
    </AdminPage>
  );
}
