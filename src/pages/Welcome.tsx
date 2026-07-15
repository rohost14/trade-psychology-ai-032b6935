/**
 * Welcome.tsx — Homepage redesign
 * Reference: Zerodha, Sensibull, Tickertape
 * Theme: light + dark via useTheme()
 * Font: Plus Jakarta Sans (display) + JetBrains Mono (data)
 */
import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  Shield, Brain, Bell, BarChart3, ArrowRight, Eye,
  Activity, Check, Target, ChevronDown, Sun, Moon,
  Lock, TrendingDown, AlertCircle, Zap,
} from 'lucide-react';
import { useBroker } from '@/contexts/BrokerContext';
import { useTheme } from '@/components/ThemeProvider';
import LiveHeroTerminal from '@/components/LiveHeroTerminal';
import LossSpiralSimulator from '@/components/LossSpiralSimulator';
import { FeatureStory, AlertFeedMock, ShieldMock, CoachMock, type Story } from '@/components/FeatureStory';

const FONT_URL =
  'https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap';

// ── per-theme tokens ────────────────────────────────────────────────────────
const LIGHT = {
  bg:         '#ffffff',
  bg2:        '#f8fafc',
  bg3:        '#f1f5f9',
  card:       '#ffffff',
  border:     '#e2e8f0',
  border2:    '#cbd5e1',
  text:       '#0f172a',
  sub:        '#475569',
  dim:        '#94a3b8',
  primary:    '#0d9488',
  primaryBg:  '#f0fdfa',
  primaryBdr: '#99f6e4',
  shadow:     '0 1px 3px rgba(0,0,0,0.08),0 1px 2px rgba(0,0,0,0.04)',
  shadowMd:   '0 4px 12px rgba(0,0,0,0.08),0 2px 4px rgba(0,0,0,0.03)',
  navBg:      'rgba(255,255,255,0.92)',
  red:        '#ef4444',  redBg:     '#fef2f2',
  orange:     '#f97316',  orangeBg:  '#fff7ed',
  yellow:     '#f59e0b',  yellowBg:  '#fffbeb',
  green:      '#16a34a',  greenBg:   '#f0fdf4',
};
const DARK = {
  bg:         '#0f172a',
  bg2:        '#1e293b',
  bg3:        '#1e293b',
  card:       '#1e293b',
  border:     '#334155',
  border2:    '#475569',
  text:       '#f8fafc',
  sub:        '#94a3b8',
  dim:        '#64748b',
  primary:    '#14b8a6',
  primaryBg:  'rgba(20,184,166,0.1)',
  primaryBdr: 'rgba(20,184,166,0.25)',
  shadow:     '0 1px 3px rgba(0,0,0,0.4),0 1px 2px rgba(0,0,0,0.3)',
  shadowMd:   '0 4px 12px rgba(0,0,0,0.5),0 2px 4px rgba(0,0,0,0.3)',
  navBg:      'rgba(15,23,42,0.92)',
  red:        '#f87171',  redBg:     'rgba(248,113,113,0.1)',
  orange:     '#fb923c',  orangeBg:  'rgba(251,146,60,0.1)',
  yellow:     '#fbbf24',  yellowBg:  'rgba(251,191,36,0.1)',
  green:      '#4ade80',  greenBg:   'rgba(74,222,128,0.1)',
};

const GLOBAL_CSS = `
  @keyframes wm-up { from { opacity:0; transform:translateY(18px); } to { opacity:1; transform:translateY(0); } }
  @keyframes wm-right { from { opacity:0; transform:translateX(24px); } to { opacity:1; transform:translateX(0); } }
  @keyframes wm-blink { 0%,100% { opacity:1; } 50% { opacity:0.3; } }
  @keyframes wm-scroll { 0% { transform:translateY(0); } 100% { transform:translateY(-50%); } }
  .wm-u0 { animation: wm-up 0.55s ease both; }
  .wm-u1 { animation: wm-up 0.55s 0.08s ease both; }
  .wm-u2 { animation: wm-up 0.55s 0.16s ease both; }
  .wm-u3 { animation: wm-up 0.55s 0.24s ease both; }
  .wm-u4 { animation: wm-up 0.55s 0.32s ease both; }
  .wm-r0 { animation: wm-right 0.6s 0.1s ease both; }
  .wm-blink { animation: wm-blink 1.8s ease-in-out infinite; }
  .wm-ticker { overflow:hidden; height:252px; }
  .wm-ticker-inner { animation: wm-scroll 14s linear infinite; }
  .wm-ticker-inner:hover { animation-play-state:paused; }
  .wm-hover { transition: transform 0.18s ease, box-shadow 0.18s ease; }
  .wm-hover:hover { transform: translateY(-2px); }
  .wm-faq-body { max-height:0; overflow:hidden; transition: max-height 0.32s ease, opacity 0.28s ease; opacity:0; }
  .wm-faq-body.open { max-height:300px; opacity:1; }
`;

// ── data ────────────────────────────────────────────────────────────────────
const ALERTS = [
  { type: 'Revenge Trading', sev: 'DANGER',   key: 'red',    msg: 'Re-entered NIFTY CE 3× in 18 min after losses. −₹14,200.' },
  { type: 'Overtrading',     sev: 'WARNING',  key: 'orange', msg: '9 trades in 45 min. Win rate drops to 22% at this pace.' },
  { type: 'FOMO Entry',      sev: 'CAUTION',  key: 'yellow', msg: 'Entered BANKNIFTY 14 min after breakout — costs ₹3,200 avg.' },
  { type: 'Blowup Risk',     sev: 'CRITICAL', key: 'red',    msg: '78% of daily loss limit hit. Stop here — data says you won\'t recover.' },
  { type: 'Loss Streak',     sev: 'WARNING',  key: 'orange', msg: '4 consecutive losses. Historical: things get worse from here.' },
  { type: 'Early Exit',      sev: 'CAUTION',  key: 'yellow', msg: 'Cut winner at ₹1,800. It ran ₹4,100 more. 7× this week.' },
];

const FEATURES = [
  { icon: Bell,      title: 'Real-time Alerts',     desc: 'Pattern detection fires within seconds — revenge trading, FOMO, meltdown risk — before you lose more.', accent: 'primary' },
  { icon: Brain,     title: 'AI Psychology Coach',  desc: 'Ask why you made a trade. Get pattern-matched analysis from your actual history, not generic advice.', accent: 'orange' },
  { icon: Shield,    title: 'Blowup Shield',        desc: 'Opt-in circuit breakers that pause trading when behavioral data predicts a cascade loss day.', accent: 'red' },
  { icon: BarChart3, title: 'Behavioral Analytics', desc: 'Win rate by time, streak context, trade count. See when you make money — and when you systematically lose it.', accent: 'green' },
  { icon: Activity,  title: 'Portfolio Radar',      desc: 'Concentration, expiry exposure, Greeks at a glance. Built for NSE/BSE F&O with real lot sizes.', accent: 'primary' },
  { icon: Target,    title: 'Pattern Commitments',  desc: 'Set behavioral goals, track streaks, measure improvement. Turn insight into lasting change.', accent: 'yellow' },
];

const STEPS = [
  { n: '1', title: 'Connect Zerodha', desc: 'One-click OAuth. No credentials stored. Live trade feed via KiteConnect webhooks. 90-second setup.' },
  { n: '2', title: 'Mirror activates', desc: 'Behavioral engine watches every order in real-time, calibrated to your own historical patterns and thresholds.' },
  { n: '3', title: 'Act on the alert', desc: 'Instant on-screen + WhatsApp alerts with pattern type, estimated cost, and your historical context.' },
];

const PATTERNS = [
  { name: 'Revenge Trading',  sev: 'DANGER',   key: 'red',    cost: '₹8,400/incident', desc: '89% of revenge trades end in larger losses than the original.' },
  { name: 'Overtrading',      sev: 'WARNING',  key: 'orange', cost: '₹4,200/session',  desc: 'Past trade #8 intraday, accuracy drops below 30% on average.' },
  { name: 'FOMO Entry',       sev: 'CAUTION',  key: 'yellow', cost: '₹2,800/trade',    desc: 'Entering after a move — you\'re buying at peak momentum, someone else\'s exit.' },
  { name: 'No Stop-Loss',     sev: 'WARNING',  key: 'orange', cost: '₹11,200/incident', desc: 'One uncapped position can erase 3 weeks of disciplined profits.' },
  { name: 'Meltdown Cascade', sev: 'CRITICAL', key: 'red',    cost: '₹22,000+/session', desc: 'Loss streak + increasing position sizes = exponential, not arithmetic damage.' },
  { name: 'Early Exit',       sev: 'CAUTION',  key: 'yellow', cost: '₹1,900 left/trade', desc: 'Cutting winners short out of anxiety while letting losers run — the slow bleed.' },
];

const TESTIMONIALS = [
  { init: 'AM', name: 'Arjun M.', role: 'NIFTY Options · 4 yrs', saved: '₹82,000 saved', quote: 'I knew I was revenge trading but couldn\'t stop mid-session. Seeing the pattern flagged with my own trade data was the interruption I needed. Down months dropped 60%.' },
  { init: 'PS', name: 'Priya S.', role: 'Bank Nifty Intraday · 2 yrs', saved: '₹1,20,000 saved', quote: 'The Blowup Shield stopped me on a day I thought I was fine. Data showed I was already 3 losses deep in my personal danger zone. I would\'ve blown the account.' },
  { init: 'RK', name: 'Rahul K.', role: 'F&O Swing · 6 yrs', saved: '₹65,000 saved', quote: 'Analytics showed my Friday win rate is 18% vs 61% Mon–Thu. I stopped trading Fridays. One behavioral insight, massive P&L improvement every quarter.' },
];

const PRICING = [
  {
    name: 'Free', monthly: '₹0', yearly: '₹0', period: 'forever', highlight: false,
    desc: 'Get started, understand your patterns',
    features: ['Real-time behavioral alerts', '5 pattern detectors', '7-day history', 'Basic analytics', 'Zerodha integration'],
    cta: 'Start Free',
  },
  {
    name: 'Pro', monthly: '₹499', yearly: '₹399', period: '/mo', highlight: true, badge: 'Most Popular',
    desc: 'For traders serious about their edge',
    features: ['Everything in Free', 'AI Psychology Coach', 'Portfolio Radar', '90-day history', 'Blowup Shield', 'WhatsApp + push alerts', 'Pattern commitment tracker'],
    cta: 'Start 7-day Trial',
  },
  {
    name: 'Elite', monthly: '₹999', yearly: '₹799', period: '/mo', highlight: false,
    desc: 'Custom thresholds, full control',
    features: ['Everything in Pro', 'Custom alert thresholds', 'Strategy analytics', 'Priority support', 'Advanced reports', '2-seat team access'],
    cta: 'Go Elite',
  },
];

const FAQS = [
  { q: 'Is my trading data secure?', a: 'We never store your Zerodha credentials. Authentication is via OAuth — the same standard banks use. Trade data is encrypted at rest and can be deleted from Settings at any time.' },
  { q: 'Does it restrict my trading?', a: 'TradeMentor is a mirror, not a blocker. We surface what your behavior looks like — the decision is always yours. Blowup Shield is opt-in and can be disabled at any time.' },
  { q: 'How does the Zerodha connection work?', a: "One-click OAuth via Zerodha's official KiteConnect API. We receive your trade feed via webhooks in real-time. We read trades for analysis — we never place, modify, or cancel orders." },
  { q: "What's different about Free vs Pro?", a: 'Free gives real-time alerts and basic analytics. Pro adds the AI Coach, Portfolio Radar, 90-day behavioral history, Blowup Shield, and WhatsApp alerts.' },
  { q: 'Which products are supported?', a: 'NSE and BSE — F&O only: MIS, NRML, MTF. Equity delivery (CNC) is excluded. Built for active intraday and swing traders.' },
];

// ── helpers ─────────────────────────────────────────────────────────────────
type C = typeof LIGHT;

function sev(c: C, key: string) {
  return { color: (c as any)[key], bg: (c as any)[`${key}Bg`] };
}

// ── sub-components ───────────────────────────────────────────────────────────

function Navbar({ c, isDark, onToggleTheme, consent, onConnect, onGuest, scrolled }: {
  c: C; isDark: boolean; onToggleTheme: () => void;
  consent: boolean; onConnect: () => void; onGuest: () => void; scrolled: boolean;
}) {
  return (
    <header style={{
      position: 'fixed', top: 0, left: 0, right: 0, zIndex: 50,
      background: scrolled ? c.navBg : 'transparent',
      backdropFilter: scrolled ? 'blur(10px)' : 'none',
      borderBottom: scrolled ? `1px solid ${c.border}` : '1px solid transparent',
      transition: 'all 0.25s ease',
    }}>
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 clamp(1rem,3vw,2rem)', height: 60, display: 'flex', alignItems: 'center', gap: 24 }}>
        {/* Logo */}
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 8, textDecoration: 'none', flexShrink: 0 }}>
          <div style={{ width: 30, height: 30, borderRadius: 8, background: c.primary, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Eye size={15} color="#fff" strokeWidth={2.5} />
          </div>
          <span style={{ fontFamily: 'Plus Jakarta Sans,sans-serif', fontWeight: 800, fontSize: '0.9375rem', color: c.text, letterSpacing: '-0.01em' }}>
            TradeMentor
          </span>
        </Link>

        {/* Nav links */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1, justifyContent: 'center' }}>
          {[['#how', 'How it works'], ['#features', 'Features'], ['#pricing', 'Pricing']].map(([href, label]) => (
            <a key={href} href={href} style={{ fontFamily: 'Plus Jakarta Sans,sans-serif', fontSize: '0.875rem', fontWeight: 500, color: c.sub, textDecoration: 'none', padding: '5px 12px', borderRadius: 6, transition: 'color 0.15s, background 0.15s' }}
              onMouseEnter={e => { e.currentTarget.style.color = c.text; e.currentTarget.style.background = c.bg2; }}
              onMouseLeave={e => { e.currentTarget.style.color = c.sub; e.currentTarget.style.background = 'transparent'; }}>
              {label}
            </a>
          ))}
        </nav>

        {/* Right actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <button onClick={onToggleTheme} title="Toggle theme"
            style={{ width: 34, height: 34, borderRadius: 8, border: `1px solid ${c.border}`, background: 'transparent', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: c.sub, transition: 'all 0.15s' }}
            onMouseEnter={e => { e.currentTarget.style.background = c.bg2; e.currentTarget.style.color = c.text; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = c.sub; }}>
            {isDark ? <Sun size={15} /> : <Moon size={15} />}
          </button>
          <button onClick={onGuest} style={{ fontFamily: 'Plus Jakarta Sans,sans-serif', fontSize: '0.8125rem', fontWeight: 500, color: c.sub, background: 'transparent', border: 'none', cursor: 'pointer', padding: '6px 10px' }}>
            Try demo
          </button>
          <button onClick={consent ? onConnect : undefined} disabled={!consent}
            style={{ fontFamily: 'Plus Jakarta Sans,sans-serif', fontSize: '0.8125rem', fontWeight: 600, color: '#fff', background: consent ? c.primary : c.dim, border: 'none', cursor: consent ? 'pointer' : 'not-allowed', padding: '7px 16px', borderRadius: 8, transition: 'opacity 0.15s, transform 0.15s', opacity: consent ? 1 : 0.6 }}
            onMouseEnter={e => { if (consent) e.currentTarget.style.opacity = '0.88'; }}
            onMouseLeave={e => { e.currentTarget.style.opacity = '1'; }}>
            Connect Zerodha
          </button>
        </div>
      </div>
    </header>
  );
}

function ProductCard({ c }: { c: C }) {
  return (
    <div style={{ background: c.card, border: `1px solid ${c.border}`, borderRadius: 14, overflow: 'hidden', boxShadow: c.shadowMd, width: '100%', maxWidth: 420 }}>
      {/* Card header */}
      <div style={{ padding: '14px 18px', borderBottom: `1px solid ${c.border}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: c.bg2 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <Eye size={13} color={c.primary} />
          <span style={{ fontFamily: 'Plus Jakarta Sans,sans-serif', fontWeight: 700, fontSize: '0.8125rem', color: c.text }}>Behavioral Mirror</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span className="wm-blink" style={{ width: 6, height: 6, borderRadius: '50%', background: '#22c55e', display: 'inline-block' }} />
          <span style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: '0.6rem', fontWeight: 600, color: '#22c55e' }}>LIVE</span>
        </div>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', borderBottom: `1px solid ${c.border}` }}>
        {[
          { label: 'P&L Impact', value: '−₹18,400', col: c.red },
          { label: 'Patterns',   value: '3',         col: c.primary },
          { label: 'Alerts',     value: '7',         col: c.sub },
        ].map(({ label, value, col }) => (
          <div key={label} style={{ padding: '10px 14px', borderRight: `1px solid ${c.border}` }}>
            <div style={{ fontFamily: 'Plus Jakarta Sans,sans-serif', fontSize: '0.625rem', color: c.dim, marginBottom: 3, fontWeight: 500 }}>{label}</div>
            <div style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: '0.9375rem', fontWeight: 600, color: col }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Scrolling alert ticker */}
      <div className="wm-ticker">
        <div className="wm-ticker-inner">
          {[...ALERTS, ...ALERTS].map((a, i) => {
            const { color, bg } = sev(c, a.key);
            return (
              <div key={i} style={{ padding: '11px 16px', borderBottom: `1px solid ${c.border}` }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontFamily: 'Plus Jakarta Sans,sans-serif', fontWeight: 700, fontSize: '0.75rem', color: c.text }}>{a.type}</span>
                  <span style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: '0.575rem', fontWeight: 600, color, background: bg, padding: '2px 7px', borderRadius: 4, letterSpacing: '0.07em' }}>{a.sev}</span>
                </div>
                <p style={{ fontFamily: 'Plus Jakarta Sans,sans-serif', fontSize: '0.75rem', color: c.sub, margin: 0, lineHeight: 1.5 }}>{a.msg}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer */}
      <div style={{ padding: '9px 16px', background: c.bg2, display: 'flex', alignItems: 'center', gap: 5 }}>
        <Lock size={10} color={c.dim} />
        <span style={{ fontFamily: 'Plus Jakarta Sans,sans-serif', fontSize: '0.6875rem', color: c.dim }}>Read-only · OAuth · SEBI compliant</span>
      </div>
    </div>
  );
}

function SectionLabel({ c, children }: { c: C; children: string }) {
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 7, background: c.primaryBg, border: `1px solid ${c.primaryBdr}`, borderRadius: 100, padding: '4px 12px', marginBottom: '1rem' }}>
      <span style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: '0.625rem', fontWeight: 600, color: c.primary, letterSpacing: '0.1em' }}>{children}</span>
    </div>
  );
}

function Divider({ c }: { c: C }) {
  return <div style={{ height: 1, background: c.border }} />;
}

// ── main ─────────────────────────────────────────────────────────────────────
export default function Welcome() {
  const navigate = useNavigate();
  const { connect: connectBroker, enterGuestMode, isConnected: isAuthenticated } = useBroker();
  const { resolvedTheme, setTheme } = useTheme();

  const isDark = resolvedTheme === 'dark';
  const c = isDark ? DARK : LIGHT;

  const [scrolled,  setScrolled]  = useState(false);
  const [consent,   setConsent]   = useState(false);
  const [billing,   setBilling]   = useState<'monthly' | 'yearly'>('monthly');
  const [openFaq,   setOpenFaq]   = useState<number | null>(null);

  useEffect(() => { if (isAuthenticated) navigate('/dashboard', { replace: true }); }, [isAuthenticated, navigate]);

  useEffect(() => {
    const link = document.createElement('link');
    link.rel = 'stylesheet'; link.href = FONT_URL;
    document.head.appendChild(link);
    const style = document.createElement('style');
    style.textContent = GLOBAL_CSS;
    document.head.appendChild(style);
    return () => { document.head.removeChild(link); document.head.removeChild(style); };
  }, []);

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 40);
    window.addEventListener('scroll', fn, { passive: true });
    return () => window.removeEventListener('scroll', fn);
  }, []);

  const handleConnect = () => { if (consent) connectBroker(); };
  const handleGuest   = () => { enterGuestMode(); navigate('/dashboard'); };
  const toggleTheme   = () => setTheme(isDark ? 'light' : 'dark');

  const wrap: React.CSSProperties = { maxWidth: 1200, margin: '0 auto', padding: '0 clamp(1rem,3vw,2rem)' };
  const section = (bg = c.bg): React.CSSProperties => ({ background: bg, padding: 'clamp(4rem,8vw,6rem) 0' });
  const mono = 'JetBrains Mono,monospace';
  const sans = 'Plus Jakarta Sans,sans-serif';

  const alertStory: Story = {
    eyebrow: "Behavioral safety net",
    title: "Real-time alerts that interrupt the spiral",
    body: "TradeMentor runs quiet in the background, matching your live executions against your historical blind spots. When it detects a pattern, it doesn't just display a warning — it interrupts the loop.",
    bullets: [
      "Revenge trading alerts within seconds of a stop-out",
      "Overtrading notifications when pace exceeds limits",
      "Adding-to-a-loser flags based on behavioral data",
      "Circuit breaker prompts suggesting a cooldown period"
    ],
    visual: <AlertFeedMock />
  };

  const shieldStory: Story = {
    eyebrow: "Accountability Loop",
    title: "A circuit breaker that actually stops you",
    body: "If you blow past your stop loss and keep click-trading, TradeMentor enforces a cooldown. It can automatically trigger a circuit breaker and dispatch an accountability alert to your partner.",
    bullets: [
      "Opt-in circuit breaker to lock terminal access",
      "WhatsApp dispatch to your accountability partner",
      "Threshold calculations based on your risk tolerance",
      "Proven pattern disruption to stop cascade losses"
    ],
    reverse: true,
    visual: <ShieldMock />
  };

  const coachStory: Story = {
    eyebrow: "Behavioral Analytics",
    title: "An AI Coach that knows your history",
    body: "Why did you make that trade? Ask your AI Psychology Coach. It cross-references your live trade logs with your history to point out structural patterns, not generic advice.",
    bullets: [
      "Win rate and profitability stats by day and time",
      "Personalized danger-zone profiling from historical logs",
      "Conversational prompts to explore trading emotions",
      "Streak tracking and pattern commitments"
    ],
    visual: <CoachMock />
  };

  return (
    <div style={{ background: c.bg, color: c.text, fontFamily: sans, minHeight: '100vh' }}>
      <Navbar c={c} isDark={isDark} onToggleTheme={toggleTheme} consent={consent} onConnect={handleConnect} onGuest={handleGuest} scrolled={scrolled} />

      {/* ── HERO ─────────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden border-b border-border/60 bg-background min-h-[calc(100dvh-70px)] flex items-center">
        {/* Subtle radial glows */}
        <div className="absolute right-[5%] top-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-[radial-gradient(circle_at_center,rgba(59,130,246,0.04)_0%,transparent_70%)] pointer-events-none z-0"></div>
        <div className="absolute left-[-10%] top-[-10%] w-[500px] h-[500px] bg-[radial-gradient(circle_at_center,rgba(239,68,68,0.02)_0%,transparent_70%)] pointer-events-none z-0"></div>
        
        <div className="max-w-[1180px] mx-auto px-6 grid lg:grid-cols-[2fr_3fr] gap-12 lg:gap-14 items-center w-full relative z-10">
          {/* Left side: Headline, Subheadline, CTAs */}
          <div className="flex flex-col gap-6 lg:gap-8 justify-center py-12 lg:py-20 z-10">
            {/* Eyebrow Pill */}
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-border bg-background/60 backdrop-blur-sm self-start">
              <span className="h-1.5 w-1.5 rounded-full bg-loss animate-pulse" />
              <span className="text-[12px] font-medium text-muted-foreground tracking-tight">
                ₹46,000 leaked per trader this year. Mostly to themselves.
              </span>
            </div>

            {/* Headline */}
            <h1 className="font-display text-[40px] sm:text-[52px] lg:text-[62px] leading-[1.05] font-semibold text-foreground tracking-tight">
              You don't have a<br />
              <span className="text-loss">strategy</span> problem.<br />
              You have a <span className="underline decoration-loss decoration-[3px] underline-offset-[6px]">7-second</span> problem.
            </h1>

            {/* Subheadline */}
            <p className="text-[16px] lg:text-[18px] leading-[1.6] text-muted-foreground max-w-[540px]">
              The seven seconds between getting stopped out and clicking buy again. That's where the month dies — not in your chart setup. TradeMentor sits in those seven seconds and refuses to let you punch yourself in the face.
            </p>

            {/* Consent checkbox */}
            <label className="flex items-start gap-3 cursor-pointer">
              <div onClick={() => setConsent(v => !v)} className={`h-4 w-4 rounded border flex items-center justify-center transition-all mt-0.5 shrink-0 cursor-pointer ${consent ? "bg-primary border-primary text-white" : "border-border bg-card"}`}>
                {consent && <Check className="h-3 w-3 stroke-[3]" />}
              </div>
              <span className="text-[12px] text-muted-foreground leading-normal">
                I've read the <Link to="/terms" className="underline hover:text-foreground">Terms</Link> and <Link to="/privacy" className="underline hover:text-foreground">Privacy Policy</Link>. TradeMentor is a behavioral co-pilot, not investment advice.
              </span>
            </label>

            {/* CTAs */}
            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={consent ? handleConnect : undefined}
                disabled={!consent}
                className={`inline-flex items-center justify-center h-12 px-6 rounded-2xl text-[14px] font-semibold gap-2 transition-all ${consent ? "bg-primary text-primary-foreground shadow-lg hover:opacity-90 cursor-pointer" : "bg-muted text-muted-foreground cursor-not-allowed opacity-50"}`}
              >
                Connect Zerodha <ArrowRight className="h-4 w-4" />
              </button>
              <button
                onClick={handleGuest}
                className="inline-flex items-center justify-center h-12 px-6 rounded-2xl text-[14px] font-semibold border border-border bg-card hover:bg-muted/50 text-foreground transition-all cursor-pointer"
              >
                Try demo first
              </button>
            </div>

            {/* Trust pills */}
            <div className="flex items-center gap-4 flex-wrap">
              {[['No credentials stored', Lock], ['Read-only access', Eye], ['Free to start', Zap]].map(([label, Icon]: any) => (
                <span key={label} className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
                  <Icon className="h-3.5 w-3.5" /> {label}
                </span>
              ))}
            </div>
          </div>

          {/* Right side: LiveHeroTerminal */}
          <div className="w-full relative z-10 lg:pl-4">
            <LiveHeroTerminal />
          </div>
        </div>
      </section>

      {/* ── STATS BAR ────────────────────────────────────────────────────── */}
      <div style={{ background: c.bg2, borderTop: `1px solid ${c.border}`, borderBottom: `1px solid ${c.border}` }}>
        <div style={{ ...wrap, display: 'grid', gridTemplateColumns: 'repeat(3,1fr)' }}>
          {[
            { v: '₹4.8Cr+', label: 'Estimated losses prevented' },
            { v: '12,400+', label: 'Behavioral alerts sent' },
            { v: '15',      label: 'Behavioral pattern detectors' },
          ].map(({ v, label }) => (
            <div key={label} style={{ padding: '1.5rem clamp(1rem,2vw,1.75rem)', textAlign: 'center', borderRight: `1px solid ${c.border}` }}>
              <div style={{ fontFamily: mono, fontSize: 'clamp(1.375rem,2.5vw,2rem)', fontWeight: 600, color: c.primary, letterSpacing: '-0.025em' }}>{v}</div>
              <div style={{ fontFamily: sans, fontSize: '0.8125rem', color: c.dim, marginTop: 3 }}>{label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── LOSS SPIRAL SIMULATOR ────────────────────────────────────────── */}
      <LossSpiralSimulator id="how" />

      {/* ── FEATURE STORIES ──────────────────────────────────────────────── */}
      <FeatureStory story={alertStory} id="features" />
      <FeatureStory story={shieldStory} />
      <FeatureStory story={coachStory} />

      <Divider c={c} />

      {/* ── PATTERNS ─────────────────────────────────────────────────────── */}
      <section style={section(c.bg)}>
        <div style={wrap}>
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1.6fr)', gap: 'clamp(2rem,5vw,4rem)', alignItems: 'start' }}>
            <div style={{ position: 'sticky', top: 80 }}>
              <SectionLabel c={c}>BEHAVIORAL PATTERNS</SectionLabel>
              <h2 style={{ fontFamily: sans, fontWeight: 800, fontSize: 'clamp(1.5rem,2.8vw,2rem)', color: c.text, letterSpacing: '-0.025em', margin: '0 0 0.875rem' }}>
                15 detectors. Calibrated to you.
              </h2>
              <p style={{ fontFamily: sans, fontSize: '0.9375rem', color: c.sub, lineHeight: 1.7, margin: '0 0 1.5rem' }}>
                Every threshold is set from your own trading history — not industry averages.
                Your patterns, your context, your blind spots.
              </p>
              <div style={{ padding: '1rem 1.25rem', background: c.primaryBg, border: `1px solid ${c.primaryBdr}`, borderRadius: 10 }}>
                <div style={{ fontFamily: mono, fontSize: '0.625rem', color: c.primary, marginBottom: 5, fontWeight: 600 }}>RESEARCH BASIS</div>
                <p style={{ fontFamily: sans, fontSize: '0.8125rem', color: c.sub, margin: 0, lineHeight: 1.6 }}>
                  All thresholds derived from F&O microstructure research — NSE lot sizes, intraday session data, premium decay curves.
                </p>
              </div>
            </div>

            <div style={{ border: `1px solid ${c.border}`, borderRadius: 12, overflow: 'hidden', boxShadow: c.shadow }}>
              {/* Table header */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 16, padding: '10px 16px', background: c.bg2, borderBottom: `1px solid ${c.border}` }}>
                {['Pattern', 'Avg Cost', 'Severity'].map(h => (
                  <span key={h} style={{ fontFamily: mono, fontSize: '0.625rem', fontWeight: 600, color: c.dim, letterSpacing: '0.08em' }}>{h}</span>
                ))}
              </div>
              {PATTERNS.map(({ name, sev: sevLabel, key, cost, desc }) => {
                const { color, bg } = sev(c, key);
                return (
                  <div key={name} style={{ display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 16, padding: '14px 16px', borderBottom: `1px solid ${c.border}`, alignItems: 'center', background: c.card }}>
                    <div>
                      <div style={{ fontFamily: sans, fontWeight: 600, fontSize: '0.875rem', color: c.text, marginBottom: 3 }}>{name}</div>
                      <div style={{ fontFamily: sans, fontSize: '0.75rem', color: c.dim }}>{desc}</div>
                    </div>
                    <span style={{ fontFamily: mono, fontSize: '0.75rem', fontWeight: 600, color: c.sub, whiteSpace: 'nowrap' }}>{cost}</span>
                    <span style={{ fontFamily: mono, fontSize: '0.575rem', fontWeight: 600, color, background: bg, padding: '3px 8px', borderRadius: 4, letterSpacing: '0.07em', whiteSpace: 'nowrap' }}>{sevLabel}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      <Divider c={c} />

      {/* ── TESTIMONIALS ─────────────────────────────────────────────────── */}
      <section style={section(c.bg2)}>
        <div style={wrap}>
          <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
            <SectionLabel c={c}>TRADERS</SectionLabel>
            <h2 style={{ fontFamily: sans, fontWeight: 800, fontSize: 'clamp(1.625rem,3vw,2.25rem)', color: c.text, letterSpacing: '-0.025em', margin: 0 }}>
              Real traders. Real results.
            </h2>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(290px,1fr))', gap: 20 }}>
            {TESTIMONIALS.map(({ init, name, role, saved, quote }) => (
              <div key={name} className="wm-hover" style={{ background: c.card, border: `1px solid ${c.border}`, borderRadius: 12, padding: '1.5rem', boxShadow: c.shadow, display: 'flex', flexDirection: 'column', gap: 16 }}>
                <p style={{ fontFamily: sans, fontSize: '0.9375rem', color: c.sub, lineHeight: 1.7, margin: 0, flex: 1 }}>"{quote}"</p>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingTop: 14, borderTop: `1px solid ${c.border}` }}>
                  <div style={{ width: 36, height: 36, borderRadius: '50%', background: c.primaryBg, border: `1px solid ${c.primaryBdr}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: mono, fontSize: '0.625rem', fontWeight: 700, color: c.primary, flexShrink: 0 }}>{init}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontFamily: sans, fontWeight: 700, fontSize: '0.8125rem', color: c.text }}>{name}</div>
                    <div style={{ fontFamily: sans, fontSize: '0.75rem', color: c.dim }}>{role}</div>
                  </div>
                  <span style={{ fontFamily: mono, fontSize: '0.625rem', fontWeight: 600, color: c.green, background: c.greenBg, padding: '3px 8px', borderRadius: 5, whiteSpace: 'nowrap' }}>{saved}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <Divider c={c} />

      {/* ── PRICING ──────────────────────────────────────────────────────── */}
      <section style={section(c.bg)} id="pricing">
        <div style={wrap}>
          <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
            <SectionLabel c={c}>PRICING</SectionLabel>
            <h2 style={{ fontFamily: sans, fontWeight: 800, fontSize: 'clamp(1.625rem,3vw,2.25rem)', color: c.text, letterSpacing: '-0.025em', margin: '0 0 1.25rem' }}>
              Start free. Upgrade when it pays for itself.
            </h2>
            {/* Billing toggle */}
            <div style={{ display: 'inline-flex', background: c.bg2, border: `1px solid ${c.border}`, borderRadius: 8, padding: 3 }}>
              {(['monthly', 'yearly'] as const).map(b => (
                <button key={b} onClick={() => setBilling(b)}
                  style={{ padding: '6px 18px', borderRadius: 6, border: 'none', cursor: 'pointer', fontFamily: sans, fontSize: '0.8125rem', fontWeight: 600, transition: 'all 0.18s',
                    background: billing === b ? c.card : 'transparent',
                    color: billing === b ? c.text : c.dim,
                    boxShadow: billing === b ? c.shadow : 'none' }}>
                  {b === 'monthly' ? 'Monthly' : 'Yearly · 20% off'}
                </button>
              ))}
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(270px,1fr))', gap: 20, alignItems: 'start' }}>
            {PRICING.map(({ name, monthly, yearly, period, highlight, badge, desc, features, cta }) => (
              <div key={name} className="wm-hover" style={{
                background: c.card, borderRadius: 14, padding: '1.75rem', position: 'relative',
                border: `${highlight ? 2 : 1}px solid ${highlight ? c.primary : c.border}`,
                boxShadow: highlight ? `${c.shadowMd}, 0 0 0 1px ${c.primary}20` : c.shadow,
              }}>
                {badge && (
                  <div style={{ position: 'absolute', top: -12, left: '50%', transform: 'translateX(-50%)', background: c.primary, color: '#fff', fontFamily: sans, fontWeight: 700, fontSize: '0.6875rem', padding: '3px 12px', borderRadius: 100, whiteSpace: 'nowrap' }}>
                    {badge}
                  </div>
                )}
                <div style={{ marginBottom: '1.5rem' }}>
                  <div style={{ fontFamily: sans, fontWeight: 700, fontSize: '0.8125rem', color: highlight ? c.primary : c.sub, marginBottom: 6, letterSpacing: '0.04em' }}>{name.toUpperCase()}</div>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 3 }}>
                    <span style={{ fontFamily: mono, fontSize: 'clamp(1.75rem,3vw,2.25rem)', fontWeight: 700, color: c.text }}>
                      {billing === 'monthly' ? monthly : yearly}
                    </span>
                    <span style={{ fontFamily: sans, fontSize: '0.875rem', color: c.dim }}>{period}</span>
                  </div>
                  <p style={{ fontFamily: sans, fontSize: '0.8125rem', color: c.dim, margin: '0.375rem 0 0' }}>{desc}</p>
                </div>
                <ul style={{ listStyle: 'none', margin: '0 0 1.75rem', padding: 0, display: 'flex', flexDirection: 'column', gap: 9 }}>
                  {features.map(f => (
                    <li key={f} style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                      <Check size={13} color={highlight ? c.primary : c.green} style={{ marginTop: 2, flexShrink: 0 }} />
                      <span style={{ fontFamily: sans, fontSize: '0.84375rem', color: c.sub }}>{f}</span>
                    </li>
                  ))}
                </ul>
                <button onClick={consent ? handleConnect : () => setConsent(true)}
                  style={{ width: '100%', padding: '11px', borderRadius: 9, cursor: 'pointer', fontFamily: sans, fontWeight: 700, fontSize: '0.875rem', transition: 'all 0.15s',
                    background: highlight ? c.primary : 'transparent',
                    color: highlight ? '#fff' : c.text,
                    border: `1px solid ${highlight ? c.primary : c.border2}` }}
                  onMouseEnter={e => { if (!highlight) { e.currentTarget.style.borderColor = c.primary; e.currentTarget.style.color = c.primary; } else { e.currentTarget.style.opacity = '0.88'; } }}
                  onMouseLeave={e => { e.currentTarget.style.opacity = '1'; if (!highlight) { e.currentTarget.style.borderColor = c.border2; e.currentTarget.style.color = c.text; } }}>
                  {cta}
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>

      <Divider c={c} />

      {/* ── FAQ ──────────────────────────────────────────────────────────── */}
      <section style={section(c.bg2)} id="faq">
        <div style={{ ...wrap, maxWidth: 720 }}>
          <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
            <SectionLabel c={c}>FAQ</SectionLabel>
            <h2 style={{ fontFamily: sans, fontWeight: 800, fontSize: 'clamp(1.625rem,3vw,2.25rem)', color: c.text, letterSpacing: '-0.025em', margin: 0 }}>
              Common questions.
            </h2>
          </div>
          <div style={{ border: `1px solid ${c.border}`, borderRadius: 12, overflow: 'hidden', boxShadow: c.shadow }}>
            {FAQS.map(({ q, a }, i) => (
              <div key={i} style={{ borderBottom: i < FAQS.length - 1 ? `1px solid ${c.border}` : 'none', background: c.card }}>
                <button onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, padding: '1.125rem 1.25rem', background: 'transparent', border: 'none', cursor: 'pointer', textAlign: 'left' }}>
                  <span style={{ fontFamily: sans, fontWeight: 600, fontSize: '0.9375rem', color: c.text }}>{q}</span>
                  <ChevronDown size={16} color={c.dim} style={{ flexShrink: 0, transform: openFaq === i ? 'rotate(180deg)' : 'none', transition: 'transform 0.28s' }} />
                </button>
                <div className={`wm-faq-body${openFaq === i ? ' open' : ''}`}>
                  <p style={{ fontFamily: sans, fontSize: '0.875rem', color: c.sub, lineHeight: 1.7, margin: 0, padding: '0 1.25rem 1.125rem' }}>{a}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FINAL CTA ────────────────────────────────────────────────────── */}
      <section style={{ ...section(c.bg), borderTop: `1px solid ${c.border}` }}>
        <div style={{ ...wrap, textAlign: 'center', maxWidth: 580 }}>
          <SectionLabel c={c}>GET STARTED</SectionLabel>
          <h2 style={{ fontFamily: sans, fontWeight: 800, fontSize: 'clamp(1.75rem,4vw,2.75rem)', color: c.text, letterSpacing: '-0.03em', lineHeight: 1.1, margin: '0 0 1rem' }}>
            See your behavior clearly.{' '}
            <span style={{ color: c.primary }}>Trade better.</span>
          </h2>
          <p style={{ fontFamily: sans, fontSize: '1rem', color: c.sub, margin: '0 0 2rem', lineHeight: 1.7 }}>
            Free forever. Connects to Zerodha in 90 seconds. No commitment required.
          </p>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, flexWrap: 'wrap' }}>
            <button onClick={consent ? handleConnect : () => { setConsent(true); }}
              style={{ display: 'flex', alignItems: 'center', gap: 8, background: c.primary, color: '#fff', border: 'none', cursor: 'pointer', fontFamily: sans, fontWeight: 700, fontSize: '1rem', padding: '13px 26px', borderRadius: 10, boxShadow: `0 4px 16px ${c.primary}40`, transition: 'all 0.15s' }}
              onMouseEnter={e => { e.currentTarget.style.opacity = '0.9'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
              onMouseLeave={e => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.transform = 'translateY(0)'; }}>
              Start free — Connect Zerodha <ArrowRight size={16} />
            </button>
            <button onClick={handleGuest}
              style={{ background: 'transparent', border: `1px solid ${c.border2}`, cursor: 'pointer', fontFamily: sans, fontWeight: 600, fontSize: '1rem', color: c.sub, padding: '12px 22px', borderRadius: 10, transition: 'all 0.15s' }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = c.primary; e.currentTarget.style.color = c.primary; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = c.border2; e.currentTarget.style.color = c.sub; }}>
              Try demo first
            </button>
          </div>
        </div>
      </section>

      {/* ── FOOTER ───────────────────────────────────────────────────────── */}
      <footer style={{ background: c.bg2, borderTop: `1px solid ${c.border}`, padding: '1.5rem 0' }}>
        <div style={{ ...wrap, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 24, height: 24, borderRadius: 6, background: c.primary, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Eye size={12} color="#fff" strokeWidth={2.5} />
            </div>
            <span style={{ fontFamily: sans, fontWeight: 700, fontSize: '0.875rem', color: c.text }}>TradeMentor</span>
            <span style={{ fontFamily: sans, fontSize: '0.75rem', color: c.dim, marginLeft: 4 }}>© 2026</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
            {[['Terms', '/terms'], ['Privacy', '/privacy']].map(([label, to]) => (
              <Link key={to} to={to} style={{ fontFamily: sans, fontSize: '0.8125rem', color: c.dim, textDecoration: 'none', transition: 'color 0.15s' }}
                onMouseEnter={e => (e.currentTarget.style.color = c.text)}
                onMouseLeave={e => (e.currentTarget.style.color = c.dim)}>
                {label}
              </Link>
            ))}
          </div>
          <p style={{ fontFamily: sans, fontSize: '0.6875rem', color: c.dim, margin: 0, maxWidth: 360, lineHeight: 1.5, textAlign: 'right' }}>
            Not SEBI registered. Not investment advice. For behavioral analysis only. F&O trading involves substantial risk.
          </p>
        </div>
      </footer>
    </div>
  );
}
