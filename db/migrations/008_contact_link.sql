-- Link de contacto libre (teléfono, WhatsApp, Instagram, web, etc.) en senderos y puntos turísticos
-- Ejecutar en Supabase

ALTER TABLE trails
  ADD COLUMN IF NOT EXISTS contact_link TEXT;

ALTER TABLE tourist_places
  ADD COLUMN IF NOT EXISTS contact_link TEXT;

COMMENT ON COLUMN trails.contact_link IS 'URL o contacto libre (teléfono, red social, web) para el detalle en la app';
COMMENT ON COLUMN tourist_places.contact_link IS 'URL o contacto libre (teléfono, red social, web) para el detalle en la app';
