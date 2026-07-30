import { describe, it, expect } from 'vitest';
import { NAV_PRIMARY, NAV_GROUPS, NAV_SECTIONS, NAV_MORE_ITEMS } from '@/lib/navigation';

/**
 * Locks the canonical navigation structure from DESIGN_SYSTEM.md §24.
 *
 * Desktop and mobile previously kept two hand-maintained lists and drifted:
 * My Rules sat ungrouped on desktop but under Risk on mobile, and "Account"
 * existed only on mobile. Both now read from `lib/navigation.ts`, and these
 * tests are what stop the structure quietly changing again.
 */

describe('canonical navigation (DESIGN_SYSTEM.md §24)', () => {
  it('primary group is the four session screens, in order', () => {
    expect(NAV_PRIMARY.map(i => i.name)).toEqual(['Dashboard', 'Analytics', 'Alerts', 'Chat']);
  });

  it('groups are Insights, Risk, Account — in order, with the specified members', () => {
    expect(NAV_GROUPS.map(g => g.label)).toEqual(['Insights', 'Risk', 'Account']);
    expect(NAV_GROUPS[0].items.map(i => i.name)).toEqual(['My Patterns', 'Reports', 'Journal']);
    expect(NAV_GROUPS[1].items.map(i => i.name)).toEqual(['My Rules', 'My Record']);
    expect(NAV_GROUPS[2].items.map(i => i.name)).toEqual(['Settings']);
  });

  it('sidebar order is the primary group followed by every labelled group', () => {
    expect(NAV_SECTIONS.map(s => s.label)).toEqual([null, 'Insights', 'Risk', 'Account']);
    expect(NAV_SECTIONS[0].items).toBe(NAV_PRIMARY);
  });

  it('covers all ten in-app screens exactly once', () => {
    const all = NAV_SECTIONS.flatMap(s => s.items.map(i => i.href));

    expect(new Set(all).size).toBe(all.length); // no duplicates
    expect(all.sort()).toEqual([
      '/alerts', '/analytics', '/chat', '/dashboard', '/journal',
      '/my-patterns', '/my-record', '/my-rules', '/reports', '/settings',
    ]);
  });

  it('mobile "More" carries exactly the non-primary screens', () => {
    const primary = new Set(NAV_PRIMARY.map(i => i.href));

    expect(NAV_MORE_ITEMS).toHaveLength(6);
    expect(NAV_MORE_ITEMS.some(i => primary.has(i.href))).toBe(false);
  });

  it('only Alerts carries the unread badge', () => {
    const badged = NAV_SECTIONS.flatMap(s => s.items).filter(i => i.hasBadge);

    expect(badged.map(i => i.name)).toEqual(['Alerts']);
  });

  it('every item has a name, a route and an icon', () => {
    for (const item of NAV_SECTIONS.flatMap(s => s.items)) {
      expect(item.name, 'name').toBeTruthy();
      expect(item.href, `${item.name} href`).toMatch(/^\//);
      expect(item.icon, `${item.name} icon`).toBeTruthy();
    }
  });
});
