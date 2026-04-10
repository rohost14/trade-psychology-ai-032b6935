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
