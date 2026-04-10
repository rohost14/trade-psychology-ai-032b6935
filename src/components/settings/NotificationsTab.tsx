import { AlertTriangle, Mail, Phone, Bell } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import NotificationSettings from '@/components/settings/NotificationSettings';
import { UserProfile, NotificationStatus, ALERT_SENSITIVITY } from '@/lib/settingsConstants';

interface BrokerAccount {
  broker_email?: string;
}

interface NotificationsTabProps {
  profile: UserProfile;
  setProfile: (profile: UserProfile) => void;
  notificationStatus: NotificationStatus | null;
  account: BrokerAccount | null;
  onTestGuardian: () => void;
}

export function NotificationsTab({
  profile,
  setProfile,
  notificationStatus,
  account,
  onTestGuardian,
}: NotificationsTabProps) {
  return (
    <div className="space-y-6">
      {/* WhatsApp not configured banner */}
      {notificationStatus && !notificationStatus.whatsapp?.twilio_configured && (
        <div className="flex items-start gap-3 p-4 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg">
          <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-700 dark:text-amber-300">
              WhatsApp Not Available
            </p>
            <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
              Twilio is not configured on the server. WhatsApp reports and guardian alerts will be logged but not delivered. Contact admin to set up Twilio credentials.
            </p>
          </div>
        </div>
      )}

      {/* Email not configured banner */}
      {notificationStatus && !notificationStatus.email?.smtp_configured && (
        <div className="flex items-start gap-3 p-4 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg">
          <AlertTriangle className="h-5 w-5 text-blue-600 dark:text-blue-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-medium text-blue-700 dark:text-blue-300">
              Email Delivery Not Configured
            </p>
            <p className="text-xs text-blue-600 dark:text-blue-400 mt-0.5">
              SMTP is not set up on the server. Email reports will be logged but not delivered. Set SMTP_HOST, SMTP_USER, SMTP_PASS, EMAIL_FROM in the backend .env file.
            </p>
          </div>
        </div>
      )}

      {/* Alert Sensitivity */}
      <div className="tm-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <p className="text-sm font-semibold text-foreground">Alert Sensitivity</p>
          <p className="text-xs text-muted-foreground mt-0.5">Control how aggressively patterns are flagged</p>
        </div>
        <div className="p-5">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 sm:gap-3">
            {ALERT_SENSITIVITY.map((level) => (
              <div
                key={level.value}
                className={`p-3 rounded-lg border-2 cursor-pointer transition-all text-center ${profile.alert_sensitivity === level.value
                  ? 'border-tm-brand bg-teal-50/50 dark:bg-teal-900/10'
                  : 'border-border hover:border-tm-brand/50'
                  }`}
                onClick={() => setProfile({ ...profile, alert_sensitivity: level.value })}
              >
                <p className="font-medium text-sm">{level.label}</p>
                <p className="text-xs text-muted-foreground">{level.description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Push Notifications */}
      <NotificationSettings />

      {/* WhatsApp Reports */}
      <div className="tm-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <p className="text-sm font-semibold text-foreground">WhatsApp Reports</p>
          <p className="text-xs text-muted-foreground mt-0.5">Daily trading summaries via WhatsApp</p>
        </div>
        <div className="p-5">
          <div className="flex items-center justify-between p-4 border rounded-lg">
            <div>
              <p className="font-medium">Daily WhatsApp Reports</p>
              <p className="text-sm text-muted-foreground">
                Receive end-of-day trading summary via WhatsApp
              </p>
            </div>
            <Switch
              checked={profile.whatsapp_enabled || false}
              onCheckedChange={(checked) => setProfile({ ...profile, whatsapp_enabled: checked })}
            />
          </div>
        </div>
      </div>

      {/* Email Reports */}
      <div className="tm-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <p className="text-sm font-semibold text-foreground flex items-center gap-2">
            <Mail className="h-4 w-4" />
            Email Reports
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Receive daily post-market reports and morning briefs by email
          </p>
        </div>
        <div className="p-5 space-y-4">
          <div className="flex items-center justify-between p-4 border rounded-lg">
            <div>
              <p className="font-medium">Daily Email Reports</p>
              <p className="text-sm text-muted-foreground">
                Post-market summary at 4:00 PM IST + morning brief at 8:30 AM IST
              </p>
            </div>
            <Switch
              checked={profile.email_enabled || false}
              onCheckedChange={(checked) => setProfile({ ...profile, email_enabled: checked })}
            />
          </div>

          {profile.email_enabled && account && (
            <div className="p-3 bg-muted/40 rounded-lg flex items-center gap-3">
              <Mail className="h-4 w-4 text-muted-foreground shrink-0" />
              <div className="min-w-0">
                <p className="text-xs text-muted-foreground">Reports will be sent to your Zerodha-registered email</p>
                <p className="text-sm font-medium truncate">{account.broker_email || 'your account email'}</p>
              </div>
            </div>
          )}

          {profile.email_enabled && notificationStatus && !notificationStatus.email?.smtp_configured && (
            <p className="text-xs text-amber-600 dark:text-amber-400">
              Email toggle saved but SMTP is not configured on the server yet — emails won't send until an admin sets up SMTP credentials.
            </p>
          )}
        </div>
      </div>

      {/* Guardian Mode */}
      <div className="tm-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <p className="text-sm font-semibold text-foreground flex items-center gap-2">
            <Phone className="h-4 w-4" />
            Guardian Mode
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Set up a trusted contact to receive alerts when you're in danger zone
          </p>
        </div>
        <div className="p-5 space-y-6">
          {/* Enable Guardian */}
          <div className="flex items-center justify-between p-4 border rounded-lg">
            <div>
              <p className="font-medium">Enable Guardian Mode</p>
              <p className="text-sm text-muted-foreground">
                Send critical alerts to your guardian via WhatsApp
              </p>
            </div>
            <Switch
              checked={profile.guardian_enabled || false}
              onCheckedChange={(checked) => setProfile({ ...profile, guardian_enabled: checked })}
            />
          </div>

          {profile.guardian_enabled && (
            <>
              {/* Guardian Name */}
              <div className="space-y-2">
                <Label>Guardian's Name</Label>
                <Input
                  placeholder="e.g. Spouse, Parent, Friend"
                  value={profile.guardian_name || ''}
                  onChange={(e) => setProfile({ ...profile, guardian_name: e.target.value })}
                />
              </div>

              {/* Guardian Phone */}
              <div className="space-y-2">
                <Label>Guardian's WhatsApp Number</Label>
                <Input
                  placeholder="+919876543210"
                  value={profile.guardian_phone || ''}
                  onChange={(e) => setProfile({ ...profile, guardian_phone: e.target.value })}
                />
                <p className="text-xs text-muted-foreground">
                  International format, no spaces — e.g. +919876543210
                </p>
              </div>

              {/* Alert Threshold */}
              <div className="space-y-2">
                <Label>Alert Threshold</Label>
                <Select
                  value={profile.guardian_alert_threshold || 'critical'}
                  onValueChange={(value) => setProfile({ ...profile, guardian_alert_threshold: value })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="critical">Critical Only (Loss limit breached)</SelectItem>
                    <SelectItem value="danger">Danger & Critical</SelectItem>
                    <SelectItem value="warning">Warning, Danger & Critical</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Daily Summary Toggle */}
              <div className="flex items-center justify-between p-4 border rounded-lg">
                <div>
                  <p className="font-medium">Daily Summary Reports</p>
                  <p className="text-sm text-muted-foreground">
                    Send end-of-day trading summary to your guardian
                  </p>
                </div>
                <Switch
                  checked={profile.guardian_daily_summary || false}
                  onCheckedChange={(checked) => setProfile({ ...profile, guardian_daily_summary: checked })}
                />
              </div>

              {/* What Guardian Receives */}
              <div className="p-4 bg-muted/50 rounded-lg space-y-2">
                <p className="font-medium text-sm">Your guardian will receive:</p>
                <ul className="text-sm text-muted-foreground space-y-1">
                  <li>- Daily loss limit breached alerts</li>
                  <li>- Critical patterns (tilt, revenge trading)</li>
                  <li>- Consecutive loss threshold exceeded</li>
                  {profile.guardian_alert_threshold === 'warning' && (
                    <li>- Early warning signs</li>
                  )}
                  {profile.guardian_daily_summary && (
                    <li>- Daily trading summary at your configured EOD time</li>
                  )}
                </ul>
              </div>

              {/* Test Message */}
              <Button
                variant="outline"
                className="w-full"
                onClick={onTestGuardian}
              >
                <Phone className="h-4 w-4 mr-2" />
                Send Test Message
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Report Delivery Timing */}
      <div className="tm-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <p className="text-sm font-semibold text-foreground flex items-center gap-2">
            <Bell className="h-4 w-4" />
            Report Delivery Timing (IST)
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Choose when you receive automated daily reports. Defaults are after market close and before open.
          </p>
        </div>
        <div className="p-5 space-y-6">
          {/* EOD Report Time */}
          <div className="space-y-2">
            <Label htmlFor="eod-time">Post-Market Report (EOD)</Label>
            <div className="flex items-center gap-3">
              <Input
                id="eod-time"
                type="time"
                value={profile.eod_report_time || '16:00'}
                onChange={(e) => setProfile({ ...profile, eod_report_time: e.target.value })}
                className="w-36"
              />
              <span className="text-sm text-muted-foreground">
                IST — Default 4:00 PM (after equity market close)
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              Includes: trade count, P&amp;L, win rate, emotional journey, patterns detected, lessons &amp; tomorrow's focus.
            </p>
          </div>

          {/* Morning Brief Time */}
          <div className="space-y-2">
            <Label htmlFor="morning-time">Morning Readiness Brief</Label>
            <div className="flex items-center gap-3">
              <Input
                id="morning-time"
                type="time"
                value={profile.morning_brief_time || '08:30'}
                onChange={(e) => setProfile({ ...profile, morning_brief_time: e.target.value })}
                className="w-36"
              />
              <span className="text-sm text-muted-foreground">
                IST — Default 8:30 AM (before market open at 9:15)
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              Includes: readiness score, yesterday's recap, watch-outs, personalised checklist &amp; commitment prompt.
            </p>
          </div>

          <div className="p-3 bg-muted/40 rounded-lg text-xs text-muted-foreground">
            ℹ️ Reports are sent to your WhatsApp (guardian number) and as push notifications.
            If no custom time is set, the default times above are used.
          </div>
        </div>
      </div>
    </div>
  );
}
