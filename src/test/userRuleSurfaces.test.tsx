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
import { render, screen, waitFor } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// ── /api/constitution/effective, controlled per test ──────────────────────
let effectivePayload: unknown = null;

vi.mock('@/lib/api', () => ({
  api: {
    get: (url: string) => {
      if (url === '/api/constitution/effective') {
        return Promise.resolve({ data: effectivePayload });
      }
      return Promise.resolve({ data: {} });
    },
  },
}));

import { ProfileTab } from '@/components/settings/ProfileTab';
import EnforcedRules from '@/components/rules/EnforcedRules';
import type { UserProfile } from '@/lib/settingsConstants';

const blank = (over: Partial<UserProfile> = {}): UserProfile =>
  ({ display_name: '', ...over } as UserProfile);

describe('ProfileTab — an unset rule is shown as unset', () => {
  it('does not highlight any options-exit preset when the value is NULL', () => {
    render(<ProfileTab profile={blank({ sl_percent_options: null })} setProfile={() => {}} />);

    // "Not set" is a real option, and it is the selected one.
    const notSet = screen.getByRole('button', { name: 'Not set' });
    expect(notSet.className).toContain('bg-tm-brand');

    // No preset may claim to be the trader's choice.
    for (const pct of ['30%', '50%', '70%', '100%']) {
      expect(screen.getByRole('button', { name: pct }).className).not.toContain('bg-tm-brand');
    }
  });

  it('highlights exactly the declared preset when one is set', () => {
    render(<ProfileTab profile={blank({ sl_percent_options: 30 })} setProfile={() => {}} />);

    expect(screen.getByRole('button', { name: '30%' }).className).toContain('bg-tm-brand');
    expect(screen.getByRole('button', { name: '50%' }).className).not.toContain('bg-tm-brand');
    expect(screen.getByRole('button', { name: 'Not set' }).className).not.toContain('bg-tm-brand');
  });

  it('shows a value that is not one of its presets, rather than nothing', () => {
    // My Rules accepts any value in 0.1-100. A 45% rule matched no preset, so
    // this control would have rendered a real declared rule as unselected -
    // the fabrication defect in reverse, and the worse direction of it.
    render(<ProfileTab profile={blank({ sl_percent_options: 45 })} setProfile={() => {}} />);

    expect(screen.getByRole('button', { name: '45%' }).className).toContain('bg-tm-brand');
    expect(screen.getByRole('button', { name: 'Not set' }).className).not.toContain('bg-tm-brand');
  });

  it('clears the rule to null rather than to a number', () => {
    const seen: Array<UserProfile> = [];
    render(
      <ProfileTab
        profile={blank({ sl_percent_options: 50 })}
        setProfile={(p) => seen.push(p)}
      />,
    );

    screen.getByRole('button', { name: 'Not set' }).click();
    expect(seen).toHaveLength(1);
    expect(seen[0].sl_percent_options).toBeNull();
  });

  it('says "Not set" for an undeclared exposure rule instead of showing 10%', () => {
    render(
      <ProfileTab
        profile={blank({ max_position_size: null, sl_percent_options: 30 })}
        setProfile={() => {}}
      />,
    );

    // Scoped to the slider's readout: the options-exit control renders a "Not
    // set" BUTTON unconditionally, because it is an option there rather than a
    // state. This one is the value display, and it must not read "10%".
    expect(screen.getByText('Not set', { selector: 'span' })).toBeTruthy();
    expect(screen.queryByText('10%')).toBeNull();
    // The caption must not describe a default the trader has not accepted.
    expect(screen.queryByText(/Default: 10%/)).toBeNull();
  });

  it('shows the declared exposure rule when there is one', () => {
    render(<ProfileTab profile={blank({ max_position_size: 4 })} setProfile={() => {}} />);
    expect(screen.getByText('4%')).toBeTruthy();
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
