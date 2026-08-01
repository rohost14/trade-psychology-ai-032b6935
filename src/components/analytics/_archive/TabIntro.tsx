import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

// Small editorial framing line at the top of each analytics tab. Insight-first:
// tell the trader in plain language what question this tab answers before the
// charts appear. Keeps the vocabulary human, not quant.
export default function TabIntro({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p className={cn(
      'text-[13px] text-muted-foreground leading-relaxed border-l-2 border-tm-brand/40 pl-3 mb-1',
      className,
    )}>
      {children}
    </p>
  );
}
