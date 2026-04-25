-- Fotos opcionales en reseñas (bucket Supabase Storage: `reviews`, público lectura).
-- Ejecutar en producción antes de usar la app con fotos en reseñas.

ALTER TABLE trail_reviews
  ADD COLUMN IF NOT EXISTS image_urls TEXT[] NOT NULL DEFAULT '{}';

ALTER TABLE place_reviews
  ADD COLUMN IF NOT EXISTS image_urls TEXT[] NOT NULL DEFAULT '{}';
