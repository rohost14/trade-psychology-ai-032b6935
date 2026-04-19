import { Shield } from 'lucide-react';
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
        <div className="px-5 py-4 border-b border-border">
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
        <div className="px-5 py-4 border-b border-border">
          <p className="text-sm font-semibold text-foreground flex items-center gap-2">
            <Shield className="h-4 w-4" />
            Trading Limits
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            These calibrate pattern detection to your actual trading style — alerts become more accurate.
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

          {/* Max position size (% of capital) */}
          <div className="space-y-2">
            <Label>Max per options trade — % of capital as premium</Label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={1}
                max={30}
                step={1}
                value={profile.max_position_size ?? 10}
                onChange={(e) => setProfile({ ...profile, max_position_size: Number(e.target.value) })}
                className="w-full accent-[#0D9488]"
              />
              <span className="text-sm font-medium w-12 text-right">{profile.max_position_size ?? 10}%</span>
            </div>
            <p className="text-xs text-muted-foreground">
              Alert fires when a single trade exceeds this % of your capital. Default: 10%.
            </p>
          </div>

          {/* SL % futures */}
          <div className="space-y-2">
            <Label>My typical stop-loss on futures (% of notional)</Label>
            <div className="flex flex-wrap gap-2">
              {[0.5, 1, 1.5, 2, 3].map((pct) => (
                <button
                  key={pct}
                  type="button"
                  className={`px-3 py-1.5 rounded-md border text-sm font-medium transition-all ${
                    (profile.sl_percent_futures ?? 1.0) === pct
                      ? 'border-tm-brand bg-tm-brand text-white'
                      : 'border-border hover:border-tm-brand/50'
                  }`}
                  onClick={() => setProfile({ ...profile, sl_percent_futures: pct })}
                >
                  {pct}%
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              Used to detect no-stop-loss behavior on futures trades.
            </p>
          </div>

          {/* SL % options */}
          <div className="space-y-2">
            <Label>I exit options when premium drops by</Label>
            <div className="flex flex-wrap gap-2">
              {[30, 50, 70, 100].map((pct) => (
                <button
                  key={pct}
                  type="button"
                  className={`px-3 py-1.5 rounded-md border text-sm font-medium transition-all ${
                    (profile.sl_percent_options ?? 50) === pct
                      ? 'border-tm-brand bg-tm-brand text-white'
                      : 'border-border hover:border-tm-brand/50'
                  }`}
                  onClick={() => setProfile({ ...profile, sl_percent_options: pct })}
                >
                  {pct}%
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              Used to detect holding losers too long on options buys.
            </p>
          </div>

          {/* Daily trade limit */}
          <div className="space-y-2">
            <Label htmlFor="daily-trade-limit">My max trades per day</Label>
            <Input
              id="daily-trade-limit"
              type="number"
              min={1}
              max={50}
              placeholder="e.g. 10"
              value={profile.daily_trade_limit ?? ''}
              onChange={(e) => setProfile({ ...profile, daily_trade_limit: e.target.value ? Number(e.target.value) : undefined })}
            />
            <p className="text-xs text-muted-foreground">
              Overtrading alert fires when you exceed this. Scales with your style.
            </p>
          </div>

          {/* Cooldown after loss */}
          <div className="space-y-2">
            <Label>I wait after a loss before re-entering</Label>
            <div className="flex flex-wrap gap-2">
              {[0, 5, 10, 15, 30, 60].map((mins) => (
                <button
                  key={mins}
                  type="button"
                  className={`px-3 py-1.5 rounded-md border text-sm font-medium transition-all ${
                    (profile.cooldown_after_loss ?? 15) === mins
                      ? 'border-tm-brand bg-tm-brand text-white'
                      : 'border-border hover:border-tm-brand/50'
                  }`}
                  onClick={() => setProfile({ ...profile, cooldown_after_loss: mins })}
                >
                  {mins === 0 ? 'None' : `${mins} min`}
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              Revenge trading alert window. If you say 15 min, re-entries at 12 min will fire.
            </p>
          </div>
        </div>
      </div>

    </div>
  );
}
