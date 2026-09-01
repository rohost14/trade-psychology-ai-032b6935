/**
 * An unset rule must look unset, and a percent must read as a percent.
 *
 * Two display defects, one class: the page told the trader a rule was in force
 * when it was not, or stated it in the wrong unit.
 *
 *   ProfileTab      `sl_percent_options ?? 50` highlighted the 50% preset for a
 *                   trader who had never chosen one, and the slider showed
 *                   `max_position_size ?? 10` under the caption "Default: 10%".
 *                   Neither value existed in the database. NULL means NO RULE -
 *                   Pattern 28 and the whole opt-in money-rule design rest on
 *                   that - so a control that renders a number instead is
 *                   claiming a promise the trader never made.
 *
 *   EnforcedRules   `max_position_size` sat in the MONEY set, so a 10% cap on
 *                   capital-at-risk was reported as the limit "₹10". The model
 *                   defines the column as a percent (`user_profile.py:84`) and
 *                   the entry check divides a capital requirement by
 *                   `trading_capital` to compare against it.
 *
 * Both rules also gained the ability to be set at all in the same pass, which
 * is why their display is worth pinning now: before this, `restricted_windows`
 * had no editor and `sl_percent_options` could not survive PUT /api/constitution/.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render as rtlRender, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import type { ReactElement } from 'react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// ── the constitution endpoints, controlled per test ───────────────────────
let effectivePayload: unknown = null;
let rulesPayload: Record<string, unknown> = {};
const putCalls: Array<Record<string, unknown>> = [];

vi.mock('@/lib/api', () => ({
  api: {
    get: (url: string) => {
      if (url === '/api/constitution/effective') {
        return Promise.resolve({ data: effectivePayload });
      }
      if (url === '/api/constitution/') {
        return Promise.resolve({
          data: { rules: rulesPayload, pending: null, accepted_at: null },
        });
      }
      if (url === '/api/constitution/status') return Promise.resolve({ data: { status: [] } });
      if (url === '/api/constitution/violations') {
        return Promise.resolve({ data: { today: [], total: 0, by_rule: {} } });
      }
      if (url === '/api/constitution/history') return Promise.resolve({ data: { history: [] } });
      return Promise.resolve({ data: {} });
    },
    put: (_url: string, body: Record<string, unknown>) => {
      putCalls.push(body);
      return Promise.resolve({ data: { change_type: 'tighten', applied: body, pending: {} } });
    },
  },
  apiDetailString: (_d: unknown, fallback: string) => fallback,
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

import { ProfileTab } from '@/components/settings/ProfileTab';
import EnforcedRules from '@/components/rules/EnforcedRules';
import MyRules from '@/pages/MyRules';
import type { UserProfile } from '@/lib/settingsConstants';

const blank = (over: Partial<UserProfile> = {}): UserProfile =>
  ({ display_name: '', ...over } as UserProfile);

// ProfileTab now links to My Rules, so it needs a router.
const render = (ui: ReactElement) => rtlRender(<MemoryRouter>{ui}</MemoryRouter>);

describe('ProfileTab — no longer edits any rule', () => {
  /**
   * WHERE THE SIX TESTS THAT STOOD HERE WENT.
   *
   * They exercised this tab's options-exit presets and exposure slider: that
   * NULL highlighted nothing, that "Not set" cleared to null, that a 45% value
   * from My Rules still displayed. Every one of those controls was removed on
   * 2026-09-02, because two editors for one rule had already diverged in what
   * they could express - this tab had four presets against My Rules' full
   * 0.1-100 range, and could not clear a rule at all, since clearing is a
   * loosen and needs an override confirmation only My Rules performs.
   *
   * The invariants are not dropped. They are asserted below against My Rules,
   * which is now the single editing surface. What remains to check here is
   * that the duplicate really is gone.
   */
  it('renders no rule control', () => {
    render(
      <ProfileTab
        profile={blank({ sl_percent_options: null, max_position_size: null })}
        setProfile={() => {}}
      />,
    );

    expect(screen.queryByText(/I exit options when premium drops by/)).toBeNull();
    expect(screen.queryByText(/Max per options trade/)).toBeNull();
    expect(screen.queryByLabelText(/My max trades per day/)).toBeNull();
  });

  it('cannot fabricate a rule value, because it holds none', () => {
    const seen: UserProfile[] = [];
    render(
      <ProfileTab
        profile={blank({ sl_percent_options: null, max_position_size: null })}
        setProfile={(p) => seen.push(p)}
      />,
    );

    // No control on this tab writes a rule field at all.
    expect(screen.queryByRole('button', { name: 'Not set' })).toBeNull();
    expect(seen).toHaveLength(0);
  });

  it('keeps trading capital, which is not a rule', () => {
    render(<ProfileTab profile={blank({ trading_capital: 500000 })} setProfile={() => {}} />);
    expect(screen.getByLabelText(/My trading capital/)).toBeTruthy();
  });
});

describe('EnforcedRules — every rule, in its own unit', () => {
  beforeEach(() => {
    effectivePayload = {
      has_baseline: false,
      ungoverned: {},
      rules: {
        daily_loss_limit:     { declared: 25000, effective: 25000, source: 'declared', overridden: false },
        per_trade_loss_limit: { declared: 6000,  effective: 6000,  source: 'declared', overridden: false },
        max_position_size:    { declared: 10,    effective: 10,    source: 'declared', overridden: false },
        sl_percent_options:   { declared: null,  effective: null,  source: 'unset',    overridden: false },
      },
    };
  });

  it('reports a percent rule as a percent, not as rupees', async () => {
    render(<EnforcedRules status={[]} />);

    await waitFor(() => expect(screen.getByText('Max risk per trade')).toBeTruthy());
    expect(screen.getByText('10%')).toBeTruthy();
    expect(screen.queryByText('₹10')).toBeNull();
  });

  it('reports an unset rule as "Not set" rather than an em dash', async () => {
    render(<EnforcedRules status={[]} />);

    await waitFor(() => expect(screen.getByText('I exit a losing option at')).toBeTruthy());
    expect(screen.getByText('Not set')).toBeTruthy();
  });

  it('lists the rules that were previously invisible', async () => {
    render(<EnforcedRules status={[]} />);

    // per_trade_loss_limit shipped with no label, so the rules page never
    // mentioned a rule the engine enforces on every closed trade.
    await waitFor(() => expect(screen.getByText('Per-trade loss limit')).toBeTruthy());
    expect(screen.getByText('I exit a losing option at')).toBeTruthy();
  });

  it('no longer offers the removed cooldown rule', async () => {
    effectivePayload = {
      has_baseline: false,
      ungoverned: {},
      // A stale server could still send it; it must not be rendered as a rule.
      rules: {
        cooldown_after_loss: { declared: 15, effective: 15, source: 'declared', overridden: false },
        daily_loss_limit:    { declared: 25000, effective: 25000, source: 'declared', overridden: false },
      },
    };
    render(<EnforcedRules status={[]} />);

    await waitFor(() => expect(screen.getByText('Daily loss limit')).toBeTruthy());
    expect(screen.queryByText('Cooldown after a loss')).toBeNull();
  });
});

describe('MyRules — the invariants that moved here from Settings', () => {
  /**
   * These are the assertions the ProfileTab block used to make. They test the
   * same promises against the surface that now keeps them: an unset rule shows
   * nothing rather than a number, a set rule shows its own value whatever it
   * is, and clearing sends an explicit null rather than a default.
   */
  const openEditor = async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    rtlRender(
      <MemoryRouter>
        <QueryClientProvider client={qc}>
          <MyRules />
        </QueryClientProvider>
      </MemoryRouter>,
    );
    const edit = await screen.findByRole('button', { name: /edit rules/i });
    await act(async () => { fireEvent.click(edit); });
    return screen.getByLabelText(/Exit a losing option at/i) as HTMLInputElement;
  };

  beforeEach(() => { putCalls.length = 0; });

  it('shows an EMPTY field for an unset rule, never a default', async () => {
    rulesPayload = { sl_percent_options: null, restricted_windows: [] };
    const input = await openEditor();

    // The defect this replaces: ProfileTab highlighted "50%" for exactly this
    // state, presenting a value that was in no database as the trader's own.
    expect(input.value).toBe('');
  });

  it('shows a value that no preset could have expressed', async () => {
    // ProfileTab offered 30/50/70/100 only, so a 45% rule was unrepresentable
    // there - the reason one editor had to win.
    rulesPayload = { sl_percent_options: 45, restricted_windows: [] };
    const input = await openEditor();
    expect(input.value).toBe('45');
  });

  it('clears a rule to null rather than to a number', async () => {
    rulesPayload = { sl_percent_options: 50, restricted_windows: [] };
    const input = await openEditor();

    await act(async () => { fireEvent.change(input, { target: { value: '' } }); });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /save rules/i }));
    });

    await waitFor(() => expect(putCalls.length).toBe(1));
    expect(putCalls[0].sl_percent_options).toBeNull();
  });

  it('sends a set value through the change gate', async () => {
    rulesPayload = { sl_percent_options: null, restricted_windows: [] };
    const input = await openEditor();

    await act(async () => { fireEvent.change(input, { target: { value: '30' } }); });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /save rules/i }));
    });

    await waitFor(() => expect(putCalls.length).toBe(1));
    expect(putCalls[0].sl_percent_options).toBe(30);
    // Blank window rows never reach the API - see the validator.
    expect(putCalls[0].restricted_windows).toEqual([]);
  });
});

describe('MyRules — the two rules are editable at all', () => {
  const source = readFileSync(
    resolve(process.cwd(), 'src/pages/MyRules.tsx'), 'utf-8',
  );

  it('offers an options-exit field in the edit dialog', () => {
    expect(source).toContain("['sl_percent_options',");
  });

  it('offers a no-trade window editor, which never existed before', () => {
    expect(source).toContain('No-trade windows (IST)');
    expect(source).toContain('Add a window');
  });

  it('strips blank window rows before saving', () => {
    // An empty input is a half-typed window, not a rule; sending it would be
    // rejected by the API validator and read as a change that was never made.
    expect(source).toContain('.map(w => w.trim()).filter(Boolean)');
  });

  it('no longer computes a cooldown status the API stopped sending', () => {
    expect(source).not.toContain("s.rule === 'cooldown'");
  });
});
