-- =============================================================================
-- 20260507_004_product_images_bucket.sql
-- US-1A-02-06 — Bucket Supabase Storage `product-images` privado + RLS por rol.
--
-- Estructura de paths:
--   master/{sku}/{uuid}.{ext}                        → originales (write comercial+)
--   thumbnails/{sku}/{256|512|1024}/primary.webp     → variantes (write Celery con service_role)
--   external_mirror/{sku}/{uuid}.{ext}               → mirror probe US-1A-02-07
--
-- Modelo de acceso (defensa en profundidad):
--   1. Bucket `public=false` — sin URLs públicas directas.
--   2. RLS sobre `storage.objects` por rol JWT:
--        comercial+ → SELECT (necesario para signed URL emission desde backend)
--        gerente_comercial+ → SELECT, INSERT, UPDATE
--        ti_integracion / admin → SELECT, INSERT, UPDATE, DELETE
--   3. El backend FastAPI emite signed URLs (TTL 1h default, configurable hasta 24h)
--      con `service_role` — bypass de RLS. Frontend nunca toca Supabase Storage
--      directamente — sólo recibe la signed URL del backend (ver
--      `app/services/storage.py`).
-- =============================================================================

-- 1. Crear bucket si no existe (idempotente — Supabase lo gestiona via tabla).
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'product-images',
    'product-images',
    false,                                       -- privado, sin URLs públicas
    5242880,                                     -- 5 MB max (5 * 1024 * 1024)
    ARRAY['image/png','image/jpeg','image/webp','image/avif']
)
ON CONFLICT (id) DO UPDATE SET
    public = EXCLUDED.public,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;

-- 2. Helper: leer rol del JWT (mismo patrón que `current_role_code()` de
-- 20260506_003 — lo redefinimos aquí porque storage.objects vive en schema
-- distinto y queremos asegurarnos que la función esté disponible).
-- Reutilizamos la del schema public.

-- 3. Políticas RLS sobre `storage.objects` para el bucket `product-images`.
-- Convención Supabase: cada policy debe referenciar `bucket_id`.

-- ---------- SELECT: comercial+ puede leer ----------
DROP POLICY IF EXISTS "product_images_select_comercial" ON storage.objects;
CREATE POLICY "product_images_select_comercial"
    ON storage.objects FOR SELECT
    TO authenticated
    USING (
        bucket_id = 'product-images'
        AND public.current_role_code() IN (
            'comercial', 'gerente_comercial', 'ti_integracion', 'admin'
        )
    );

-- ---------- INSERT: gerente_comercial+ puede subir ----------
-- Nota: comercial NO sube directamente — debe pasar por el backend, que usa
-- service_role. El requirement dice "gerente+ puede write".
DROP POLICY IF EXISTS "product_images_insert_gerente" ON storage.objects;
CREATE POLICY "product_images_insert_gerente"
    ON storage.objects FOR INSERT
    TO authenticated
    WITH CHECK (
        bucket_id = 'product-images'
        AND public.current_role_code() IN (
            'gerente_comercial', 'ti_integracion', 'admin'
        )
    );

-- ---------- UPDATE: gerente_comercial+ puede sobrescribir ----------
DROP POLICY IF EXISTS "product_images_update_gerente" ON storage.objects;
CREATE POLICY "product_images_update_gerente"
    ON storage.objects FOR UPDATE
    TO authenticated
    USING (
        bucket_id = 'product-images'
        AND public.current_role_code() IN (
            'gerente_comercial', 'ti_integracion', 'admin'
        )
    )
    WITH CHECK (
        bucket_id = 'product-images'
        AND public.current_role_code() IN (
            'gerente_comercial', 'ti_integracion', 'admin'
        )
    );

-- ---------- DELETE: admin/TI sólo ----------
DROP POLICY IF EXISTS "product_images_delete_admin" ON storage.objects;
CREATE POLICY "product_images_delete_admin"
    ON storage.objects FOR DELETE
    TO authenticated
    USING (
        bucket_id = 'product-images'
        AND public.current_role_code() IN ('ti_integracion', 'admin')
    );

-- 4. Documentación.
COMMENT ON POLICY "product_images_select_comercial" ON storage.objects IS
    'US-1A-02-06: comercial+ puede leer objetos del bucket product-images.';
COMMENT ON POLICY "product_images_insert_gerente" ON storage.objects IS
    'US-1A-02-06: gerente_comercial+ puede subir. Comercial sube via backend (service_role).';
COMMENT ON POLICY "product_images_delete_admin" ON storage.objects IS
    'US-1A-02-06: sólo admin/TI puede borrar archivos (incluso archivados).';
