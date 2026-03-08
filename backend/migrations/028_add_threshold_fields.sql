-- Migration 028: Add trader threshold fields to user_profiles
-- These drive the 3-tier threshold system for pattern detection

ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS trading_capital FLOAT;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS sl_percent_futures FLOAT DEFAULT 1.0;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS sl_percent_options FLOAT DEFAULT 50.0;
