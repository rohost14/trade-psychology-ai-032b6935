/**
 * Admin UI kit — theme-aware presentational primitives built on the app's design
 * tokens (index.css CSS vars) and shadcn/ui. Replaces the per-page `const T = {}`
 * hex palettes and the ~700 inline styles the admin pages used to carry.
 *
 * Rule: NO hardcoded hex here. Colour comes from tokens only:
 *   text/bg  → text-foreground, text-muted-foreground, bg-card, border-border …
 *   accents  → rgb(var(--tm-profit | --tm-loss | --tm-obs | --tm-brand))
 * so admin follows the app's light/dark theme via next-themes.
 */
import * as React from 'react';
import { RefreshCw, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';

// ── Accent tokens ──────────────────────────────────────────────────────────────
export type Accent = 'profit' | 'loss' | 'warning' | 'brand' | 'muted';

const ACCENT_TEXT: Record<Accent, string> = {
  profit:  'text-[rgb(var(--tm-profit))]',
  loss:    'text-[rgb(var(--tm-loss))]',
  warning: 'text-[rgb(var(--tm-obs))]',
  brand:   'text-[rgb(var(--tm-brand))]',
  muted:   'text-muted-foreground',
};
const ACCENT_RGB: Record<Accent, string> = {
  profit:  'rgb(var(--tm-profit))',
  loss:    'rgb(var(--tm-loss))',
  warning: 'rgb(var(--tm-obs))',
  brand:   'rgb(var(--tm-brand))',
  muted:   'rgb(var(--muted-foreground))',
};

// ── Number helpers (shared across pages) ────────────────────────────────────────
export const fmtNum = (n: number) => n.toLocaleString('en-IN');
export function pct(n: number, d: number, decimals = 1): string {
  if (!d) return '—';
  return ((n / d) * 100).toFixed(decimals) + '%';
}

// ── Page scaffold ───────────────────────────────────────────────────────────────
export function AdminPage({
  title, subtitle, actions, children, maxWidth = 1200,
}: {
  title: string;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  maxWidth?: number;
}) {
  return (
    <div className="px-6 py-6 md:px-8 md:py-7 mx-auto w-full" style={{ maxWidth }}>
      <header className="flex items-start justify-between gap-4 mb-7">
        <div>
          <h1 className="text-foreground">{title}</h1>
          {subtitle && <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>}
        </div>
        {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
      </header>
      {children}
    </div>
  );
}

// ── Card ─────────────────────────────────────────────────────────────────────────
// Matches the app idiom: `.tm-card` + header `px-5 py-3.5 border-b` + body `p-5`.
export function AdminCard({
  title, subtitle, right, children, className, bodyClassName, noPadding,
}: {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  right?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  noPadding?: boolean;
}) {
  return (
    <div className={cn('tm-card', className)}>
      {(title || right) && (
        <div className="flex items-center justify-between gap-3 px-5 py-3.5 border-b border-border">
          <div className="min-w-0">
            {title && <div className="text-sm font-semibold text-foreground truncate">{title}</div>}
            {subtitle && <div className="mt-0.5 text-xs text-muted-foreground">{subtitle}</div>}
          </div>
          {right && <div className="shrink-0">{right}</div>}
        </div>
      )}
      <div className={cn(noPadding ? '' : 'p-5', bodyClassName)}>{children}</div>
    </div>
  );
}

// ── Section header (inside a card / above a group) ──────────────────────────────
export function SectionHeader({ title, sub }: { title: string; sub?: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between mb-4">
      <span className="text-sm font-semibold text-foreground tracking-tight">{title}</span>
      {sub && <span className="text-[11px] text-muted-foreground">{sub}</span>}
    </div>
  );
}

// ── KPI card ─────────────────────────────────────────────────────────────────────
export function KpiCard({
  label, value, sub, accent, badge,
}: {
  label: string;
  value: number | string;
  sub?: React.ReactNode;
  accent?: Accent;
  badge?: string;
}) {
  return (
    <div className="tm-card p-4 md:px-5">
      <div className="tm-label mb-2.5">{label}</div>
      <div className="flex items-baseline gap-2 mb-1.5">
        <div className={cn('text-[28px] font-bold leading-none tabular-nums tracking-tight',
          accent ? ACCENT_TEXT[accent] : 'text-foreground')}>
          {typeof value === 'number' ? fmtNum(value) : value}
        </div>
        {badge && (
          <span className="text-[11px] font-semibold text-muted-foreground px-1.5 py-0.5 rounded-full bg-muted border border-border">
            {badge}
          </span>
        )}
      </div>
      {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

// ── Status pill (health/up-down) ────────────────────────────────────────────────
export function StatusPill({ label, ok, okText = 'healthy', badText = 'error' }: {
  label: string; ok: boolean; okText?: string; badText?: string;
}) {
  const c = ok ? 'rgb(var(--tm-profit))' : 'rgb(var(--tm-loss))';
  return (
    <div
      className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border"
      style={{ background: `color-mix(in srgb, ${c} 10%, transparent)`, borderColor: `color-mix(in srgb, ${c} 25%, transparent)` }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: c }} />
      <span className="text-xs font-medium" style={{ color: c }}>{label}</span>
      <span className="text-[11px] text-muted-foreground">{ok ? okText : badText}</span>
    </div>
  );
}

// ── Progress meter row (feature adoption / lifecycle style) ─────────────────────
export function MeterRow({
  label, hint, value, total, accent = 'brand',
}: {
  label: React.ReactNode; hint?: React.ReactNode; value: number; total: number; accent?: Accent;
}) {
  const p = total > 0 ? value / total : 0;
  const rgb = ACCENT_RGB[accent];
  return (
    <div className="mb-3.5 last:mb-0">
      <div className="flex items-center justify-between mb-1.5">
        <div className="min-w-0">
          <span className="text-[13px] font-medium text-foreground">{label}</span>
          {hint && <span className="ml-2 text-[11px] text-muted-foreground">{hint}</span>}
        </div>
        <div className="flex items-center gap-2.5 shrink-0">
          <span className="text-xs text-muted-foreground tabular-nums">{fmtNum(value)} / {fmtNum(total)}</span>
          <span className="text-[13px] font-bold tabular-nums min-w-[38px] text-right" style={{ color: rgb }}>
            {total > 0 ? `${(p * 100).toFixed(0)}%` : '—'}
          </span>
        </div>
      </div>
      <div className="h-1.5 rounded-full bg-muted overflow-hidden">
        <div className="h-full rounded-full transition-[width] duration-500" style={{ width: `${p * 100}%`, background: rgb }} />
      </div>
    </div>
  );
}

// ── Area sparkline (token-driven; replaces the inline SVG in Overview) ──────────
export function AreaSparkline({ data, height = 80 }: { data: { date: string; count: number }[]; height?: number }) {
  const id = React.useId();
  if (!data || data.length < 2) {
    return <p className="text-xs text-muted-foreground py-3">Not enough data yet</p>;
  }
  const max = Math.max(...data.map(d => d.count), 1);
  const W = 600, H = height, P = 4;
  const pts = data.map((d, i) => {
    const x = P + (i / (data.length - 1)) * (W - P * 2);
    const y = H - P - (d.count / max) * (H - P * 2);
    return `${x},${y}`;
  });
  const brand = 'rgb(var(--tm-brand))';
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full block" style={{ height }} preserveAspectRatio="none">
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={brand} stopOpacity="0.18" />
            <stop offset="100%" stopColor={brand} stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon points={`${P},${H} ${pts.join(' ')} ${W - P},${H}`} fill={`url(#${id})`} />
        <polyline points={pts.join(' ')} fill="none" stroke={brand} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      <div className="flex justify-between mt-1">
        <span className="text-[11px] text-muted-foreground">{data[0]?.date}</span>
        <span className="text-[11px] text-muted-foreground">{data[data.length - 1]?.date}</span>
      </div>
    </div>
  );
}

// ── Common states ────────────────────────────────────────────────────────────────
export function Spinner({ size = 24 }: { size?: number }) {
  return (
    <div
      className="rounded-full border-2 border-[rgb(var(--tm-brand))] border-t-transparent animate-spin"
      style={{ width: size, height: size }}
    />
  );
}

export function LoadingBlock() {
  return <div className="flex justify-center py-14"><Spinner /></div>;
}

export function ErrorBanner({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div
      className="flex items-center gap-2 px-3.5 py-2.5 rounded-lg mb-5 border"
      style={{ background: 'color-mix(in srgb, rgb(var(--tm-loss)) 8%, transparent)', borderColor: 'color-mix(in srgb, rgb(var(--tm-loss)) 20%, transparent)' }}
    >
      <AlertTriangle size={13} style={{ color: 'rgb(var(--tm-loss))' }} className="shrink-0" />
      <span className="text-xs" style={{ color: 'rgb(var(--tm-loss))' }}>{message}</span>
    </div>
  );
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return <p className="text-xs text-muted-foreground text-center py-4">{children}</p>;
}

// ── Refresh button (used in most page headers) ──────────────────────────────────
export function RefreshButton({ onClick, loading }: { onClick: () => void; loading?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-card border border-border text-xs text-muted-foreground hover:text-foreground transition-colors disabled:cursor-not-allowed disabled:opacity-60"
    >
      <RefreshCw size={12} className={cn(loading && 'animate-spin')} />
      Refresh
    </button>
  );
}
