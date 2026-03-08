-- Migration: Create push_subscriptions table for Web Push notifications
-- Run this in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS push_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,

    -- Web Push subscription data
    endpoint TEXT NOT NULL UNIQUE,
    p256dh_key VARCHAR(255) NOT NULL,
    auth_key VARCHAR(255) NOT NULL,

    -- Device info
    user_agent VARCHAR(500),
    device_type VARCHAR(50),  -- 'desktop', 'mobile', 'tablet'

    -- Status tracking
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    last_used_at TIMESTAMP WITH TIME ZONE,
    failed_count VARCHAR(10) DEFAULT '0',

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_push_subscriptions_broker_account
    ON push_subscriptions(broker_account_id);
CREATE INDEX IF NOT EXISTS idx_push_subscriptions_active
    ON push_subscriptions(broker_account_id, is_active) WHERE is_active = TRUE;

-- Updated at trigger
CREATE OR REPLACE FUNCTION update_push_subscriptions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_push_subscriptions_updated_at ON push_subscriptions;
CREATE TRIGGER trigger_push_subscriptions_updated_at
    BEFORE UPDATE ON push_subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION update_push_subscriptions_updated_at();

-- RLS (Row Level Security) - Optional, enable if using Supabase auth
-- ALTER TABLE push_subscriptions ENABLE ROW LEVEL SECURITY;
