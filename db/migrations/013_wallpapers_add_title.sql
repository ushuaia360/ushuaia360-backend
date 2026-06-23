-- La tabla wallpapers se creó antes con is_premium; el admin panel usa title.
ALTER TABLE wallpapers ADD COLUMN IF NOT EXISTS title TEXT;
