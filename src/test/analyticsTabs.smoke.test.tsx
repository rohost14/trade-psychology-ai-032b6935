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
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
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
import HabitsTab from '@/components/analytics/HabitsTab';
import BehaviourLead from '@/components/analytics/BehaviourLead';
import PnlCalendar from '@/components/analytics/PnlCalendar';
import ReportCard from '@/components/analytics/ReportCard';
import EdgeLeakCard from '@/components/analytics/EdgeLeakCard';
import StrategyCard from '@/components/analytics/StrategyCard';

// BrokerProvider as well as the router: BehaviorTab reaches useBroker through a
// child, and useBroker throws outside a provider rather than degrading. Without
// it the smoke test fails on the harness rather than on the component.
//
// QueryClientProvider for the tabs on useApiQuery — useQuery throws outside one.
// A FRESH client per render, with retries off and gc immediate: a client shared
// between tests would let one test's cached response satisfy the next one's
// query, so a component that had stopped fetching entirely would still pass.
function renderWithRouter(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <BrokerProvider>{ui}</BrokerProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Analytics tab render smoke (demo data, backend-shaped)', () => {
  it('OverviewTab renders KPIs, edge banner and charts without NaN', async () => {
    const { container } = renderWithRouter(<OverviewTab days={30} />);

    // KPI strip carries only what the ReportCard hero above does NOT state.
    // Win rate and profit factor were removed on purpose -- the hero has them,
    // and printing them twice 400px apart was the page's worst duplication.
    expect(await screen.findByText('Expectancy')).toBeInTheDocument();
    expect(screen.getByText('Win Days')).toBeInTheDocument();
    expect(screen.getByText('Max Drawdown')).toBeInTheDocument();
    expect(screen.queryByText('Win Rate')).not.toBeInTheDocument();

    // Edge-confidence banner — demo verdict is 'too_few'
    expect(screen.getByText('Not enough trades yet')).toBeInTheDocument();

    // Charts + product mix
    expect(screen.getByText('Equity Curve')).toBeInTheDocument();
    expect(screen.getByText('Daily P&L')).toBeInTheDocument();
    expect(screen.getByText('Product Mix')).toBeInTheDocument();

    // Attribution is a ranked table now, not a donut (§20 bans donut/pie).
    expect(screen.getByText('Where the P&L came from')).toBeInTheDocument();

    expect(container.textContent).not.toContain('NaN');
  });

  // HabitsTab was the one tab this file never covered, and it is the one that
  // shipped the regression: DEMO_HABITS called the bucket figure `pnl` while the
  // component (and habits_service.py) use `net_pnl`, so every bar printed "₹NaN",
  // took the loss colour because NaN >= 0 is false, and stretched to full width
  // because a NaN width is dropped and the bar's `inset: 0` takes over. Asserting
  // a real figure is present matters as much as the NaN check — a tab that
  // rendered nothing at all would satisfy "no NaN" on its own.
  it('HabitsTab renders after-loss drift and signed bucket bars without NaN', async () => {
    const { container } = renderWithRouter(<HabitsTab days={30} />);

    expect(await screen.findByText('After a loss, do you size up?')).toBeInTheDocument();
    expect(screen.getByText('Time of day')).toBeInTheDocument();
    expect(screen.getByText('Day of week')).toBeInTheDocument();
    expect(screen.getByText('By instrument')).toBeInTheDocument();

    // Real figures, correctly signed — the bug rendered these as "₹NaN".
    expect(screen.getByText('₹5,100')).toBeInTheDocument();   // 09:00 bucket
    expect(screen.getByText('-₹14,270')).toBeInTheDocument(); // 14:00 bucket
    expect(screen.getByText('-₹6,500')).toBeInTheDocument();  // SOLARINDS

    expect(container.textContent).not.toContain('NaN');
  });

  it('BehaviorTab renders the tendency cards it still owns, without NaN', async () => {
    const { container } = renderWithRouter(<BehaviorTab days={30} />);

    // Pattern frequency moved to Alerts with the rest of the alert-derived
    // blocks; BehaviorTab keeps the trade- and journal-derived tendencies.
    expect(await screen.findByText('After a loss')).toBeInTheDocument();
    expect(screen.queryByText('Pattern Frequency')).not.toBeInTheDocument();

    // Conditional-performance cards (conditions[] array consumption)
    expect(screen.getByText('Opening 30 minutes')).toBeInTheDocument();

    // Options behaviour card (crashed in guest mode before the shape fix).
    // It fetches on its own timeline — await its render separately.
    expect(await screen.findByText('Options behaviour')).toBeInTheDocument();

    expect(container.textContent).not.toContain('NaN');
  });

  it('SessionsTab renders calendar, opening/expiry cards and expiry comparison without NaN', async () => {
    const { container } = renderWithRouter(<SessionsTab days={30} />);

    // The P&L calendar moved to the Behaviour tab; SessionsTab keeps the
    // session-window analysis only.
    expect(await screen.findByText('Opening 30 Minutes (9:15–9:45)')).toBeInTheDocument();

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

    expect(screen.getByText(/^Best \d+ Trades?$/)).toBeInTheDocument();
    expect(screen.getByText(/^Worst \d+ Trades?$/)).toBeInTheDocument();
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

  it('BehaviourLead states the leak, the money and one action', async () => {
    const { container } = renderWithRouter(<BehaviourLead days={30} />);

    // The whole point of this block: a plain-language sentence carrying the
    // number, plus one concrete action. A correlation with no action is the
    // documented failure state for reflection products.
    expect(await screen.findByText(/Your biggest leak/i)).toBeInTheDocument();
    expect(screen.getByText(/revenge trades/i)).toBeInTheDocument();
    expect(screen.getByText('−₹13,000')).toBeInTheDocument();

    const action = screen.getByRole('link', { name: /cooldown after a loss/i });
    expect(action).toHaveAttribute('href', '/my-rules');

    // True minus, never an ASCII hyphen, on any money figure.
    expect(container.textContent).not.toMatch(/-₹/);
    expect(container.textContent).not.toContain('NaN');
  });

  it('PnlCalendar renders the months the period covers', async () => {
    const { container } = renderWithRouter(<PnlCalendar days={30} />);

    expect(await screen.findByText('When you trade well')).toBeInTheDocument();
    // 30 days back from today spans this month and the previous one.
    expect(screen.getAllByText(/^(January|February|March|April|May|June|July|August|September|October|November|December) \d{4}$/).length)
      .toBeGreaterThanOrEqual(1);

    expect(container.textContent).not.toContain('NaN');
  });
});
