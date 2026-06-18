-- Apple Sign-In support: columna para vincular usuarios con su Apple ID
-- Ejecutar en Supabase

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS apple_user_id TEXT UNIQUE;
