# Plan as-built (retrospectivo): Traducciones de Producto (CAT — sub-recurso)

**Branch**: `docs/f1-traducciones-producto` | **Fecha**: 2026-05-25 | **Spec**: [spec.md](./spec.md)

> **PLAN AS-BUILT / RETROSPECTIVO** — Este plan NO diseña implementación nueva.
> Documenta la arquitectura EXISTENTE del sub-recurso Traducciones de Producto para
> soporte de la verificacion F1. Stack, modulos y decisiones ya estan fijados.
> No ejecutar `/speckit-tasks` ni `/speckit-implement`.

---

## Resumen

El sub-recurso TRD gestiona las traducciones de producto en el PIM de MT Middle East.
Ofrece CRUD basico (GET lista, PUT upsert, PATCH parcial, POST approve clasico) en
`products.py`, un workflow de aprobacion four-eyes S3 (request-review, reject,
mark-stale) en `translations_workflow.py`, y endpoints de cobertura + completion AI
en `translations.py`. El modelo de datos central es `product_translations` con PK
compuesto `(sku, lang)`.

---

## Contexto tecnico

**Lenguaje/Version**: Python 3.11

**Dependencias primarias**: FastAPI + SQLAlchemy 2.0 async + Pydantic + Anthropic SDK
(solo para completion AI)

**Almacenamiento**: PostgreSQL (esquema `public.product_translations`,
ORM Alembic). Sin cache de traducciones en Redis.

**Testing**: pytest (unit sin DB — todos los tests de traducciones son unit);
cobertura de endpoints: 100 % de los endpoints de traducciones tienen al menos
un test unitario.

**Plataforma destino**: Linux / AWS EC2 + Docker Compose (backend)

**Tipo de proyecto**: Sub-recurso REST del API PIM interno

---

## Constitution Check

| Articulo | Estado | Notas |
|----------|--------|-------|
| Art. 1 — Stack obligatorio | Alineado | FastAPI + SQLAlchemy + Supabase |
| Art. 2 — Migraciones | Alineado | `product_translations` gestionado por Alembic |
| Art. 3 — Rendimiento backend | Parcial | GET list usa `get_for_sku` (1 query SELECT); upsert atomico. BRECHA: `approve_translation` hace `session.refresh()` extra (round-trip adicional). `_raise_domain` en `translations_workflow.py` omite `type`/`instance` RFC 7807 |
| Art. 4 — Rendimiento frontend | N/A | Solo backend API |
| Art. 5 — LLM/Anthropic | Parcial | `TranslationCompletionService` usa Claude; los system prompts son cortos (< 2048 tokens segun CLAUDE.md directriz 9) — no aplica cache_control por ahora |
| Art. 6 — Esquema de IDs | Alineado | FR-TRD-NNN, NFR-TRD-NNN, BR-TRD-NNN |
| Art. 7 — Definicion de Listo | Aplicado | Spec sin `[NEEDS CLARIFICATION]`; brechas registradas |

---

## Estructura del proyecto (as-built)

### Documentacion de esta spec

```text
specs/002-cat-traducciones-producto/
├── plan.md                    # Este archivo
├── spec.md                    # Spec retrospectiva (FR-TRD-001..014, NFR-TRD-001..006, BR-TRD-001..006)
├── verification.md            # Verificacion de conformidad F1
├── traceability-cat.csv       # Matriz de trazabilidad F1
└── checklists/
    └── requirements.md        # Checklist de calidad del spec
```

### Codigo fuente existente (rutas relativas al repo)

```text
mt-pricing-backend/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── products.py              # Endpoints CRUD + approve clasico (lineas 939-1019)
│   │   │   ├── translations_workflow.py # Endpoints workflow S3 (request-review, reject, mark-stale)
│   │   │   └── translations.py          # Endpoints coverage + AI completion
│   ├── db/
│   │   ├── models/
│   │   │   └── product.py               # ProductTranslation model (lineas 476-523)
│   │   └── enums.py                     # TranslationStatus enum (lineas 57-64)
│   ├── repositories/
│   │   └── product.py                   # ProductTranslationRepository (lineas 469-524)
│   ├── schemas/
│   │   ├── products.py                  # ProductTranslationBase/Create/Patch/Response (lineas 537-604)
│   │   └── translations_workflow.py     # TranslationWorkflowResponse, TranslationRejectRequest, etc.
│   └── services/
│       ├── products/
│       │   ├── product_service.py       # ProductService.list/upsert/update/approve_translation (lineas 754-843)
│       │   ├── translation_workflow.py  # TranslationWorkflowService + FSM + errores de dominio
│       │   └── translation_audit.py     # TranslationAuditEmitter + audit actions canonicas
│       └── translations/
│           └── completion_service.py    # TranslationCompletionService (AI via Claude)

mt-pricing-backend/tests/
├── unit/
│   ├── api/
│   │   ├── test_translations_api.py           # Tests endpoint coverage + complete
│   │   └── test_translations_workflow_api.py  # Tests endpoints workflow S3
│   └── services/
│       └── products/
│           ├── test_translation_workflow.py   # Tests FSM + service
│           └── test_translation_audit.py      # Tests audit emitter
```

---

## Decisiones de arquitectura existentes relevantes para F1

| Decision | Descripcion | Impacto en verificacion |
|----------|-------------|------------------------|
| PK compuesto `(sku, lang)` | No hay ID UUID propio; las traducciones se identifican por `sku:lang` | FR-TRD-002, FR-TRD-004 |
| Upsert atomico con `INSERT ON CONFLICT DO UPDATE` | Evita condicion de carrera bajo concurrencia | NFR-TRD-005, FR-TRD-004 |
| `lang` restringido a `es\|ar` en endpoints CRUD | El master EN solo es modificable via `ProductService._extract_en_translation_payload` | NFR-TRD-006, BR-TRD-001 |
| Dos rutas de aprovacion coexistentes | `products.py:approve_translation` (sin four-eyes) y `TranslationWorkflowService.approve` (con four-eyes) | BRECHA-TRD-01 |
| `_raise_domain` con shape diferente en cada router | `products.py` incluye `type`/`status`/`instance`; `translations_workflow.py` solo `code`/`title` | BRECHA-TRD-02 |
| Completion service acepta 7 idiomas | `en`, `es`, `fr`, `de`, `it`, `pt`, `ar` — mas que el CRUD (solo es/ar) | FR-TRD-014 |
| `TranslationAuditEmitter` con validacion de acciones canonicas | `ValueError` si la action no pertenece al set canonico — defensa contra typos | NFR-TRD-003 |
| `approve_translation` clasico usa `session.refresh()` | Evita `MissingGreenlet` en columnas con `onupdate` server-side | BRECHA-TRD-03 |
| Estado `stale` en `TranslationStatus` enum pero no en schemas CRUD | `schemas/products.py:553` solo expone `pending\|draft\|approved` — los clientes CRUD no pueden setear `stale` directamente | BR-TRD-002 |

---

## Notas de ejecucion F1

- **NO ejecutar** `/speckit-tasks` ni `/speckit-implement` — F1 es solo verificacion.
- El siguiente paso es `verification.md` (Paso 5) y `traceability-cat.csv` (Paso 6).
- Las brechas se convierten en issues de GitHub; no en correcciones en F1.
- La brecha BRECHA-TRD-01 (four-eyes en endpoint clasico) tiene impacto funcional
  real (control interno) y se clasifica Alta.
- La brecha BRECHA-TRD-02 (RFC 7807 parcial) ya fue detectada en el dominio CAT
  principal (ver `verification.md` de 001) — consistente con el patron del codebase.
