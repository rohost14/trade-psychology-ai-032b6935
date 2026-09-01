import { useState, useEffect, useRef } from 'react';
import {
  User,
  TrendingUp,
  Settings,
  Shield,
  Bell,
  ChevronRight,
  ChevronLeft,
  Check,
  Brain,
  Target,
  Clock,
  Wallet,
  Upload,
} from 'lucide-react';
import { TradebookImportCard } from '@/components/settings/TradebookImportCard';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Switch } from '@/components/ui/switch';
import { Slider } from '@/components/ui/slider';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import { api } from '@/lib/api';

interface OnboardingWizardProps {
  brokerAccountId: string;
  onComplete: () => void;
  onSkip: () => void;
}

interface OnboardingData {
  display_name: string;
  trading_since: number;
  experience_level: string;
  trading_style: string;
  risk_tolerance: string;
  preferred_instruments: string[];
  trading_hours_start: string;
  trading_hours_end: string;
  // MONEY RULES ARE NULLABLE AND OFF BY DEFAULT.
  //
  // `constitution_service.generate_defaults` returns null for both and offers
  // `suggested_*` beside them: the server suggests, the trader decides, and
  // only then does it become an enforced Rule. This form used to defeat that -
  // it carried its own defaults (`daily_loss_limit: 5000`,
  // `max_position_size: 50000`) which survived the merge because the server's
  // null lost to `??`, so every trader was silently given a loss limit they
  // never chose and a per-trade risk rule in the WRONG UNIT: 50000 was a rupee
  // figure written into a field the backend, MyRules and the detector all read
  // as a PERCENTAGE of capital.
  //
  // See docs/patterns/24-constitution_violation/.
  daily_loss_limit: number | null;
  //: Max RAW realised loss on ONE position, in rupees. Opt-in, never suggested.
  per_trade_loss_limit: number | null;
  daily_trade_limit: number;
  max_position_size: number | null;
  cooldown_after_loss: number;
  max_consecutive_losses: number;
  trading_capital: number | null;
  //: Explicit opt-in. Unchecked -> the rule stays null and is never enforced.
  enable_daily_loss_limit: boolean;
  enable_per_trade_loss_limit: boolean;
  enable_max_position_size: boolean;
  known_weaknesses: string[];
  push_enabled: boolean;
  whatsapp_enabled: boolean;
  alert_sensitivity: string;
  guardian_enabled: boolean;
}

const STEPS = [
  { id: 1, title: 'Welcome', icon: User, description: 'Tell us about yourself' },
  { id: 2, title: 'Trading Style', icon: TrendingUp, description: 'Your trading approach' },
  { id: 3, title: 'Preferences', icon: Settings, description: 'Customize your experience' },
  { id: 4, title: 'Risk Limits', icon: Shield, description: 'Protect your capital' },
  { id: 5, title: 'Notifications', icon: Bell, description: 'Stay informed' },
  { id: 6, title: 'History', icon: Upload, description: 'Import past trades (optional)' },
];

const EXPERIENCE_LEVELS = [
  { value: 'beginner', label: 'Beginner', description: 'Less than 1 year trading' },
  { value: 'intermediate', label: 'Intermediate', description: '1-3 years experience' },
  { value: 'experienced', label: 'Experienced', description: '3-5 years of trading' },
  { value: 'professional', label: 'Professional', description: '5+ years, full-time trader' },
];

const TRADING_STYLES = [
  { value: 'scalper', label: 'Scalper', description: 'Quick trades, < 5 minutes' },
  { value: 'intraday', label: 'Intraday', description: 'Close all positions same day' },
  { value: 'swing', label: 'Swing Trader', description: 'Hold for 2-7 days' },
  { value: 'positional', label: 'Positional', description: 'Hold for weeks/months' },
  { value: 'mixed', label: 'Mixed', description: 'Combination of styles' },
];

const RISK_TOLERANCE = [
  { value: 'conservative', label: 'Conservative', color: 'bg-tm-profit' },
  { value: 'moderate', label: 'Moderate', color: 'bg-tm-obs' },
  { value: 'aggressive', label: 'Aggressive', color: 'bg-tm-loss' },
];

const INSTRUMENTS = [
  { value: 'NIFTY', label: 'Nifty 50' },
  { value: 'BANKNIFTY', label: 'Bank Nifty' },
  { value: 'FINNIFTY', label: 'Fin Nifty' },
  { value: 'STOCKS', label: 'Individual Stocks' },
  { value: 'COMMODITIES', label: 'Commodities' },
];

const WEAKNESSES = [
  { value: 'revenge_trading', label: 'Revenge Trading' },
  { value: 'overtrading', label: 'Overtrading' },
  { value: 'fomo', label: 'FOMO' },
  { value: 'no_stoploss', label: 'Not Using Stop Loss' },
  { value: 'early_exit', label: 'Exiting Too Early' },
  { value: 'late_entry', label: 'Chasing Entries' },
];


export default function OnboardingWizard({ brokerAccountId, onComplete, onSkip }: OnboardingWizardProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [data, setData] = useState<OnboardingData>({
    display_name: '',
    trading_since: new Date().getFullYear() - 1,
    experience_level: 'intermediate',
    trading_style: 'intraday',
    risk_tolerance: 'moderate',
    preferred_instruments: ['NIFTY', 'BANKNIFTY'],
    trading_hours_start: '09:15',
    trading_hours_end: '15:30',
    daily_loss_limit: null,          // off until the trader opts in
    per_trade_loss_limit: null,      // off until the trader opts in
    daily_trade_limit: 10,
    max_position_size: null,         // off until the trader opts in
    cooldown_after_loss: 15,
    max_consecutive_losses: 3,
    trading_capital: null,
    enable_daily_loss_limit: false,
    enable_per_trade_loss_limit: false,
    enable_max_position_size: false,
    known_weaknesses: [],
    push_enabled: true,
    whatsapp_enabled: false,
    alert_sensitivity: 'medium',
    guardian_enabled: false,
  });

  const progress = (currentStep / STEPS.length) * 100;

  // Constitution review (Engine v2 Q24): when the review step opens, prefill the
  // recommended rules.
  //
  // These values come from the server. A local copy of the matrix used to live
  // here, and it had already drifted — it never set max_position_size, so the
  // review screen showed four of the five recommended rules and the fifth stayed
  // whatever the form defaulted to. The backend owns the matrix
  // (ConstitutionService.generate_defaults); this asks it.
  // The server's suggested money rules, shown but never applied on their own.
  // Calculated ONCE, in `constitution_service.generate_defaults`; this form
  // deliberately does not recompute them - a local copy of that matrix already
  // existed here once and had drifted.
  // Only the DAILY LOSS LIMIT is suggested. `suggested_max_position_size` was
  // removed from the backend on 1 Sep 2026: it returned a generic 1-3% "risk
  // per trade", and this product is for F&O traders, where the median position
  // needs Rs 7,580 of margin and a 2% rule is unsatisfiable below roughly
  // Rs 379,000 of capital. The exposure rule is still offered — we simply do
  // not put a number in the trader's mouth.
  const [suggested, setSuggested] = useState<{
    daily_loss_limit: number | null;
  }>({ daily_loss_limit: null });

  const prefilledRef = useRef(false);
  useEffect(() => {
    if (currentStep !== 4) return;
    // Re-runs when capital changes, because the SUGGESTED daily loss limit is
    // derived from it and capital is entered on this very screen — it is not
    // persisted until this step is submitted, so the server is told the value
    // rather than asked to look it up. The count/time prefill below is guarded
    // by `prefilledRef` so it still happens exactly once and never overwrites
    // a slider the trader has already moved.
    const capital = data.trading_capital;
    const t = setTimeout(() => {
    (async () => {
      try {
        const res = await api.post('/api/constitution/generate',
          capital != null ? { trading_capital: capital } : {});
        const rec = res.data?.recommended;
        if (!rec) return;
        // The SUGGESTED money rules are displayed; they are not applied.
        setSuggested({ daily_loss_limit: rec.suggested_daily_loss_limit ?? null });
        if (prefilledRef.current) return;
        prefilledRef.current = true;
        setData(d => ({
          ...d,
          // Count and time rules are enforced defaults — they are not shares of
          // capital, so "more than 10 trades today" means the same at any
          // account size and the server ships them set.
          daily_trade_limit: rec.daily_trade_limit ?? d.daily_trade_limit,
          cooldown_after_loss: rec.cooldown_after_loss ?? d.cooldown_after_loss,
          max_consecutive_losses: rec.max_consecutive_losses ?? d.max_consecutive_losses,
          // daily_loss_limit and max_position_size are deliberately NOT taken
          // from `rec` — the server returns null for both on purpose. They are
          // set only by the opt-in below.
        }));
      } catch {
        // A failed recommendation must not block onboarding — the review step
        // still works. The money rules simply stay off and un-suggested, which
        // is the correct fallback: they are opt-in, so "no suggestion" costs
        // the trader nothing and enforces nothing.
      }
    })();
    }, 400);   // debounce: capital is typed a digit at a time
    return () => clearTimeout(t);
    // `data.trading_capital` is a dependency on purpose — the suggested loss
    // limit is derived from it. Depending on the whole `data` object would
    // refetch on every slider move.
  }, [currentStep, data.trading_capital]);

  const handleNext = async () => {
    setIsLoading(true);
    try {
      // Steps 1–5 persist profile data; step 6 (history import) is optional and
      // saves nothing itself — the import card posts directly when a file is chosen.
      if (currentStep <= 5) {
        const stepData = getStepData(currentStep);
        await api.post(`/api/profile/onboarding/step${currentStep}`, stepData);
      }

      if (currentStep < STEPS.length) {
        setCurrentStep(currentStep + 1);
      } else {
        toast.success('Setup complete! Welcome to TradeMentor.');
        onComplete();
      }
    } catch (error) {
      console.error('Failed to save step:', error);
      toast.error('Failed to save. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleSkip = async () => {
    try {
      await api.post('/api/profile/onboarding/skip', null);
      toast.info('Setup skipped. You can configure settings anytime.');
      onSkip();
    } catch (error) {
      console.error('Failed to skip:', error);
      onSkip();
    }
  };

  const getStepData = (step: number) => {
    switch (step) {
      case 1:
        return { display_name: data.display_name, trading_since: data.trading_since };
      case 2:
        return {
          experience_level: data.experience_level,
          trading_style: data.trading_style,
          risk_tolerance: data.risk_tolerance,
        };
      case 3:
        return {
          preferred_instruments: data.preferred_instruments,
          trading_hours_start: data.trading_hours_start,
          trading_hours_end: data.trading_hours_end,
        };
      case 4:
        return {
          // null unless explicitly enabled. The backend drops nulls
          // (`{k: v for k, v in rules.items() if v is not None}`), so an
          // un-opted rule is never written and `constitution_violation`
          // abstains on it.
          daily_loss_limit: data.enable_daily_loss_limit ? data.daily_loss_limit : null,
          per_trade_loss_limit: data.enable_per_trade_loss_limit ? data.per_trade_loss_limit : null,
          daily_trade_limit: data.daily_trade_limit,
          // Enabled AND filled in. A ticked box with an empty field enforces
          // nothing - the rule needs a number, and we do not supply one.
          max_position_size: data.enable_max_position_size ? data.max_position_size : null,
          cooldown_after_loss: data.cooldown_after_loss,
          max_consecutive_losses: data.max_consecutive_losses,
          trading_capital: data.trading_capital,
          known_weaknesses: data.known_weaknesses,
        };
      case 5:
        return {
          push_enabled: data.push_enabled,
          whatsapp_enabled: data.whatsapp_enabled,
          alert_sensitivity: data.alert_sensitivity,
          guardian_enabled: data.guardian_enabled,
        };
      default:
        return {};
    }
  };

  const toggleInstrument = (instrument: string) => {
    setData(prev => ({
      ...prev,
      preferred_instruments: prev.preferred_instruments.includes(instrument)
        ? prev.preferred_instruments.filter(i => i !== instrument)
        : [...prev.preferred_instruments, instrument]
    }));
  };

  const toggleWeakness = (weakness: string) => {
    setData(prev => ({
      ...prev,
      known_weaknesses: prev.known_weaknesses.includes(weakness)
        ? prev.known_weaknesses.filter(w => w !== weakness)
        : [...prev.known_weaknesses, weakness]
    }));
  };

  return (
    <div className="fixed inset-0 bg-background/95 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="tm-card overflow-hidden w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="px-6 py-5 border-b border-border flex-shrink-0">
          <div className="mb-5">
            {/* Progress bar */}
            <div className="h-1.5 bg-muted rounded-full overflow-hidden mb-3">
              <div
                className="h-full bg-tm-brand rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="flex justify-between">
              {STEPS.map((step) => {
                const StepIcon = step.icon;
                const isComplete = currentStep > step.id;
                const isCurrent = currentStep === step.id;
                return (
                  <div
                    key={step.id}
                    className={`flex flex-col items-center ${isCurrent ? 'text-tm-brand' : isComplete ? 'text-tm-profit' : 'text-muted-foreground'}`}
                  >
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center ${
                        isCurrent ? 'bg-tm-brand text-white' :
                        isComplete ? 'bg-tm-profit text-white' : 'bg-muted'
                      }`}
                    >
                      {isComplete ? <Check className="h-4 w-4" /> : <StepIcon className="h-4 w-4" />}
                    </div>
                    <span className="text-xs mt-1 hidden sm:block">{step.title}</span>
                  </div>
                );
              })}
            </div>
          </div>

          <p className="text-base font-semibold text-foreground">{STEPS[currentStep - 1].title}</p>
          <p className="text-sm text-muted-foreground mt-0.5">{STEPS[currentStep - 1].description}</p>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-6">
          <div key={currentStep} className="animate-fade-in-up">
              {/* Step 1: Welcome */}
              {currentStep === 1 && (
                <div className="space-y-6">
                  <div className="text-center py-4">
                    <div className="w-20 h-20 bg-teal-50 dark:bg-teal-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                      <Brain className="h-10 w-10 text-tm-brand" />
                    </div>
                    <h3 className="text-lg font-semibold">Welcome to TradeMentor</h3>
                    <p className="text-muted-foreground text-sm mt-2">
                      Your AI-powered trading psychology coach. Let's personalize your experience.
                    </p>
                  </div>

                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label>What should we call you?</Label>
                      <Input
                        placeholder="Your name or nickname"
                        value={data.display_name}
                        onChange={(e) => setData({ ...data, display_name: e.target.value })}
                      />
                    </div>

                    <div className="space-y-2">
                      <Label>When did you start trading?</Label>
                      <Select
                        value={data.trading_since.toString()}
                        onValueChange={(value) => setData({ ...data, trading_since: parseInt(value) })}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {Array.from({ length: 15 }, (_, i) => new Date().getFullYear() - i).map((year) => (
                            <SelectItem key={year} value={year.toString()}>
                              {year}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>
              )}

              {/* Step 2: Trading Style */}
              {currentStep === 2 && (
                <div className="space-y-6">
                  <div className="space-y-3">
                    <Label>Experience Level</Label>
                    <div className="grid grid-cols-2 gap-3">
                      {EXPERIENCE_LEVELS.map((level) => (
                        <div
                          key={level.value}
                          className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${data.experience_level === level.value
                              ? 'border-tm-brand bg-teal-50/50 dark:bg-teal-900/10'
                              : 'border-border hover:border-tm-brand/50'
                            }`}
                          onClick={() => setData({ ...data, experience_level: level.value })}
                        >
                          <p className="font-medium">{level.label}</p>
                          <p className="text-xs text-muted-foreground">{level.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-3">
                    <Label>Trading Style</Label>
                    <div className="grid grid-cols-2 gap-3">
                      {TRADING_STYLES.map((style) => (
                        <div
                          key={style.value}
                          className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${data.trading_style === style.value
                              ? 'border-tm-brand bg-teal-50/50 dark:bg-teal-900/10'
                              : 'border-border hover:border-tm-brand/50'
                            }`}
                          onClick={() => setData({ ...data, trading_style: style.value })}
                        >
                          <p className="font-medium">{style.label}</p>
                          <p className="text-xs text-muted-foreground">{style.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-3">
                    <Label>Risk Tolerance</Label>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 sm:gap-3">
                      {RISK_TOLERANCE.map((risk) => (
                        <div
                          key={risk.value}
                          className={`p-4 rounded-lg border-2 cursor-pointer transition-all text-center ${data.risk_tolerance === risk.value
                              ? 'border-tm-brand bg-teal-50/50 dark:bg-teal-900/10'
                              : 'border-border hover:border-tm-brand/50'
                            }`}
                          onClick={() => setData({ ...data, risk_tolerance: risk.value })}
                        >
                          <div className={`w-4 h-4 rounded-full ${risk.color} mx-auto mb-2`} />
                          <p className="font-medium text-sm">{risk.label}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Step 3: Preferences */}
              {currentStep === 3 && (
                <div className="space-y-6">
                  <div className="space-y-3">
                    <Label>What do you trade?</Label>
                    <div className="flex flex-wrap gap-2">
                      {INSTRUMENTS.map((instrument) => (
                        <Button
                          key={instrument.value}
                          variant="outline"
                          size="sm"
                          className={data.preferred_instruments.includes(instrument.value)
                            ? 'bg-tm-brand text-white border-tm-brand hover:bg-tm-brand/90'
                            : ''}
                          onClick={() => toggleInstrument(instrument.value)}
                        >
                          {instrument.label}
                        </Button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-3">
                    <Label className="flex items-center gap-2">
                      <Clock className="h-4 w-4" />
                      Your Trading Hours
                    </Label>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label className="text-xs text-muted-foreground">Start Time</Label>
                        <Input
                          type="time"
                          value={data.trading_hours_start}
                          onChange={(e) => setData({ ...data, trading_hours_start: e.target.value })}
                        />
                      </div>
                      <div>
                        <Label className="text-xs text-muted-foreground">End Time</Label>
                        <Input
                          type="time"
                          value={data.trading_hours_end}
                          onChange={(e) => setData({ ...data, trading_hours_end: e.target.value })}
                        />
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      We'll only monitor and alert during these hours
                    </p>
                  </div>
                </div>
              )}

              {/* Step 4: Constitution review — accept or adjust (Q24) */}
              {currentStep === 4 && (
                <div className="space-y-6">
                  <div className="rounded-lg border border-tm-brand/30 bg-tm-brand/5 px-4 py-3">
                    <p className="text-sm text-foreground font-medium">
                      Based on your profile, here are your recommended trading rules.
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Accept them or customize now. You can always tighten them instantly,
                      while relaxing them later requires additional safeguards.
                    </p>
                  </div>

                  <div className="space-y-3">
                    <Label className="flex items-center gap-2">
                      <Wallet className="h-4 w-4" />
                      Trading Capital (₹)
                    </Label>
                    <Input
                      type="number"
                      placeholder="e.g. 200000"
                      value={data.trading_capital ?? ''}
                      onChange={(e) => {
                        const cap = e.target.value === '' ? null : Number(e.target.value);
                        // Capital alone sets no rule. It feeds the server's
                        // SUGGESTION, which the trader may then enable below.
                        // This used to compute `cap * 0.02` here — a second
                        // copy of the backend matrix, and the path by which a
                        // loss limit was applied without anyone choosing it.
                        setData(d => ({ ...d, trading_capital: cap }));
                      }}
                    />
                    <p className="text-xs text-muted-foreground">
                      Powers your loss limit and position sizing rules
                    </p>
                  </div>

                  {/*
                    MONEY RULES — OPTIONAL, OFF BY DEFAULT.

                    The count and time rules above are enforced defaults; these
                    two are not. The distinction is the product's, not this
                    screen's: `constitution_service.generate_defaults` returns
                    null for both and offers a `suggested_*` value beside each,
                    because a share-of-capital rule cannot be chosen for someone
                    else. F&O lot sizes are fixed — on ₹50,000 a 2% per-trade
                    rule allows ₹1,000 while one option lot costs ₹5,000-15,000,
                    so an auto-applied limit breaches on contact and teaches the
                    trader to ignore the alert.

                    Suggestion → trader decides → Rule becomes active.
                  */}
                  <div className="space-y-4 rounded-lg border border-border p-4">
                    <div className="space-y-1">
                      <Label className="flex items-center gap-2 text-sm font-semibold">
                        <Wallet className="h-4 w-4" />
                        Set your money rules
                      </Label>
                      <p className="text-xs text-muted-foreground">
                        Optional limits you can choose to enforce. Left off, nothing
                        is enforced and no alerts are raised against them.
                      </p>
                    </div>

                    {/* Daily loss limit */}
                    <div className="space-y-2">
                      <div className="flex items-start gap-3">
                        <Checkbox
                          id="enable-daily-loss"
                          checked={data.enable_daily_loss_limit}
                          disabled={suggested.daily_loss_limit === null}
                          onCheckedChange={(checked) =>
                            setData(d => ({
                              ...d,
                              enable_daily_loss_limit: checked === true,
                              daily_loss_limit: checked === true
                                ? (d.daily_loss_limit ?? suggested.daily_loss_limit)
                                : null,
                            }))}
                        />
                        <div className="space-y-0.5">
                          <Label htmlFor="enable-daily-loss" className="text-sm">
                            Enable daily loss limit
                          </Label>
                          <p className="text-xs text-muted-foreground">
                            {suggested.daily_loss_limit !== null
                              ? `Suggested: ₹${suggested.daily_loss_limit.toLocaleString()} — based on your account size.`
                              : 'Enter your trading capital above to see a suggestion.'}
                          </p>
                        </div>
                      </div>
                      {data.enable_daily_loss_limit && data.daily_loss_limit !== null && (
                        <div className="space-y-2 pl-7">
                          <div className="flex justify-between">
                            <span className="text-xs text-muted-foreground">Your limit</span>
                            <span className="text-sm font-medium">
                              ₹{data.daily_loss_limit.toLocaleString()}
                            </span>
                          </div>
                          <Slider
                            value={[data.daily_loss_limit]}
                            onValueChange={([value]) => setData({ ...data, daily_loss_limit: value })}
                            min={1000}
                            max={100000}
                            step={1000}
                          />
                        </div>
                      )}
                    </div>

                    {/* Per-trade loss limit — RUPEES, and no suggestion */}
                    <div className="space-y-2">
                      <div className="flex items-start gap-3">
                        <Checkbox
                          id="enable-per-trade-loss"
                          checked={data.enable_per_trade_loss_limit}
                          onCheckedChange={(checked) =>
                            setData(d => ({
                              ...d,
                              enable_per_trade_loss_limit: checked === true,
                              per_trade_loss_limit: checked === true ? d.per_trade_loss_limit : null,
                            }))}
                        />
                        <div className="space-y-0.5">
                          <Label htmlFor="enable-per-trade-loss" className="text-sm">
                            Enable per-trade loss limit
                          </Label>
                          <p className="text-xs text-muted-foreground">
                            The most you are willing to lose on a single position.
                            We do not suggest a number.
                          </p>
                        </div>
                      </div>
                      {data.enable_per_trade_loss_limit && (
                        <div className="space-y-2 pl-7">
                          <Label htmlFor="per-trade-loss-value" className="text-xs text-muted-foreground">
                            Your limit (₹ per trade)
                          </Label>
                          <Input
                            id="per-trade-loss-value"
                            type="number"
                            min={100}
                            step={100}
                            placeholder="e.g. 4000"
                            value={data.per_trade_loss_limit ?? ''}
                            onChange={(e) =>
                              setData(d => ({
                                ...d,
                                per_trade_loss_limit: e.target.value === '' ? null : Number(e.target.value),
                              }))}
                          />
                          <p className="text-xs text-muted-foreground">
                            Checked after a position closes, on its realised loss.
                            On a multi-leg strategy each leg is measured
                            separately.
                          </p>
                        </div>
                      )}
                    </div>

                    {/* Max risk per trade — a PERCENTAGE of capital */}
                    <div className="space-y-2">
                      <div className="flex items-start gap-3">
                        <Checkbox
                          id="enable-max-risk"
                          checked={data.enable_max_position_size}
                          onCheckedChange={(checked) =>
                            setData(d => ({
                              ...d,
                              enable_max_position_size: checked === true,
                              max_position_size: checked === true ? d.max_position_size : null,
                            }))}
                        />
                        <div className="space-y-0.5">
                          <Label htmlFor="enable-max-risk" className="text-sm">
                            Enable capital exposure limit
                          </Label>
                          <p className="text-xs text-muted-foreground">
                            The most of your capital a single position may commit
                            as margin. We do not suggest a number — F&amp;O lot
                            sizes are fixed, so the right limit depends on your
                            account and your instruments.
                          </p>
                        </div>
                      </div>
                      {data.enable_max_position_size && (
                        <div className="space-y-2 pl-7">
                          <Label htmlFor="max-risk-value" className="text-xs text-muted-foreground">
                            Your limit (% of capital per position)
                          </Label>
                          <Input
                            id="max-risk-value"
                            type="number"
                            min={0.1}
                            max={100}
                            step={0.5}
                            placeholder="e.g. 25"
                            value={data.max_position_size ?? ''}
                            onChange={(e) =>
                              setData(d => ({
                                ...d,
                                max_position_size: e.target.value === '' ? null : Number(e.target.value),
                              }))}
                          />
                          <p className="text-xs text-muted-foreground">
                            Leave blank to skip — the rule is only enforced once
                            you enter a number.
                          </p>
                        </div>
                      )}
                    </div>

                    <p className="text-xs text-muted-foreground">
                      You can turn these on, off or change them any time in{' '}
                      <span className="font-medium text-foreground">My Rules</span>.
                    </p>
                  </div>

                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <Label className="flex items-center gap-2">
                        <Target className="h-4 w-4" />
                        Max Trades Per Day
                      </Label>
                      <span className="text-sm font-medium">{data.daily_trade_limit} trades</span>
                    </div>
                    <Slider
                      value={[data.daily_trade_limit]}
                      onValueChange={([value]) => setData({ ...data, daily_trade_limit: value })}
                      min={1}
                      max={50}
                      step={1}
                    />
                  </div>

                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <Label className="flex items-center gap-2">
                        <Clock className="h-4 w-4" />
                        Cooldown After Loss
                      </Label>
                      <span className="text-sm font-medium">{data.cooldown_after_loss} min</span>
                    </div>
                    <Slider
                      value={[data.cooldown_after_loss]}
                      onValueChange={([value]) => setData({ ...data, cooldown_after_loss: value })}
                      min={5}
                      max={60}
                      step={5}
                    />
                  </div>

                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <Label className="flex items-center gap-2">
                        <Shield className="h-4 w-4" />
                        Stop After Consecutive Losses
                      </Label>
                      <span className="text-sm font-medium">{data.max_consecutive_losses} losses</span>
                    </div>
                    <Slider
                      value={[data.max_consecutive_losses]}
                      onValueChange={([value]) => setData({ ...data, max_consecutive_losses: value })}
                      min={2}
                      max={10}
                      step={1}
                    />
                  </div>

                  <div className="space-y-3">
                    <Label>Known Weaknesses (be honest!)</Label>
                    <div className="flex flex-wrap gap-2">
                      {WEAKNESSES.map((weakness) => (
                        <Button
                          key={weakness.value}
                          variant="outline"
                          size="sm"
                          className={data.known_weaknesses.includes(weakness.value)
                            ? 'bg-tm-brand text-white border-tm-brand hover:bg-tm-brand/90'
                            : ''}
                          onClick={() => toggleWeakness(weakness.value)}
                        >
                          {weakness.label}
                        </Button>
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      This helps us give you more relevant alerts and coaching
                    </p>
                  </div>
                </div>
              )}

              {/* Step 5: Notifications */}
              {currentStep === 5 && (
                <div className="space-y-6">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between p-4 border rounded-lg">
                      <div>
                        <p className="font-medium">Push Notifications</p>
                        <p className="text-xs text-muted-foreground">Real-time alerts in your browser</p>
                      </div>
                      <Switch
                        checked={data.push_enabled}
                        onCheckedChange={(checked) => setData({ ...data, push_enabled: checked })}
                      />
                    </div>

                    <div className="flex items-center justify-between p-4 border rounded-lg">
                      <div>
                        <p className="font-medium">WhatsApp Reports</p>
                        <p className="text-xs text-muted-foreground">Daily summary via WhatsApp</p>
                      </div>
                      <Switch
                        checked={data.whatsapp_enabled}
                        onCheckedChange={(checked) => setData({ ...data, whatsapp_enabled: checked })}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Step 6: Import history (optional) */}
              {currentStep === 6 && (
                <div className="space-y-4">
                  <div className="text-center py-2">
                    <div className="w-16 h-16 bg-tm-brand/10 rounded-full flex items-center justify-center mx-auto mb-3">
                      <Upload className="h-8 w-8 text-tm-brand" />
                    </div>
                    <h3 className="text-lg font-semibold">Start with your real history</h3>
                    <p className="text-muted-foreground text-sm mt-2 max-w-md mx-auto">
                      Zerodha only shares <span className="text-foreground font-medium">today's</span> trades with us.
                      Import your Console tradebook so your Analytics, Edge and Habits are full from day one.
                    </p>
                  </div>
                  <TradebookImportCard />
                  <p className="text-xs text-muted-foreground text-center">
                    Optional — you can always do this later in Settings. Click <span className="font-medium">Complete Setup</span> to finish.
                  </p>
                </div>
              )}
            </div>
        </div>

        {/* Navigation — outside the scrollable area so it's always visible */}
        <div className="flex justify-between px-6 py-4 border-t border-border flex-shrink-0">
          <div>
            {currentStep === 1 ? (
              <Button variant="ghost" onClick={handleSkip}>
                Skip Setup
              </Button>
            ) : (
              <Button variant="outline" onClick={handleBack} disabled={isLoading}>
                <ChevronLeft className="h-4 w-4 mr-1" />
                Back
              </Button>
            )}
          </div>

          <Button
            className="bg-tm-brand hover:bg-tm-brand/90 text-white"
            onClick={handleNext}
            disabled={isLoading}
          >
            {isLoading ? "Saving…" : currentStep === STEPS.length ? (
              <>Complete Setup <Check className="h-4 w-4 ml-2" /></>
            ) : (
              <>Next <ChevronRight className="h-4 w-4 ml-1" /></>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
