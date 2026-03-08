-- 1. Fix Holdings Table
ALTER TABLE holdings 
ADD COLUMN IF NOT EXISTS broker_account_id UUID REFERENCES broker_accounts(id);

-- 2. Fix User Profiles Table (Guardian & Personalization)
ALTER TABLE user_profiles 
ADD COLUMN IF NOT EXISTS guardian_daily_summary BOOLEAN DEFAULT FALSE;

ALTER TABLE user_profiles 
ADD COLUMN IF NOT EXISTS guardian_alert_threshold VARCHAR(20) DEFAULT 'danger';

ALTER TABLE user_profiles 
ADD COLUMN IF NOT EXISTS ai_persona VARCHAR(50) DEFAULT 'coach';

ALTER TABLE user_profiles 
ADD COLUMN IF NOT EXISTS detected_patterns JSONB DEFAULT '{}';

-- 3. Fix Cooldowns Table (Meta Data)
ALTER TABLE cooldowns 
ADD COLUMN IF NOT EXISTS meta_data JSONB DEFAULT '{}';

ALTER TABLE cooldowns 
ADD COLUMN IF NOT EXISTS message VARCHAR(500);

ALTER TABLE cooldowns 
ADD COLUMN IF NOT EXISTS acknowledged BOOLEAN DEFAULT FALSE;

ALTER TABLE cooldowns 
ADD COLUMN IF NOT EXISTS acknowledged_at TIMESTAMP WITH TIME ZONE;
