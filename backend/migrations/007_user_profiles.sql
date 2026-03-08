-- Migration: Create user_profiles table for onboarding and personalization
-- Run this in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL UNIQUE REFERENCES broker_accounts(id) ON DELETE CASCADE,

    -- Onboarding status
    onboarding_completed BOOLEAN DEFAULT FALSE,
    onboarding_step INTEGER DEFAULT 0,

    -- Basic info
    display_name VARCHAR(100),
    trading_since INTEGER,  -- Year started trading

    -- Trading profile
    experience_level VARCHAR(20) DEFAULT 'beginner',  -- beginner, intermediate, experienced, professional
    trading_style VARCHAR(20) DEFAULT 'intraday',     -- scalper, intraday, swing, positional, mixed
    risk_tolerance VARCHAR(20) DEFAULT 'moderate',    -- conservative, moderate, aggressive

    -- Preferences (JSONB arrays)
    preferred_instruments JSONB DEFAULT '[]'::jsonb,
    preferred_segments JSONB DEFAULT '[]'::jsonb,
    trading_hours_start VARCHAR(5) DEFAULT '09:15',
    trading_hours_end VARCHAR(5) DEFAULT '15:30',

    -- Risk management
    daily_loss_limit FLOAT,
    daily_trade_limit INTEGER,
    max_position_size FLOAT,
    cooldown_after_loss INTEGER DEFAULT 15,

    -- Known weaknesses (JSONB array)
    known_weaknesses JSONB DEFAULT '[]'::jsonb,

    -- Notification preferences
    push_enabled BOOLEAN DEFAULT TRUE,
    whatsapp_enabled BOOLEAN DEFAULT FALSE,
    email_enabled BOOLEAN DEFAULT FALSE,
    alert_sensitivity VARCHAR(20) DEFAULT 'medium',  -- low, medium, high

    -- Guardian settings
    guardian_enabled BOOLEAN DEFAULT FALSE,
    guardian_alert_threshold VARCHAR(20) DEFAULT 'danger',  -- danger, caution, all

    -- AI personalization
    ai_persona VARCHAR(50) DEFAULT 'coach',  -- coach, mentor, friend, strict
    detected_patterns JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index
CREATE INDEX IF NOT EXISTS idx_user_profiles_broker_account
    ON user_profiles(broker_account_id);

-- Updated at trigger
CREATE OR REPLACE FUNCTION update_user_profiles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_user_profiles_updated_at ON user_profiles;
CREATE TRIGGER trigger_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_user_profiles_updated_at();

COMMENT ON TABLE user_profiles IS 'User preferences, trading style, and personalization settings';
