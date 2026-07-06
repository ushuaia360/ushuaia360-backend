CREATE TABLE IF NOT EXISTS legal_documents (
    type        TEXT        PRIMARY KEY CHECK (type IN ('terms', 'privacy')),
    content     TEXT        NOT NULL DEFAULT '',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed rows so GET always returns something
INSERT INTO legal_documents (type, content) VALUES
    ('terms',   ''),
    ('privacy', '')
ON CONFLICT (type) DO NOTHING;
