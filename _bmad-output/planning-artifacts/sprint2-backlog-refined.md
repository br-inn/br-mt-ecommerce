---
title: "Sprint 2 Backlog Refinado — MT Middle East MDM + Pricing Fase 1a"
status: "draft"
version: "1.0"
created: "2026-05-07"
project_name: "mt-pricing-mdm-phase1"
sprint: "S2"
sprint_goal: "Cerrar el módulo PIM CRUD completo (edit + imágenes + filtros) y traer datos reales: importer PIM con preview/apply + suppliers/costs schemas listos para EP-1A-04."
related:
  - "epics-and-stories-mt-pricing-mdm-phase1.md"
  - "sprint1-backlog-refined.md"
  - "../implementation-artifacts/sprint1-execution-report.md"
  - "architecture-mt-pricing-mdm-phase1.md"
  - "prd-mt-pricing-mdm-phase1.md"
  - "ux-mockups-mt-pricing-mdm-phase1.md"
  - "risk-register-consolidado.md"
---

# Sprint 2 Backlog Refinado — MT Middle East MDM + Pricing Fase 1a

## 1. Sprint goal

> "Cerrar el módulo PIM CRUD completo (edit + imágenes + filtros) y traer datos reales: importer PIM con preview/apply + suppliers/costs schemas listos para EP-1A-04."

Demo objetivo (Friday-of-S2, 45 min):

1. Comercial real entra a `https://dev.mtme.example`, hace login.
2. Va a `/imports/new?type=pim` y sube `PIM completo.xlsx` (o `stock_dubai_v23` como fallback si Q-03 sigue bloqueado).
3. El sistema muestra preview: `5086 detectadas / N nuevas / M actualizables / 0 huérfanas` (counts reales del archivo).
4. Click "Apply", la barra avanza, toast `"Importación completada: N creados, M actualizados"`.
5. Va a `/products`, ve > 1 000 SKUs reales, filtra `family=gate_valve & q="MT-V-038"`, cambia el `dn` de un SKU vía PUT, audit registra el cambio.
6. Abre `/products/MT-V-038`, click tab Imágenes → arrastra una imagen (o pulsa "Probe + Mirror" sobre `image_url_pim`), espera ~3 s, ve thumbnail mirroreado en Supabase Storage con badge `mirrored`.
7. Va a `/suppliers` (nuevo), crea `MT Valves España (EUR)`. Audit registra.
8. Intenta `DELETE /products/MT-V-038` con curl → 405. Audit muestra el bloqueo.

Si los 8 puntos pasan en staging, S2 está done. Si Q-03 sigue bloqueado al día 5, sustituir paso 2 por importer fixture US-1A-06-06.

## 2. Capacidad asumida

| Concepto | Valor S1 | Valor S2 | Δ |
|----------|----------|----------|---|
| Devs FTE | 2-3 | 2-3 (idealmente +TI Integración FTE confirmado por Q-05) | = |
| Velocity asumida | 30-40 SP/sprint | 32-40 SP/sprint | leve subida (curva de aprendizaje S1 done, scaffolding ya pagado) |
| Sprint length | 2 semanas (10 días lab.) | 2 semanas (10 días lab.) | = |
| Reservas | 20 % buffer | 20 % buffer + 10 % refinement S3 (importer es nuevo) | -3 SP de capacity efectiva |
| Capacidad efectiva | ~28-32 SP | ~30-34 SP humano / 40 SP modo multi-agente | + |
| Carga heredada de S1 | 0 | 1-2 días de hardening (typecheck Wave 1/2 + `pnpm lint` migration; ver §10 reporte S1) | -2 SP |

> El reporte S1 absorbió **53 SP en una iteración multi-agente** (~25 min wall-clock), pero esa velocidad NO es replicable como base de planning humana. Mantenemos planning con **velocity humana 32-40 SP/sprint** y dejamos modo multi-agente como aceleración táctica si capacidad real cae por debajo del target.

> Si TI Integración entra en S2 como FTE dedicado (decisión Q-05), capacidad sube a 40 SP. Si entra como role-share o vendor part-time, capacidad baja a 26-30 SP — en ese caso aplicar §6 (stories candidatas a S3).

## 3. Stories incluidas

> Convención: `US-{epic}-{nn}` por consistencia con `epics-and-stories-mt-pricing-mdm-phase1.md` v1.1. Donde la historia ya existe en el doc fuente, se preserva el ID; donde se splittea/scopea para S2, se sufija `-S2`.

---

### US-1A-02-03 — Endpoint `PUT /products/{sku}` y `PATCH /products/{sku}/data-quality`

**Épica**: EP-1A-02 ([epics-and-stories-mt-pricing-mdm-phase1.md §EP-1A-02 línea 441](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** Comercial
**Quiero** editar specs técnicas y cambiar el flag `data_quality` de un SKU
**Para** mantener la ficha actualizada y gobernar publicabilidad.

#### Contexto
Sin esta story, `/products` queda read-only. Sprint 1 dejó `GET /products`, `GET /products/{sku}` y `POST /products`; aquí se cierra el CRUD. La PATCH separada para `data_quality` permite que un job futuro (S3) la dispare automáticamente sin reusar el PUT general (que requiere todos los campos). El PUT debe respetar `manual_locked_fields` (que el importer leerá en US-1A-06-01) — en S2 sólo definimos el campo, los locks operativos llegan en S3.

#### Criterios de aceptación (BDD)
- [ ] **Dado** un Comercial autenticado y un SKU `MT-V-038` existente con `dn=50` **Cuando** envío `PUT /api/v1/products/MT-V-038` con body completo (incluido `dn=65`) **Entonces** el sistema persiste, retorna 200 con la ficha actualizada y registra `audit_events(action='update', diff={"dn":[50,65]})`.
- [ ] **Dado** un payload sin `name_en` **Cuando** lo envío **Entonces** retorna 422 con `error.code = "BR_1A_02"`.
- [ ] **Dado** un PUT que cambia `sku` **Cuando** se envía **Entonces** retorna 422 (SKU es identificador inmutable, BR-1a-01).
- [ ] **Dado** un Comercial **Cuando** envía `PATCH /api/v1/products/MT-V-038/data-quality` con `{"data_quality":"blocked"}` **Entonces** retorna 200 y el flag se actualiza con audit.
- [ ] **Dado** un usuario sin auth **Cuando** llama PUT **Entonces** retorna 401.
- [ ] **Dado** un SKU inexistente **Cuando** envío PUT **Entonces** retorna 404 (no upsert).
- [ ] **Dado** un PUT con dos requests concurrentes (race) sobre la misma fila **Cuando** se ejecutan **Entonces** ambos persisten en serie (last-write-wins en S2; optimistic locking via `updated_at` queda para S3 si necesario).

#### Tareas técnicas (subtasks)
- [ ] Backend: `app/api/v1/products.py` añadir `put_product(sku, payload)` y `patch_product_data_quality(sku, payload)`.
- [ ] Backend: `app/services/product_service.py` añadir `update_product(sku, payload, actor)` con cálculo de diff vs estado actual y emit a audit.
- [ ] Backend: schema Pydantic `ProductUpdate` (todos los campos editables; `sku` excluido).
- [ ] Backend: schema Pydantic `ProductDataQualityPatch` con enum `data_quality_t`.
- [ ] Backend: helper `compute_diff(before: dict, after: dict) -> dict` reusable por audit (será reusado en US-1A-06-01 importer y en US-1A-04-04 costs editor).
- [ ] Tests: unit del service (diff vacío → no audit; diff con campos NOT NULL → audit). Integration (PUT happy path, 401/404/422, PATCH data_quality).
- [ ] Docs: `mt-api-contract-openapi.yaml` actualizar con los 2 endpoints.

#### Dependencias
- Bloqueada por: US-1A-02-01-S1, US-1A-02-02-S1, US-1A-07-01-S1 (audit trigger ya existe sobre `products`).
- Bloquea a: US-1A-02-04-S2 (UI Editar SKU consume PUT), US-1A-06-01 (importer reusa el service).

#### Mocks / Wireframes
- Referencia: `ux-mockups-mt-pricing-mdm-phase1.md` Pantalla 3 + Pantalla 4 (forms inline en Identidad / Imágenes).
- Datos test: 5 SKUs fixture cargados en S1; el smoke test edita uno.

#### Endpoints API afectados
- `PUT /api/v1/products/{sku}` (nuevo, arquitectura §11.1).
- `PATCH /api/v1/products/{sku}/data-quality` (nuevo).

#### Modelos afectados
- `Product` (sin cambios de schema; sólo writes nuevos).
- `AuditEvent` (ya existe; el trigger en `products` lo poblará automáticamente vía US-1A-07-01-S1).

#### Observability
- Métricas: `products.update.success/failure` count, `products.update.duration_p95`, `products.data_quality.transitions{from,to}`.
- Logs: `actor=user_id, action=update_product, sku=..., fields_changed=[...], request_id`.
- Error scenarios: violación constraint → 422 + Sentry breadcrumb. 5xx → Sentry crit.

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial (Pantalla 3 inline edit).
- [ ] API contract acordado y mergeado (PUT + PATCH).
- [ ] Modelo SQLAlchemy disponible (`Product` desde S1).
- [ ] Permisos RBAC definidos (`comercial+` write).
- [ ] Datos test disponibles.
- [ ] No tiene dependencias bloqueantes pendientes.
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan (unit + integration).
- [ ] Coverage ≥ 80 % en código nuevo del service.
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada (N/A — no nuevo schema).
- [ ] Deploy a staging exitoso.
- [ ] Smoke test en staging por dev distinto al autor (PUT + PATCH con httpie).
- [ ] Audit event verificado (diff JSON correcto en `audit_events`).
- [ ] Documentación actualizada (OpenAPI).
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.

#### Notas
Optimistic locking via `If-Match: <updated_at>` queda como mejora S3 si se observa contención real. En S2 last-write-wins es aceptable (1 Comercial activo).

#### SP
**3**

#### Sprint asignado
S2.

#### Owner técnico (placeholder)
TBD.

---

### US-1A-02-04-S2 — UI tabs Imágenes + Editar inline en tab Ficha técnica

**Épica**: EP-1A-02 (subset del US-1A-02-04 doc fuente, scoped a 2 tabs activos en S2; Costes/Precios/Traducciones/Auditoría llegan en S3)
**Como** Comercial
**Quiero** editar la ficha de un SKU (campos identidad) y gestionar imágenes desde la UI
**Para** mantener la ficha sin pasar por API directa.

#### Contexto
Cierra la mitad funcional de la "ficha de SKU" del PRD §12.2. En S1 las tabs Imágenes/Costes/Precios/Traducciones/Auditoría están disabled con tooltip "Próximamente S2". En S2 activamos sólo **Ficha técnica edit + Imágenes** (las demás necesitan suppliers + costs + currencies, que son work-in-progress en S2). Tab Auditoría queda en S3 (necesita endpoint `GET /audit?entity=products&entity_id=...` finalizado).

#### Criterios de aceptación (BDD)
- [ ] **Dado** un Comercial en `/products/MT-V-038` tab Ficha técnica **Cuando** click "Editar" **Entonces** los campos pasan a inputs editables (sku read-only) y aparecen botones Guardar/Cancelar.
- [ ] **Dado** edita `dn` de 50 a 65 y click Guardar **Cuando** el PUT responde 200 **Entonces** la UI sale de modo edit, muestra toast "Guardado" y refresca el detalle.
- [ ] **Dado** un error 422 (validación) **Cuando** ocurre **Entonces** los errores se muestran inline por campo.
- [ ] **Dado** click tab "Imágenes" **Cuando** se carga **Entonces** ve la grid de imágenes (cards 240×240, cada una con badge `mirrored`/`origin`/`failed`, star si primary), drop zone arriba.
- [ ] **Dado** una imagen subida **Cuando** termina el upload **Entonces** aparece en la grid con badge `origin` (aún no mirroreada — mirror se ejecuta async via Celery).
- [ ] **Dado** click "Set primary" en una image card **Cuando** confirma **Entonces** la card actual gana star, la anterior la pierde, audit registra.
- [ ] **Dado** click "Eliminar" sobre image **Cuando** confirma en AlertDialog **Entonces** la imagen pasa a `status=archived` (soft) y desaparece de la grid.
- [ ] **Dado** click "Probe + Mirror" en panel derecho **Cuando** se invoca con `image_url_pim` no null **Entonces** la UI muestra spinner, lanza job Celery, polling cada 2 s, refresca grid cuando job completa.

#### Tareas técnicas (subtasks)
- [ ] Frontend: `app/(app)/products/[sku]/_components/identity-edit-form.tsx` con react-hook-form + zod, integrado al PUT.
- [ ] Frontend: `app/(app)/products/[sku]/_components/images-tab.tsx` con grid Shadcn + drop zone (`react-dropzone`).
- [ ] Frontend: `lib/api/images.ts` con typed fetcher (`uploadImage`, `setPrimary`, `deleteImage`, `triggerProbeMirror`, `getImageStatus`).
- [ ] Frontend: lightbox component reusando Shadcn Dialog (preview imagen tamaño completo).
- [ ] Frontend: i18n keys (es + en) — "Editar", "Guardar", "Imagen primaria", "Probe + Mirror", "Subiendo...", "Mirror failed", "Origin", "Mirrored".
- [ ] Frontend: empty state imágenes ("No hay imágenes para este SKU. Arrastrá la primera arriba.").
- [ ] Tests: unit de identity-edit-form (validación zod) y images-tab (upload mock, set-primary mock).
- [ ] Tests: E2E light Playwright happy path: edit `dn`, save, verify in detail; upload imagen, ver en grid.
- [ ] Docs: README "Cómo añadir una nueva tab al detalle de SKU" extender.

#### Dependencias
- Bloqueada por: US-1A-02-03 (PUT), US-1A-02-06 (bucket + signed URL endpoints), US-1A-02-07 (probe+mirror endpoints), US-1A-02-08 (thumbnails async).
- Bloquea a: ninguna directa S2; abre el camino a tabs Costes/Precios en S3.

#### Mocks / Wireframes
- Referencia: `ux-mockups-mt-pricing-mdm-phase1.md` Pantalla 3 (Ficha técnica edit) y Pantalla 4 (Imágenes).
- Datos test: 5 SKUs cargados; uno con `image_url_pim` válido del PIM real para validar Probe+Mirror end-to-end.

#### Endpoints API afectados
- Consume: `PUT /products/{sku}`, `POST /products/{sku}/images`, `POST /products/{sku}/images/{id}/probe`, `PATCH /products/{sku}/images/{id}` (set primary, archive), `GET /products/{sku}/images`.

#### Modelos afectados
- Frontend types `ProductImage` reflejan `product_images` SQLAlchemy.

#### Observability
- Métricas (Sentry frontend): tasa error en `images.upload`, latencia p95 set primary, tasa de éxito Probe + Mirror.
- Logs: `actor=user_id, action=image_upload|image_set_primary|image_probe`.
- Error scenarios: 5xx backend → toast error + Sentry. Probe falla → badge red + tooltip motivo (`broken_link`, `too_large`, `invalid_format`).

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial (Pantalla 4 firmado).
- [ ] API contract acordado y mergeado.
- [ ] Modelo SQLAlchemy disponible.
- [ ] Permisos RBAC definidos.
- [ ] Datos test disponibles.
- [ ] No tiene dependencias bloqueantes pendientes (US-1A-02-06/07/08 done).
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan (unit + 1 E2E happy).
- [ ] Coverage ≥ 80 % en componentes nuevos.
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada (N/A frontend).
- [ ] Deploy a staging exitoso.
- [ ] Smoke test en staging por dev distinto al autor (subir 1 imagen real, set primary, eliminar).
- [ ] Audit event verificado (image_upload + image_set_primary).
- [ ] Documentación actualizada.
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.

#### Notas
Si Probe + Mirror llega tarde (US-1A-02-07 slipea), entregar tab Imágenes en modo "manual upload only" (sin botón Probe + Mirror) — quitar 2 SP del estimate. Tab Costes / Precios / Traducciones siguen disabled con tooltip "Próximamente S3".

#### SP
**5** (subset; el doc fuente original era 8 SP cubriendo 6 tabs).

#### Sprint asignado
S2.

#### Owner técnico (placeholder)
TBD.

---

### US-1A-02-06 — Bucket `product-images` privado con signed URLs y RLS por rol

**Épica**: EP-1A-02 ([epics-and-stories-mt-pricing-mdm-phase1.md §EP-1A-02 línea 489](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** TI Integración
**Quiero** un bucket Supabase Storage `product-images` privado con paths convencionales y RLS por rol
**Para** cumplir el requisito explícito del cliente de que toda imagen viva en Supabase (PRD §14.6, ADR-033).

#### Contexto
Sin este bucket, no existe storage de imágenes. La RLS en Storage es distinta de la RLS en tablas — Supabase Storage usa policies escritas en `storage.objects`. Los paths siguen convención `master/{sku}/primary.{ext}` para originales y `thumbnails/{sku}/{256|512|1024}/primary.webp` para variantes (US-1A-02-08).

#### Criterios de aceptación (BDD)
- [ ] **Dado** la migración aplicada **Cuando** consulto la consola Supabase **Entonces** existe bucket `product-images` con `public=false`.
- [ ] **Dado** un usuario `comercial` autenticado **Cuando** llama `GET /api/v1/products/{sku}/images/{image_id}/signed-url` **Entonces** el backend retorna URL signed con TTL **24 h** (ADR-033) firmada con `service_role`.
- [ ] **Dado** un usuario sin auth **Cuando** intenta acceder a un signed URL expirado **Entonces** Supabase retorna 403.
- [ ] **Dado** un Comercial **Cuando** sube vía `POST /api/v1/products/{sku}/images` (multipart, ≤ 5 MB MIME image/png|jpeg|webp|avif) **Entonces** el backend persiste el archivo en `product-images/master/{sku}/{uuid}.{ext}` con `service_role`, crea fila en `product_images` con `storage_path`, `width`, `height`, `hash_sha256`, `role='primary'` si es la primera.
- [ ] **Dado** un upload > 5 MB **Cuando** se intenta **Entonces** retorna 422 con `error.code="image_too_large"`.
- [ ] **Dado** un MIME no soportado (ej. `image/gif`) **Cuando** se intenta **Entonces** retorna 422.
- [ ] **Dado** RLS de `product_images` **Cuando** un usuario sin rol intenta `SELECT` directo **Entonces** retorna 0 filas (defense-in-depth aplica también a la tabla, no sólo al bucket).

#### Tareas técnicas (subtasks)
- [ ] Backend: SQL migration `0004_create_product_images.py` que crea tabla `product_images` (modelo ya está en `mt-sqlalchemy-models.md` §587).
- [ ] DB / Supabase: script `infra/supabase/migrations/0004_storage_product_images.sql` que crea bucket via `storage.create_bucket('product-images', public=false)` + storage policies (`storage.objects` SELECT/INSERT/UPDATE/DELETE por rol auth).
- [ ] Backend: `app/services/image_service.py` con `upload_image(sku, file, actor)`, `list_images(sku)`, `set_primary(sku, image_id, actor)`, `archive_image(sku, image_id, actor)`, `get_signed_url(image_id, ttl=86400)`.
- [ ] Backend: validador MIME (`python-magic` o cabecera) + size check + cálculo `hash_sha256` para dedup futuro.
- [ ] Backend: `app/api/v1/images.py` con endpoints `POST /products/{sku}/images`, `GET /products/{sku}/images`, `PATCH /products/{sku}/images/{id}` (set primary / archive), `GET /products/{sku}/images/{id}/signed-url`.
- [ ] Backend: dependency `get_supabase_admin` (US-1A-01-09-S1) usado para Storage operations.
- [ ] Backend: RLS policies tabla `product_images` (SELECT auth, INSERT/UPDATE comercial+, DELETE deny).
- [ ] Tests: unit del service (mock supabase-py). Integration con Supabase staging real: upload 1 KB blob → list → signed URL → fetch externo verifica retorna 200 → archive → list filtra archived.
- [ ] Docs: ADR-033 referenciado en README; `mt-security-compliance-design.md` actualizado con la policy de storage.

#### Dependencias
- Bloqueada por: US-1A-01-09-S1 (`get_supabase_admin`), US-1A-02-01-S1 (`products` table), US-1A-01-08-S1 (Alembic).
- Bloquea a: US-1A-02-04-S2 (tab Imágenes), US-1A-02-07 (probe+mirror), US-1A-02-08 (thumbnails).

#### Mocks / Wireframes
- Referencia: `ux-mockups-mt-pricing-mdm-phase1.md` Pantalla 4 (UI consume signed URLs).
- Datos test: 1 imagen 800×600 JPEG (~50 KB) en `tests/fixtures/images/sample.jpg`.

#### Endpoints API afectados
- `POST /api/v1/products/{sku}/images`.
- `GET /api/v1/products/{sku}/images`.
- `PATCH /api/v1/products/{sku}/images/{id}`.
- `GET /api/v1/products/{sku}/images/{id}/signed-url`.

#### Modelos afectados
- `ProductImage` (`app/db/models/product.py` o `app/db/models/product_images.py`).

#### Observability
- Métricas: `images.upload.success/failure`, `images.signed_url.requests`, `images.bucket.size_bytes`.
- Logs: `actor, action=image_upload, sku, image_id, bytes, mime`.
- Error scenarios: Supabase Storage 5xx → Sentry crit + retry 1 vez con backoff. MIME inválido → 422 sin Sentry.

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial (Pantalla 4).
- [ ] API contract acordado y mergeado.
- [ ] Modelo SQLAlchemy disponible.
- [ ] Permisos RBAC definidos (comercial+ write, todos auth read via signed URL).
- [ ] Datos test disponibles.
- [ ] No tiene dependencias bloqueantes pendientes.
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan.
- [ ] Coverage ≥ 80 % en `app/services/image_service.py`.
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada.
- [ ] Migration de bucket + policies aplicada en Supabase staging.
- [ ] Deploy a staging exitoso.
- [ ] Smoke test en staging por dev distinto al autor.
- [ ] Audit event verificado (image_upload registra).
- [ ] Documentación actualizada (ADR-033 referenced).
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.

#### Notas
TTL signed URLs **24 h** confirmado por ADR-033 + epics-and-stories §497. Si se decide reducir a 1 h por seguridad, ajustar y refrescar en frontend cada N min.

#### SP
**5**

#### Sprint asignado
S2.

#### Owner técnico (placeholder)
TBD (idealmente dev backend con experiencia previa en Supabase Storage).

---

### US-1A-02-07 — Probe + mirror obligatorio de imágenes externas (sync version + SSRF guard)

**Épica**: EP-1A-02 ([epics-and-stories-mt-pricing-mdm-phase1.md §EP-1A-02 línea 505](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** Comercial
**Quiero** que cualquier `image_url` externa se descargue automáticamente al bucket interno
**Para** no depender de hot-links de fabricantes (PRD §14.6.4).

#### Contexto
Sin esto, las imágenes del PIM real apuntan a `pim.mt-valves.es/...` que puede romperse o cambiar. **Riesgo de seguridad crítico (R-022 SSRF importer)**: la URL de origen viene de un campo libre del PIM y un actor malicioso podría inyectar URLs a `169.254.169.254` (metadata AWS), `localhost`, redes internas, etc. La probe DEBE bloquear esos casos.

En S2 entregamos la versión **sync** (request HTTP directo desde el endpoint POST /probe). La versión **async vía Celery** es identica funcionalmente — la encolamos como tarea Celery dentro del mismo endpoint para no bloquear UI; el resultado se persiste y la UI hace polling sobre `image_status`.

#### Criterios de aceptación (BDD)
- [ ] **Dado** un SKU con `image_url_pim = "https://pim.mt-valves.es/img/MT-V-038.jpg"` (válida) **Cuando** ejecuto `POST /api/v1/products/{sku}/images/probe` con body `{"origin_url":"..."}` **Entonces** el sistema encola job Celery que descarga la imagen, valida formato (JPEG/PNG/WebP/AVIF, ≤ 10 MB MAX para probe — más permisivo que upload directo), persiste en `product-images/master/{sku}/{uuid}.{ext}`, crea fila `product_images` con `image_origin_url`, retorna 202 con `job_id`.
- [ ] **Dado** una imagen 11 MB **Cuando** se descarga **Entonces** el job rechaza con `image_status='too_large'` y registra evento.
- [ ] **Dado** una URL 404 **Cuando** se descarga **Entonces** el job marca `image_status='broken_link'` con `last_error='HTTP 404'`.
- [ ] **Dado** una URL `http://169.254.169.254/...` (metadata cloud) **Cuando** se intenta probe **Entonces** el sistema rechaza con 422 `error.code="ssrf_blocked"` ANTES de la descarga (R-022 mitigation).
- [ ] **Dado** una URL en host privado (`10.*`, `172.16-31.*`, `192.168.*`, `127.0.0.0/8`, `::1`, `fc00::/7`, `fe80::/10`) **Cuando** se resuelve DNS **Entonces** rechaza con `ssrf_blocked`.
- [ ] **Dado** una URL HTTP plana (no HTTPS) **Cuando** se invoca probe **Entonces** rechaza salvo que `ENV=dev` y `ALLOW_HTTP_PROBE=1` explícito.
- [ ] **Dado** un MIME falso (extensión `.jpg` pero contenido HTML) **Cuando** se descarga **Entonces** rechaza con `image_status='invalid_format'` (chequear magic bytes, no extensión).
- [ ] **Dado** un job exitoso **Cuando** termina **Entonces** `image_status='mirrored'` y `image_origin_url` queda guardada para auditoría legal (Q-09 image rights).

#### Tareas técnicas (subtasks)
- [ ] Backend: `app/services/image_probe_service.py` con función `probe_and_mirror(origin_url, sku, actor)` y validador SSRF (`_validate_url_for_ssrf`).
- [ ] Backend: validador SSRF — resolver DNS pre-fetch, bloquear ranges privados (lista canónica), HTTPS-only, redirect-follow MAX 2 con re-validación cada hop, timeout 10 s, max-bytes 10 MB en streaming.
- [ ] Backend: `app/worker/tasks/probe_image.py` Celery task con retry policy (3 retries, exp backoff).
- [ ] Backend: actualizar modelo `ProductImage` con campos `image_origin_url`, `image_status` (enum: `mirrored|origin|broken_link|too_large|invalid_format|ssrf_blocked`), `last_error`, `last_probe_at`. Migración Alembic.
- [ ] Backend: `app/api/v1/images.py` endpoint `POST /products/{sku}/images/probe` que retorna 202 + job_id. Endpoint complementario `GET /jobs/{job_id}` para polling (genérico — reusable por US-1A-02-08).
- [ ] Backend: registro de hash sha256 + dedup (si misma imagen ya mirrored, reutilizar storage_path).
- [ ] Tests: unit del SSRF validator con vectores de ataque (metadata IP, localhost, redirección a interno, file://, DNS rebinding mock).
- [ ] Tests: integration con Supabase staging y httpbin (URL válida, URL 404, URL > 10MB simulada).
- [ ] Docs: ADR-NEW (proponer ADR-047) "Política SSRF probe imágenes" + actualizar `mt-security-compliance-design.md`.

#### Dependencias
- Bloqueada por: US-1A-02-06 (bucket).
- Bloquea a: US-1A-02-04-S2 (tab Imágenes botón Probe), US-1A-06-01 (importer PIM dispara probe por cada SKU con `image_url_pim`).

#### Mocks / Wireframes
- Referencia: `ux-mockups-mt-pricing-mdm-phase1.md` Pantalla 4 (panel "Probe & Mirror status").
- Datos test: 5 SKUs fixture con `image_url_pim` poblado (3 válidas, 1 broken, 1 SSRF para test).

#### Endpoints API afectados
- `POST /api/v1/products/{sku}/images/probe` (nuevo).
- `GET /api/v1/jobs/{job_id}` (nuevo, genérico).

#### Modelos afectados
- `ProductImage` (extender con 4 campos nuevos + enum `image_status_t`).

#### Observability
- Métricas: `images.probe.success/failure{reason}`, `images.probe.duration_p95`, `images.probe.ssrf_blocks` count.
- Logs: `actor, action=image_probe, sku, origin_url_host, status, bytes, duration_ms, dns_resolved_ip`.
- Error scenarios: SSRF block → log warn + Sentry breadcrumb (no crit). Network 5xx → reintenta. Final fail → Sentry warning con tag `image.probe.failure`.

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial.
- [ ] API contract acordado y mergeado.
- [ ] Modelo SQLAlchemy disponible (extension acordada).
- [ ] Permisos RBAC definidos.
- [ ] Datos test disponibles (3 URLs de test).
- [ ] No tiene dependencias bloqueantes pendientes.
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan (unit SSRF battery + integration).
- [ ] Coverage ≥ 80 % en código nuevo.
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada.
- [ ] Deploy a staging exitoso.
- [ ] Smoke test en staging por dev distinto al autor (probe URL real → status mirrored).
- [ ] Audit event verificado.
- [ ] Documentación actualizada (ADR-047 propuesto + security design).
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.

#### Notas
**Q-09 image rights** sigue abierta. Mientras no haya acuerdo legal MT España ↔ MT ME, el mirror se ejecuta con riesgo legal del sponsor (R-044). Documentar `image_origin_url` siempre para trazabilidad. Considerar feature flag `ALLOW_PROBE_FROM_PIM_ES` que pueda activarse/desactivarse desde admin si Q-09 cambia.

#### SP
**5**

#### Sprint asignado
S2.

#### Owner técnico (placeholder)
TBD (idealmente dev backend con experiencia security/SSRF).

---

### US-1A-02-08 — Generación async de thumbnails (256/512/1024 px) en WebP via Celery

**Épica**: EP-1A-02 ([epics-and-stories-mt-pricing-mdm-phase1.md §EP-1A-02 línea 521](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** TI Integración
**Quiero** que cada imagen subida o mirroreada genere thumbnails async vía Celery
**Para** que la UI cargue rápido sin servir originales pesados.

#### Contexto
Las imágenes originales pueden ser 5-10 MB. Listar 50 SKUs con thumbnail original = 250 MB+ transferidos. Los thumbnails 256 px en WebP suelen ser ~10 KB. **Esta es la primera tarea Celery operativa del proyecto** — establece el patrón para US-1A-02-07 probe (que en S2 puede o no ir async — ver notas), y para futuros jobs S3 (recompute pricing, embeddings).

#### Criterios de aceptación (BDD)
- [ ] **Dado** una imagen subida o mirroreada en `master/{sku}/{uuid}.jpg` **Cuando** la tarea Celery `generate_thumbnails(image_id)` se ejecuta **Entonces** se persisten 3 variantes WebP en `thumbnails/{sku}/{256|512|1024}/{uuid}.webp`.
- [ ] **Dado** los thumbnails generados **Cuando** la UI solicita signed URL para variante 256 **Entonces** retorna URL del thumbnail (no del original).
- [ ] **Dado** un fallo de generación (imagen corrupta) **Cuando** ocurre **Entonces** Sentry captura el error con tag `image.thumbnails.failure`, la imagen original sigue accesible como fallback (`image_status` queda en `mirrored` aunque thumbnails fallen).
- [ ] **Dado** la tarea Celery con max_retries=2 **Cuando** falla 3 veces **Entonces** queda en dead-letter queue Redis.
- [ ] **Dado** el endpoint `GET /products/{sku}/images/{id}/signed-url?variant=256` **Cuando** se invoca **Entonces** retorna URL del 256; si variant no existe aún (job no terminó), retorna URL del original con header `X-Thumbnail-Status: pending`.

#### Tareas técnicas (subtasks)
- [ ] Backend: `app/worker/celery_app.py` setup Celery con broker Redis, queues (`images`, `imports`, `recompute` — sólo `images` activo en S2).
- [ ] Backend: `app/worker/tasks/thumbnails.py` con tarea `generate_thumbnails(image_id)`. Usa Pillow + WebP encoder.
- [ ] Backend: hook después de `upload_image` y `probe_and_mirror` que encola `generate_thumbnails.delay(image_id)`.
- [ ] Backend: extender `ProductImage` con campos `thumbnails_generated_at`, `thumbnails_status` (enum `pending|done|failed`), o tabla auxiliar `product_image_variants` (preferido — soporta múltiples variantes en futuro).
- [ ] Infra: `docker-compose.dev.yml` añade servicio `worker` (mismo image que backend, command `celery -A app.worker.celery_app worker -Q images -l info`).
- [ ] Infra: healthcheck del worker (`celery inspect ping`).
- [ ] Tests: unit de `generate_thumbnails` con imagen sintética (PIL Image.new). Integration: subir imagen → esperar < 10 s → verificar 3 variantes en bucket.
- [ ] Docs: README "Cómo arrancar el worker en dev" + `mt-jobs-module-design.md` actualizar con esta primera tarea.

#### Dependencias
- Bloqueada por: US-1A-02-06 (bucket), US-1A-01-09-S1 (supabase-py), Redis disponible (debería estar desde docker-compose dev S0).
- Bloquea a: US-1A-02-04-S2 (UI consume thumbnail variants), US-1A-02-07 (probe puede usar el mismo flujo).

#### Mocks / Wireframes
- N/A (backend job).
- Datos test: 1 imagen JPEG 2 MB en fixture.

#### Endpoints API afectados
- `GET /api/v1/products/{sku}/images/{id}/signed-url?variant=256|512|1024|original` (extiende US-1A-02-06).

#### Modelos afectados
- `ProductImage` (campos thumbnails_*) o `ProductImageVariant` (tabla nueva).

#### Observability
- Métricas: `worker.tasks.thumbnails.duration_p95`, `worker.tasks.thumbnails.success/failure`, `worker.queue.images.length`.
- Logs: `task_id, image_id, sku, variants_generated=[256,512,1024], duration_ms`.
- Error scenarios: Pillow fail → Sentry crit (probable imagen corrupta upstream). DLQ → Sentry warn diario con count.

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial (N/A).
- [ ] API contract acordado y mergeado (signed-url variants).
- [ ] Modelo SQLAlchemy disponible.
- [ ] Permisos RBAC definidos (worker = service-role admin).
- [ ] Datos test disponibles.
- [ ] No tiene dependencias bloqueantes pendientes.
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan.
- [ ] Coverage ≥ 80 % en código nuevo.
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada.
- [ ] Deploy a staging exitoso (worker container live).
- [ ] Smoke test en staging por dev distinto al autor (subir imagen → ver thumbnails en bucket UI Supabase).
- [ ] Audit event verificado (N/A — internal job).
- [ ] Documentación actualizada (jobs design).
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.

#### Notas
Esta historia es prerequisito *de facto* para US-1A-02-07 si decidimos hacerlo async. Si capacidad obliga a bajar una, recomendado mantener thumbnails (UX más visible) y dejar probe sync sin Celery (probe sigue funcional, sólo bloquea HTTP request unos segundos).

#### SP
**3**

#### Sprint asignado
S2.

#### Owner técnico (placeholder)
TBD.

---

### US-1A-02-09 — Filtros avanzados + búsqueda full-text en lista productos

**Épica**: EP-1A-02 ([epics-and-stories-mt-pricing-mdm-phase1.md §EP-1A-02 línea 537](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** Comercial
**Quiero** un listado filtrable por familia, brand, dn, pn, material, data_quality, active y full-text en name_en/sku
**Para** encontrar SKUs rápidamente entre 5 000+ filas tras importar PIM real.

#### Contexto
S1 dejó listado básico con `family`, `data_quality`, `q` simple. Tras importar PIM real (US-1A-06-01), los Comerciales tendrán > 5 000 SKUs y necesitan filtros más finos. Esta story es **gating soft** del éxito demo S2 — sin ella la UI con 5 000 filas es poco útil.

#### Criterios de aceptación (BDD)
- [ ] **Dado** 5 086 SKUs cargados **Cuando** envío `GET /api/v1/products?family=gate_valve&brand=MT&dn=50&active=true&page_size=50` **Entonces** retorna ≤ 50 filas con cursor next.
- [ ] **Dado** un `q="brass DN50"` **Cuando** consulto **Entonces** retorna SKUs cuyo `name_en` o `sku` matchean (full-text con `to_tsvector` en español+inglés simples) ranked por relevance.
- [ ] **Dado** un filtro `data_quality=blocked` **Cuando** consulto **Entonces** retorna sólo SKUs en ese estado.
- [ ] **Dado** un `page_size=500` **Cuando** consulto **Entonces** retorna 422 (max 200, NFR-06).
- [ ] **Dado** todos los filtros aplicados a la vez **Cuando** consulto **Entonces** la latencia p95 en backend es < **500 ms** sobre 5 086 filas (NFR-06).
- [ ] **Dado** la UI con un input de búsqueda con debounce 300 ms **Cuando** el usuario tipea **Entonces** la URL refleja `?q=...&family=...` y la lista se actualiza.

#### Tareas técnicas (subtasks)
- [ ] Backend: extender `list_products` service con `brand`, `dn`, `pn`, `material`, `active` filters.
- [ ] Backend: `to_tsvector('simple', coalesce(name_en,'') || ' ' || coalesce(sku,''))` como columna generada o índice GIN expression. Migración Alembic.
- [ ] Backend: índices compuestos `(family, active, data_quality)` y GIN sobre tsvector. Verificar con EXPLAIN.
- [ ] Frontend: extender `products-filters.tsx` con FilterPanel (Sheet derecho) con todos los filtros + chips activos en toolbar.
- [ ] Frontend: input de búsqueda con `useDebouncedCallback`.
- [ ] Frontend: chips de filtros activos con × para borrar individual + botón "Limpiar todo".
- [ ] Tests: integration backend con fixture de 1 000 SKUs, latencia < 500 ms.
- [ ] Tests: unit frontend del filter panel.
- [ ] Docs: actualizar OpenAPI con nuevos query params.

#### Dependencias
- Bloqueada por: US-1A-02-02-S1, US-1A-02-03-S1, US-1A-06-01 (necesita PIM real cargado para validar perf).
- Bloquea a: ninguna directa S2; requerido por demo final.

#### Mocks / Wireframes
- Referencia: `ux-mockups-mt-pricing-mdm-phase1.md` Pantalla 2 (Filter Sheet derecho).
- Datos test: PIM real importado en staging.

#### Endpoints API afectados
- `GET /api/v1/products` (extiende; mismo path).

#### Modelos afectados
- `Product` (sin nuevas columnas; añadir índices y posiblemente columna `search_vector` generada).

#### Observability
- Métricas: `products.list.duration_p95{filter_count}`, `products.list.empty_results` count.
- Logs: filtros aplicados con cardinality (no values, sólo set).
- Error scenarios: query lenta (> 1 s) → Sentry breadcrumb. Filter inválido → 422.

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial.
- [ ] API contract acordado y mergeado.
- [ ] Modelo SQLAlchemy disponible.
- [ ] Permisos RBAC definidos.
- [ ] Datos test disponibles.
- [ ] No tiene dependencias bloqueantes pendientes.
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan.
- [ ] Coverage ≥ 80 % en código nuevo.
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada.
- [ ] Deploy a staging exitoso.
- [ ] Smoke test en staging por dev distinto al autor (filtrar 5k SKUs en < 1 s wall-clock).
- [ ] Audit event verificado (N/A — read).
- [ ] Documentación actualizada.
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.

#### Notas
Si la perf con 5 000 SKUs no llega a < 500 ms, considerar denormalizar `search_vector` como columna `STORED GENERATED` y/o añadir caché en Redis con TTL 60 s (riesgo: stale data).

#### SP
**3**

#### Sprint asignado
S2.

#### Owner técnico (placeholder)
TBD.

---

### US-1A-02-10 — Bloqueo de borrado físico (sólo soft-deactivate)

**Épica**: EP-1A-02 ([epics-and-stories-mt-pricing-mdm-phase1.md §EP-1A-02 línea 553](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** TI Integración
**Quiero** que `DELETE /products/{sku}` esté deshabilitado y sólo `PATCH /products/{sku}/active=false` funcione
**Para** preservar histórico VAT-compliant (BR-1a-07, NFR-35).

#### Contexto
VAT UAE (FTA 2026) exige preservar audit trail durante 7 años (Q-13). Permitir DELETE físico violaría compliance. Esta story es trivial pero hardening crítico — bloqueo se aplica además a las otras tablas operativas en su sprint correspondiente (`costs`, `prices` en S3; `suppliers` ya en su CRUD US-1A-03-02).

#### Criterios de aceptación (BDD)
- [ ] **Dado** un Comercial **Cuando** envía `DELETE /api/v1/products/{sku}` **Entonces** retorna 405 Method Not Allowed con `error.code="vat_compliance_block"` y mensaje en español.
- [ ] **Dado** un Comercial **Cuando** envía `PATCH /api/v1/products/{sku}/active` con body `{"active":false}` **Entonces** persiste `active=false`, registra `audit_events(action='deactivate')`, retorna 200.
- [ ] **Dado** un SKU desactivado **Cuando** consulto `GET /products?active=true` **Entonces** no aparece.
- [ ] **Dado** un SKU desactivado **Cuando** consulto `GET /products/{sku}` **Entonces** retorna 200 con la ficha (no 404 — sólo el flag está en false).
- [ ] **Dado** un Comercial **Cuando** reactiva con `PATCH active=true` **Entonces** vuelve a aparecer en listados activos. Audit registra ambos eventos.

#### Tareas técnicas (subtasks)
- [ ] Backend: NO añadir handler DELETE en `app/api/v1/products.py` — FastAPI auto-retorna 405 si el método no está mapeado. Verificar esto con test explícito.
- [ ] Backend: añadir endpoint `PATCH /api/v1/products/{sku}/active` con body `{"active": bool}`.
- [ ] Backend: extender list filter `active` (default UI = `true` para listados normales; `false` o `all` accesibles).
- [ ] Tests: integration test que `DELETE` retorna 405 con mensaje correcto. Test que reactivación funciona.
- [ ] Docs: actualizar OpenAPI con nota explícita "DELETE no soportado por VAT compliance UAE".

#### Dependencias
- Bloqueada por: US-1A-02-02-S1.
- Bloquea a: ninguna; es hardening transversal.

#### Mocks / Wireframes
- N/A (botón "Desactivar" en UI llega en US-1A-02-04-S2 — ver Pantalla 3 kebab menu).
- Datos test: 1 SKU activo + 1 desactivado.

#### Endpoints API afectados
- `PATCH /api/v1/products/{sku}/active` (nuevo).
- `DELETE /api/v1/products/{sku}` (explícitamente bloqueado, retorna 405).

#### Modelos afectados
- `Product.active` (campo ya existe desde S1).

#### Observability
- Métricas: `products.deactivate` count, `products.delete_attempts_blocked` count (alerta si > 5/día).
- Logs: `actor, action=deactivate_product, sku, prev_active`.
- Error scenarios: intento DELETE → log warn (no Sentry; comportamiento esperado).

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial.
- [ ] API contract acordado y mergeado.
- [ ] Modelo SQLAlchemy disponible.
- [ ] Permisos RBAC definidos.
- [ ] Datos test disponibles.
- [ ] No tiene dependencias bloqueantes pendientes.
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan.
- [ ] Coverage ≥ 80 % en código nuevo.
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada (N/A).
- [ ] Deploy a staging exitoso.
- [ ] Smoke test en staging por dev distinto al autor.
- [ ] Audit event verificado.
- [ ] Documentación actualizada.
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.

#### Notas
Patrón replicable: **toda tabla con audit trail en este proyecto NO debe tener DELETE en API**. Documentar en arquitectura §X como guideline general.

#### SP
**2**

#### Sprint asignado
S2.

#### Owner técnico (placeholder)
TBD.

---

### US-1A-03-01 — Schema `suppliers` con moneda contractual + lead time + currencies seed mínimo

**Épica**: EP-1A-03 ([epics-and-stories-mt-pricing-mdm-phase1.md §EP-1A-03 línea 573](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** dev backend
**Quiero** la migración Alembic que crea `suppliers` + un seed mínimo de `currencies` (AED, EUR, USD, SAR)
**Para** soportar costos por proveedor en EP-1A-04 sin esperar a S3 (donde llega el FX engine completo US-1A-05-01).

#### Contexto
El doc fuente declara `US-1A-03-01` con dependencia `US-1A-05-01 (currencies seed)`, que está asignada a S3. Para no bloquear S2, **adelantamos un seed minimal de `currencies` aquí** (sólo la tabla y 4 filas, sin lógica de FX rates ni triggers — eso queda en S3). Apéndice B documenta la decisión y propone aclaración al doc fuente.

#### Criterios de aceptación (BDD)
- [ ] **Dado** la migración aplicada **Cuando** consulto `\d currencies` **Entonces** existe la tabla con (`code` PK, `name`, `symbol`, `is_base`, `active`).
- [ ] **Dado** la migración aplicada **Cuando** consulto `SELECT * FROM currencies` **Entonces** existen 4 filas: AED (`is_base=true`), EUR, USD, SAR.
- [ ] **Dado** la migración aplicada **Cuando** consulto `\d suppliers` **Entonces** existe con (`code` PK, `name`, `contact_email` CITEXT, `contact_phone`, `contract_currency` FK→currencies, `lead_time_days`, `payment_terms`, `notes`, `active`, `created_at`, `updated_at`).
- [ ] **Dado** un INSERT en `suppliers` con `contract_currency='EUR'` **Cuando** se ejecuta **Entonces** persiste con FK válida.
- [ ] **Dado** un INSERT con `contract_currency='XYZ'` (no en currencies) **Cuando** se ejecuta **Entonces** falla por FK.
- [ ] **Dado** la migración aplicada **Cuando** ejecuto `alembic downgrade -1` **Entonces** ambas tablas se eliminan limpio (orden correcto: suppliers antes que currencies).
- [ ] **Dado** RLS activo **Cuando** un usuario sin rol intenta INSERT **Entonces** deniega.

#### Tareas técnicas (subtasks)
- [ ] Backend: `app/db/models/currency.py` clase `Currency` mínima.
- [ ] Backend: `app/db/models/supplier.py` clase `Supplier` (modelo ya en `mt-sqlalchemy-models.md` §608).
- [ ] DB: migración Alembic `0005_create_currencies_and_suppliers.py` con CREATE TABLE + seed currencies + RLS policies.
- [ ] DB: enums + check constraints (`is_base` única).
- [ ] DB: RLS — `suppliers_select_authenticated`, `suppliers_insert_comercial`, `suppliers_update_comercial`, `currencies_select_authenticated`.
- [ ] Tests: unit del modelo. Integration: insert supplier, verify FK, downgrade.
- [ ] Docs: ADR breve sobre adelanto del seed currencies a S2 (o nota en arquitectura §X).

#### Dependencias
- Bloqueada por: US-1A-01-08-S1.
- Bloquea a: US-1A-03-02 (CRUD suppliers), US-1A-04-01 (cost schemes, en S2 también).

#### Mocks / Wireframes
- N/A (data layer).
- Datos test: 4 currencies (seed) + 1 supplier fixture (`MT_VALVES_ES`).

#### Endpoints API afectados
- Ninguno directamente.

#### Modelos afectados
- `Currency` (nuevo).
- `Supplier` (nuevo).

#### Observability
- Métricas: `suppliers.count`, `suppliers.active.count`.
- Logs: queries lentas con actor.
- Error scenarios: violación constraint → 422 al cliente, breadcrumb a Sentry.

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial (N/A directo).
- [ ] API contract acordado y mergeado (N/A).
- [ ] Modelo SQLAlchemy disponible.
- [ ] Permisos RBAC definidos.
- [ ] Datos test disponibles.
- [ ] No tiene dependencias bloqueantes pendientes.
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan.
- [ ] Coverage ≥ 80 % en código nuevo.
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada.
- [ ] Deploy a staging exitoso.
- [ ] Smoke test en staging por dev distinto al autor.
- [ ] Audit event verificado (sin trigger en S2 sobre suppliers — emitir desde service layer en US-1A-03-02).
- [ ] Documentación actualizada.
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.

#### Notas
La tabla `currencies` se queda **read-only en S2** (sólo el seed). UI/admin para gestionarla llega en S3 (US-1A-05-03). El trigger FX as-of stamping en `costs` también es S3 (US-1A-04-02). Esta story crea el "hueco" para que `suppliers.contract_currency` valide FK.

#### SP
**2** (originalmente 2 SP en doc fuente; +0 por seed currencies trivial).

#### Sprint asignado
S2.

#### Owner técnico (placeholder)
TBD.

---

### US-1A-03-02 — CRUD UI + API de proveedores con audit

**Épica**: EP-1A-03 ([epics-and-stories-mt-pricing-mdm-phase1.md §EP-1A-03 línea 589](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** Comercial
**Quiero** crear/editar/desactivar proveedores desde la UI
**Para** mantener el maestro sin pasar por TI.

#### Contexto
Primera UI de "maestro auxiliar". Establece patrón replicable para otros maestros (currencies admin S3, fx_rates S3, schemes S2). Ruta `/suppliers` con DataTable + form modal.

#### Criterios de aceptación (BDD)
- [ ] **Dado** un Comercial **Cuando** entra a `/suppliers` **Entonces** ve DataTable con columnas (Code, Name, Currency, Lead time, Active) paginada.
- [ ] **Dado** click "Nuevo proveedor" **Cuando** completa form (`code, name, contract_currency, lead_time_days, contact_email`) y guarda **Entonces** llama `POST /api/v1/suppliers`, persiste, registra `audit_events(action='create', entity='suppliers', payload_after)`, refresca lista.
- [ ] **Dado** un proveedor existente **Cuando** click "Editar" y modifica `lead_time_days` **Entonces** llama `PUT /api/v1/suppliers/{code}`, audit con `diff`.
- [ ] **Dado** un proveedor activo **Cuando** click "Desactivar" **Entonces** AlertDialog confirma "Esto ocultará el proveedor pero mantendrá costes históricos. ¿Continuar?", luego `PATCH active=false`, audit, lista refresca.
- [ ] **Dado** un proveedor con `code` duplicado **Cuando** intento crearlo **Entonces** 409 con error inline en UI.
- [ ] **Dado** un usuario sin auth **Cuando** llama cualquier endpoint **Entonces** 401.
- [ ] **Dado** un Comercial **Cuando** envía `DELETE /api/v1/suppliers/{code}` **Entonces** 405 (mismo patrón VAT-block que US-1A-02-10).

#### Tareas técnicas (subtasks)
- [ ] Backend: `app/api/v1/suppliers.py` con CRUD endpoints (GET list, POST, GET by code, PUT, PATCH active).
- [ ] Backend: `app/services/supplier_service.py` con audit emit en create/update/deactivate.
- [ ] Backend: Pydantic schemas (`SupplierCreate`, `SupplierUpdate`, `SupplierRead`).
- [ ] Backend: trigger Postgres `audit.log_event()` aplicado a `suppliers` (reusa función PL/pgSQL S1).
- [ ] Frontend: ruta `/suppliers` con DataTable + filtros (`active`, search by name).
- [ ] Frontend: form modal `supplier-form.tsx` con react-hook-form + zod.
- [ ] Frontend: i18n keys.
- [ ] Tests: unit service + integration CRUD.
- [ ] Tests: E2E light Playwright: crear, editar, desactivar.
- [ ] Docs: OpenAPI updated.

#### Dependencias
- Bloqueada por: US-1A-03-01.
- Bloquea a: US-1A-04-03 (`POST /costs` referencia supplier_code), US-1A-04-04 (UI tab Costes lista proveedores).

#### Mocks / Wireframes
- **No hay pantalla específica** en `ux-mockups-mt-pricing-mdm-phase1.md` para `/suppliers`. Reusar patrón Pantalla 2 (DataTable productos) + form modal estilo Pantalla 9 (Alta SKU) — **DECISIÓN UX pendiente**, ver Apéndice B.
- Datos test: 1 supplier fixture (`MT_VALVES_ES`, EUR, 45 días).

#### Endpoints API afectados
- `GET /api/v1/suppliers`.
- `POST /api/v1/suppliers`.
- `GET /api/v1/suppliers/{code}`.
- `PUT /api/v1/suppliers/{code}`.
- `PATCH /api/v1/suppliers/{code}/active`.

#### Modelos afectados
- `Supplier`.

#### Observability
- Métricas: `suppliers.create/update/deactivate` count.
- Logs: `actor, action, supplier_code`.
- Error scenarios: estándar.

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial (DECISIÓN UX pendiente — ver Apéndice B).
- [ ] API contract acordado y mergeado.
- [ ] Modelo SQLAlchemy disponible.
- [ ] Permisos RBAC definidos.
- [ ] Datos test disponibles.
- [ ] No tiene dependencias bloqueantes pendientes.
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan.
- [ ] Coverage ≥ 80 % en código nuevo.
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada (N/A — heredado de US-1A-03-01).
- [ ] Deploy a staging exitoso.
- [ ] Smoke test en staging por dev distinto al autor (crear, editar, desactivar 1 supplier).
- [ ] Audit event verificado.
- [ ] Documentación actualizada.
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.

#### Notas
Si la decisión UX para `/suppliers` se demora, usar wireframe textual del PRD §10.1. UI mínima viable: DataTable + modal de form.

#### SP
**3**

#### Sprint asignado
S2.

#### Owner técnico (placeholder)
TBD.

---

### US-1A-04-01 — Schemes seeded (FBA, FBM, DIRECT_B2C, DIRECT_B2B, MARKETPLACE) con `cost_components_template`

**Épica**: EP-1A-04 ([epics-and-stories-mt-pricing-mdm-phase1.md §EP-1A-04 línea 609](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** dev backend
**Quiero** los 5 esquemas seeded en migration con plantilla de componentes
**Para** que el motor de costes (S2-S3) valide breakdown por esquema.

#### Contexto
Inicia EP-1A-04. Schema y seed son trivial (2 SP). El motor real de costes (US-1A-04-02 trigger FX, US-1A-04-03 endpoint, US-1A-04-04 UI) llega en S3 una vez `fx_rates` esté implementada — esos están en S3.

#### Criterios de aceptación (BDD)
- [ ] **Dado** la migration aplicada **Cuando** consulto `SELECT * FROM schemes` **Entonces** existen 5 filas: FBA, FBM, DIRECT_B2C, DIRECT_B2B, MARKETPLACE con `cost_components_template` JSONB poblada.
- [ ] **Dado** el esquema FBA **Cuando** consulto su template **Entonces** incluye `["fob", "freight", "customs", "fba_fees", "payment_fees"]`.
- [ ] **Dado** el esquema FBM **Cuando** consulto su template **Entonces** incluye `["fob", "freight", "customs", "fbm_fees", "payment_fees"]`.
- [ ] **Dado** el esquema DIRECT_B2C **Cuando** consulto su template **Entonces** incluye `["fob", "freight", "customs", "payment_fees", "marketing"]`.
- [ ] **Dado** el esquema DIRECT_B2B **Cuando** consulto su template **Entonces** incluye `["fob", "freight", "customs", "payment_fees"]`.
- [ ] **Dado** el esquema MARKETPLACE **Cuando** consulto su template **Entonces** incluye `["fob", "freight", "customs", "marketplace_fees", "payment_fees", "marketing"]`.
- [ ] **Dado** un código `FBA` **Cuando** intento crearlo de nuevo **Entonces** falla por UNIQUE.
- [ ] **Dado** la migración aplicada **Cuando** ejecuto `alembic downgrade -1` **Entonces** la tabla y seed se eliminan limpio.

#### Tareas técnicas (subtasks)
- [ ] Backend: `app/db/models/scheme.py` clase `Scheme`.
- [ ] DB: migración Alembic `0006_create_schemes.py` con CREATE TABLE + seed 5 filas + RLS (read-all-auth, write-admin-only — TI).
- [ ] Tests: unit del modelo. Integration: query 5 schemes, validate templates.
- [ ] Docs: actualizar arquitectura §10.1 mencionando que los 5 templates son el contrato implícito para US-1A-04-03 cost validator.

#### Dependencias
- Bloqueada por: US-1A-01-08-S1.
- Bloquea a: US-1A-04-02, US-1A-04-03 (S3).

#### Mocks / Wireframes
- N/A.
- Datos test: las 5 filas seed (mismas para todos los entornos).

#### Endpoints API afectados
- Ninguno (read via Pydantic settings o SQLAlchemy directo en S2).

#### Modelos afectados
- `Scheme` (nuevo).

#### Observability
- Métricas: N/A.
- Logs: N/A.
- Error scenarios: violación UNIQUE → 422.

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial (N/A).
- [ ] API contract acordado y mergeado (N/A).
- [ ] Modelo SQLAlchemy disponible.
- [ ] Permisos RBAC definidos.
- [ ] Datos test disponibles.
- [ ] No tiene dependencias bloqueantes pendientes.
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan.
- [ ] Coverage ≥ 80 % en código nuevo.
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada.
- [ ] Deploy a staging exitoso.
- [ ] Smoke test en staging por dev distinto al autor (verificar 5 rows en Supabase Table Editor).
- [ ] Audit event verificado (N/A).
- [ ] Documentación actualizada.
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.

#### Notas
La validación del breakdown contra template se implementa en US-1A-04-03 (S3). En S2 sólo dejamos los 5 templates accesibles vía SELECT.

#### SP
**2**

#### Sprint asignado
S2.

#### Owner técnico (placeholder)
TBD.

---

### US-1A-06-01 — Importer `PIM completo.xlsx` con preview + apply (MUST de S2)

**Épica**: EP-1A-06 ([epics-and-stories-mt-pricing-mdm-phase1.md §EP-1A-06 línea 745](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** Comercial / TI
**Quiero** subir el archivo `PIM completo.xlsx` (5086 filas) en modo preview, ver diff, y luego confirmar
**Para** cargar el catálogo sin riesgo de overwrites silenciosos.

#### Contexto
**MUST DE S2** según preview Sprint 1 §10. Sin importer, S3 arranca con BD vacía. El doc fuente lo asignó a S1 originalmente, pero quedó deferido por capacity (no estaba en backlog S1). Entrega ahora con preview + apply (Pantalla 10 wizard 4 pasos del UX). Pipeline detallado en arquitectura §16.

**Gating**: depende de **Q-03 (PIM real entregado por MT)**. Si Q-03 sigue bloqueado al día 5 del sprint, fallback es US-1A-06-06 (Excel demo `stock_dubai_v23`). El equipo debe arrancar US-1A-06-01 desarrollando contra **fixture sintético derivado del PIM real estructuralmente** (5086 filas, headers conocidos por Sprint 0 mapping `sprint0-pim-column-mapping.md`); switch a archivo real cuando llegue.

#### Criterios de aceptación (BDD)
- [ ] **Dado** un Comercial sube `PIM completo.xlsx` (≤ 50 MB) **Cuando** llama `POST /api/v1/imports` con `multipart/form-data` y query `?type=pim&mode=preview` **Entonces** el sistema persiste el archivo en `import-batches/pim/{run_id}/raw.xlsx`, crea fila `import_runs(status='queued')`, encola `ImportTask`, retorna 202 con `run_id`.
- [ ] **Dado** la tarea Celery procesa el archivo **Cuando** termina parsing+validation+diff **Entonces** `import_runs.preview` queda con JSONB: `{summary: {total, new, updated, errors, orphans, locked}, rows: [{row_index, sku, action, diff?}]}`, `status='preview_ready'`.
- [ ] **Dado** un row con SKU sin `name_en` **Cuando** se procesa **Entonces** `import_run_rows.action='error'` con `error_code='BR_1A_02'`. El resto de rows se procesa.
- [ ] **Dado** un SKU duplicado dentro del archivo (misma key 2 veces) **Cuando** se procesa **Entonces** la primera ocurrencia se procesa, las siguientes quedan en errores.
- [ ] **Dado** preview ready **Cuando** Comercial llama `POST /api/v1/imports/{run_id}/apply` **Entonces** el sistema adquiere `pg_advisory_lock(hash('import:pim'))`, comienza chunked savepoints (5k rows max), ejecuta INSERT/UPDATE row-by-row con audit emit, libera lock, marca `status='completed'`, retorna 200 con stats finales.
- [ ] **Dado** un apply fallido en mid-flight (e.g. 2000 OK, 500 fail por DB connection drop) **Cuando** ocurre **Entonces** las 2000 OK ya commiteadas en savepoints anteriores quedan persistidas; el savepoint 500 hace rollback parcial; reporte muestra `success: 2000, failed: 500`.
- [ ] **Dado** un `manual_locked_fields` declarado en un row PIM existente **Cuando** apply intenta UPDATE **Entonces** los locked fields quedan intactos y el reporte indica `action='skip_locked'` para esos fields.
- [ ] **Dado** un Comercial **Cuando** llama `GET /api/v1/imports/{run_id}` **Entonces** retorna estado actual + summary + link a preview/report CSVs.
- [ ] **Dado** un Comercial **Cuando** llama `GET /api/v1/imports/{run_id}/report?format=csv` **Entonces** retorna CSV con columnas `row_index, sku, action, error_code, diff`.

#### Tareas técnicas (subtasks)
- [ ] Backend: migración Alembic `0007_create_import_tables.py` con `import_runs` y `import_run_rows` (modelo en `mt-sqlalchemy-models.md` §936).
- [ ] Backend: `app/services/import_service.py` con `create_import_run`, `get_run_status`, `apply_run`.
- [ ] Backend: `app/importers/pim_parser.py` con openpyxl streaming reader (no carga 5k filas en RAM de golpe). Mapeo columnas según `sprint0-pim-column-mapping.md`.
- [ ] Backend: `app/importers/pim_validator.py` (BR-1a-01..1a-12 validations).
- [ ] Backend: `app/importers/pim_differ.py` (compute action ∈ create|update|skip_locked|no_change|error|orphan).
- [ ] Backend: `app/worker/tasks/import_pim.py` con dos tareas: `pim_preview_task(run_id)` y `pim_apply_task(run_id)`.
- [ ] Backend: Celery `pg_advisory_lock` helper (locks por tipo de import — evita 2 PIM apply concurrentes).
- [ ] Backend: chunked savepoint commit (cada 1000 rows).
- [ ] Backend: `app/api/v1/imports.py` endpoints `POST /imports`, `GET /imports`, `GET /imports/{run_id}`, `POST /imports/{run_id}/apply`, `POST /imports/{run_id}/cancel`, `GET /imports/{run_id}/report`.
- [ ] Frontend: ruta `/imports` (lista de runs) y `/imports/new?type=pim` (wizard 4 pasos Pantalla 10).
- [ ] Frontend: componentes `import-wizard-step1-upload.tsx`, `step2-mapping.tsx` (auto-detect, override manual), `step3-preview.tsx` (4 tabs Nuevos/Modificados/Errores/Huérfanos), `step4-confirm.tsx`.
- [ ] Frontend: polling `useQuery` sobre `GET /imports/{run_id}` con interval 2 s mientras `status` ∈ `queued|parsing|preview_ready|applying`.
- [ ] Frontend: i18n.
- [ ] Tests: unit parser (fixture XLSX sintético 100 rows). Unit validator (rows con todos los errores BR). Unit differ (create/update/skip_locked). Integration full pipeline preview→apply con fixture 1k rows en testcontainer Postgres.
- [ ] Tests: tests de SSRF lateral si parsamos referencias a URLs (ver US-1A-02-07; aquí relevante si auto-disparamos probe por cada SKU con `image_url_pim` — **decidir scope**: en S2 NO, importer sólo carga campos; probe es post-import manual).
- [ ] Tests: E2E Playwright: subir XLSX 100 rows → preview → apply → ver en `/products`.
- [ ] Docs: ADR-008 referenciado; nueva sección en `mt-jobs-module-design.md` con flujo PIM apply.

#### Dependencias
- Bloqueada por: US-1A-02-01-S1, US-1A-02-03 (PUT products — el importer lo reusa internamente para UPDATE), US-1A-02-08 (Celery setup), US-1A-01-09-S1 (supabase-py para storage de raw).
- Bloquea a: US-1A-02-09 (validación de perf con 5k SKUs reales), US-1A-04-03 cost importer (S3, mismo patrón).

#### Mocks / Wireframes
- Referencia: `ux-mockups-mt-pricing-mdm-phase1.md` Pantalla 10 (firmado UX requerido).
- Datos test: fixture sintético `tests/fixtures/pim_completo_synthetic_100rows.xlsx` (replica headers reales por sprint0 mapping).

#### Endpoints API afectados
- `POST /api/v1/imports` (multipart).
- `GET /api/v1/imports`.
- `GET /api/v1/imports/{run_id}`.
- `POST /api/v1/imports/{run_id}/apply`.
- `POST /api/v1/imports/{run_id}/cancel`.
- `GET /api/v1/imports/{run_id}/report`.

#### Modelos afectados
- `ImportRun`, `ImportRunRow` (nuevos).
- `Product` (writes — ya existe).

#### Observability
- Métricas: `imports.runs.duration_p95{type}`, `imports.runs.success/failure{type}`, `imports.rows.processed_per_sec`, `imports.rows.errors{error_code}`.
- Logs: `actor, action=import_pim_preview|apply, run_id, rows_processed, duration_ms`.
- Error scenarios: archivo corrupto → 422 + Sentry breadcrumb. Apply timeout (> 5 min para 5k rows) → Sentry warn + investigar query plan. Race condition (2 applies concurrentes) → bloqueado por advisory_lock + 409.

#### Definition of Ready (DoR) — checklist
- [ ] Mocks revisados con UX/Comercial (Pantalla 10 firmada).
- [ ] API contract acordado y mergeado.
- [ ] Modelo SQLAlchemy disponible.
- [ ] Permisos RBAC definidos (`comercial+` puede import PIM).
- [ ] Datos test disponibles (fixture sintético + ideal: PIM real Q-03).
- [ ] No tiene dependencias bloqueantes pendientes.
- [ ] Story points ≤ 8.
- [ ] Aceptación clara con BDD.
- [ ] Owner técnico identificado.

#### Definition of Done (DoD) — checklist
- [ ] Code review aprobado por 2 devs.
- [ ] Tests pasan (unit + integration + 1 E2E happy).
- [ ] Coverage ≥ 80 % en código nuevo (`app/importers/`, `app/services/import_service.py`, `app/worker/tasks/import_pim.py`).
- [ ] Lint + typecheck OK.
- [ ] Migración Alembic up + down testeada.
- [ ] Deploy a staging exitoso.
- [ ] Smoke test en staging por dev distinto al autor (subir fixture 100 rows → preview → apply → ver en /products → verificar audit_events count = 100).
- [ ] Audit event verificado.
- [ ] Documentación actualizada.
- [ ] PR mergeado a main.
- [ ] Sentry sin errores nuevos sustained.
- [ ] **Acceptance final**: si Q-03 destrabado, importar el PIM real (5086 rows) en staging y validar que la perf de apply queda < **10 min** (NFR-03 implícita).

#### Notas
Esta story es la "money story" del sprint. Si llega tarde, plan B es US-1A-06-06 (importer fixture Excel demo) — más simple, sin diff/apply, sólo carga directa con prefijo `stg_`. Riesgo principal: complejidad del differ con `manual_locked_fields` (ese campo NO existe aún en `products` en S1; agregarlo aquí o defer la lógica a S3 — ver Apéndice B).

**Decision punto en mid-sprint (día 5)**: si fixture sintético no funciona bien con headers PIM reales (Q-03 trae sorpresas), bajar scope:
- Quitar diff de `manual_locked_fields` → -2 SP.
- Quitar reporte CSV downloadable (sólo summary JSON en API) → -1 SP.
- Total reducible: 8 → 5 SP.

#### SP
**8**

#### Sprint asignado
S2.

#### Owner técnico (placeholder)
TBD (idealmente dev backend con experiencia openpyxl + Celery).

---

## 4. Resumen de SP del sprint

| Story | SP | Comentario |
|-------|----|------------|
| US-1A-02-03 | 3 | PUT/PATCH products |
| US-1A-02-04-S2 | 5 | UI tabs Imágenes + edit inline |
| US-1A-02-06 | 5 | Bucket `product-images` + signed URLs |
| US-1A-02-07 | 5 | Probe + mirror imágenes externas + SSRF guard |
| US-1A-02-08 | 3 | Thumbnails async via Celery |
| US-1A-02-09 | 3 | Filtros avanzados + full-text |
| US-1A-02-10 | 2 | Bloqueo DELETE físico |
| US-1A-03-01 | 2 | Schema `suppliers` + currencies seed mínimo |
| US-1A-03-02 | 3 | CRUD UI+API suppliers |
| US-1A-04-01 | 2 | Schemes seeded |
| US-1A-06-01 | 8 | Importer PIM (MUST) |
| **TOTAL** | **41 SP** | sobre target 32-40 |

> El total **41 SP** queda 1 SP arriba del techo de 40. Aceptable dado:
> 1. La sub-cadena de imágenes (US-1A-02-06/07/08) tiene mucho código compartido — el TOTAL real de esfuerzo es < suma de SP individuales.
> 2. US-1A-06-01 tiene plan de bajada in-flight a 5 SP si fixture sintético no llega.
> 3. Si capacidad real cierra en 28-32 SP, ver §6 para bajar 9-13 SP a S3.

## 5. Stories con dependencias críticas (bloqueos)

| Story | Bloqueada por (intra-S2) | Bloqueada por (externa) | Resolución antes de S2 start |
|-------|--------------------------|-------------------------|------------------------------|
| US-1A-02-03 | US-1A-02-02-S1 ✓, US-1A-07-01-S1 ✓ | — | Done en S1 |
| US-1A-02-04-S2 | US-1A-02-03, US-1A-02-06, US-1A-02-07, US-1A-02-08 | UX Pantalla 4 firmada | UX firma + ordering interno |
| US-1A-02-06 | US-1A-01-09-S1 ✓, US-1A-01-08-S1 ✓ | Supabase staging operativo | Pre-S2 (item §7) |
| US-1A-02-07 | US-1A-02-06 | ADR-047 SSRF policy firmado | Sprint mid (escribir ADR) |
| US-1A-02-08 | US-1A-02-06 | Worker container en docker-compose dev | Pre-S2 (item §7) |
| US-1A-02-09 | US-1A-02-02-S1 ✓, US-1A-06-01 | — | Ordering interno (al final del sprint) |
| US-1A-02-10 | US-1A-02-02-S1 ✓ | — | Trivial |
| US-1A-03-01 | US-1A-01-08-S1 ✓ | Confirmar adelanto seed currencies a S2 con arquitecto | Decisión kickoff |
| US-1A-03-02 | US-1A-03-01 | UX wireframe `/suppliers` (Apéndice B) | UX firma o decisión "reusar Pantalla 2 patrón" |
| US-1A-04-01 | US-1A-01-08-S1 ✓ | — | Trivial |
| US-1A-06-01 | US-1A-02-03, US-1A-02-08 | **Q-03 PIM real entregado** | TI MT (ver R-001) |

## 6. Stories candidatas a S3 si capacity insuficiente

Si capacidad real cierra en 28-32 SP (escenario probable si TI Integración no es FTE), bajar 9-13 SP a S3 en este orden:

1. **US-1A-02-09 (filtros avanzados)** — 3 SP. UI con sólo filtros básicos S1 funciona para demo si PIM no se carga del todo.
2. **US-1A-02-08 (thumbnails async)** — 3 SP. Las imágenes originales son visibles aunque pesadas; demo no se ve afectado. **Mitigación**: si bajamos esta, US-1A-02-04-S2 sirve `original` siempre — reducir scope.
3. **US-1A-04-01 (schemes seed)** — 2 SP. Sin master de schemes, EP-1A-04 no arranca; pero no bloquea S2. Diferir a inicio S3.
4. **US-1A-03-02 (CRUD UI suppliers)** — 3 SP. Si bajamos esta, suppliers se gestionan vía SQL directo en S3 hasta que UI llegue (Plan B aceptable, único usuario en S2).
5. **US-1A-02-10 (DELETE block)** — 2 SP. Hardening; defer a S3 sin riesgo en S2 (no hay DELETE attempts esperados).

**Plan B canónico (32 SP)**: bajar #1 + #2 + #3 → 41 - 8 = **33 SP**. Aceptable.

**Plan C agresivo (28 SP)**: Plan B + #4 → 33 - 3 = **30 SP**. Suppliers CRUD vía SQL directo. Suppliers UI llega S3 con la tabla Costes.

**Plan D extremo**: bajar US-1A-06-01 a US-1A-06-06 (importer fixture Excel demo, 5 SP) → 41 - 8 + 5 = **38 SP**. **Sólo si Q-03 sigue bloqueado al día 5**.

## 7. Tooling / setup pre-Sprint 2 (checklist dev lead)

Items pendientes del setup S1 + nuevos S2:

- [ ] **(Pendiente S1) Doppler proyectos `dev`/`staging`/`prod`** sembrados con: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SENTRY_DSN_BACKEND`, `SENTRY_DSN_FRONTEND`, `REDIS_URL`. Pendiente TI Integración (ver Reporte S1 §5).
- [ ] **(Pendiente S1) Supabase staging provisionado** — requerido para validar US-1A-01-05 + US-1A-01-09-S1 + US-1A-07-01-S1 hash chain end-to-end + smoke RLS.
- [ ] **(Pendiente S1) Sentry org + projects** (`mt-pricing-backend`, `mt-pricing-frontend`) — DSNs en Doppler.
- [ ] **(Pendiente S1) Hetzner box dev** confirmado provisionado (S0-D12).
- [ ] **(Nuevo S2) Bucket `product-images` creado en Supabase staging** con políticas básicas (lo crea US-1A-02-06; pero el proyecto Supabase con la feature Storage habilitada es prerequisito).
- [ ] **(Nuevo S2) Worker Celery en docker-compose.dev.yml** (lo configura US-1A-02-08; verificar que Redis ya esté en compose desde S1).
- [ ] **(Nuevo S2) Q-03 PIM real archivo confirmado** o fixture sintético `pim_completo_synthetic_5086rows.xlsx` generado a partir de `sprint0-pim-column-mapping.md`. **Owner: Champion + TI MT.**
- [ ] **(Nuevo S2) UX firma Pantalla 4 (Imágenes) y Pantalla 10 (Importer wizard)** — sin firma, US-1A-02-04-S2 y US-1A-06-01 pasan a draft state.
- [ ] **(Nuevo S2) Decisión UX wireframe `/suppliers`** — sin pantalla específica en mockups; ver Apéndice B.
- [ ] **(Nuevo S2) ADR-047 (SSRF policy probe imágenes)** redactado — borrador en US-1A-02-07.
- [ ] **(Nuevo S2) Hardening backlog ticket** creado con los 18 typecheck errors Wave 1/2 + migración `next lint` → `eslint` (carry-over Reporte S1 §5 items 6 y 7). NO entra en S2 backlog formal pero limpiarlo en buffer time.
- [ ] **(Nuevo S2) Decidir naming env var** `NEXT_PUBLIC_API_URL` vs `NEXT_PUBLIC_BACKEND_URL` (carry-over Reporte S1 §5 item 9).
- [ ] **(Nuevo S2) Implementar `audit_partitions_ensure` Celery task** (carry-over Reporte S1 §5 item 10) — particiones audit_events sólo cubren may/jun 2026; falta tarea Celery beat.
- [ ] **(Nuevo S2) Confirmar versión Python (3.11 vs 3.12)** — carry-over Reporte S1 §5 item 8.

## 8. Riesgos del sprint

| ID | Riesgo | Severidad | Probabilidad | Mitigación |
|----|--------|-----------|--------------|------------|
| R-S2-01 | Q-03 PIM real no entregado al día 5 → US-1A-06-01 sin archivo real | Alta | Media | Plan D §6: switch a US-1A-06-06 (importer fixture Excel demo, 5 SP). Champion escala a TI MT en kickoff. Develop contra fixture sintético hasta entonces. (R-001 register) |
| R-S2-02 | SSRF en Probe + Mirror — URL maliciosa accede a redes internas Hetzner | Alta | Media | US-1A-02-07 implementa validador SSRF con denylist canónica + DNS pre-resolve + HTTPS-only. ADR-047 obligatorio antes de merge. Tests con vectores conocidos (R-022 register). |
| R-S2-03 | Q-09 image rights MT España no firmado → mirror legalmente expuesto | Media | Alta | Ya en R-044 register. US-1A-02-07 conserva `image_origin_url` siempre. Feature flag `ALLOW_PROBE_FROM_PIM_ES` que pueda desactivarse. **Mitigación operativa**: NO lanzar probe en bulk hasta que Q-09 firmado. |
| R-S2-04 | Celery setup en docker-compose dev no se reproduce en Hetzner staging | Media | Media | Worker en docker-compose.prod.yml también; US-1A-02-08 incluye healthcheck `celery inspect ping`. Smoke test en staging incluye job thumbnails completándose. |
| R-S2-05 | Apply de PIM 5086 rows excede 10 min wall-clock | Media | Media | Chunked savepoints cada 1000 rows. Si excede, paralelizar por familia con worker fan-out. Si aún así excede, NO bloquea S2 (sólo NFR warn). NFR-03 declara target. |
| R-S2-06 | Conflicto `manual_locked_fields` no existe en products S1 → importer differ inválido | Media | Alta | Apéndice B propone aclaración: agregar columna en migración 0007 o defer la lógica a S3. Decisión: **agregar columna `manual_locked_fields TEXT[]` en migración importer y dejar siempre vacía en S2** (la lógica de marcado UI llega en S3). |
| R-S2-07 | Capacidad real < 32 SP si TI Integración no es FTE | Alta | Alta | Q-05 (R-049 register) sigue abierto. Aplicar §6 plan B (33 SP) o C (30 SP). |
| R-S2-08 | Particiones audit_events agotadas en julio 2026 | Media | Baja | Carry-over Reporte S1; añadir `audit_partitions_ensure` Celery beat task — incluir en buffer S2 (no es story formal, ~1 día efectivo). |
| R-S2-09 | Pillow + WebP encoder rompen en Linux musl (alpine) container | Baja | Media | Usar `python:3.11-slim` (Debian) base — alpine causa issues con libwebp/libjpeg. Documentar en Dockerfile worker. |
| R-S2-10 | Doppler aún no sembrado al kickoff S2 | Media | Media | Aceptable arrancar con secrets locales `.env.local`; Doppler sólo crítico para apply en staging. Recordatorio TI Integración día 1. |

## 9. Métricas a trackear durante el sprint

- **Velocity real** (SP done) vs estimado (41 SP target / 32 SP realista).
- **Burn-down chart** diario.
- **Stories estado**: backlog → in-progress → in-review → done. Alerta si una story queda > 3 días en in-review.
- **Defect ratio**: bugs detectados (Sentry crit + critical PR comments) / stories cerradas.
- **Coverage delta**: line coverage antes vs después del sprint (target: mantener ≥ 80 % en código nuevo).
- **CI build time** p50/p95.
- **Importer test corpus**: ejecuciones sobre fixture 100 / 1k / 5086 (target final). Latencia p95 de apply.
- **Storage volume**: bytes en bucket `product-images` (proyectar costo Supabase).
- **Thumbnails generation lag**: tiempo entre upload y `thumbnails_status='done'` p95 (target: < 30 s).
- **Q-03 status**: días desde decisión pendiente.
- **Q-09 status**: días desde decisión pendiente.
- **Sprint goal viability**: cada miércoles, demo informal flujo end-to-end (importer → list → edit → image probe). Si rompe, alarma.

## 10. Sprint 3 preview (alto nivel)

Stories candidatas (con racional):

| Story | SP | Racional |
|-------|----|----------|
| US-1A-04-02 (`costs` schema + FX as-of trigger) | 5 | Necesita `fx_rates` (US-1A-05-02) en mismo sprint |
| US-1A-04-03 (`POST /costs` endpoint) | 5 | Depende de US-1A-04-02 |
| US-1A-04-04 (UI tab Costes) | 5 | Cierra ficha SKU |
| US-1A-05-01 (currencies seed completo + admin) | 2 | Si sólo se hizo seed minimal en S2, completar |
| US-1A-05-02 (`fx_rates` con cierre auto `effective_to`) | 5 | Bloqueante de US-1A-04-02 |
| US-1A-05-03 (`POST /fx-rates` + admin UI) | 3 | TI puede registrar tasas |
| US-1A-02-05 (`product_translations`) | 5 | Habilita tab Traducciones |
| US-1A-06-02 (importer costs) | 8 | Carga master de costes |
| US-1A-06-03 (importer compatibilidades materiales) | 5 | Tabla referencial Fase 2 |
| US-1A-06-07 (reporte cross-validation PIM ↔ costos) | 5 | Entregable cierre S3 |
| US-1A-07-02 (RLS policies finas) | 5 | Defense-in-depth nivel 2 |
| (carry-over) US-1A-02-09, 02-10, 03-02, 04-01 si bajan de S2 | 0-13 | Plan B/C |

**Total candidatos S3**: ~53 SP (aplicar selección a 32-40 SP realistas).

**S3 stretch goals**: traer las stories que bajaron de S2 (Plan B/C); empezar US-1A-02-04-S3 (tab Costes una vez que US-1A-04-04 quede listo).

**S3 MUST**: US-1A-04-02 + US-1A-05-02 (FX engine operativo) — sin esto, costs no pueden persistir, bloquea EP-1A-04 entero.

---

## Apéndice A — Mapeo de stories del doc fuente vs stories S2

| Doc fuente (epics-and-stories v1.1) | Sprint asignado original | S2 backlog refinado | Cambio |
|-------------------------------------|--------------------------|---------------------|--------|
| US-1A-02-03 (PUT/PATCH products) | S1 | US-1A-02-03 (S2) | Slip por capacity S1 |
| US-1A-02-04 (UI tabs ficha) | S1 | US-1A-02-04-S2 (S2, scoped) | S1 hizo tab "Ficha técnica" read-only; S2 agrega edit + Imágenes; tabs Costes/Precios/Traducciones/Auditoría → S3 |
| US-1A-02-06 (bucket product-images) | S1 | US-1A-02-06 (S2) | Slip |
| US-1A-02-07 (probe+mirror) | S1 | US-1A-02-07 (S2) | Slip + scope expandido (SSRF guard explícito) |
| US-1A-02-08 (thumbnails async) | S1 | US-1A-02-08 (S2) | Slip |
| US-1A-02-09 (filtros + full-text) | S1 | US-1A-02-09 (S2) | S1 hizo filtros básicos; S2 expande |
| US-1A-02-10 (bloqueo DELETE) | S1 | US-1A-02-10 (S2) | Slip |
| US-1A-03-01 (suppliers schema) | S2 | US-1A-03-01 (S2, +seed currencies) | Aclaración: incluye seed mínimo currencies (originalmente dependía de US-1A-05-01 S3) |
| US-1A-03-02 (CRUD suppliers) | S2 | US-1A-03-02 (S2) | Sin cambios; UX wireframe ad-hoc |
| US-1A-04-01 (schemes seed) | S2 | US-1A-04-01 (S2) | Sin cambios |
| US-1A-06-01 (importer PIM) | S1 | US-1A-06-01 (S2) | Slip — MUST de S2 |
| US-1A-06-06 (importer fixture demo) | S1 | — (queda como Plan D fallback) | NO incluida formalmente; descrita en §6 plan D |
| US-1A-02-05 (translations) | S1 | — (defer S3) | Defer |

## Apéndice B — TODOs / cosas dudadas

1. **UX wireframe `/suppliers` no existe en mockups firmados**: Pantallas 1-27 cubren pricing/products/audit/login, pero NO hay pantalla dedicada a maestro de proveedores. **Propuesta**: reusar patrón de Pantalla 2 (DataTable + filter) + form modal estilo Pantalla 9. Aclaración requerida con UX/Sally antes de iniciar US-1A-03-02. Si UX se demora, aplicar `bmad-create-ux-design` para una pantalla mínima en buffer pre-S2.

2. **`manual_locked_fields` no existe en `products` schema S1**: la lógica de "respect manual lock" en US-1A-06-01 differ asume el campo. Decisión propuesta: **agregar columna `manual_locked_fields TEXT[] DEFAULT '{}'` en migración 0007 (importer)** y dejar la lógica de UI/marking para S3. Confirmar con arquitecto.

3. **Seed `currencies` adelantado de S3 a S2**: doc fuente declara dependencia US-1A-03-01 ← US-1A-05-01 (S3). Se rompe agregando el seed mínimo (4 filas, sin lógica de FX) en S2. **Aclaración requerida**: actualizar `epics-and-stories-mt-pricing-mdm-phase1.md` US-1A-03-01 dependencia a "currencies table existe (seed mínimo, S2)" y US-1A-05-01 a "currencies admin UI + RBAC + audit (S3)".

4. **TTL signed URL imágenes**: ADR-033 dice 24 h. ¿Sigue válido? Confirmar con seguridad MT antes de merge US-1A-02-06. Algunas industrias prefieren 1 h. Si cambia → impact análisis trivial (rotar TTL en `image_service.get_signed_url`).

5. **Probe en bulk vs lazy**: ¿después del importer PIM, debe disparar `probe_and_mirror` para cada SKU con `image_url_pim` no null automáticamente, o esperar a click manual del Comercial en UI? **Decisión propuesta**: lazy en S2 (manual). En S3, evaluar si añadir `import_options.auto_probe=true` checkbox en wizard. Confirmar con Champion.

6. **Importer apply mid-flight: chunked savepoints vs single tx**: arquitectura §16.2 dice "Begin transaction (or chunked savepoints if rows > 5000)". Para 5086 rows estamos en frontera — decidir: siempre chunked (más complejo pero seguro) o siempre single tx (peligroso si DB connection drop). **Propuesta**: chunked siempre, threshold 1000 rows por chunk. Confirmar con arquitecto.

7. **Storage policy para thumbnails bucket**: ¿reusamos `product-images` con prefijo `thumbnails/` o creamos bucket separado? Arquitectura §6 (línea 274) lista solo `product-images`, sugiriendo prefijo. Confirmar.

8. **¿`pg_advisory_lock` por tipo o global?**: §16.2 sugiere `pg_advisory_lock(hash('import:pim'))`. Si Comercial corre PIM mientras TI corre Excel demo, ¿deben bloquearse mutuamente? Propuesta: locks separados por type (ya escrito así). Confirmar.

9. **R-S2-09 Pillow/WebP en alpine**: el carry-over Reporte S1 §5 item Python 3.11 vs 3.12 puede afectar también la base image. Decidir consistentemente (probably `python:3.11-slim-bookworm` para todo).

10. **Estado real Q-03 PIM al kickoff S2**: si Champion confirma que el archivo no llega antes del día 5, considerar arrancar US-1A-06-06 (importer fixture) en paralelo con US-1A-06-01 contra fixture sintético, y switch al final.

11. **Tarea Celery `audit_partitions_ensure` (carry-over Reporte S1 §5 item 10)**: las particiones de `audit_events` sólo cubren may/jun 2026. Si no se ejecuta job, julio 2026 los inserts fallarán. **NO está en S2 backlog formal**. Recomendación: agregar como story 1-SP US-1A-07-01-S2 si capacidad permite, o resolver en buffer time.

12. **Hardening typecheck Wave 1/2 (carry-over Reporte S1 §5 items 6-7)**: 18 errors + migración `next lint` → `eslint .` directo. NO en S2 backlog formal. Crear ticket de mantenimiento para ejecutar en buffer time.

13. **Métricas Hetzner cost projection**: con 5 086 SKUs × imagen original promedio 200 KB + 3 thumbnails × 30 KB cada uno = ~1.5 GB en bucket `product-images`. Supabase free tier es 1 GB. **Acción**: confirmar tier `pro` en Supabase staging antes de US-1A-02-08, o monitorear y planear upgrade.

