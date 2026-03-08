-- Migration 025: Add ai_cache JSONB column to user_profiles
-- Stores cached AI responses (persona, narratives) with timestamps for 24hr caching
-- Prevents redundant LLM calls (~$0.08/call for persona)

ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ai_cache JSONB DEFAULT '{}'::jsonb;

COMMENT ON COLUMN user_profiles.ai_cache IS 'Cached AI responses with timestamps. Keys: persona, overview_30, behavior_30, etc.';
