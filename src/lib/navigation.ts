/**
 * The canonical navigation structure — one source of truth for every platform.
 *
 * DESIGN_SYSTEM.md §24: grouping and labels never differ between desktop and
 * mobile. Desktop renders this as a sidebar; mobile renders the primary items in
 * the bottom bar and the groups in the "More" sheet. Both import from here, so
 * they cannot drift apart the way they previously had (My Rules sat ungrouped on
 * desktop but under Risk on mobile, and "Account" existed only on mobile).
 *
 * Adding a screen means adding it here, once.
 */
import type { ElementType } from 'react';
import {
  LayoutDashboard, TrendingUp, Bell, MessageSquare,
  Brain, BookOpen, ScrollText, Scale, Search, Settings,
} from 'lucide-react';

export interface NavItem {
  name: string;
  href: string;
  icon: ElementType;
  /** Renders the unread-alert count. Only Alerts carries one. */
  hasBadge?: boolean;
}

export interface NavGroup {
  /** null = the primary, unlabelled group at the top. */
  label: string | null;
  items: NavItem[];
}

/** Always reachable in one tap: the four screens a trader uses during a session. */
export const NAV_PRIMARY: NavItem[] = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Analytics', href: '/analytics', icon: TrendingUp },
  { name: 'Alerts',    href: '/alerts',    icon: Bell, hasBadge: true },
  { name: 'Chat',      href: '/chat',      icon: MessageSquare },
];

/** Everything else, grouped. Mobile shows these in the "More" sheet. */
export const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Insights',
    items: [
      { name: 'Reports',     href: '/reports',     icon: BookOpen },
      { name: 'Journal',      href: '/journal',     icon: ScrollText },
    ],
  },
  {
    label: 'Risk',
    items: [
      { name: 'My Rules',  href: '/my-rules',  icon: Scale },
      { name: 'My Record', href: '/my-record', icon: Search },
    ],
  },
  {
    label: 'Account',
    items: [
      { name: 'Settings', href: '/settings', icon: Settings },
    ],
  },
];

/** The full sidebar order: primary first, then each labelled group. */
export const NAV_SECTIONS: NavGroup[] = [
  { label: null, items: NAV_PRIMARY },
  ...NAV_GROUPS,
];

/** Flat list of the non-primary items, for the mobile active-state check. */
export const NAV_MORE_ITEMS: NavItem[] = NAV_GROUPS.flatMap(g => g.items);
