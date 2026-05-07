-- =============================================================================
-- 20260507_007_product_images_image_status.sql
-- Mirror SQL de la migración Alembic homónima — añade `image_status` a
-- `product_images` para soportar el pipeline de mirror del worker S2
-- (US-1A-02-07). Existente RLS en `product_images` (read/write por rol)
-- cubre esta columna implícitamente; no se requieren policies nuevas.
-- =============================================================================

ALTER TABLE product_images
    ADD COLUMN IF NOT EXISTS image_status text NOT NULL DEFAULT 'pending';

ALTER TABLE product_images
    DROP CONSTRAINT IF EXISTS ck_product_images_image_status;

ALTER TABLE product_images
    ADD CONSTRAINT ck_product_images_image_status
    CHECK (image_status IN ('pending','mirroring','mirrored','failed'));

CREATE INDEX IF NOT EXISTS ix_product_images_image_status_active
    ON product_images (image_status)
 WHERE image_status IN ('pending','mirroring');

COMMENT ON COLUMN product_images.image_status IS
    'Estado del pipeline de mirror (pending|mirroring|mirrored|failed). Worker probe_mirror lo actualiza.';
