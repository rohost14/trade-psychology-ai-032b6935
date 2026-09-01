import { Shield } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  UserProfile,
  EXPERIENCE_LEVELS,
  TRADING_STYLES,
  RISK_TOLERANCE,
} from '@/lib/settingsConstants';

interface ProfileTabProps {
  profile: UserProfile;
  setProfile: (profile: UserProfile) => void;
}

export function ProfileTab({ profile, setProfile }: ProfileTabProps) {
  return (
    <div className="space-y-6">
      {/* Basic Info */}
      <div className="tm-card overflow-hidden">
        <div className="px-5 py-3.5 border-b border-border">
          <p className="text-sm font-semibold text-foreground">Trading Profile</p>
          <p className="text-xs text-muted-foreground mt-0.5">Tell us about your trading style and experience</p>
        </div>
        <div className="p-5 space-y-6">
          {/* Display Name */}
          <div className="space-y-2">
            <Label>Display Name</Label>
            <Input
              placeholder="Your name"
              value={profile.display_name || ''}
              onChange={(e) => setProfile({ ...profile, display_name: e.target.value })}
            />
          </div>

          {/* Experience Level */}
          <div className="space-y-2">
            <Label>Experience Level</Label>
            <Select
              value={profile.experience_level}
              onValueChange={(value) => setProfile({ ...profile, experience_level: value })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select experience level" />
              </SelectTrigger>
              <SelectContent>
                {EXPERIENCE_LEVELS.map((level) => (
                  <SelectItem key={level.value} value={level.value}>
                    {level.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Trading Style */}
          <div className="space-y-3">
            <Label>Trading Style</Label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 sm:gap-3">
              {TRADING_STYLES.map((style) => (
                <div
                  key={style.value}
                  className={`p-3 rounded-lg border-2 cursor-pointer transition-all ${profile.trading_style === style.value
                    ? 'border-tm-brand bg-teal-50/50 dark:bg-teal-900/10'
                    : 'border-border hover:border-tm-brand/50'
                    }`}
                  onClick={() => setProfile({ ...profile, trading_style: style.value })}
                >
                  <p className="font-medium text-sm">{style.label}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{style.description}</p>
                </div>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              Helps your AI coach understand your approach. Detection thresholds auto-calibrate from your actual trade history after 5 sessions.
            </p>
          </div>

          {/* Risk Tolerance */}
          <div className="space-y-3">
            <Label>Risk Tolerance</Label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 sm:gap-3">
              {RISK_TOLERANCE.map((risk) => (
                <div
                  key={risk.value}
                  className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${profile.risk_tolerance === risk.value
                    ? 'border-tm-brand bg-teal-50/50 dark:bg-teal-900/10'
                    : 'border-border hover:border-tm-brand/50'
                    }`}
                  onClick={() => setProfile({ ...profile, risk_tolerance: risk.value })}
                >
                  <p className="font-medium text-sm">{risk.label}</p>
                  <p className="text-xs text-muted-foreground mt-1">{risk.description}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Trading Hours */}
          <div className="space-y-2">
            <Label>Trading Hours</Label>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-xs text-muted-foreground">Start Time</Label>
                <Input
                  type="time"
                  value={profile.trading_hours_start || '09:15'}
                  onChange={(e) => setProfile({ ...profile, trading_hours_start: e.target.value })}
                />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">End Time</Label>
                <Input
                  type="time"
                  value={profile.trading_hours_end || '15:30'}
                  onChange={(e) => setProfile({ ...profile, trading_hours_end: e.target.value })}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Trading Limits */}
      <div className="tm-card overflow-hidden">
        <div className="px-5 py-3.5 border-b border-border">
          <p className="text-sm font-semibold text-foreground flex items-center gap-2">
            <Shield className="h-4 w-4" />
            Trading Capital
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            The denominator for every rule expressed as a percentage of capital.
          </p>
        </div>
        <div className="p-5 space-y-6">
          {/* Capital */}
          <div className="space-y-2">
            <Label htmlFor="trading-capital">My trading capital (₹)</Label>
            <Input
              id="trading-capital"
              type="number"
              placeholder="e.g. 500000"
              value={profile.trading_capital ?? ''}
              onChange={(e) => setProfile({ ...profile, trading_capital: e.target.value ? Number(e.target.value) : undefined })}
            />
            <p className="text-xs text-muted-foreground">
              Used to calculate position sizing alerts as % of your actual capital.
            </p>
          </div>

          {/* THE RULES THEMSELVES ARE NOT EDITED HERE.

              `max_position_size`, `sl_percent_options` and `daily_trade_limit`
              had controls on this tab and controls in My Rules. Two editors for
              one rule diverge, and these already had: My Rules accepts any
              options-exit value in 0.1-100 while this tab offered four presets,
              so a 45% rule set there could not be represented here. They also
              differed in what they could express - only My Rules can clear a
              rule, because clearing is a LOOSEN and needs the override
              confirmation and the audit row that only its flow provides. This
              tab's own 409 handler proved the split: it caught the gate and
              told the trader to go to My Rules to finish.

              So the rule editors are gone from here and My Rules is the single
              surface. `trading_capital` stays: it is not a rule, nothing
              enforces it, and it is the denominator every capital-relative rule
              divides by.

              Onboarding still writes the initial rules. That is rule CREATION
              through the same service, not a second editor. */}
          <div className="rounded-lg border border-border px-4 py-3">
            <p className="text-[13px] text-foreground">
              Your loss limits, trade limits, position size, options exit and
              no-trade windows live in{' '}
              <Link to="/my-rules" className="text-tm-brand font-medium hover:underline">
                My Rules
              </Link>.
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Tightening a rule applies at once; relaxing or removing one asks
              for confirmation and is recorded.
            </p>
          </div>

        </div>
      </div>

    </div>
  );
}
