# Spec retrospectiva: Assets/Imágenes de producto (CAT — sub-recurso)

**Feature Branch**: `003-cat-assets-producto`

**Creado**: 2026-05-25

**Tipo**: Retrospectivo — documenta el comportamiento ACTUAL del sistema, no funcionalidad futura.

**Estado**: Borrador

**Dominio**: CAT — Catálogo de Productos (sub-recurso Assets/Imágenes)

**Input**: Spec retrospectiva del proceso EXISTENTE de gestión de assets multimedia
vinculados a fichas de producto. Cubre los endpoints `/{sku}/assets/*`,
`/{sku}/images/*` (deprecados), y el sub-router polimórfico `asset_links`.

---

## Clarificaciones

### Sesión 2026-05-25

- Q: ¿Cuántos tipos de asset soporta el sistema? → A: 10 kinds:
  `photo`, `banner`, `datasheet_pdf`, `exploded_3d`, `section_drawing`,
  `dimension_drawing`, `certificate_pdf`, `video_link`, `external_url`, `mirror_url`
  (confirmado en `assets.py:30-41`).
- Q: ¿Qué roles soporta la tabla `asset_links`? → A: 12 roles:
  `image_padre`, `banner`, `ficha_pdf`, `manual_pdf`, `ce_pdf`,
  `catalogo_pdf`, `exploded_3d`, `section_drawing`, `dimensions_drawing`,
  `video`, `web_image`, `main_image` (confirmado en `asset_links.py:39-52`).
- Q: ¿El bucket de Storage es configurable? → A: `product-images` es el único bucket
  declarado en el stack; está fijo como `DEFAULT_BUCKET` en `asset_service.py:105`.

---

## Escenarios de usuario y prueba *(obligatorio)*

### Historia de usuario 1 — Subir y gestionar imágenes de producto (Priority: P1)

El operador de catálogo (Comercial) sube imágenes de producto al PIM en un flujo
de tres pasos: solicita una URL firmada a Supabase Storage, carga el archivo
directamente desde el navegador, y confirma la operación para que quede persistida
en la base de datos y se encole la generación de miniaturas.

**Por qué esta prioridad**: Las imágenes son obligatorias para publicar en canales
(Amazon/Noon) y para que el comprador B2B pueda identificar el producto correcto.

**Prueba independiente**: Verificable con POST /{sku}/assets/upload-url →
PUT firmado → POST /{sku}/assets/{id}/confirm, sin requerir UI.

**Escenarios de aceptación**:

1. **Dado** que soy Comercial autenticado con permiso `products:write`,
   **Cuando** envío POST /products/{sku}/assets/upload-url con
   `{"kind":"photo","filename":"img.jpg","mime_type":"image/jpeg"}`,
   **Entonces** el sistema devuelve `{ storage_path, upload_url, token, method,
   headers, expires_in, bucket, kind }` con HTTP 200, y el `upload_url` apunta
   al bucket `product-images` de Supabase Storage.

2. **Dado** el `storage_path` y `token` obtenidos en el paso anterior,
   **Cuando** el frontend llama a `supabase.storage.uploadToSignedUrl(path, token, file)`,
   **Entonces** el archivo queda alojado en Storage y el operador puede llamar
   al endpoint de confirmación.

3. **Dado** que el archivo ha sido cargado en Storage,
   **Cuando** envío POST /products/{sku}/assets/{uuid}/confirm con
   `{ storage_path, kind, mime_type, bytes_size, width, height, is_primary }`,
   **Entonces** el sistema crea el registro `ProductAsset` con HTTP 201,
   y para `kind=photo/banner/mirror_url` encola la tarea Celery de miniaturas.

4. **Dado** un producto sin imágenes,
   **Cuando** envío GET /products/{sku}/assets,
   **Entonces** el sistema devuelve una lista vacía con HTTP 200.

5. **Dado** un producto con múltiples assets de distintos kinds,
   **Cuando** envío GET /products/{sku}/assets?kind=photo,
   **Entonces** el sistema filtra y devuelve solo los assets de kind `photo`,
   ordenados por `position` y `created_at`.

---

### Historia de usuario 2 — Gestión del ciclo de vida de un asset (Priority: P2)

El operador marca un asset como imagen principal, archiva assets obsoletos o los
restaura, y elimina permanentemente assets erróneos. En el caso de imágenes
mirroreadas desde URLs externas (scraped), el operador registra la URL origen.

**Por qué esta prioridad**: El control del activo principal y el ciclo de vida de
archivado son imprescindibles para mantener la galería del producto limpia en canales.

**Prueba independiente**: Verificable con PATCH /primary, /archive, /restore,
DELETE /{asset_id}, y POST de mirror externo.

**Escenarios de aceptación**:

1. **Dado** un asset de kind `photo` para el SKU `MT-V-038`,
   **Cuando** envío PATCH /products/MT-V-038/assets/{id}/primary,
   **Entonces** el sistema marca ese asset como `is_primary=true` y desmarca
   automáticamente los demás assets del mismo (sku, kind).

2. **Dado** un asset activo,
   **Cuando** envío PATCH /products/{sku}/assets/{id}/archive,
   **Entonces** el sistema cambia `status='archived'` y registra `archived_at`
   y `archived_by` (actor del request).

3. **Dado** un asset archivado,
   **Cuando** envío PATCH /products/{sku}/assets/{id}/restore,
   **Entonces** el sistema cambia `status='active'` y limpia `archived_at`
   y `archived_by`.

4. **Dado** un asset existente,
   **Cuando** envío DELETE /products/{sku}/assets/{id} con permiso `products:delete`,
   **Entonces** el sistema elimina el registro permanentemente (hard-delete)
   y devuelve HTTP 204.

5. **Dado** un asset inexistente o que no pertenece al SKU,
   **Cuando** envío PATCH /primary, /archive, /restore, o DELETE,
   **Entonces** el sistema devuelve HTTP 404.

---

### Historia de usuario 3 — Links polimórficos de assets a owners (Priority: P3)

El equipo técnico vincula un mismo asset a múltiples entidades del catálogo
(producto, variante, serie, familia, recambio) asignando un rol semántico.
Esto permite reutilizar fichas PDF o imágenes de explosión entre modelos
de la misma serie.

**Por qué esta prioridad**: Evita duplicar archivos en Storage cuando el mismo PDF
técnico aplica a múltiples SKUs de una serie.

**Prueba independiente**: Verificable con POST /asset-links + GET /{owner_type}/{owner_id}/asset-links + DELETE /asset-links/{id}.

**Escenarios de aceptación**:

1. **Dado** un asset existente con `asset_id=<uuid>`,
   **Cuando** envío POST /api/v1/asset-links con
   `{ asset_id, owner_type:"product", owner_id:"MT-V-038", role:"ficha_pdf" }`,
   **Entonces** el sistema crea el link con HTTP 201.

2. **Dado** que el mismo link ya existe,
   **Cuando** envío POST /api/v1/asset-links de nuevo,
   **Entonces** el sistema devuelve HTTP 409 con código `asset_link_conflict`.

3. **Dado** un producto `MT-V-038` con links registrados,
   **Cuando** envío GET /api/v1/product/MT-V-038/asset-links,
   **Entonces** el sistema devuelve la lista de links ordenados por `role, order_index, created_at`.

4. **Dado** un link existente,
   **Cuando** envío DELETE /api/v1/asset-links/{link_id},
   **Entonces** el sistema lo elimina y devuelve HTTP 204.

---

### Casos límite

- ¿Qué ocurre al solicitar upload-url con MIME incompatible con el kind? → HTTP 422
  (validado en Pydantic schema `ProductAssetUploadRequest`).
- ¿Qué ocurre si `bytes_size` excede el límite del kind? → HTTP 422 desde el servicio.
- ¿Qué ocurre al confirmar un upload para un SKU inexistente? → HTTP 404.
- ¿Qué ocurre si el cliente Supabase no está configurado? → Degradado graceful;
  devuelve URL fake determinista en test/local; no rompe el contrato del API.
- ¿Qué ocurre al archivar un asset ya archivado? → Idempotente (sin error).
- ¿Qué ocurre al intentar DELETE de un asset vinculado via asset_links
  (FK RESTRICT)? → Error de integridad referencial (no manejado explícitamente
  como error de dominio — brecha BRECHA-AST-03).
- ¿Qué ocurre al intentar acceder sin autenticación? → HTTP 401/403.

---

## Requisitos *(obligatorio)*

### Requisitos funcionales

#### Área 1 — Listado y consulta de assets

- **FR-AST-001**: El sistema DEBE devolver la lista de assets vinculados a un SKU
  (`GET /products/{sku}/assets`) filtrable por `kind` e `include_archived`. Por defecto
  excluye los archivados. El resultado se ordena por `kind`, `position`, `created_at`.
  *Origen: as-built; código `products.py:1163-1184`; `asset_service.py:111-125`.*

- **FR-AST-002**: El endpoint de listado DEBE devolver HTTP 404 si el SKU no existe
  (verificado contra el producto antes de consultar assets).
  *Origen: as-built; código `products.py:1177-1180`.*

- **FR-AST-003**: El listado de assets DEBE devolver para cada asset el conjunto de URLs
  computadas (`urls`) que incluye: `original`, `thumb_160`, `thumb_400`, `thumb_800`,
  `thumb_1600`, `avif_400`, `avif_800`, `blurhash`, calculadas a partir de `variants`
  JSONB + `bucket` + `storage_path`.
  *Origen: as-built; código `assets.py:140-169` (`compute_asset_urls`);
  `assets.py:344-352` (`_compute_urls` validator de `ProductAssetResponse`).*

#### Área 2 — Flujo de upload en tres pasos

- **FR-AST-004**: El sistema DEBE ofrecer un endpoint para solicitar una URL firmada
  de Supabase Storage (`POST /products/{sku}/assets/upload-url`) que acepta `kind`,
  `filename`, `mime_type`, opcionalmente `locale`, `alt_text`, `position`.
  Requiere permiso `products:write`.
  *Origen: as-built; código `products.py:1187-1212`.*

- **FR-AST-005**: El endpoint `POST /assets/upload-url` DEBE validar que el `mime_type`
  sea compatible con el `kind` solicitado (reglas en `_MIME_RULES`), devolviendo
  HTTP 422 si no es compatible.
  *Origen: as-built; código `assets.py:54-71`; `asset_service.py:159-164`.*

- **FR-AST-006**: El endpoint `POST /assets/upload-url` DEBE devolver:
  `{ storage_path, upload_url, token, method, headers, expires_in, bucket, kind }`.
  En entornos sin Supabase configurado, degradar gracefully con URL fake.
  *Origen: as-built; código `asset_service.py:143-226`.*

- **FR-AST-007**: El path canónico en Supabase Storage DEBE seguir la convención
  `products/{sku}/{folder}/{uuid}_{filename}`, donde `folder` depende del `kind`
  (photos → `photos`, PDFs → `docs`, planos → `drawings`, links → `links`).
  *Origen: as-built; código `asset_service.py:59-83`.*

- **FR-AST-008**: El sistema DEBE ofrecer un endpoint de confirmación de upload
  (`POST /products/{sku}/assets/{asset_id}/confirm`) que crea la fila `ProductAsset`
  en la base de datos con los metadatos provistos (storage_path, kind, mime_type,
  bytes_size, width, height, alt_text, locale, caption, is_primary, position).
  Devuelve HTTP 201 + `ProductAssetResponse`.
  *Origen: as-built; código `products.py:1215-1282`.*

- **FR-AST-009**: Tras confirmar un upload de kind `photo`, `banner` o `mirror_url`,
  el sistema DEBE encolar la tarea Celery `generate_thumbnails` de forma no-bloqueante
  (cualquier fallo en el encolado se silencia; no rompe la respuesta).
  *Origen: as-built; código `products.py:1258-1265`.*

#### Área 3 — Designación de imagen primaria

- **FR-AST-010**: El sistema DEBE permitir marcar un asset como primario dentro de su
  (sku, kind) (`PATCH /products/{sku}/assets/{asset_id}/primary`). La operación es
  exclusiva: todos los demás assets del mismo (sku, kind) pasan a `is_primary=false`
  en el mismo UPDATE.
  Requiere permiso `products:write`.
  *Origen: as-built; código `products.py:1285-1302`; `asset_service.py:294-318`.*

- **FR-AST-011**: Solo puede existir un asset con `is_primary=true` por (sku, kind)
  en un momento dado.
  *Origen: as-built; código `asset_service.py:303-318` (`_set_primary_exclusive`).*

#### Área 4 — Archivado y restauración

- **FR-AST-012**: El sistema DEBE ofrecer un endpoint de archivado suave
  (`PATCH /products/{sku}/assets/{asset_id}/archive`) que cambia `status='archived'`
  y registra `archived_at` y `archived_by` (id del actor autenticado).
  Requiere permiso `products:write`.
  *Origen: as-built; código `products.py:1305-1322`; `asset_service.py:321-330`.*

- **FR-AST-013**: El sistema DEBE ofrecer un endpoint de restauración de assets
  archivados (`PATCH /products/{sku}/assets/{asset_id}/restore`) que cambia
  `status='active'` y limpia `archived_at` y `archived_by`.
  Requiere permiso `products:write`.
  *Origen: as-built; código `products.py:1325-1342`; `asset_service.py:333-342`.*

#### Área 5 — Eliminación permanente

- **FR-AST-014**: El sistema DEBE ofrecer un endpoint de hard-delete de assets
  (`DELETE /products/{sku}/assets/{asset_id}`) que elimina la fila de `product_assets`
  permanentemente. Requiere permiso `products:delete`.
  *Origen: as-built; código `products.py:1345-1364`; `asset_service.py:345-350`.*

#### Área 6 — Endpoints deprecados (compatibilidad hacia atrás)

- **FR-AST-015**: El sistema MANTIENE los endpoints deprecados `/{sku}/images`,
  `/{sku}/images/upload-url`, `/{sku}/images/confirm`, `/{sku}/images/{id}/set-primary`,
  `/{sku}/images/{id}` (DELETE) como proxies a los nuevos endpoints de assets,
  con header `Deprecation: true` y `Link: <successor>; rel="successor-version"`.
  *Origen: as-built; código `products.py:1022-1159`.*

#### Área 7 — Links polimórficos (asset_links)

- **FR-AST-016**: El sistema DEBE permitir crear un link polimórfico entre un asset
  y cualquier entidad owner del catálogo (`POST /api/v1/asset-links`) con campos
  `asset_id`, `owner_type`, `owner_id`, `role`, `order_index`.
  Requiere permiso `products:write`.
  *Origen: as-built; código `asset_links.py:68-90`.*

- **FR-AST-017**: El sistema DEBE listar los assets vinculados a un owner
  (`GET /api/v1/{owner_type}/{owner_id}/asset-links`) ordenados por
  `role`, `order_index`, `created_at`. Requiere permiso `products:read`.
  *Origen: as-built; código `asset_links.py:49-62`; `asset_link_service.py:78-88`.*

- **FR-AST-018**: El sistema DEBE eliminar un link polimórfico específico
  (`DELETE /api/v1/asset-links/{link_id}`) devolviendo HTTP 204.
  Requiere permiso `products:write`.
  *Origen: as-built; código `asset_links.py:96-111`; `asset_link_service.py:104-113`.*

- **FR-AST-019**: El sistema DEBE rechazar con HTTP 409 (`asset_link_conflict`) si
  se intenta crear un link duplicado (misma tupla asset_id + owner_type + owner_id + role).
  *Origen: as-built; código `asset_link_service.py:51-63`.*

#### Área 8 — Mirror de URLs externas

- **FR-AST-020**: El sistema DEBE soportar el registro de assets mirroreados desde
  URLs externas via `AssetService.mirror_external()`. La operación crea la fila
  `ProductAsset` con `status='pending_upload'` y encola la descarga + re-upload
  al worker Celery (solo registra el path determinista; no descarga en el request).
  *Origen: as-built; código `asset_service.py:354-387`.*

#### Área 9 — Deduplicación de assets por hash

- **FR-AST-021**: El sistema DEBE soportar deduplicación de assets por SHA-256
  via `AssetLinkService.find_or_create_asset_by_hash()`. Si ya existe un asset
  con el mismo `hash_sha256`, devuelve el existente sin crear duplicado.
  *Origen: as-built; código `asset_link_service.py:116-160`.*

---

### Requisitos no funcionales

- **NFR-AST-001**: Todos los endpoints de assets DEBEN requerir autenticación.
  Lectura requiere `products:read`; escritura/archivado/restauración requieren
  `products:write`; eliminación permanente requiere `products:delete`.
  *Origen: CLAUDE.md; código `products.py:1032,1051,1121,1146,1173,1195,1226,1294,1314,1334,1356`.*

- **NFR-AST-002**: Los errores de dominio en endpoints de asset (404 asset no encontrado,
  422 validación) DEBEN devolver RFC 7807 `ProblemDetails` con campos
  `type`, `title`, `status`, `detail`, `instance`, `code`.
  *Origen: CLAUDE.md; código `products.py:147-157` (helper `_problem`).*

- **NFR-AST-003**: El bucket de Supabase Storage utilizado para assets de producto
  DEBE ser `product-images`. No está permitido usar otro bucket.
  *Origen: CLAUDE.md; código `asset_service.py:105`.*

- **NFR-AST-004**: Los endpoints de listado de assets NO DEBEN producir queries N+1
  por asset para construir las URLs. Las URLs se calculan en memoria a partir de
  los campos JSONB `variants` + `bucket` + `storage_path` ya cargados con el registro.
  *Origen: CLAUDE.md directriz 1; código `assets.py:140-169`.*

- **NFR-AST-005**: El filename para uploads DEBE ser sanitizado para rechazar
  separadores de ruta (`/`, `\`, `..`) y caracteres fuera del patrón
  `^[A-Za-z0-9._\-]{1,256}$`.
  *Origen: as-built; código `assets.py:201-208` (`_validate_filename`);
  `asset_service.py:73-76` (`_safe_filename`).*

- **NFR-AST-006**: La generación de la URL firmada de Supabase Storage DEBE degradar
  gracefully en entornos sin credenciales Supabase (placeholder o missing): devuelve
  un payload fake determinista sin levantar excepción.
  *Origen: as-built; código `asset_service.py:180-211`.*

---

### Reglas de negocio

- **BR-AST-001**: El campo `is_primary` tiene semántica exclusiva por (sku, kind):
  solo un asset puede ser primario por tipo de asset por producto. Al marcar uno
  como primario, el servicio desmarca automáticamente los demás.
  *Origen: as-built; código `asset_service.py:303-318`.*

- **BR-AST-002**: Los assets de kind `photo`, `banner` o `mirror_url` disparan
  automáticamente la tarea de generación de miniaturas Celery al confirmar el upload.
  Otros kinds (PDFs, planos, videos) no generan miniaturas.
  *Origen: as-built; código `products.py:1258-1265`.*

- **BR-AST-003**: El tamaño máximo de archivo para imágenes (`photo`, `banner`,
  `mirror_url`) es 10 MB. Para PDFs (`datasheet_pdf`, `certificate_pdf`) es 50 MB.
  Para planos (`exploded_3d`, `section_drawing`, `dimension_drawing`) es 30 MB.
  Kinds de URL (`video_link`, `external_url`) no tienen binario (0 MB).
  *Origen: as-built; código `assets.py:73-84` (`_MAX_BYTES_RULES`).*

- **BR-AST-004**: El `storage_path` en `product_assets` es único junto con `bucket`
  (índice único `uq_assets_bucket_path`). Impide registrar dos assets con el mismo
  path en el mismo bucket.
  *Origen: as-built; código `product.py:614` (`uq_assets_bucket_path`).*

- **BR-AST-005**: Los assets marcados como `status='archived'` se excluyen del
  listado por defecto (`GET /assets`). Solo se incluyen si se pasa
  `include_archived=true` explícitamente.
  *Origen: as-built; código `asset_service.py:119-121`.*

- **BR-AST-006**: La tabla `asset_links` utiliza FK con `ON DELETE RESTRICT` desde
  `asset_links.asset_id` → `product_assets.id`. Intentar hacer hard-delete de un
  asset referenciado por links activos falla a nivel de base de datos.
  *Origen: as-built; código `asset_links.py:62-64`.*

- **BR-AST-007**: Los links polimórficos soportan 5 tipos de owner:
  `product`, `variant`, `series`, `family`, `spare_part`, y 12 roles semánticos.
  *Origen: as-built; código `asset_links.py:37-52`.*

---

### Entidades clave

- **ProductAsset**: Entidad de asset multimedia. PK = `id` (UUID).
  Campos clave: `sku` (FK a products), `kind`, `bucket`, `storage_path`,
  `original_url`, `is_primary`, `position`, `alt_text`, `locale`, `caption`,
  `width`, `height`, `bytes_size`, `mime_type`, `hash_sha256`, `variants` (JSONB),
  `asset_meta` (JSONB, columna DB `metadata`), `revision`, `supersedes_id`,
  `status`, `archived_at`, `archived_by`, `created_at`, `created_by`.

- **AssetLink**: Link polimórfico asset ↔ owner. PK = `id` (UUID).
  Campos: `asset_id`, `owner_type`, `owner_id`, `role`, `order_index`, `created_at`.

- **ProductAssetResponse**: Schema de respuesta. Incluye campo computado `urls`
  con las URLs CDN para variantes de miniatura.

---

## Criterios de éxito *(obligatorio)*

- **SC-AST-001**: El flujo completo upload-url → upload → confirm funciona para
  todos los 10 kinds sin errores para usuarios con `products:write`.

- **SC-AST-002**: Al marcar un asset como primario, el sistema garantiza que solo
  ese asset queda con `is_primary=true` para ese (sku, kind).

- **SC-AST-003**: Los assets archivados no aparecen en listados sin
  `include_archived=true`.

- **SC-AST-004**: La generación de miniaturas se encola de forma no-bloqueante:
  un fallo en Celery no rompe la respuesta HTTP 201.

- **SC-AST-005**: Sin autenticación válida, todos los endpoints devuelven 401/403.

- **SC-AST-006**: Los links polimórficos previenen duplicados y devuelven 409 limpio.

---

## Supuestos

- El sistema está desplegado sobre FastAPI + Supabase Storage + SQLAlchemy 2.0 async.
- El bucket `product-images` existe y está configurado en el entorno de producción.
- El worker Celery de miniaturas (`generate_thumbnails`) está operativo;
  si no, el sistema degrada silenciosamente (sin error al cliente).
- Los endpoints deprecados `/{sku}/images/*` se mantienen indefinidamente
  hasta que todos los clientes migren a `/{sku}/assets/*`.
- No existe actualmente un endpoint PATCH genérico para actualizar metadatos de un
  asset (alt_text, caption, locale, position) — esto es una brecha documentada.
