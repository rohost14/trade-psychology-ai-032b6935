import { useState } from 'react';
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
  Wallet
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
  daily_loss_limit: number;
  daily_trade_limit: number;
  max_position_size: number;
  cooldown_after_loss: number;
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
    daily_loss_limit: 5000,
    daily_trade_limit: 10,
    max_position_size: 50000,
    cooldown_after_loss: 15,
    known_weaknesses: [],
    push_enabled: true,
    whatsapp_enabled: false,
    alert_sensitivity: 'medium',
    guardian_enabled: false,
  });

  const progress = (currentStep / STEPS.length) * 100;

  const handleNext = async () => {
    setIsLoading(true);
    try {
      const stepData = getStepData(currentStep);
      await api.post(`/api/profile/onboarding/step${currentStep}`, stepData);

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
          daily_loss_limit: data.daily_loss_limit,
          daily_trade_limit: data.daily_trade_limit,
          max_position_size: data.max_position_size,
          cooldown_after_loss: data.cooldown_after_loss,
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
      <div className="tm-card overflow-hidden w-full max-w-2xl max-h-[90vh] overflow-auto">
        <div className="px-6 py-5 border-b border-border">
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

        <div className="px-6 pb-6">
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

              {/* Step 4: Risk Management */}
              {currentStep === 4 && (
                <div className="space-y-6">
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <Label className="flex items-center gap-2">
                        <Wallet className="h-4 w-4" />
                        Daily Loss Limit
                      </Label>
                      <span className="text-sm font-medium">₹{data.daily_loss_limit.toLocaleString()}</span>
                    </div>
                    <Slider
                      value={[data.daily_loss_limit]}
                      onValueChange={([value]) => setData({ ...data, daily_loss_limit: value })}
                      min={1000}
                      max={100000}
                      step={1000}
                    />
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
            </div>

          {/* Navigation */}
          <div className="flex justify-between mt-8 pt-4 border-t border-border">
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
    </div>
  );
}
