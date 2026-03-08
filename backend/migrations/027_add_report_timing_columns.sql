-- Migration 027: Add user-configurable report timing columns to user_profiles
-- EOD report time and morning brief time stored as HH:MM strings (IST)
-- Defaults: EOD at 16:00 (4:00 PM), Morning at 08:30 (8:30 AM)

ALTER TABLE user_profiles
    ADD COLUMN IF NOT EXISTS eod_report_time VARCHAR(5) DEFAULT '16:00',
    ADD COLUMN IF NOT EXISTS morning_brief_time VARCHAR(5) DEFAULT '08:30';

COMMENT ON COLUMN user_profiles.eod_report_time IS 'Time to send EOD report in HH:MM IST (default 16:00)';
COMMENT ON COLUMN user_profiles.morning_brief_time IS 'Time to send morning briefing in HH:MM IST (default 08:30)';
