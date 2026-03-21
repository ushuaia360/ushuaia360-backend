-- Lugares turísticos en el mapa (opcional: ejecutar si aún no existe el esquema)
CREATE TABLE IF NOT EXISTS tourist_places (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT UNIQUE NOT NULL,
    name TEXT,
    category TEXT,
    region TEXT,
    country TEXT DEFAULT 'AR',
    description TEXT,
    is_premium BOOLEAN DEFAULT FALSE,
    location GEOGRAPHY(Point, 4326),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS place_media (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    place_id UUID NOT NULL REFERENCES tourist_places(id) ON DELETE CASCADE,
    media_type TEXT NOT NULL CHECK (media_type IN ('image', 'photo_360', 'photo_180')),
    url TEXT NOT NULL,
    thumbnail_url TEXT,
    order_index INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_place_media_place ON place_media(place_id);
