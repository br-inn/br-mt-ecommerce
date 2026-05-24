# Plan as-built (retrospectivo): Gestión del catálogo de productos (CAT)

**Branch**: `001-cat-gestion-catalogo-productos` | **Fecha**: 2026-05-24 | **Spec**: [spec.md](./spec.md)

> ⚠️ **PLAN AS-BUILT / RETROSPECTIVO** — Este plan NO diseña implementación nueva.
> Documenta la arquitectura EXISTENTE del proceso CAT para soporte de la verificación
> F1. Stack, módulos y decisiones ya están fijados por la constitución del proyecto y
> por el código en producción. No ejecutar `/speckit-tasks` ni `/speckit-implement`.

---

## Resumen

El proceso CAT gestiona el ciclo de vida completo de la ficha de producto en el PIM
interno de MT Middle East: creación, consulta, edición, baja lógica, búsqueda, facetas,
jerarquía de variantes, clasificación masiva, exportación y esquemas de validación.
El stack y la arquitectura están fijados por la Constitución (Art. 1).

---

## Contexto técnico

**Lenguaje/Versión**: Python 3.11

**Dependencias primarias**: FastAPI + SQLAlchemy 2.0 async + Pydantic + Celery + Redis

**Almacenamiento**: PostgreSQL (Supabase, esquema `public.*`, ORM Alembic)

**Testing**: pytest (integración) — cobertura actual: 62 % endpoints (ver hallazgo A-1 auditoría BMAD)

**Plataforma destino**: Linux / AWS EC2 + Docker Compose (backend)

**Tipo de proyecto**: API REST interna (PIM backend)

**Objetivos de performance**:
- Listados paginados: no definido SLA explícito (CLAUDE.md: no N+1)
- Facetas: p95 < 200 ms con 5 000–50 000 productos (SC-009)
- Búsqueda rápida: < 500 ms con 5 000+ productos (SC-004)

**Restricciones**: cursor-based pagination obligatorio; `include_total=False` por defecto;
sin `Cache-Control` manual excepto override en export; `manual_locked_fields` respetado
por PVF y PATCH.

**Escala/Alcance**: 224 SKUs actuales → 50 000 SKUs objetivo Fase 2+.

---

## Constitution Check

| Artículo | Estado | Notas |
|----------|--------|-------|
| Art. 1 — Stack obligatorio | ✅ Alineado | FastAPI + SQLAlchemy + Supabase |
| Art. 2 — Migraciones | ✅ Alineado | Alembic para `public.*` |
| Art. 3 — Rendimiento backend | ⚠️ Parcial | `_build_product_detail` tiene N+1 (hallazgo E-2 BMAD; no corregir en F1) |
| Art. 4 — Rendimiento frontend | N/A | Esta spec cubre solo el backend API |
| Art. 5 — LLM/Anthropic | N/A | No hay llamadas LLM en el proceso CAT |
| Art. 6 — Esquema de IDs | ✅ Alineado | FR-CAT-NNN, NFR-CAT-NNN, BR-CAT-NNN |
| Art. 7 — Definición de Listo | ✅ Aplicado | Spec sin `[NEEDS CLARIFICATION]`; criterios verificables |

---

## Estructura del proyecto (as-built)

### Documentación de esta spec

```text
specs/001-cat-gestion-catalogo-productos/
├── plan.md                    # Este archivo
├── spec.md                    # Spec retrospectiva (FR-CAT-001..FR-CAT-037)
├── verification.md            # Verificación de conformidad F1 (Paso 5)
├── traceability-cat.csv       # Matriz de trazabilidad F1 (Paso 6)
└── checklists/
    └── requirements.md        # Checklist de calidad del spec
```

### Código fuente existente (rutas relativas al repo)

```text
mt-pricing-backend/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   └── products.py              # 2 378 líneas — 14 endpoints en alcance CAT
│   │   └── pagination.py                # Cursor encode/decode
│   ├── db/
│   │   └── models/
│   │       └── product.py               # 852 líneas — Product, ProductTranslation, ProductAsset
│   ├── repositories/
│   │   └── product.py                   # Repositorio de productos
│   ├── schemas/
│   │   ├── products.py                  # ProductCreate, ProductPatch, ProductReplace, etc.
│   │   └── facets.py                    # FacetsResponse, ProductFilters
│   └── services/
│       └── products/
│           ├── product_service.py        # 35 KB — lógica de negocio principal
│           ├── facets_service.py         # compute_facets + ProductFilters
│           ├── parent_resolver.py        # Jerarquía de variantes, ciclos, profundidad
│           └── pvf_classifier.py         # Clasificador PVF rule-based
│   └── specs/
│       ├── specs_registry.py            # Singleton con JSON Schemas por familia
│       └── specs_validator.py           # Validación de specs contra schema

mt-pricing-frontend/
└── app/(app)/catalogo/                  # Listado, detalle, wizard de alta (fuera de alcance F1 API)
```

---

## Decisiones de arquitectura existentes relevantes para F1

| Decisión | Descripción | Impacto en verificación |
|----------|-------------|------------------------|
| SKU como PK texto | `products.sku` TEXT PRIMARY KEY; `internal_id` UUID auxiliar | FR-CAT-001, BR-CAT-002 |
| Cursor-based pagination | Cursor opaco = base64url(json({"sku": "..."})) | FR-CAT-011 |
| Soft-delete via `lifecycle_status='discontinued'` + `deleted_at` | No hard-delete expuesto en API | FR-CAT-027, BR-CAT-003 |
| `manual_locked_fields` ARRAY(Text) | PVF y PATCH respetan el array | FR-CAT-019, FR-CAT-031, BR-CAT-004 |
| Profundidad máxima de variantes = 1 | `ParentResolver.validate_parent_link` rechaza profundidad > 1 | FR-CAT-033, BR-CAT-005 |
| `name_en` como `hybrid_property` read-only | Columna eliminada en mig 065; escritura via translations | BR-CAT-001 |
| `_DATA_QUALITY_REQUIRED_FIELDS` = 4 campos físicos | `family`, `material`, `dn`, `pn` — verificación name_en pendiente | FR-CAT-025, FR-CAT-031 |
| `CacheControlMiddleware` global | `private, max-age=60` en todos los GET 200; export sobreescribe con `no-store` | NFR-CAT-004 |
| Auditoría desde la capa de servicio | No desde handlers de API | NFR-CAT-003 |

---

## Notas de ejecución F1

- **NO ejecutar** `/speckit-tasks` ni `/speckit-implement` — F1 es solo verificación.
- El siguiente paso es crear `verification.md` (Paso 5) y `traceability-cat.csv` (Paso 6).
- Las brechas encontradas en `verification.md` se convierten en issues/historias futuras, no en correcciones en F1.
- La violación de Art. 3 (N+1 en `_build_product_detail`) ya está catalogada como E-2 en la auditoría BMAD; se referenciará en `verification.md` sin corrección en F1.
