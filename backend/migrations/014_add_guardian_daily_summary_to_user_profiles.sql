-- Add missing columns to user_profiles table
ALTER TABLE user_profiles 
ADD COLUMN IF NOT EXISTS guardian_daily_summary BOOLEAN DEFAULT FALSE;

-- Also adding other potentially missing columns just in case, based on the model definition
-- These seem like newer features that might have been added recently
ALTER TABLE user_profiles 
ADD COLUMN IF NOT EXISTS guardian_alert_threshold VARCHAR(20) DEFAULT 'danger';

ALTER TABLE user_profiles 
ADD COLUMN IF NOT EXISTS ai_persona VARCHAR(50) DEFAULT 'coach';

ALTER TABLE user_profiles 
ADD COLUMN IF NOT EXISTS detected_patterns JSONB DEFAULT '{}';
