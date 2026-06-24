ALTER TABLE wallpapers
  ADD COLUMN IF NOT EXISTS orientation TEXT NOT NULL DEFAULT 'vertical'
    CHECK (orientation IN ('vertical', 'horizontal'));
