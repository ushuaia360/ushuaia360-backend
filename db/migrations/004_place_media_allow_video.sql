-- Allow video in place_media (parity with trail_media / admin uploads).
-- Requires bucket `tourist_places` in Supabase Storage with policies similar to `trails`.

ALTER TABLE place_media DROP CONSTRAINT IF EXISTS place_media_media_type_check;

ALTER TABLE place_media ADD CONSTRAINT place_media_media_type_check
    CHECK (media_type IN ('image', 'photo_360', 'photo_180', 'video'));
