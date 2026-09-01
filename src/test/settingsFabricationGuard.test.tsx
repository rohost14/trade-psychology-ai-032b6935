/**
 * The Settings fabrication race, pinned.
 *
 * THE BUG THIS EXISTS TO PREVENT
 *
 * `Settings.tsx` seeds its editable state with hardcoded values - among them
 * max_position_size 10, sl_percent_options 50, guardian_enabled false and
 * whatsapp_enabled false. (sl_percent_futures and cooldown_after_loss were
 * in this list until they were removed as user inputs on 2026-09-02.)
 *
 * The render guard already refused to show the form after a FAILED profile
 * load, for exactly the right reason - the comment in the file says so. What it
 * did not cover was a PENDING one. The broker context usually resolves first,
 * so the form rendered from those hardcoded values while the profile was still
 * in flight. Any edit set `isDirty`, which permanently disables the seeding
 * effect, so the server values never arrived - and Save wrote the defaults.
 *
 * Thirteen fields could be written that way. Three are RULE_FIELDS, and because
 * 10 and 50 are TIGHTER than nothing the constitution gate accepted them
 * instantly with no friction. Two others silently switched protections OFF.
 *
 * Evidence: docs/DEEP_REVIEW/SETTINGS_LIFECYCLE_INVESTIGATION.md
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// ── the server profile every test controls ────────────────────────────────
let resolveProfile: ((v: unknown) => void) | null = null;
let profilePayload: Record<string, unknown> = {};
const putCalls: Array<Record<string, unknown>> = [];

vi.mock('@/lib/api', () => ({
  api: {
    get: (url: string) => {
      if (url === '/api/profile/') {
        // Deliberately controllable: a test can hold this pending.
        return new Promise((res) => {
          resolveProfile = () =>
            res({ data: { profile: profilePayload, needs_onboarding: false } });
        });
      }
      return Promise.resolve({ data: {} });
    },
    post: () => Promise.resolve({ data: {} }),
    put: (_url: string, body: Record<string, unknown>) => {
      putCalls.push(body);
      return Promise.resolve({ data: { success: true } });
    },
    delete: () => Promise.resolve({ data: {} }),
  },
  apiDetailString: (_d: unknown, fallback: string) => fallback,
  AUTH_TOKEN_KEY: 'tradementor_token',
  getAuthToken: () => null,
}));

vi.mock('@/contexts/BrokerContext', () => ({
  useBroker: () => ({
    isConnected: true,
    isLoading: false,          // broker resolves FIRST - the race condition
    account: { id: 'acct-1', broker_user_id: 'AB1234', last_sync_at: null },
    connect: vi.fn(),
    disconnect: vi.fn(),
  }),
}));

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import Settings from '@/pages/Settings';

function renderSettings() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Settings />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  resolveProfile = null;
  putCalls.length = 0;
  profilePayload = {};
});

describe('Settings — the profile-pending guard', () => {
  it('does not render the form while the profile request is pending', async () => {
    renderSettings();

    // The broker has resolved; the profile has not. This is the exact window.
    await screen.findByTestId('settings-loading');

    // None of the fabricable controls may exist yet.
    expect(screen.queryByText(/I exit options when premium drops by/i)).toBeNull();
    expect(screen.queryByText(/Max per options trade/i)).toBeNull();
  });

  it('does not offer Save while the profile request is pending', async () => {
    renderSettings();
    await screen.findByTestId('settings-loading');

    // Not merely disabled - absent. A disabled button one re-render away from
    // being enabled is the same trap.
    expect(screen.queryByRole('button', { name: /save all settings/i })).toBeNull();
  });

  it('renders the form once the profile arrives', async () => {
    profilePayload = { max_position_size: null, sl_percent_options: null };
    renderSettings();

    await screen.findByTestId('settings-loading');
    resolveProfile?.(null);

    expect(
      await screen.findByRole('button', { name: /save all settings/i }),
    ).toBeInTheDocument();
    expect(screen.queryByTestId('settings-loading')).toBeNull();
  });

  it('an unrelated save does NOT manufacture the optional rules from NULL', async () => {
    // The whole point. Server says "no rule set"; the trader edits something
    // else entirely; the optional rules must not acquire 10 / 50 / 1.0.
    profilePayload = {
      max_position_size: null,
      sl_percent_options: null,
      daily_loss_limit: null,
      guardian_enabled: true,
      whatsapp_enabled: true,
      alert_sensitivity: 'high',
      experience_level: 'professional',
    };
    renderSettings();
    await screen.findByTestId('settings-loading');
    resolveProfile?.(null);

    const save = await screen.findByRole('button', { name: /save all settings/i });
    await act(async () => { fireEvent.click(save); });

    await waitFor(() => expect(putCalls.length).toBe(1));
    const body = putCalls[0];

    expect(body.max_position_size).toBeNull();
    expect(body.sl_percent_options).toBeNull();

    // and the values that WERE set round-trip untouched
    expect(body.guardian_enabled).toBe(true);
    expect(body.whatsapp_enabled).toBe(true);
    expect(body.alert_sensitivity).toBe('high');
    expect(body.experience_level).toBe('professional');
  });

  it('stored optional-rule values round-trip unchanged', async () => {
    profilePayload = {
      max_position_size: 25,
      sl_percent_options: 70,
    };
    renderSettings();
    await screen.findByTestId('settings-loading');
    resolveProfile?.(null);

    const save = await screen.findByRole('button', { name: /save all settings/i });
    await act(async () => { fireEvent.click(save); });

    await waitFor(() => expect(putCalls.length).toBe(1));
    expect(putCalls[0].max_position_size).toBe(25);
    expect(putCalls[0].sl_percent_options).toBe(70);
  });

  it('an explicit selection still persists', async () => {
    profilePayload = { sl_percent_options: null, max_position_size: null };
    renderSettings();
    await screen.findByTestId('settings-loading');
    resolveProfile?.(null);
    await screen.findByRole('button', { name: /save all settings/i });

    // Click the 70% preset under "I exit options when premium drops by".
    const seventy = screen.getAllByRole('button', { name: '70%' })[0];
    await act(async () => { fireEvent.click(seventy); });
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: /save all settings/i })); });

    await waitFor(() => expect(putCalls.length).toBe(1));
    expect(putCalls[0].sl_percent_options).toBe(70);
    // the rule the trader did NOT touch stays unset
    expect(putCalls[0].max_position_size).toBeNull();
  });

  it('no longer exposes the removed user inputs', async () => {
    // sl_percent_futures and cooldown_after_loss stopped being user inputs on
    // 2026-09-02. The controls are gone and the payload must not carry them -
    // a leftover key would keep writing a value nobody can see or change.
    profilePayload = { max_position_size: null, sl_percent_options: null };
    renderSettings();
    await screen.findByTestId('settings-loading');
    resolveProfile?.(null);

    const save = await screen.findByRole('button', { name: /save all settings/i });
    expect(screen.queryByText(/My typical stop-loss on futures/i)).toBeNull();
    expect(screen.queryByText(/I wait after a loss before re-entering/i)).toBeNull();

    await act(async () => { fireEvent.click(save); });
    await waitFor(() => expect(putCalls.length).toBe(1));
    expect('sl_percent_futures' in putCalls[0]).toBe(false);
    expect('cooldown_after_loss' in putCalls[0]).toBe(false);
  });
});

/**
 * CONTRACT — the guard itself, not one symptom of it.
 *
 * The bug was not a wrong condition. It was a RIGHT condition that existed and
 * was never wired: `isLoadingProfile` was computed and referenced nowhere, so
 * the form rendered from hardcoded state while the profile was in flight. These
 * assertions fail if that happens again, including to a field that does not
 * exist yet - a new key added to the Settings payload with a concrete default
 * is covered automatically, because the guard is on the whole form.
 */
describe('Settings — guard contract', () => {
  const src = readFileSync(resolve(process.cwd(), 'src/pages/Settings.tsx'), 'utf-8');

  it('derives the loading flag from the profile query', () => {
    expect(src).toMatch(/const\s+isLoadingProfile\s*=\s*profileQuery\.isPending/);
  });

  it('uses it — assigned-but-unused is the exact bug', () => {
    const uses = src.split('isLoadingProfile').length - 1;
    // one declaration + at least the two render gates
    expect(uses).toBeGreaterThanOrEqual(3);
  });

  it('gates BOTH the Save action and the form on it', () => {
    // Every JSX gate that renders form content must carry the flag. Counting
    // rather than matching one site, so moving a block cannot silently drop it.
    const gates = src.match(/isConnected && !profileError && !isLoadingProfile/g) || [];
    expect(gates.length).toBeGreaterThanOrEqual(2);
  });

  it('renders a loading state instead of the form while pending', () => {
    expect(src).toMatch(/isConnected && !profileError && isLoadingProfile/);
    expect(src).toContain('data-testid="settings-loading"');
  });

  it('the payload is still built from component state, so the guard is what protects it', () => {
    // If this ever stops being true the guard is no longer sufficient and this
    // whole test file needs rethinking - which is the point of asserting it.
    expect(src).toMatch(/const payload = \{/);
    expect(src).toMatch(/api\.put\('\/api\/profile\/', payload\)/);
  });
});
