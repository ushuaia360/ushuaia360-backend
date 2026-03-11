-- Agregar campo description a la tabla trails
ALTER TABLE trails ADD COLUMN IF NOT EXISTS description TEXT;

-- Comentario sobre la columna
COMMENT ON COLUMN trails.description IS 'Descripción detallada del sendero';
