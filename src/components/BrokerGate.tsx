/**
 * The shared not-connected gate.
 *
 * Every data screen needs the same thing when no broker is attached: say what is
 * missing, say what it unlocks, offer one action. Six screens previously
 * hand-rolled it with drifting copy, icon sizes and raw palette tints — and My
 * Record had no gate at all, silently rendering a dead search box.
 *
 * DESIGN_SYSTEM.md §9 justification 3: a genuine aside, content that must read
 * as separate from the page's flow. That is why this one earns a card.
 *
 *   if (!isConnected) return <BrokerGate title="My Record" unlocks="…" />;
 */
import { Link2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useBroker } from '@/contexts/BrokerContext';

export default function BrokerGate({
  title,
  unlocks,
}: {
  /** Screen title, so the page still identifies itself while gated. */
  title: string;
  /** One sentence: what connecting gives them on THIS screen. */
  unlocks: string;
}) {
  const { connect } = useBroker();

  return (
    <div className="w-full pb-12">
      <div className="mb-5">
        <h1 className="text-[22px] font-semibold tracking-tight text-foreground">{title}</h1>
      </div>

      <div className="desk-card flex flex-col items-center justify-center text-center min-h-[50vh] px-6 py-16">
        <div className="p-4 rounded-full bg-primary/10 mb-5">
          <Link2 className="h-5 w-5 text-primary" />
        </div>
        <h2 className="text-[17px] font-semibold tracking-tight text-foreground mb-1">
          Connect your broker
        </h2>
        <p className="text-[14px] text-muted-foreground max-w-sm mb-5">{unlocks}</p>
        {/* Starts the OAuth flow directly — §12, minimum clicks. Sending the
            user to Settings to find the same button is a wasted hop. */}
        <Button onClick={() => connect()}>
          <Link2 className="h-4 w-4" />
          Connect Zerodha
        </Button>
      </div>
    </div>
  );
}
