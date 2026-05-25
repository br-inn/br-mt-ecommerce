# Checklist de requisitos — Compatibilidad y Variantes (sub-recurso CAT)

**Spec**: `specs/004-cat-compatibilidad-variantes/spec.md`
**Verificación**: `specs/004-cat-compatibilidad-variantes/verification.md`
**Fecha**: 2026-05-25

---

## Requisitos funcionales

- [x] FR-CPT-001 — Listado outgoing con filtro kind (verificado)
- [x] FR-CPT-002 — Listado inverse / incoming (parcial — BRECHA-CPT-03)
- [x] FR-CPT-003 — Alta de enlace con validaciones (verificado)
- [x] FR-CPT-004 — Baja de enlace HTTP 204 (verificado)
- [x] FR-CPT-005 — Reemplazo bulk PUT (verificado)
- [x] FR-CPT-006 — 5 tipos kind válidos (verificado)
- [x] FR-CPT-007 — Sincronización replaces/replaced_by (verificado)
- [x] FR-CPT-008 — Desnormalización compatible_product (parcial — BRECHA-CPT-01)
- [x] FR-CPT-009 — Filtro DN polimórfico series (verificado)
- [x] FR-CPT-010 — Display pair simétrico con limpieza previa (verificado)
- [x] FR-CPT-011 — Display pair clear idempotente (verificado)
- [x] FR-CPT-012 — Effective display tags + certs (verificado)

## Requisitos no funcionales

- [x] NFR-CPT-001 — RBAC en todos los endpoints (verificado)
- [x] NFR-CPT-002 — Sin N+1 en listado outgoing (verificado)
- [x] NFR-CPT-003 — Sin N+1 en effective display (verificado)
- [x] NFR-CPT-004 — Formato error RFC 7807 (parcial — campo `instance` ausente en `_raise_compat`)

## Reglas de negocio

- [x] BR-CPT-001 — No auto-enlace (verificado)
- [x] BR-CPT-002 — No duplicados UNIQUE constraint (verificado)
- [x] BR-CPT-003 — Unidireccional por diseño (verificado)
- [x] BR-CPT-004 — Display pair 1:1 simétrico (verificado)
- [x] BR-CPT-005 — DN range coherente (verificado)
- [x] BR-CPT-006 — Auditoría mutaciones compat (parcial — display pair sin auditoría)
- [x] BR-CPT-007 — products.tags eliminado en Fase B (verificado)

---

## Brechas activas

| ID | Issue | Severidad | Estado |
|----|-------|-----------|--------|
| BRECHA-CPT-01 | [#92](https://github.com/br-inn/br-mt-ecommerce/issues/92) | Media | Abierta |
| BRECHA-CPT-02 | [#93](https://github.com/br-inn/br-mt-ecommerce/issues/93) | Baja | Abierta |
| BRECHA-CPT-03 | [#94](https://github.com/br-inn/br-mt-ecommerce/issues/94) | Baja-Media | Abierta |

---

## Tests automatizados cubiertos

| Suite | Archivo | Estado |
|-------|---------|--------|
| Unit API compat | `tests/unit/api/test_compatibility_api.py` | 13 tests — Verde |
| Unit service compat | `tests/unit/services/compatibility/test_compatibility_service.py` | Verde |
| Unit schema compat | `tests/unit/schemas/test_compatibility.py` | Verde |
| Unit display pair | `tests/unit/services/products/test_display_pair_sync.py` | Verde |
| Unit effective display | `tests/unit/services/products/test_effective_display.py` | Verde |
| Unit API display | `tests/unit/api/test_products_api_stage3.py` | Verde |

**Gaps de tests**:
- `GET /vocabularies/series/{series_id}/spare-parts` sin tests unitarios.
- `NFR-CPT-004` (`instance` en error) sin test específico.
- BRECHA-CPT-03 (inverse sin desnormalización) no cubierta por tests actuales.

---

## Resumen de completitud

| Categoría | Total | Completo | Parcial | No implementado |
|-----------|-------|----------|---------|-----------------|
| FR | 12 | 10 | 2 | 0 |
| NFR | 4 | 3 | 1 | 0 |
| BR | 7 | 6 | 2 | 0 |
| **Total** | **23** | **19 (83%)** | **4 (17%)** | **0** |
