-- Agrega la columna gps_path a user_trail_history para almacenar la ruta GPS
-- real recorrida por el usuario durante el sendero.
--
-- Formato JSONB: array de { "latitude": number, "longitude": number }
-- Ejemplo: [{"latitude": -54.8019, "longitude": -68.303}, ...]
--
-- NULL significa que el recorrido fue completado antes de esta funcionalidad
-- o que el usuario no tenía GPS disponible.

ALTER TABLE user_trail_history
    ADD COLUMN IF NOT EXISTS gps_path JSONB;
