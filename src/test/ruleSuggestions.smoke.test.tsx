/**
 * Render-smoke test for RuleSuggestions against the demo dataset.
 *
 * Same guard as analyticsTabs.smoke: the guest fixture is supposed to mirror
 * the real backend response, and when it has not, the component renders
 * nothing at all rather than failing — which is how two guest-mode bugs shipped
 * (DEMO_HABITS using `pnl` for `net_pnl`, and session-log having no stub).
 *
 * A suggestion component that silently renders "your rules already match your
 * data" because the payload shape was wrong is exactly that failure again: it
 * looks like a working feature with nothing to say.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { getGuestResponse } from '@/lib/guestMode';

vi.mock('@/lib/api', () => ({
  api: {
    get: (url: string) => Promise.resolve({ data: getGuestResponse(url, 'GET') }),
    post: () => Promise.resolve({ data: { success: true } }),
    put: () => Promise.resolve({ data: { success: true } }),
    delete: () => Promise.resolve({ data: { success: true } }),
  },
  apiDetailString: (_detail: unknown, fallback: string) => fallback,
  AUTH_TOKEN_KEY: 'tradementor_token',
  getAuthToken: () => null,
}));

import RuleSuggestions from '@/components/rules/RuleSuggestions';

function renderWithProviders(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('RuleSuggestions (demo data, backend-shaped)', () => {
  it('renders each suggestion with its headline and evidence', async () => {
    renderWithProviders(<RuleSuggestions />);

    await waitFor(() => {
      expect(screen.getByText(/Rules your trading suggests/i)).toBeInTheDocument();
    });

    // Both demo suggestions must appear — not the "nothing to change" copy.
    await waitFor(() => {
      expect(screen.getByText(/Set your daily loss limit to/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Stop after 2 consecutive losses/i)).toBeInTheDocument();

    // Evidence rows are the whole point of the feature.
    expect(screen.getByText(/Red sessions in this window/i)).toBeInTheDocument();
    expect(screen.getByText(/Your win rate the rest of the time/i)).toBeInTheDocument();

    // Every suggestion is actionable.
    expect(screen.getAllByRole('button', { name: /Set rule/i })).toHaveLength(2);
  });

  it('paints no NaN and does not claim there is nothing to change', async () => {
    const { container } = renderWithProviders(<RuleSuggestions />);
    await waitFor(() => {
      expect(screen.getByText(/Set your daily loss limit to/i)).toBeInTheDocument();
    });
    expect(container.textContent).not.toContain('NaN');
    expect(container.textContent).not.toMatch(/already match what your trading data supports/i);
  });
});
