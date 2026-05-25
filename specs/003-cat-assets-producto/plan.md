# Plan as-built (retrospectivo): Assets/Imágenes de producto (CAT — sub-recurso)

**Branch**: `003-cat-assets-producto` | **Fecha**: 2026-05-25 | **Spec**: [spec.md](./spec.md)

> **PLAN AS-BUILT / RETROSPECTIVO** — Este plan NO diseña implementación nueva.
> Documenta la arquitectura EXISTENTE del sub-recurso assets para soporte de la
> verificación F1. Stack, módulos y decisiones ya están fijados. No ejecutar
> `/speckit-tasks` ni `/speckit-implement`.

---

## Resumen

El sub-recurso Assets de producto gestiona todos los archivos multimedia vinculados
a fichas de producto en el PIM: imágenes (`photo`, `banner`), documentación técnica
(PDFs, planos), videos y URLs externas. El almacenamiento binario usa Supabase Storage
(bucket `product-images`); los metadatos se persisten en la tabla `product_assets` vía
SQLAlchemy async. Un segundo sistema polimórfico (`asset_links`) permite vincular el
mismo asset a múltiples entidades del catálogo.

---

## Contexto técnico

**Lenguaje/Versión**: Python 3.11

**Dependencias primarias**: FastAPI + SQLAlchemy 2.0 async + Pydantic V2 + supabase-py

**Almacenamiento binario**: Supabase Storage — bucket `product-images` (obligatorio)

**ORM/DB**: PostgreSQL, tabla `product_assets` y `asset_links` (Alembic `public.*`)

**Worker async**: Celery + Redis — tarea `generate_thumbnails` para kinds de imagen

**Testing**: pytest — cobertura unitaria de endpoints (14 tests) y servicio

**Plataforma destino**: Linux / AWS EC2 + Docker Compose

---

## Módulos / Archivos principales

| Archivo | Rol |
|---------|-----|
| `app/api/routes/products.py` (líneas 1022-1365) | Endpoints de assets: listado, upload-url, confirm, primary, archive, restore, delete; endpoints deprecados /images |
| `app/api/routes/asset_links.py` | Sub-router polimórfico: list, create, delete asset links |
| `app/services/assets/asset_service.py` | Lógica de negocio de assets: generate_signed_upload_url, confirm_upload, set_primary, archive, restore, delete_hard, mirror_external, update_variants |
| `app/services/assets/asset_link_service.py` | Lógica de asset_links: create_link, list_links_for_owner, delete_link, find_or_create_asset_by_hash |
| `app/services/products/image_service.py` | Servicio legacy (Sprint 1) — solo para endpoints deprecados /images; sustituido por AssetService |
| `app/db/models/product.py` (líneas 526-623) | Modelo ORM `ProductAsset` con 10 kinds, 5 status, unicidad bucket+path, índices |
| `app/db/models/asset_links.py` | Modelo ORM `AssetLink` con 5 owner_types, 12 roles, FK RESTRICT |
| `app/schemas/assets.py` | Schemas Pydantic: `ProductAssetUploadRequest`, `ProductAssetConfirmRequest`, `ProductAssetPatch`, `ProductAssetResponse`, `AssetKind`, `AssetStatus`, helpers MIME/size |
| `app/schemas/asset_links.py` | Schemas Pydantic: `AssetLinkCreate`, `AssetLinkResponse`, enums owner_type y role |
| `tests/unit/api/test_products_assets_api.py` | 14 tests unitarios de endpoints de asset (mock) |
| `tests/unit/services/assets/test_asset_service.py` | Tests unitarios del AssetService |
| `tests/unit/services/assets/test_asset_link_service.py` | Tests unitarios del AssetLinkService |
| `tests/unit/schemas/test_assets.py` | Tests unitarios de schemas de assets |
| `tests/unit/schemas/test_asset_links.py` | Tests unitarios de schemas de asset_links |

---

## Decisiones arquitectónicas observadas

### 1. Flujo de upload en tres pasos (signed URL pattern)

El sistema implementa el patrón estándar de Supabase Storage para upload directo
desde el frontend:

```
Frontend → POST /upload-url   → { storage_path, upload_url, token }
Frontend → PUT upload_url     → (archivo a Supabase Storage, directo)
Frontend → POST /confirm      → ProductAsset row creada en DB
```

Este diseño evita que el backend actúe como proxy de archivos binarios, reduciendo
el consumo de memoria del servidor y la latencia percibida.

### 2. Tabla unificada `product_assets` (Wave 1)

La tabla original `product_images` fue renombrada a `product_assets` en la migración
030 para soportar los 10 kinds de asset más allá de fotos. `ProductImage` se mantiene
como alias deprecado (`ProductImage = ProductAsset`). La relación `Product.images`
filtra solo kind='photo' para compatibilidad hacia atrás.

### 3. Designación de primario via UPDATE exclusivo

`_set_primary_exclusive` emite dos UPDATE en la misma transacción:
1. Desmarca todos los assets del (sku, kind) → `is_primary=False`.
2. Marca el asset objetivo → `is_primary=True`.

Esto garantiza la invariante sin cursores ni loops Python (1 round-trip por UPDATE).

### 4. Cálculo de URLs en memoria (sin queries adicionales)

`ProductAssetResponse` usa un `@model_validator(mode="after")` que llama a
`compute_asset_urls()` para construir el campo `urls` a partir de `variants` JSONB,
`bucket` y `storage_path` ya presentes en el row. No hay queries adicionales por asset.

### 5. Links polimórficos sin FK a owners

`asset_links.owner_type` + `owner_id` son polimórficos (TEXT, sin FK real).
La integridad referencial hacia el owner se hace en capa de servicio manualmente.
El `asset_id` sí tiene FK real con `ON DELETE RESTRICT` hacia `product_assets`.

### 6. Degradado graceful de Supabase Storage

`AssetService.generate_signed_upload_url()` detecta si `SUPABASE_URL` o
`SUPABASE_SERVICE_ROLE_KEY` son placeholders y devuelve un payload fake determinista
en lugar de fallar. Esto permite el flujo de desarrollo local sin credenciales reales.

### 7. Deduplicación por SHA-256

`AssetLinkService.find_or_create_asset_by_hash()` permite dedup binario: si ya existe
un `ProductAsset` con el mismo `hash_sha256`, lo reutiliza en lugar de crear un
duplicado. La columna `hash_sha256` tiene índice (`idx_product_assets_hash`).

---

## Constitution Check

| Artículo | Estado | Notas |
|----------|--------|-------|
| Art. 1 — Stack obligatorio (FastAPI + Supabase Storage + SQLAlchemy) | ✅ Alineado | supabase-py solo para Storage API; ORM para metadatos |
| Art. 2 — Migraciones Alembic para public.* | ✅ Alineado | `product_assets`, `asset_links` vía Alembic |
| Art. 3 — Sin N+1 en backend | ✅ Alineado | URLs calculadas en memoria; listado de assets es 1 query |
| Art. 4 — Rendimiento frontend | N/A | Esta spec cubre solo el backend API |
| Art. 5 — LLM/Anthropic | N/A | No hay llamadas LLM en este sub-recurso |
| Art. 6 — Esquema de IDs | ✅ Aplicado | FR-AST-NNN, NFR-AST-NNN, BR-AST-NNN |
| Art. 7 — Definición de Listo | ✅ Aplicado | Spec sin `[NEEDS CLARIFICATION]`; brechas documentadas |

### Brechas de Constitución

- **Art. 3 (parcial)**: El endpoint `set_primary_asset` no verifica que el SKU exista
  antes de llamar al servicio — confía en que `AssetNotFoundError` cubra el caso.
  La validación de existencia del producto es implícita via FK, no explícita.

- **NFR-AST-002 (parcial)**: Los errores 422 de validación de asset (`AssetValidationError`)
  se lanzan como `HTTPException(status_code=422, detail=str(exc))` — el campo `detail`
  es un string plano, no un `ProblemDetails` RFC 7807 completo con `type`, `instance`,
  `code`. Los errores 404 sí usan el helper `_problem` RFC 7807.

- **asset_links — RFC 7807 incompleto**: `_raise_domain` en `asset_links.py` lanza
  `HTTPException` con `detail` como dict básico `{type, title, detail}` sin `instance`
  ni `code` completo. Ver BRECHA-AST-04.
