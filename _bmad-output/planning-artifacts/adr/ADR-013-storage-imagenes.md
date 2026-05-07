# ADR-013: Storage de imágenes (S3-compatible mirror, no hot-link a PIM España)

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT

## Contexto

El catálogo de 224 SKUs tiene `image_url_pim` apuntando al PIM de MT España. Hot-linking ese URL desde la app MT ME tiene problemas:

- **Disponibilidad**: si PIM España cae o cambia URLs, todo MT ME pierde imágenes.
- **Latencia**: usuarios y connectors UAE accediendo a CDN España = latencia mayor.
- **Derechos**: no hay acuerdo formal documentado con MT España de uso comercial de las imágenes en marketplaces UAE.
- **Compliance**: marketplaces (Amazon UAE, Noon UAE) requieren URLs estables y propias.
- **Retención**: PIM España puede borrar/renombrar — vínculo se rompe sin aviso.

## Decisión

### Mirror local en object storage S3-compatible

- Cada `image_url_pim` se **descarga** y **almacena** en el bucket de MT ME.
- **Default Fase 1**: Cloudflare R2 (S3-compatible, sin egress fees, edge global).
- **Alternativas si TI MT exige**: AWS S3 (Frankfurt o UAE region), Azure Blob, MinIO self-hosted.
- Nomenclatura del objeto:
  ```
  s3://mtme-products/{sku}/original/{timestamp}.{ext}
  s3://mtme-products/{sku}/thumb/{timestamp}.{ext}     (resize on-demand vía CDN)
  s3://mtme-products/{sku}/marketplace_amazon/{timestamp}.jpg  (variantes por canal)
  ```

### Pipeline de ingestión

1. Importer PIM detecta `image_url_pim` no nulo.
2. Job `mirror_image` (BullMQ) descarga la imagen.
3. Validación: tipo MIME, dimensiones, peso (< 10 MB), no malware (ClamAV opcional Fase 2).
4. Hash SHA256 del contenido → si ya existe (deduplicación por hash), no se duplica.
5. Subida a R2 con metadatos `original_url`, `imported_at`, `imported_by`, `source='pim_es'`.
6. Tabla `product_images`:
   ```sql
   CREATE TABLE product_images (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     sku TEXT NOT NULL REFERENCES products(sku),
     role TEXT NOT NULL,                  -- 'main' | 'gallery_1' | 'marketplace_amazon' | ...
     storage_path TEXT NOT NULL UNIQUE,
     original_url TEXT,
     content_type TEXT,
     bytes INT,
     width INT,
     height INT,
     hash_sha256 TEXT,
     status TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'archived' | 'broken'
     created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
     created_by UUID REFERENCES users(id)
   );
   ```
7. URL pública servida desde el bucket público / CDN (R2 public bucket o presigned URL).

### Variantes / transformaciones

- Default Fase 1: resize on-demand vía Next.js `<Image>` + Cloudflare Image Resizing (R2) o Vercel image optimizer.
- Variantes específicas (Amazon UAE: fondo blanco 1500x1500, Noon: 1200x1200) se preparan **manual o batch** por SKU.
- Marketplaces requieren formatos específicos → tabla `product_images` con `role` permite múltiples variantes por SKU.

### Lifecycle

- Imagen `archived` (no borrada) cuando se reemplaza — preservar historia.
- Backups: snapshot del bucket diario; cross-region opcional Fase 2.

### Acuerdo de derechos con MT España

- Documentar formalmente en S0: BR + MT España firman acuerdo de uso comercial de imágenes para mercados UAE/GCC.
- Si MT España no firma, evaluar:
  - Re-fotografiar productos en Dubai (coste alto, plazo lento).
  - Usar imágenes genéricas / proveedor.

### Política con marketplaces

- Cada vez que se publique a Amazon UAE / Noon UAE, el URL emitido es del bucket MT ME, no del PIM España.
- Si Amazon hace caching de la imagen (lo hace), el URL del bucket es estable → cumple su requisito.

## Alternativas evaluadas

### Alternativa A: Hot-link a PIM España (no mirror)
- **Pros**: cero storage cost, cero pipeline.
- **Contras**: dependencia externa, latencia, riesgo broken link, sin control de derechos.
- **Veredicto**: descartada.

### Alternativa B: Servidor de imágenes self-hosted
- **Pros**: control total.
- **Contras**: ops cost, escalado, CDN, backup → reinventar S3. Sin valor añadido.
- **Veredicto**: descartada.

### Alternativa C: Cloudinary / imgix / Sirv (image SaaS)
- **Pros**: transformaciones automáticas, CDN global, optimizaciones.
- **Contras**: lock-in vendor, coste $$$ a escala (bandwith pricing), data residency UAE no garantizada.
- **Veredicto**: descartada Fase 1; revisar Fase 3 si transformaciones automáticas son críticas.

### Alternativa D: AWS S3 Frankfurt vs Cloudflare R2
- **Pros AWS**: marca conocida, ecosistema completo (Lambda, CloudFront, IAM).
- **Pros R2**: zero egress fees (clave para uso CDN), API S3-compatible, precio menor.
- **Veredicto**: R2 default, AWS S3 si TI MT lo exige.

## Consecuencias positivas

- Independencia operativa de MT España.
- URLs estables para marketplaces.
- Cero egress fees (R2) → CDN-friendly.
- Versionado por hash + lifecycle controlado.
- Pipeline de mirror también valida (tipo, peso, dimensiones) — no se cuelan imágenes corruptas.

## Consecuencias negativas / riesgos

- Storage cost (despreciable: 224 imágenes × 500 KB = ~ 112 MB).
- Pipeline puede fallar (URL del PIM cae). Mitigación: retry exponencial + reporte de imágenes broken al Comercial.
- Acuerdo de derechos con MT España puede tardar. Mitigación: workaround manual usando imágenes proveedor o foto local mientras se firma.

## Cuándo revisar

- **S0**: firmar acuerdo de derechos con MT España.
- **S1** (cuando se implementa importer PIM): validar pipeline end-to-end.
- **Fase 3**: re-evaluar si necesitamos image SaaS (Cloudinary) por transformaciones automáticas.
