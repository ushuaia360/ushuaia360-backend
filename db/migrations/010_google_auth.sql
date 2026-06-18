-- Google Sign-In support: columna para vincular usuarios con su Google ID
-- Ejecutar en Supabase

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS google_user_id TEXT UNIQUE;
