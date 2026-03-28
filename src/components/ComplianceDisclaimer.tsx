import { AlertTriangle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';

interface ComplianceDisclaimerProps {
  variant?: 'inline' | 'footer';
  className?: string;
}

/**
 * SEBI compliance disclaimer — required on all AI coach and analytics screens.
 * TradeMentor AI is NOT a SEBI-registered Investment Adviser or Research Analyst.
 */
export default function ComplianceDisclaimer({
  variant = 'inline',
  className,
}: ComplianceDisclaimerProps) {
  if (variant === 'footer') {
    return (
      <p className={cn('text-xs text-muted-foreground text-center', className)}>
        TradeMentor AI provides <strong>behavioral analytics only</strong> — not investment
        advice.{' '}
        <Link to="/terms" className="underline hover:text-foreground">
          Terms
        </Link>{' '}
        ·{' '}
        <Link to="/privacy" className="underline hover:text-foreground">
          Privacy
        </Link>
      </p>
    );
  }

  return (
    <div
      className={cn(
        'flex items-start gap-2 px-4 py-2.5 rounded-lg bg-muted/40 border border-border/50',
        className
      )}
    >
      <AlertTriangle className="h-3.5 w-3.5 text-muted-foreground mt-0.5 shrink-0" aria-hidden="true" />
      <p className="text-xs text-muted-foreground leading-relaxed">
        <strong className="text-foreground font-medium">Not investment advice.</strong>{' '}
        TradeMentor AI analyses your <em>behaviour</em>, not the market. It is not a SEBI-registered
        Investment Adviser or Research Analyst. Nothing shown here constitutes advice to buy, sell,
        or hold any security.{' '}
        <Link to="/terms" className="underline hover:text-foreground">
          Terms
        </Link>{' '}
        ·{' '}
        <Link to="/privacy" className="underline hover:text-foreground">
          Privacy Policy
        </Link>
      </p>
    </div>
  );
}
