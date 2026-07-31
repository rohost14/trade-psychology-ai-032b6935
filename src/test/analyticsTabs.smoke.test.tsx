/**
 * Render-smoke tests for the Analytics tabs against the demo dataset.
 *
 * The demo mocks in src/lib/demoData.ts mirror the REAL backend response
 * shapes (kept in sync since the 2026-07 API-shape repair). Rendering each
 * tab against them guards the exact regression class that broke production:
 * a component written against fields the backend never returns either paints
 * "NaN" into the UI or silently renders nothing.
 *
 * Every test asserts:
 *   1. the section headers actually appear (nothing silently dead), and
 *   2. the rendered text contains no "NaN".
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { BrokerProvider } from '@/contexts/BrokerContext';

import { getGuestResponse } from '@/lib/guestMode';

// Route every api.get through the guest-mode resolver — the same demo data
// a guest user sees, shaped like the real backend.
vi.mock('@/lib/api', () => ({
  api: {
    get: (url: string) => Promise.resolve({ data: getGuestResponse(url, 'GET') }),
    post: () => Promise.resolve({ data: { success: true } }),
    put: () => Promise.resolve({ data: { success: true } }),
    delete: () => Promise.resolve({ data: { success: true } }),
  },
  apiDetailString: (_detail: unknown, fallback: string) => fallback,
  // BrokerProvider (added to the harness below) reads these two. A partial
  // module mock is not a partial module — anything the tree imports from
  // '@/lib/api' has to exist here or the import throws at render.
  AUTH_TOKEN_KEY: 'tradementor_token',
  getAuthToken: () => null,
}));

import OverviewTab from '@/components/analytics/OverviewTab';
import BehaviorTab from '@/components/analytics/BehaviorTab';
import SessionsTab from '@/components/analytics/SessionsTab';
import TradeDnaTab from '@/components/analytics/TradeDnaTab';
import EdgeTab from '@/components/analytics/EdgeTab';
import ReportCard from '@/components/analytics/ReportCard';
import EdgeLeakCard from '@/components/analytics/EdgeLeakCard';
import StrategyCard from '@/components/analytics/StrategyCard';

// BrokerProvider as well as the router: BehaviorTab reaches useBroker through a
// child, and useBroker throws outside a provider rather than degrading. Without
// it the smoke test fails on the harness rather than on the component.
function renderWithRouter(ui: React.ReactElement) {
  return render(
    <MemoryRouter>
      <BrokerProvider>{ui}</BrokerProvider>
    </MemoryRouter>,
  );
}

describe('Analytics tab render smoke (demo data, backend-shaped)', () => {
  it('OverviewTab renders KPIs, edge banner and charts without NaN', async () => {
    const { container } = renderWithRouter(<OverviewTab days={30} />);

    // KPI strip (waits out the loading skeleton)
    expect(await screen.findByText('Win Rate')).toBeInTheDocument();
    expect(screen.getByText('Profit Factor')).toBeInTheDocument();
    expect(screen.getByText('Max Drawdown')).toBeInTheDocument();

    // Edge-confidence banner — demo verdict is 'too_few'
    expect(screen.getByText('Not enough trades yet')).toBeInTheDocument();

    // Charts + product mix
    expect(screen.getByText('Equity Curve')).toBeInTheDocument();
    expect(screen.getByText('Daily P&L')).toBeInTheDocument();
    expect(screen.getByText('Product Mix')).toBeInTheDocument();

    expect(container.textContent).not.toContain('NaN');
  });

  it('BehaviorTab renders pattern frequency, scenario cards and options card without NaN', async () => {
    const { container } = renderWithRouter(<BehaviorTab days={30} />);

    expect(await screen.findByText('Pattern Frequency')).toBeInTheDocument();
    // formatPatternName('revenge_trade') from the demo alerts_summary
    expect(screen.getByText('Revenge Trade')).toBeInTheDocument();

    // Conditional-performance cards (conditions[] array consumption)
    expect(screen.getByText('After a loss')).toBeInTheDocument();
    expect(screen.getByText('Opening 30 minutes')).toBeInTheDocument();

    // Options behaviour card (crashed in guest mode before the shape fix).
    // It fetches on its own timeline — await its render separately.
    expect(await screen.findByText('Options behaviour')).toBeInTheDocument();

    // Cross-link to Alerts, not a recomputed response-stats table
    expect(screen.getByText(/How you responded to each alert/)).toBeInTheDocument();

    expect(container.textContent).not.toContain('NaN');
  });

  it('SessionsTab renders calendar, opening/expiry cards and expiry comparison without NaN', async () => {
    const { container } = renderWithRouter(<SessionsTab days={30} />);

    expect(await screen.findByText('3-Month P&L Calendar')).toBeInTheDocument();

    // conditions[] driven cards
    expect(screen.getByText('Opening 30 Minutes (9:15–9:45)')).toBeInTheDocument();
    expect(screen.getByText('Expiry Day Trades')).toBeInTheDocument();

    expect(screen.getByText('Expiry vs Non-Expiry Performance')).toBeInTheDocument();
    expect(screen.getByText('Expiry Week by Day')).toBeInTheDocument();

    expect(container.textContent).not.toContain('NaN');
  });

  it('TradeDnaTab renders quality tiers, best/worst trades and trade log without NaN', async () => {
    const { container } = renderWithRouter(<TradeDnaTab days={30} />);

    expect(await screen.findByText('Trade Quality')).toBeInTheDocument();
    expect(screen.getByText('High (7–8)')).toBeInTheDocument();
    expect(screen.getByText('Low (0–4)')).toBeInTheDocument();

    expect(screen.getByText('Best 5 Trades')).toBeInTheDocument();
    expect(screen.getByText('Worst 5 Trades')).toBeInTheDocument();
    expect(screen.getByText('Trade Log')).toBeInTheDocument();
    expect(screen.getByText('Hold Time vs Performance')).toBeInTheDocument();
    expect(screen.getByText('Risk : Reward')).toBeInTheDocument();

    expect(container.textContent).not.toContain('NaN');
  });

  it('EdgeTab renders leaderboard, day-of-week and size analysis without NaN', async () => {
    const { container } = renderWithRouter(<EdgeTab days={30} />);

    expect(await screen.findByText('Instrument Leaderboard')).toBeInTheDocument();

    // Regression: this chart never rendered while the numeric `day` was
    // filtered against 'Mon'-style strings.
    expect(screen.getByText('Day of Week')).toBeInTheDocument();

    expect(screen.getByText('Position Size vs Performance')).toBeInTheDocument();
    expect(screen.getByText('Hour-of-Day Performance')).toBeInTheDocument();

    expect(container.textContent).not.toContain('NaN');
  });

  it('ReportCard renders the period verdict and edge/leak pillars without NaN', async () => {
    const { container } = renderWithRouter(<ReportCard days={30} />);

    expect(await screen.findByText(/Your 30-day report/)).toBeInTheDocument();
    expect(screen.getByText('Biggest strength')).toBeInTheDocument();
    expect(screen.getByText('Biggest leak')).toBeInTheDocument();
    expect(screen.getByText('Profit factor')).toBeInTheDocument();

    // Pillars carry actual edge/leak labels from the demo edge-leak data
    expect(screen.getByText('9 AM-10 AM')).toBeInTheDocument();
    expect(screen.getByText('2 PM-3 PM')).toBeInTheDocument();

    expect(container.textContent).not.toContain('NaN');
  });

  it('EdgeLeakCard + StrategyCard render their buckets without NaN', async () => {
    const { container } = renderWithRouter(
      <div>
        <EdgeLeakCard days={30} />
        <StrategyCard days={30} />
      </div>
    );

    expect(await screen.findByText('Where you make money')).toBeInTheDocument();
    expect(screen.getByText('Where you lose money')).toBeInTheDocument();
    expect(screen.getByText('Thursday')).toBeInTheDocument();

    expect(container.textContent).not.toContain('NaN');
  });
});
