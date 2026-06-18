-- Tabla de reportes enviados desde la app móvil
-- Soporta reportes sobre senderos, puntos turísticos y reseñas
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_type VARCHAR(20) NOT NULL CHECK (target_type IN ('trail', 'place', 'review')),
    target_id UUID NOT NULL,
    reported_by UUID REFERENCES users(id) ON DELETE SET NULL,
    reason TEXT NOT NULL,
    context_id UUID,  -- trail_id o place_id cuando se reporta una reseña
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'reviewed', 'dismissed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_target ON reports(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_reported_by ON reports(reported_by);
