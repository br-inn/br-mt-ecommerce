# Architecture Decision Records (ADRs)

Registro de decisiones arquitecturales de la plataforma MT Pricing & MDM.
Los archivos viven en
[`_bmad-output/planning-artifacts/adr/`](../../_bmad-output/planning-artifacts/adr/).

**Convenciones**:

- ADRs son **inmutables** una vez `accepted`. Si la decisión cambia, se crea
  un ADR nuevo con status `accepted` que `supersedes` el anterior; el anterior
  pasa a `superseded by ADR-0XX`.
- Numeración correlativa, sin reuso.
- Status posibles: `proposed`, `accepted`, `superseded`, `deprecated`,
  `planned` (registrado pero no escrito todavía).

Cómo proponer un ADR: ver [`CONTRIBUTING.md`](../../CONTRIBUTING.md#5-adrs--architecture-decision-records).

---

## Índice (54 ADRs)

### Bloque 1 — Decisiones originales (ADR-001 a ADR-021)

| ID | Título | Status | Tema |
|---|---|---|---|
| ADR-001 | Stack tecnológico (versión inicial) | superseded by ADR-028/029/030/031 | Stack |
| ADR-002 | Persistencia: Postgres single-DB | accepted | DB |
| ADR-003 | Estrategia de monedas | accepted | Pricing |
| ADR-004 | Estrategia de i18n | accepted | UX/Frontend |
| ADR-005 | RBAC | accepted | Seguridad |
| ADR-006 | Workflow de aprobación con excepciones | accepted | Pricing |
| ADR-007 | Audit trail | accepted | Auditabilidad |
| ADR-008 | Estrategia de imports | accepted | Catálogo |
| ADR-009 | Estados de canal y simulación | accepted | Pricing |
| ADR-010 | Regla dura: "no aprobado, no integra" | accepted | Pricing |
| ADR-011 | IA-ready hooks | accepted | Extensibilidad |
| ADR-012 | Comparación de productos — research workstream | accepted | Comparator |
| ADR-013 | Storage de imágenes | superseded by ADR-033 | Storage |
| ADR-014 | Single-tenant MT | accepted | Producto |
| ADR-015 | Build custom (vs. SaaS) | accepted | Producto |
| ADR-016 | Arquitectura hexagonal en connectors | accepted | Arquitectura |
| ADR-017 | Secretos vía vault | superseded by ADR-051 | Seguridad |
| ADR-018 | Cola de jobs con BullMQ | superseded by ADR-030 | Jobs |
| ADR-019 | Observabilidad (versión inicial) | superseded by ADR-047 | Observability |
| ADR-020 | Cloud y residencia en EAU | accepted | Compliance |
| ADR-021 | ORM Prisma | superseded by ADR-045 | DB |

### Bloque 2 — Research spike comparator (ADR-022 a ADR-027)

| ID | Título | Status | Tema |
|---|---|---|---|
| ADR-022 | OCR de imágenes de competidores | accepted | Comparator |
| ADR-023 | Reverse image search (fallback) | accepted | Comparator |
| ADR-024 | VLM judge audit-grade | accepted | Comparator |
| ADR-025 | Capa humana permanente | accepted | Comparator / proceso |
| ADR-026 | Hybrid search Fase 1.5 | accepted | Comparator / search |
| ADR-027 | Build vs. Buy: regla operativa | accepted | Producto |

### Bloque 3 — Pivot de stack (ADR-028 a ADR-037)

| ID | Título | Status | Tema |
|---|---|---|---|
| ADR-028 | Frontend Next.js 16 + React 19 | accepted | Frontend |
| ADR-029 | Backend FastAPI (Python) | accepted | Backend |
| ADR-030 | Workers Celery + Redis | accepted | Jobs |
| ADR-031 | DB Supabase Postgres (managed) | accepted | DB |
| ADR-032 | Auth Supabase (JWT + RLS) | accepted | Auth |
| ADR-033 | Storage Supabase | accepted | Storage |
| ADR-034 | Deploy Hetzner Cloud + Docker Compose | accepted | Infra |
| ADR-035 | Reverse proxy Caddy | accepted | Infra |
| ADR-036 | Estructura del monorepo | accepted | DevEx |
| ADR-037 | Neo4j en Fase 1.5 | accepted | Search / KB |

### Bloque 4 — RAG → GraphRAG roadmap (ADR-038 a ADR-041)

| ID | Título | Status | Tema |
|---|---|---|---|
| ADR-038 | Roadmap RAG hybrid → GraphRAG | accepted | IA / KB |
| ADR-039 | Ontología knowledge graph PVF | accepted | KB |
| ADR-040 | Seed de compatibilidad de materiales | accepted | KB |
| ADR-041 | CDC Postgres → Neo4j | accepted | KB / data pipeline |

### Bloque 5 — KB module (ADR-042 a ADR-044)

| ID | Título | Status | Tema |
|---|---|---|---|
| ADR-042 | KB ingestion pipeline | planned | KB |
| ADR-043 | KB retrieval API | planned | KB |
| ADR-044 | KB feedback loop & curation | planned | KB |

> Los ADRs 042-044 fueron asignados durante el diseño del módulo KB pero
> aún no están escritos en disco — quedan como `planned` hasta su redacción
> formal en Sprint 2+ (ver [`mt-kb-module-design.md`](../../_bmad-output/planning-artifacts/mt-kb-module-design.md)).

### Bloque 6 — Persistencia + scheduler (ADR-045, ADR-046)

| ID | Título | Status | Tema |
|---|---|---|---|
| ADR-045 | Persistencia híbrida SQLAlchemy + Supabase | accepted | DB |
| ADR-046 | Celery Beat con DatabaseScheduler | accepted | Jobs |

### Bloque 7 — Production readiness (ADR-047 a ADR-054)

| ID | Título | Status | Tema |
|---|---|---|---|
| ADR-047 | Observability stack (OTel + Loki + Prom + Grafana + Tempo) | accepted | Observability |
| ADR-048 | Healthcheck endpoints (liveness + readiness + startup) | accepted | Operability |
| ADR-049 | Migration discipline (expand-contract obligatorio) | accepted | DB / proceso |
| ADR-050 | IaC con Terraform sobre Hetzner | accepted | Infra / IaC |
| ADR-051 | Secrets management con Doppler | accepted | Seguridad |
| ADR-052 | SLI / SLO + error budget | accepted | SRE |
| ADR-053 | Backup & DR strategy | accepted | DR |
| ADR-054 | Rate limiting + WAF strategy | accepted | Seguridad |

---

## Resumen por status

| Status | Cantidad |
|---|---|
| accepted | 44 |
| superseded | 7 |
| planned | 3 |
| **Total** | **54** |

---

## Próximos ADRs candidatos (no asignados)

Reservar números a partir de **ADR-055** para:

- Feature flags strategy.
- Multi-region DR (cuando MT lo requiera).
- LLM provider selection y cost guardrails.
- Versionado de API pública (v1, v2…).
- Política de retención de datos por dominio.
