-- Storage policies para todos los buckets del admin panel.
-- El panel usa auth propio (JWT custom), no Supabase Auth,
-- por lo que las subidas llegan como rol 'anon'.
-- Ejecutar en: Supabase Dashboard → SQL Editor

-- ── wallpapers ───────────────────────────────────────────────────────────────
INSERT INTO storage.buckets (id, name, public)
VALUES ('wallpapers', 'wallpapers', true)
ON CONFLICT (id) DO UPDATE SET public = true;

CREATE POLICY "wallpapers: public read"
  ON storage.objects FOR SELECT
  USING (bucket_id = 'wallpapers');

CREATE POLICY "wallpapers: anon insert"
  ON storage.objects FOR INSERT
  WITH CHECK (bucket_id = 'wallpapers');

CREATE POLICY "wallpapers: anon delete"
  ON storage.objects FOR DELETE
  USING (bucket_id = 'wallpapers');

-- ── trails ───────────────────────────────────────────────────────────────────
INSERT INTO storage.buckets (id, name, public)
VALUES ('trails', 'trails', true)
ON CONFLICT (id) DO UPDATE SET public = true;

CREATE POLICY "trails: public read"
  ON storage.objects FOR SELECT
  USING (bucket_id = 'trails');

CREATE POLICY "trails: anon insert"
  ON storage.objects FOR INSERT
  WITH CHECK (bucket_id = 'trails');

CREATE POLICY "trails: anon delete"
  ON storage.objects FOR DELETE
  USING (bucket_id = 'trails');

-- ── tourist_places ───────────────────────────────────────────────────────────
INSERT INTO storage.buckets (id, name, public)
VALUES ('tourist_places', 'tourist_places', true)
ON CONFLICT (id) DO UPDATE SET public = true;

CREATE POLICY "tourist_places: public read"
  ON storage.objects FOR SELECT
  USING (bucket_id = 'tourist_places');

CREATE POLICY "tourist_places: anon insert"
  ON storage.objects FOR INSERT
  WITH CHECK (bucket_id = 'tourist_places');

CREATE POLICY "tourist_places: anon delete"
  ON storage.objects FOR DELETE
  USING (bucket_id = 'tourist_places');

-- ── reviews ──────────────────────────────────────────────────────────────────
INSERT INTO storage.buckets (id, name, public)
VALUES ('reviews', 'reviews', true)
ON CONFLICT (id) DO UPDATE SET public = true;

CREATE POLICY "reviews: public read"
  ON storage.objects FOR SELECT
  USING (bucket_id = 'reviews');

CREATE POLICY "reviews: anon insert"
  ON storage.objects FOR INSERT
  WITH CHECK (bucket_id = 'reviews');

CREATE POLICY "reviews: anon delete"
  ON storage.objects FOR DELETE
  USING (bucket_id = 'reviews');
