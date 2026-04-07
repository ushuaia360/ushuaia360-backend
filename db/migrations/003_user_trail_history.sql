-- Historial de recorridos (app móvil): inicio / completado de senderos
CREATE TABLE IF NOT EXISTS user_trail_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    trail_id UUID NOT NULL REFERENCES trails(id) ON DELETE CASCADE,
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    completion_time_minutes INTEGER,
    distance_km NUMERIC(10, 2),
    elevation_gain INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_trail_history_user_started
    ON user_trail_history(user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_trail_history_trail
    ON user_trail_history(trail_id);
