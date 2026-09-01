import { z } from 'zod';

export interface UserProfile {
  display_name?: string;
  trading_since?: number;
  experience_level?: string;
  trading_style?: string;
  risk_tolerance?: string;
  preferred_instruments?: string[];
  trading_hours_start?: string;
  trading_hours_end?: string;
  daily_loss_limit?: number;
  daily_trade_limit?: number;
  max_position_size?: number;     // % of capital per trade (e.g., 10 = 10%)
  trading_capital?: number;       // Rs capital deployed for trading
  sl_percent_options?: number;    // % of premium to exit losing options
  known_weaknesses?: string[];
  push_enabled?: boolean;
  whatsapp_enabled?: boolean;
  email_enabled?: boolean;
  alert_sensitivity?: string;
  guardian_enabled?: boolean;
  guardian_phone?: string;
  guardian_name?: string;
  guardian_alert_threshold?: string;
  guardian_daily_summary?: boolean;
  guardian_confirmed?: boolean;
  guardian_loss_limit?: number;
  eod_report_time?: string;       // HH:MM IST, default '16:00'
  morning_brief_time?: string;    // HH:MM IST, default '08:30'
  ai_persona?: string;
  onboarding_completed?: boolean;
}

export interface NotificationStatus {
  whatsapp: { twilio_configured: boolean };
  push: { vapid_configured: boolean };
  email: { smtp_configured: boolean };
}

export const EXPERIENCE_LEVELS = [
  { value: 'beginner', label: 'Beginner (< 1 year)' },
  { value: 'intermediate', label: 'Intermediate (1-3 years)' },
  { value: 'experienced', label: 'Experienced (3-5 years)' },
  { value: 'professional', label: 'Professional (5+ years)' },
];

export const TRADING_STYLES = [
  { value: 'scalper', label: 'Scalper', description: 'Multiple trades per day, quick exits' },
  { value: 'intraday', label: 'Intraday', description: 'Day trader, no overnight positions' },
  { value: 'swing', label: 'Swing', description: 'Hold for days/weeks' },
  { value: 'positional', label: 'Positional', description: 'Hold for weeks/months' },
  { value: 'mixed', label: 'Mixed', description: 'Combination of styles' },
];

export const RISK_TOLERANCE = [
  { value: 'conservative', label: 'Conservative', description: 'Preserve capital, small positions' },
  { value: 'moderate', label: 'Moderate', description: 'Balanced risk/reward' },
  { value: 'aggressive', label: 'Aggressive', description: 'Higher risk for higher returns' },
];

export const AI_PERSONAS = [
  { value: 'coach', label: 'Coach', description: 'Supportive, encouraging, process-focused' },
  { value: 'mentor', label: 'Mentor', description: 'Experienced guide, shares wisdom' },
  { value: 'friend', label: 'Friend', description: 'Casual, relatable, empathetic' },
  { value: 'strict', label: 'Strict', description: 'No-nonsense, direct, disciplined' },
];

export const ALERT_SENSITIVITY = [
  { value: 'low', label: 'Low', description: 'Only critical alerts' },
  { value: 'medium', label: 'Medium', description: 'Important patterns' },
  { value: 'high', label: 'High', description: 'All detected patterns' },
];

// NULL IS A VALID STATE FOR AN OPTIONAL RULE. 2026-09-02.
//
// Every one of these was `.optional().or(z.undefined())`, which accepts
// `undefined` but REJECTS `null` - and the server sends explicit `null` for an
// unset rule (`to_dict()` emits every key, no exclude_none). So a trader with
// no declared exposure limit, no options stop and no declared capital could not
// save Settings AT ALL: validation failed on the first null field and the save
// aborted with a toast before any request was made.
//
// `.nullable()` states the fact the product already relies on: unset is a
// legitimate value, distinct from a bad one. The RANGES are untouched, so an
// out-of-range number is still rejected exactly as before.
export const profileSchema = z.object({
  daily_loss_limit: z.number().positive('Daily loss limit must be positive').nullable().optional(),
  daily_trade_limit: z.number().int('Must be a whole number').positive('Must be positive').nullable().optional(),
  max_position_size: z.number().min(0.1, 'Min 0.1%').max(100, 'Max 100%').nullable().optional(),
  trading_capital: z.number().positive('Capital must be positive').nullable().optional(),
  sl_percent_options: z.number().min(1, 'Min 1%').max(100, 'Max 100%').nullable().optional(),
  trading_hours_start: z.string().regex(/^\d{2}:\d{2}$/, 'Use HH:MM format').nullable().optional(),
  trading_hours_end: z.string().regex(/^\d{2}:\d{2}$/, 'Use HH:MM format').nullable().optional(),
  guardian_phone: z.string().regex(/^\+\d{10,15}$/, 'Use international format: +919876543210').or(z.literal('')).nullable().optional(),
  guardian_loss_limit: z.number().positive('Guardian loss limit must be positive').nullable().optional(),
  eod_report_time: z.string().regex(/^\d{2}:\d{2}$/, 'Use HH:MM format').nullable().optional(),
  morning_brief_time: z.string().regex(/^\d{2}:\d{2}$/, 'Use HH:MM format').nullable().optional(),
}).passthrough();
