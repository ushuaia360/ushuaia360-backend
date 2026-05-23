-- Puntos de emergencia asociados a un sendero (refugios, contactos de rescate, etc.)
-- Ejecutar en Supabase antes de desplegar el backend con soporte de emergency_points.

CREATE TABLE IF NOT EXISTS trail_emergency_points (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trail_id UUID NOT NULL REFERENCES trails(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    phone TEXT NOT NULL,
    location JSONB NOT NULL,
    order_index INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trail_emergency_points_trail
    ON trail_emergency_points(trail_id, order_index);

COMMENT ON TABLE trail_emergency_points IS 'Puntos de emergencia / contacto en senderos (coordenadas exactas + teléfono)';
COMMENT ON COLUMN trail_emergency_points.location IS 'JSON {latitude, longitude, elevation?}';
