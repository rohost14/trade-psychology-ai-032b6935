import { Link } from 'react-router-dom';
import { Bot, ArrowRight } from 'lucide-react';

export function AiCoachCta() {
  return (
    <Link
      to="/chat"
      className="tm-coach-cta flex items-center gap-3 rounded-xl p-4 hover:opacity-90 transition-opacity group"
    >
      <div className="w-9 h-9 rounded-lg bg-white/15 flex items-center justify-center shrink-0">
        <Bot className="w-4 h-4 text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-white">AI Trading Coach</p>
        <p className="text-[12px] text-white/70">Ask about your patterns or get a debrief</p>
      </div>
      <ArrowRight className="w-4 h-4 text-white/40 group-hover:text-white transition-colors shrink-0" />
    </Link>
  );
}
