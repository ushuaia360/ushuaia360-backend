-- Ítems destacados (senderos y puntos turísticos) gestionados desde el panel de Partners
CREATE TABLE IF NOT EXISTS featured_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('trail', 'place')),
    entity_id UUID NOT NULL,
    order_index INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_featured_items_order ON featured_items(order_index ASC);

-- Migra los senderos ya marcados is_featured=true para no perder curaduría existente
INSERT INTO featured_items (entity_type, entity_id, order_index)
SELECT 'trail', id, (ROW_NUMBER() OVER (ORDER BY created_at DESC) - 1)
FROM trails WHERE is_featured = true
ON CONFLICT (entity_type, entity_id) DO NOTHING;
