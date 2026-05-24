# Plan de Pruebas — Piloto F1, proceso CAT (catálogo de productos)

> **Encaje.** Aplicación concreta de la [[Estrategia_Pruebas_Validacion_SpecKit_ES|Estrategia de Pruebas y Validación]] al proceso piloto. Acompaña al [[F1-CAT_Control_Piloto|control del piloto F1-CAT]] y al prompt de verificación (`MT-ME\_INBOX\Prompt_ClaudeCode_F1_CAT_Piloto_ES.md`). La automatización de estas pruebas se encarga vía `MT-ME\_INBOX\Prompt_ClaudeCode_F1_CAT_Pruebas_ES.md`.

- **Proceso:** Gestión del catálogo de productos (dominio **CAT**) — la ficha de producto
  canónica: alta, consulta, búsqueda/listado, edición, clasificación, baja (14 endpoints).
- **Fecha:** 2026-05-24 · **Estado:** 🟡 Pendiente de ejecución.

---

## 1. Cómo se prueba el proceso CAT, capa por capa

| Capa | Qué prueba en CAT | Herramienta | Marcador / ubicación |
|------|-------------------|-------------|----------------------|
| 1 — Desarrollo | Lógica de `ProductService`, repositorio, schemas, modelo | pytest / vitest | `unit`, `integration` |
| 2 — e2e | Journeys: listar catálogo, abrir ficha, editar, dar de alta | Playwright | `tests/e2e/0X-*.spec.ts` |
| 3 — Proceso | Cada `FR-CAT-NNN` ↔ test anclado a su ID | pytest | `acceptance` · `test_cat_acceptance.py` |
| 4 — Dato real | Calidad del catálogo en producción | `GET /admin/pim/data-quality` | instantánea archivada |

## 2. Cobertura actual por área de requisito

Mapa de las 13 áreas del proceso (ver [[F1-CAT_Control_Piloto]] §2) contra los tests que
**ya existen** en el repo. La columna *Brecha* es lo que el piloto debe cerrar.

| Área | Capacidad | Tests existentes | Capa | Brecha |
|------|-----------|------------------|:----:|--------|
| A1 | Alta de producto | `db/test_products_model.py`, `unit/schemas/test_products_wave2.py` | 1 | Falta test `api` happy/unhappy de `POST /products` |
| A2 | Consulta por SKU | `integration/test_products.py` (parcial) | 1 | Falta caso 404; verificar N+1 (BMAD **E-2**) |
| A3 | Ficha resuelta (fallback al padre) | — | — | Sin cobertura |
| A4 | Listado + filtros | `api/test_products_cursor.py`, `api/test_products_filters.py`, `unit/repositories/test_product_repo_stage3_filters.py` | 1 | Buena base; faltan combinaciones de filtros |
| A5 | Búsqueda rápida | — | — | Sin cobertura |
| A6 | Facetas | — | — | Sin cobertura |
| A7 | Edición parcial (`PATCH`) | `api/test_products_put_patch.py` | 1 | Verificar respeto a `manual_locked_fields` |
| A8 | Reemplazo (`PUT`, optimistic locking) | `api/test_products_put_patch.py`, `db/test_products_lock.py` | 1 | Buena base; falta caso `If-Match` en conflicto (412) |
| A9 | Calidad de dato (`PATCH .../data-quality`) | — | — | Sin cobertura |
| A10 | Baja lógica (`DELETE`) | — | — | Sin cobertura; verificar exclusión de listados |
| A11 | Clasificación PVF | `unit/services/products/` (revisar) | 1 | Falta test `api` de `POST /classify` |
| A12 | Jerarquía de variantes (`parent`) | `unit/db/models/test_product_model_fk.py` | 1 | Falta test de ciclos / profundidad |
| A13 | Transversales (RBAC, RFC 7807, audit, export, schema) | `unit/api/test_products_api_stage3.py` (parcial) | 1 | Falta matriz de permisos; export CSV sin test |

**Frontend e2e (Capa 2) ya disponible:** `03-products-list`, `04-product-detail-edit`,
`08-filtros-avanzados`, `10-catalog-filters-nuqs`. Cubren A4 y parte de A2/A7; faltan
journeys de alta (A1) y baja (A10).

## 3. Objetivos de cobertura del piloto

- **Cada uno de los 14 endpoints en alcance** tiene ≥ 1 caso *happy* y ≥ 1 *unhappy*.
- **Cada FR-CAT P1/P2** tiene un test de proceso (Capa 3) anclado a su ID.
- La cobertura del módulo respeta el gate **≥ 70 %** y no lo baja.
- Los *journeys* P1 (listar, abrir ficha, editar, alta) tienen spec de Playwright.
- Estado objetivo: 0 áreas en "Sin cobertura".

## 4. Casos de prueba ejemplo

Ilustran cómo un escenario Given/When/Then de la spec se vuelve un test anclado al FR.

**A8 · Optimistic locking** — `PUT /products/{sku}` con `If-Match`
> *Given* una ficha con ETag `v1`, *When* dos clientes la reemplazan y el segundo envía
> `If-Match: v1` ya obsoleto, *Then* el segundo recibe `412 Precondition Failed`.
> → `test_cat_acceptance.py::test_put_product_stale_etag_returns_412` *(api)*

**A2 · Consulta inexistente** — `GET /products/{sku}`
> *Given* un SKU que no existe, *When* se consulta su ficha, *Then* respuesta `404` con
> cuerpo `ProblemDetails` (RFC 7807).
> → `test_cat_acceptance.py::test_get_product_unknown_sku_returns_404_problemdetails` *(api)*

**A10 · Baja lógica** — `DELETE /products/{sku}`
> *Given* un producto activo, *When* se elimina, *Then* `active=false` y `deleted_at`
> poblado, *And* el SKU **no** aparece en `GET /products`.
> → `test_cat_acceptance.py::test_delete_product_soft_deletes_and_hides_from_list` *(api)*

**A7 · Campos bloqueados** — `PATCH /products/{sku}`
> *Given* una ficha con `manual_locked_fields=["brand"]`, *When* un `PATCH` intenta
> cambiar `brand`, *Then* el cambio se rechaza o se ignora según la regla, sin tocar
> otros campos.
> → `test_cat_acceptance.py::test_patch_respects_manual_locked_fields` *(api)*

**A4 · Journey de listado** *(Capa 2)*
> *Given* un catálogo con productos de varias familias, *When* el usuario filtra por
> familia y pagina, *Then* la grilla muestra solo esa familia y el cursor avanza.
> → ampliar `tests/e2e/03-products-list.spec.ts` / `08-filtros-avanzados.spec.ts`

## 5. Capa 4 — validación de la calidad del dato del catálogo CAT

El piloto establece la **línea base** del catálogo real y propone umbrales.

1. Ejecutar `GET /admin/pim/data-quality` (permiso `admin:read`) contra la base real.
2. Registrar la línea base: `% missing_name_en`, `% missing_specs`, `% missing_images`,
   `% missing_brand`, `% specs_below_threshold`, y el reparto de `data_quality`
   (`complete` / `partial` / `blocked` / `migrated_demo`).
3. Proponer umbrales CAT para ratificar con el equipo (valores iniciales sugeridos):

   | Métrica | Umbral propuesto |
   |---------|------------------|
   | `migrated_demo` | **0 %** en producción real |
   | `missing_specs` | ≤ 5 % |
   | `missing_name_en` | ≤ 2 % |
   | `missing_images` | ≤ 15 % |
   | `specs_below_threshold` | ≤ 10 % |

4. Archivar la instantánea en `MT-ME\F1-Control\calidad-dato\2026-05-DD.md` y repetir con
   el job programado (recomendación R-A3 de la estrategia).

> La calidad del dato **no bloquea** un merge; es una señal de salud del catálogo que se
> revisa por tendencia, no por foto puntual.

## 6. Brechas conocidas heredadas (auditoría BMAD)

La auditoría `_bmad-output/analysis/products-module/` (2026-05-20) ya catalogó deuda del
módulo. Las que tocan el proceso piloto — **no se corrigen en F1, se cruzan**:

- **A-1** — 62 % de endpoints del módulo sin test. Es la brecha que este plan ataca.
- **E-2** — `_build_product_detail` hace +3 round-trips por `GET /products/{sku}` (A2).
- **E-4** — `selectinload` sobre relación many-to-one `Product.model` (debería `joinedload`).
- **F-2 / F-4** — lógica de negocio en handlers de `products.py`; `_parse_iso` duplicado.
- **B-1** — el tab `edit` del detalle falla en silencio ante error de red (journey A7).

Cuando un test de proceso destape una de estas brechas, cita el ID BMAD en la columna
`Brecha/Notas` de la matriz y en el `verification.md`.

## 7. Dónde se registra lo probado

- **Tests** → `mt-pricing-backend/tests/.../test_cat_acceptance.py` (marcador `acceptance`)
  y specs Playwright en `mt-pricing-frontend/tests/e2e/`.
- **Estado por FR** → `specs/001-cat-.../traceability-cat.csv`, columnas
  `Prueba(s) automatizada(s)` y `Estado de prueba`; volcado a la matriz maestra.
- **Detalle de verificación** → `specs/001-cat-.../verification.md`.
- **Calidad de dato** → `MT-ME\F1-Control\calidad-dato\YYYY-MM-DD.md`.
- **Revisión sin leer código** → checks de CI en el PR + la matriz (ver
  [[Estrategia_Pruebas_Validacion_SpecKit_ES]] §6).

## 8. Notas

> **NOTA 1.** Este plan asume el alcance del proceso piloto definido en
> [[F1-CAT_Control_Piloto]] §3. Si la cola F1 del documento F0 acota CAT de otro modo,
> ajustar las áreas A1–A13.

> **NOTA 2.** Los tests de proceso de la Capa 3 que destapen un defecto nacen en `xfail`
> con el enlace a la issue; pasan a verde cuando la corrección se entrega (fuera de F1).

> **NOTA 3.** Activar Playwright como gate bloqueante para los journeys P1 de CAT en
> cuanto sus specs e2e sean estables (recomendación R-A1 de la estrategia).
