-- Migration: Add profile_completed field to profiles table
-- Date: 2025-09-27
-- Description: Adds a boolean field to track coach profile completion status for onboarding flow

-- Add the profile_completed column with default false
ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS profile_completed boolean NOT NULL DEFAULT false;

-- Optional: Update existing coach profiles to set profile_completed based on existing data
-- This backfills data for existing coaches who may already have complete profiles
UPDATE profiles 
SET profile_completed = CASE 
    WHEN role = 'coach' AND full_name IS NOT NULL AND bio IS NOT NULL AND city IS NOT NULL THEN true
    ELSE false
END
WHERE profile_completed = false;

-- Add a comment to document the column purpose
COMMENT ON COLUMN profiles.profile_completed IS 'Indicates whether a coach has completed their onboarding profile setup';