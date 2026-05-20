# Track D — Seguridad
**Fecha:** 2026-05-20
**Alcance:** Módulo de productos — backend (`products.py`, `products_display.py`, `ficha_enrich.py`, `asset_links.py`, `attributes.py`, `translations_workflow.py`) + frontend (middleware, API client, upload components).

---

## D1 — Autenticación en endpoints de productos

Todos los archivos de rutas analizados usan `require_permissions(...)` de `app/api/deps.py`, que internamente llama a `get_current_user` (verifica Bearer JWT HS256/JWKS contra Supabase, valida `exp`+`sub`, carga `public.users`).

### products.py (58 endpoints)

| Endpoint | Dependency de auth | Veredicto |
|----------|-------------------|-----------|
| GET /specs/schema | `require_permissions("products:read")` | OK |
| GET /export | `require_permissions("products:read")` | OK |
| GET / (list) | `require_permissions("products:read")` | OK |
| GET /search | `require_permissions("products:read")` | OK |
| GET /facets | `require_permissions("products:read")` | OK |
| POST / (create) | `require_permissions("products:write")` | OK |
| GET /{sku} | `require_permissions("products:read")` | OK |
| GET /{sku}/certificates | `require_permissions("products:read")` | OK |
| GET /{sku}/flow-data | `require_permissions("products:read")` | OK |
| PATCH /{sku} | `require_permissions("products:write")` | OK |
| PUT /{sku} | `require_permissions("products:write")` | OK |
| PATCH /{sku}/data-quality | `require_permissions("products:write")` | OK |
| POST /classify | `require_permissions("products:write")` | OK |
| DELETE /{sku} | `require_permissions("products:delete")` | OK |
| GET /{sku}/translations | `require_permissions("products:read")` | OK |
| PUT /{sku}/translations/{lang} | `require_permissions("products:write")` | OK |
| PATCH /{sku}/translations/{lang} | `require_permissions("products:write")` | OK |
| POST /{sku}/translations/{lang}/approve | `require_permissions("products:write")` | OK |
| GET /{sku}/images | `require_permissions("products:read")` | OK |
| POST /{sku}/images/upload-url (deprecated) | `require_permissions("products:write")` | OK |
| POST /{sku}/images/confirm | `require_permissions("products:write")` | OK |
| POST /{sku}/images/{image_id}/set-primary | `require_permissions("products:write")` | OK |
| DELETE /{sku}/images/{image_id} | `require_permissions("products:delete")` | OK |
| GET /{sku}/assets | `require_permissions("products:read")` | OK |
| POST /{sku}/assets/upload-url | `require_permissions("products:write")` | OK |
| POST /{sku}/assets/{asset_id}/confirm | `require_permissions("products:write")` | OK |
| PATCH /{sku}/assets/{asset_id}/primary | `require_permissions("products:write")` | OK |
| PATCH /{sku}/assets/{asset_id}/archive | `require_permissions("products:write")` | OK |
| PATCH /{sku}/assets/{asset_id}/restore | `require_permissions("products:write")` | OK |
| DELETE /{sku}/assets/{asset_id} | `require_permissions("products:delete")` | OK |
| GET /{sku}/compatibility | `require_permissions("products:read")` | OK |
| GET /{sku}/compatibility/inverse | `require_permissions("products:read")` | OK |
| POST /{sku}/compatibility | `require_permissions("products:write")` | OK |
| DELETE /{sku}/compatibility/{…}/{kind} | `require_permissions("products:write")` | OK |
| PUT /{sku}/compatibility | `require_permissions("products:write")` | OK |
| GET /{sku}/materials | `require_permissions("products:read")` | OK |
| POST /{sku}/materials | `require_permissions("products:write")` | OK |
| DELETE /{sku}/materials/{…}/{position} | `require_permissions("products:write")` | OK |
| PUT /{sku}/materials | `require_permissions("products:write")` | OK |
| GET /{sku}/connections | `require_permissions("products:read")` | OK |
| POST /{sku}/connections | `require_permissions("products:write")` | OK |
| DELETE /{sku}/connections/{position} | `require_permissions("products:write")` | OK |
| PUT /{sku}/connections | `require_permissions("products:write")` | OK |
| GET /{sku}/resolved | `require_permissions("products:read")` | OK |
| POST /{sku}/parent | `require_permissions("products:write")` | OK |
| GET /{sku}/tech-tables | `require_permissions("products:read")` | OK |
| PUT /{sku}/tech-tables/{kind} | `require_permissions("products:write")` | OK |
| DELETE /{sku}/tech-tables/{kind} | `require_permissions("products:write")` | OK |
| GET /{sku}/releases | `require_permissions("products:read")` | OK |
| POST /{sku}/releases | `require_permissions("products:write")` | OK |
| PATCH /{sku}/releases/{market_code} | `require_permissions("products:write")` | OK |
| POST /{sku}/releases/{market_code}/activate | `require_permissions("products:write")` | OK |
| POST /{sku}/releases/{market_code}/deactivate | `require_permissions("products:write")` | OK |
| GET /{sku}/uom-conversions | `require_permissions("products:read")` | OK |
| POST /{sku}/uom-conversions | `require_permissions("products:write")` | OK |
| DELETE /{sku}/uom-conversions/{from}/{to} | `require_permissions("products:write")` | OK |
| GET /{sku}/bore-dimensions | `require_permissions("products:read")` | OK |
| GET /{sku}/datasheets | `require_permissions("products:read")` | OK |

### products_display.py (3 endpoints)

| Endpoint | Dependency de auth | Veredicto |
|----------|-------------------|-----------|
| GET /{sku}/effective-display | `require_permissions("products:read")` | OK |
| PUT /{sku}/display-pair | `require_permissions("products:write")` | OK |
| DELETE /{sku}/display-pair | `require_permissions("products:write")` | OK |

### ficha_enrich.py (4 endpoints)

| Endpoint | Dependency de auth | Veredicto |
|----------|-------------------|-----------|
| POST /products/{sku}/ficha-enrich/preview | `require_permissions("products:write")` | OK |
| POST /products/{sku}/ficha-enrich/apply | `require_permissions("products:write")` | OK |
| POST /ficha-enrich/series/preview | `require_permissions("products:write")` | OK |
| POST /ficha-enrich/series/apply | `require_permissions("products:write")` | OK |

### asset_links.py (3 endpoints)

| Endpoint | Dependency de auth | Veredicto |
|----------|-------------------|-----------|
| GET /{owner_type}/{owner_id}/asset-links | `require_permissions("products:read")` | OK |
| POST /asset-links | `require_permissions("products:write")` | OK |
| DELETE /asset-links/{link_id} | `require_permissions("products:write")` | OK |

### attributes.py (14 endpoints)

| Endpoint | Dependency de auth | Veredicto |
|----------|-------------------|-----------|
| GET /attributes | `require_permissions("products:read")` | OK |
| GET /attributes/{id}/options | `require_permissions("products:read")` | OK |
| GET /families/{id}/attributes | `require_permissions("products:read")` | OK |
| POST /attributes | `require_permissions("admin:vocabularies")` | OK |
| PATCH /attributes/{id} | `require_permissions("admin:vocabularies")` | OK |
| DELETE /attributes/{id} | `require_permissions("admin:vocabularies")` | OK |
| POST /attributes/{id}/options | `require_permissions("admin:vocabularies")` | OK |
| PATCH /attributes/{id}/options/{opt} | `require_permissions("admin:vocabularies")` | OK |
| DELETE /attributes/{id}/options/{opt} | `require_permissions("admin:vocabularies")` | OK |
| POST /families/{id}/attributes/{attr} | `require_permissions("admin:vocabularies")` | OK |
| DELETE /families/{id}/attributes/{attr} | `require_permissions("admin:vocabularies")` | OK |
| GET /{sku}/attributes | `require_permissions("products:read")` | OK |
| PUT /{sku}/attributes/{code} | `require_permissions("products:write")` | OK |
| DELETE /{sku}/attributes/{code} | `require_permissions("products:write")` | OK |

### translations_workflow.py (3 endpoints)

| Endpoint | Dependency de auth | Veredicto |
|----------|-------------------|-----------|
| POST /{sku}/translations/{lang}/request-review | `require_permissions("products:write")` | OK |
| POST /{sku}/translations/{lang}/reject | `require_permissions("products:write")` | OK |
| POST /{sku}/translations/mark-stale | `require_permissions("products:write")` | OK |

**Endpoints sin protección (en módulo de productos):** ninguno.

**Nota fuera de alcance:** Se detectaron rutas completamente sin auth en módulos adyacentes (`billing.py`, `finance.py`, `rule_engine.py`, `hitl_queue_price.py`, `channels.py`, `price_intelligence.py`). Estos representan hallazgos de alta prioridad para un audit más amplio.

---

## D2 — Autorización (RBAC)

### Cómo funciona el sistema de roles

- **`require_permissions("perm:code")`** — verifica permisos cargados desde `public.roles.permissions_snapshot` (JSONB). Los usuarios con `role.code == "admin"` tienen bypass automático (líneas 304-305 de `deps.py`).
- **`require_role("role_code")`** — compara `user.role.code` contra la lista permitida. **No tiene bypass de admin**: un `admin` que no tenga el código exacto en la lista falla igualmente. Esto es inconsistente con `require_permissions`.
- **`require_role_claim("role_code")`** — lee el claim JWT `app_metadata.role` sin tocar DB (fast-path). Útil pre-bootstrap pero no verifica permisos granulares.

### Hallazgos de autorización

1. **Granularidad de `products:write` es amplia (medio):** La misma permission `products:write` protege operaciones muy distintas en impacto: crear un producto, reemplazarlo completamente (`PUT /{sku}`), aprobar traducciones, archivar assets, activar/desactivar releases de mercado. No existe diferenciación granular por sub-operación. Un usuario con `products:write` puede activar releases de mercado igual que quien solo debería editar metadata.

2. **`POST /classify` encolado como `products:write` (bajo):** La tarea `classify_pim_batch` modifica todos los productos (hasta 10.000) de forma masiva. Requiere solo `products:write`, no un permiso específico de `admin:*`. Cualquier usuario con write puede lanzar este batch.

3. **`GET /export` retorna hasta 10.000 registros (bajo):** Accesible con `products:read`. No hay diferenciación de acceso al CSV bulk vs. la paginación normal.

4. **`require_role` no tiene admin bypass (bajo):** A diferencia de `require_permissions`, `require_role` no permite a usuarios `admin` pasar si su `role.code` no está exactamente en la lista. Puede causar bloqueos inesperados en producción.

5. **Sin RBAC en releases de precio (medio):** `GET /{sku}/releases` y `PATCH /{sku}/releases/{market_code}` exponen/permiten modificar `list_price` y `price_currency` con solo `products:read`/`products:write`. No existe un permiso específico `products:releases` o `pricing:write`.

---

## D3 — Inyección SQL

### En rutas de productos (products.py, products_display.py, ficha_enrich.py, asset_links.py, attributes.py, translations_workflow.py)

No se encontraron usos de SQL raw inseguro.

### En servicios de productos y repositorios

| Archivo | Línea aprox. | Código | Severidad |
|---------|-------------|--------|-----------|
| `app/repositories/unmatched_offers.py` | L281 | `text(f"scraped_at > NOW() - INTERVAL '{max_age_days} days'")` | Bajo |

**Análisis del hallazgo:** `max_age_days` es un parámetro `int` definido en la firma del método Python (`max_age_days: int = 7`). Un entero no puede contener SQL injection. Sin embargo, el uso de `text(f"...")` es un anti-patrón: si en el futuro el parámetro cambia a `str` o se recibe de input HTTP, se convierte en vulnerable. La forma segura sería `text("scraped_at > NOW() - INTERVAL :days").bindparams(days=f"{max_age_days} days")`.

**Severidad real actual:** Baja (el tipo `int` previene inyección). **Riesgo potencial:** Alto si el tipo cambia.

---

## D4 — Exposición de datos sensibles

### ProductResponse (response de listados y GET /{sku})

Accesible con `products:read`. Campos analizados:

- **`internal_id` (UUID):** Expuesto en la respuesta. Es el UUID interno de la fila en `public.products`. Su exposición permite correlacionar con otras tablas o usarlo en ataques de enumeración de recursos. No es un secreto crítico, pero exponer el UUID interno cuando `sku` ya es el identificador único es redundante. **Severidad: Baja.**
- **Sin `cost_price`, `purchase_price`, `margin`:** Los campos de costo no aparecen en `ProductResponse`. Correcto.
- **`specs` (JSONB):** Expuesto como `dict[str, Any]`. Dependiendo del contenido real del JSONB en producción, podría contener campos internos inesperados. Merecería revisión del contenido.

### ProductReleaseResponse (response de GET /{sku}/releases)

Accesible con `products:read`. Hereda de `ProductReleaseBase` que incluye:

- **`list_price` (Decimal):** Precio de lista del producto por mercado. Accesible a cualquier usuario con `products:read`. En una aplicación B2C pública esto sería aceptable, pero en un sistema PIM interno con usuarios de diferentes roles (comercial, gerente, ti), el precio de lista podría ser información confidencial de negociación. **Severidad: Media** (depende de política empresarial).
- **`price_currency`:** Asociado al precio, misma observación.
- **`tax_class`:** Información interna de configuración fiscal. Potencialmente sensible.

### ProductTranslationResponse

Expone `translated_by` y `reviewed_by` (UUIDs de usuarios internos). Menor preocupación, pero identifica qué usuarios realizaron qué acciones.

### Resumen D4

No hay exposición de costos de compra, márgenes o precios de proveedor en los endpoints de productos. El hallazgo principal es `list_price`/`price_currency` en releases accesibles a todos los usuarios con `products:read`.

---

## D5 — Seguridad de carga de archivos

### Imágenes (POST /{sku}/images/upload-url + confirm / POST /{sku}/assets/upload-url + confirm)

| Check | Estado | Detalle |
|-------|--------|---------|
| Tipo de archivo validado en backend | **SÍ** | `allowed_mimes_for_kind()` en `AssetService.generate_signed_upload_url()` — whitelist por kind (foto: jpeg/png/webp/avif; PDF: application/pdf; etc.) |
| Tipo de archivo validado en frontend | **SÍ** | `ALLOWED_MIME` array + `validateFile()` en `ImageUploader` antes del request al backend |
| Tamaño validado en backend | **PARCIAL** | Validado en `confirm_upload()` si se pasa `bytes_size`. El cliente lo informa — no hay verificación server-side del tamaño real del objeto en Supabase Storage |
| Tamaño validado en frontend | **SÍ** | `MAX_BYTES = 10 MB` verificado en `validateFile()` antes del upload |
| Path traversal en nombre de archivo | **PROTEGIDO** | `_safe_filename()` aplica regex `^[A-Za-z0-9._\-]{1,256}$` — rechaza `/`, `\`, `..` |
| Validación en schema Pydantic | **SÍ** | `ProductAssetUploadRequest._validate_filename()` rechaza separadores de ruta |
| Storage path controlado por usuario | **NO** | El path es `products/{sku}/{folder}/{uuid4().hex}_{filename}`. El `uuid4()` es generado server-side. El `sku` viene del path param validado (1-64 chars). El `folder` viene de un dict interno. No hay traversal posible |
| Validación de magic bytes (PDF) | **SÍ** | `ficha_enrich.py` L104: `if not pdf_bytes.lstrip().startswith(b"%PDF")` — rechaza archivos que no son PDF real |
| Nombre de archivo reflejado en respuesta | **SÍ** | `original_filename` derivado de `basename(asset.storage_path)`. Sin riesgo de XSS en API JSON |

**Hallazgo principal D5:** El tamaño del archivo se valida solo si el cliente envía `bytes_size` en el payload de confirm. Un cliente malicioso podría no enviar este campo (es `Optional` en `ProductAssetConfirmRequest`) y eludir el límite de tamaño en la DB row. El archivo ya subido a Supabase Storage no se valida por tamaño desde el backend. Depende de los límites configurados en Supabase Storage directamente.

---

## D6 — Seguridad frontend

### middleware.ts

- Usa `@supabase/ssr` con `createServerClient` en el edge.
- Llama a `supabase.auth.getUser()` (no `getSession()`) — canónico y más seguro (verifica JWT contra el servidor).
- Redirige a `/login?next=...` si no hay sesión. `next` se pasa como query param URL-encoded — sin riesgo de Open Redirect ya que es usado internamente.
- Rutas públicas declaradas explícitamente: `/login`, `/reset-password`, `/auth/callback`, `/auth/confirm`, `/api/health`.
- No hay `dangerouslySetInnerHTML`.

### lib/api/client.ts

- `apiClient` (openapi-fetch) no incluye el token automáticamente. **Hallazgo:** Para las llamadas tipadas via `apiClient`, NO se adjunta el Bearer token JWT. El cliente usa `openapi-fetch` con `baseUrl` pero sin interceptor de auth.
- `authedFetch` y `authedDownload` sí adjuntan token: leen el `access_token` de `supabase.auth.getSession()` y lo añaden como `Authorization: Bearer ...` header.
- **Riesgo:** Las llamadas realizadas via `apiClient` directamente (sin pasar por `authedFetch`) llegarían al backend sin autenticación → el backend retornaría 401. Esto no es un vulnerability si el backend siempre requiere auth, pero puede provocar errores silenciosos si algún endpoint fuera público.
- Los tokens no se almacenan en `localStorage` — Supabase SSR los gestiona en cookies httpOnly a través del middleware.

### lib/env.ts

- Solo expone variables `NEXT_PUBLIC_*` al cliente: `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`/`ANON_KEY`, `BACKEND_URL`, `SENTRY_DSN`, `DEFAULT_LOCALE`.
- La `anon_key` de Supabase (es pública por diseño) es la única "key" expuesta al cliente — correcto para Supabase.
- No hay acceso a variables privadas (`SUPABASE_SERVICE_ROLE_KEY`, `JWT_SECRET`, etc.) desde el frontend.

### imagenes/_client.tsx

- No hay `dangerouslySetInnerHTML`.
- No hay tokens ni secrets.
- Usa `RbacGuard` para mostrar/ocultar el uploader según permisos — esto es UI-only; el backend también lo valida.

### datasheets/_client.tsx

- No hay `dangerouslySetInnerHTML`.
- Renderiza `run.error` como texto plano (no como HTML) — seguro contra XSS.
- `datasheet.signed_url` se usa en `href` de `<a>` — riesgo teórico de javascript: URL si el signed_url fuera controlado por un atacante, pero viene del backend que construye URLs de Supabase Storage, por lo que es seguro en la práctica.

### Resumen D6

| Check | Estado |
|-------|--------|
| `dangerouslySetInnerHTML` | No encontrado |
| Secrets en código cliente | No encontrados |
| Tokens en `localStorage` | No (cookies httpOnly via Supabase SSR) |
| `apiClient` sin Bearer token | SÍ — puede causar 401s silenciosos |
| `authedFetch` con Bearer token | SÍ — correcto |
| XSS en render de datos | No encontrado |

---

## Hallazgos por severidad

### Crítico (CVSS 9-10)
Ninguno en el módulo de productos.

### Alto (CVSS 7-8.9)
- **H1 — Módulos fuera de scope sin auth:** `billing.py` (facturas, pagos), `finance.py` (P&L, balance sheet, aging), `rule_engine.py` (configuración de reglas de pricing), `hitl_queue_price.py` (cola de revisión de precios) tienen endpoints completamente sin protección de auth. Aunque fuera del módulo de productos, son parte de la misma aplicación y su explotación comprometería datos financieros críticos.

### Medio (CVSS 4-6.9)
- **M1 — `list_price` accesible a todos los `products:read` vía releases endpoint:** `GET /{sku}/releases` retorna `list_price`, `price_currency`, `tax_class` a cualquier usuario autenticado con `products:read`. Si el modelo de acceso requiere separar quién ve precios de lista, falta un permiso dedicado.
- **M2 — Granularidad insuficiente en `products:write`:** Un solo permiso cubre desde edición de metadata hasta activación de releases de mercado y batch classification de 10.000 productos. Recomendable separar en `products:releases`, `products:classify`, etc.
- **M3 — Validación de tamaño de archivo solo client-trust en confirm:** `bytes_size` es opcional en `ProductAssetConfirmRequest`. Un cliente puede no enviarlo y eludir el límite de la DB row. El archivo en Supabase Storage no se re-valida en tamaño desde el backend.
- **M4 — `apiClient` no adjunta Bearer token:** Las rutas que usen `apiClient` sin pasar por `authedFetch` no enviarán el JWT. Si un endpoint protegido se llama via `apiClient` directamente, fallará con 401. Genera superficie de error y confusión.

### Bajo (CVSS < 4)
- **B1 — `text(f"...")` con `int` en `unmatched_offers.py:281`:** Anti-patrón de SQL dinámico. Actualmente seguro (tipo `int`), pero debería reescribirse con `bindparams` para prevenir regresiones.
- **B2 — `internal_id` UUID expuesto en `ProductResponse`:** Innecesario cuando `sku` ya es el identificador público. Mínimo impacto de seguridad, pero reduce superficie de información.
- **B3 — `X-User-Id` aceptado en middleware desde cliente:** `RequestContextMiddleware` lee `X-User-Id` del request para logging. Solo se usa en structlog (`bind_contextvars`) — no se propaga al sistema de auth. Sin impacto real de seguridad, pero el middleware confía en un header que cualquier cliente puede falsificar para contaminar los logs.
- **B4 — `require_role` sin bypass admin:** Inconsistencia con `require_permissions`. Puede causar bloqueos inesperados para usuarios `admin` en endpoints que usen `require_role` en el futuro.
- **B5 — `stale-while-revalidate=30` en CacheControlMiddleware:** Las respuestas GET 200 pueden servirse stale hasta 90s (`max-age=60` + `stale-while-revalidate=30`). Correcto con `private` (no se cachea en proxies), pero si un token se revoca, la sesión del browser puede seguir viendo datos hasta 90s más.

---

## Top 3 críticos a resolver primero

1. **H1 — Añadir auth a `billing.py`, `finance.py`, `rule_engine.py`, `hitl_queue_price.py`:** Son rutas completamente abiertas que exponen datos financieros críticos (facturas, P&L, balance sheet, configuración de reglas de precios). Cualquier usuario sin autenticar puede acceder. Añadir `Depends(require_permissions("finance:read"))` / `Depends(require_permissions("admin:pricing"))` a todos los endpoints afectados.

2. **M1 — Añadir permiso `products:releases` para separar acceso a precios de lista:** `GET /{sku}/releases` expone `list_price` a todos los `products:read`. Crear permiso `products:releases:read` y reemplazar la dependency. El endpoint es el único lugar del módulo de productos que expone pricing data sin gating específico.

3. **M3 — Validar tamaño real de archivo en Supabase Storage al confirmar upload:** En `confirm_asset_upload`, llamar a la API de Supabase Storage para obtener los metadatos del objeto ya subido y verificar `bytes_size` server-side, independientemente de lo que el cliente reporte. Alternativamente, configurar límites de tamaño en las políticas de Supabase Storage (bucket `product-images`) como primera línea de defensa.
