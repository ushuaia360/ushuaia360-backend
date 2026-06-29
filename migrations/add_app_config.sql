-- Tabla de configuración de estado de la app (mantenimiento / actualización requerida)
--
-- type = 'maintenance'      → bloquea la app cuando is_active = TRUE
-- type = 'required_update'  → muestra modal de update cuando el build del usuario
--                             es menor al mínimo configurado para su plataforma
--
-- Para required_update:
--   android_min_build / ios_min_build indican el build mínimo requerido.
--   Si el build instalado < min_build  →  se muestra el aviso.
--   NULL significa "no aplica check de build para esa plataforma".

CREATE TABLE IF NOT EXISTS app_config (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    type             TEXT        NOT NULL CHECK (type IN ('maintenance', 'required_update')),
    is_active        BOOLEAN     NOT NULL DEFAULT FALSE,
    title            TEXT        NOT NULL DEFAULT '',
    message          TEXT        NOT NULL DEFAULT '',
    -- build mínimo requerido por plataforma (solo relevante para required_update)
    ios_min_build     INTEGER,
    android_min_build INTEGER,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Solo puede haber un registro por tipo
CREATE UNIQUE INDEX IF NOT EXISTS app_config_type_unique ON app_config (type);

-- Trigger para updated_at automático
CREATE OR REPLACE FUNCTION app_config_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS app_config_updated_at ON app_config;
CREATE TRIGGER app_config_updated_at
    BEFORE UPDATE ON app_config
    FOR EACH ROW EXECUTE FUNCTION app_config_set_updated_at();

-- Registros iniciales (inactivos)
INSERT INTO app_config (type, is_active, title, message, ios_min_build, android_min_build)
VALUES
    (
        'maintenance',
        FALSE,
        'En mantenimiento',
        'La app está temporalmente fuera de servicio. Volvé en unos minutos.',
        NULL,
        NULL
    ),
    (
        'required_update',
        FALSE,
        'Actualización requerida',
        'Hay una nueva versión disponible con mejoras importantes. Por favor actualizá la app para continuar.',
        NULL,
        NULL
    )
ON CONFLICT (type) DO NOTHING;
