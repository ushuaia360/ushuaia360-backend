-- Agregar campo name a la tabla trails
ALTER TABLE trails ADD COLUMN IF NOT EXISTS name TEXT;

-- Comentario sobre la columna
COMMENT ON COLUMN trails.name IS 'Nombre legible del sendero';
