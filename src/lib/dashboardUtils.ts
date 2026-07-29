// Dashboard session-state utilities — extracted from Dashboard.tsx

export const STATE_CFG = {
  stable: {
    label:  'On Track',
    pill:   'bg-teal-100 dark:bg-teal-900/40 text-teal-700 dark:text-teal-300',
    dot:    'bg-teal-500',
    accent: 'border-l-[3px] border-l-teal-400 dark:border-l-teal-500',
  },
  caution: {
    label:  'Patterns',          // behavioral patterns noted — NOT financial caution
    pill:   'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300',
    dot:    'bg-amber-500',
    accent: 'border-l-[3px] border-l-amber-400 dark:border-l-amber-500',
  },
  risk: {
    label:  'High Alert',        // multiple/critical patterns — review immediately
    pill:   'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300',
    dot:    'bg-red-500',
    accent: 'border-l-[3px] border-l-red-400 dark:border-l-red-500',
  },
};

export type SessionState = keyof typeof STATE_CFG;

export function getSessionState(unreadCount: number, highSevCount: number): SessionState {
  if (highSevCount >= 2 || unreadCount >= 5) return 'risk';
  if (highSevCount >= 1 || unreadCount >= 2) return 'caution';
  return 'stable';
}

export function getSessionDesc(
  state: SessionState,
  unreadCount: number,
  tradesCount: number,
  winRate: number,
): string {
  if (state === 'risk') {
    return unreadCount >= 2
      ? `${unreadCount} high-severity pattern${unreadCount !== 1 ? 's' : ''} active — review before your next trade`
      : 'Multiple patterns detected — trade with extra caution this session';
  }
  if (state === 'caution') {
    if (unreadCount > 0)
      return `${unreadCount} behavioral pattern${unreadCount !== 1 ? 's' : ''} noted — review before continuing`;
    return 'Session elevated — stay within your plan';
  }
  if (tradesCount === 0) return 'No trades yet — session tracking is ready';
  if (winRate > 0 && winRate < 40) return `Win rate at ${winRate}% — focus on setup quality, not frequency`;
  return 'Session tracking normally — keep following your plan';
}

export function getISTMidnightUTC(): Date {
  const IST_OFFSET_MS = 5.5 * 60 * 60 * 1000;
  const nowIST = new Date(Date.now() + IST_OFFSET_MS);
  nowIST.setUTCHours(0, 0, 0, 0);
  return new Date(nowIST.getTime() - IST_OFFSET_MS);
}

/**
 * Start of the current trading SESSION (09:15 IST), as a UTC Date.
 * Before today's open it points at the previous trading day, and it skips
 * weekends — so the dashboard keeps showing (and lets you journal) the last
 * session's closed trades until the next 09:15, instead of going blank at
 * midnight. (Exchange holidays aren't special-cased — a rare, harmless edge.)
 */
export function getLastSessionStartUTC(): Date {
  const IST_OFFSET_MS = 5.5 * 60 * 60 * 1000;
  const OPEN_MIN = 9 * 60 + 15; // 09:15 IST
  const ist = new Date(Date.now() + IST_OFFSET_MS);
  const nowMin = ist.getUTCHours() * 60 + ist.getUTCMinutes();
  ist.setUTCHours(9, 15, 0, 0);
  if (nowMin < OPEN_MIN) ist.setUTCDate(ist.getUTCDate() - 1);
  // Skip Sat (6) / Sun (0) back to Friday.
  while (ist.getUTCDay() === 0 || ist.getUTCDay() === 6) {
    ist.setUTCDate(ist.getUTCDate() - 1);
  }
  return new Date(ist.getTime() - IST_OFFSET_MS);
}

export function formatTimeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins} min ago`;
  if (diffHours < 24) return `${diffHours} hours ago`;
  return date.toLocaleDateString();
}
