# ADR-037: Neo4j externo Fase 1.5+ (opcional)

- Status: **superseded by ADR-038** (2026-05-06)
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT
- Supersedes: —
- Superseded by: ADR-038 — ADR-038 da scope concreto a la introducción de Neo4j (roadmap RAG → Hybrid → GraphRAG); ADR-039 define ontología, ADR-040 define seed inicial desde compatibilidad de materiales y ADR-041 define el CDC Postgres ↔ Neo4j.

## Contexto

Las fuentes reales del catálogo descubiertas en `Documentos referencia de articulos/` revelan tres dimensiones que se cruzan:

- **SKUs** (PIM completo, ~5086 filas).
- **Fichas técnicas** (`MTFT_*.pdf`, `MTCE_*.pdf`, `MTMAN_*.pdf`).
- **Compatibilidades de material** (tabla con productos × materiales × temperatura, `Copia de Compatibilidad de Materiales MT V4.xlsx`).

Las relaciones SKU ↔ ficha técnica ↔ compatibilidades de material son inherentemente **grafo**: un material es compatible con muchos productos, una ficha técnica documenta varios SKUs, un SKU se cruza con familia, brand, conexión, etc. Para queries como "dado este SKU, qué SKUs son intercambiables considerando NPT vs BSP, SS304 vs SS316, T máx, etc." un grafo es la representación natural.

Sin embargo, **Fase 1 no necesita un grafo**:

- 224 SKUs en producción hoy.
- Las consultas de matching las puede absorber Postgres con joins + reglas duras.
- Operación de Neo4j adicional encarece y complica handoff.

## Decisión

**Reservar Neo4j externo como sistema opcional para Fase 1.5+**. No bloqueante Fase 1.

| Aspecto | Decisión |
|---------|----------|
| Plataforma | Neo4j Aura (managed) o self-host en Hetzner |
| Trigger de activación | Fase 1.5+ cuando se valide caso de uso real (cross-sell, intercambiabilidad, recomendador de canal) |
| Dominio | relaciones SKU ↔ ficha técnica ↔ compatibilidad de material ↔ familia ↔ proveedor |
| Sincronización | tareas Celery que reflejan cambios de Postgres → Neo4j (eventual consistency aceptable) |
| Hooks Fase 1 | abstracción `GraphRepository` con backend Postgres (queries SQL recursivas / joins) y backend Neo4j (Cypher); Fase 1 usa el Postgres backend |

**Ningún refactor mayor cuando se active**: la abstracción `GraphRepository` se introduce desde Fase 1 con una sola implementación (Postgres). Activar Neo4j Fase 1.5+ implica añadir la implementación Cypher y un toggle de feature flag.

## Alternativas evaluadas

- **Postgres puro con joins recursivos** (Fase 1 default): suficiente para 224-50k SKUs y queries simples.
- **Apache AGE (Postgres con Cypher)**: experimentar grafo dentro de Supabase sin operar otro sistema.
- **Amazon Neptune / TigerGraph**: enterprise; over-engineered Fase 1.5+.

## Consecuencias positivas

- **No bloqueante Fase 1**: activable cuando el caso de uso lo justifique.
- **Hooks listos** evitan refactor.
- Si Fase 2.5+ (capa IA) requiere knowledge graph para el comparador, ya hay puerto.

## Consecuencias negativas / riesgos

- **Complejidad operativa adicional** cuando se active.
- **Sync DB↔Neo4j** introduce eventual consistency que hay que documentar.
- **Lock-in parcial** si los queries Cypher se vuelven críticos.

## Cuándo revisar

- **Cierre Fase 1b**: confirmar si los casos de uso de cross-sell justifican activar Fase 1.5+.
- Cuando catálogo > 5k SKUs o consultas multi-hop se vuelvan dolorosas en SQL.
- Antes de Fase 2.5 (capa IA) — el comparador podría beneficiarse de un knowledge graph.
