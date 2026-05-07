# ADR-014: Single-tenant MT (no multi-tenant white-label)

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor)

## Contexto

BR Innovation desarrolla la plataforma **para MT Middle East** como cliente, no como producto multi-tenant SaaS. Aclaración explícita en brief:

> Modelo de relación: BR Innovation desarrolla y mantiene el sistema **para MT Middle East** como cliente. La plataforma es **single-tenant** (uso exclusivo MT), no multi-tenant ni white-label.

Decisión arquitectural: ¿modelar para multi-tenant "por si acaso" (típico instinto SaaS) o asumir single-tenant en el modelo de datos?

## Decisión

**Single-tenant explícito**. No hay columna `tenant_id` en ninguna tabla. No hay schemas separados por tenant. No hay infraestructura para spinning up de instancias.

### Implicaciones concretas

- Modelo de datos: tablas planas, FKs directas. Ej. `prices(sku, channel, scheme)`, no `prices(tenant_id, sku, channel, scheme)`.
- Settings: tabla `settings (key, value)` global, no por tenant.
- Despliegue: una sola instancia (dev / staging / prod) con datos de MT exclusivamente.
- Auth: usuarios pertenecen al sistema MT, no a un tenant.
- Storage: un bucket MT (`mtme-products`).
- DB: una database, un schema.

### Si BR quisiera productizar a futuro

- **No** se debería partir de este código sin refactor sustancial. La extracción multi-tenant requiere:
  - Añadir `tenant_id` a todas las tablas críticas.
  - Row-Level Security (RLS) en Postgres.
  - Aislamiento de storage por tenant.
  - Multi-tenant auth (Keycloak / Auth0 organizations).
  - UI: tenant switcher.
- Esa decisión es **fuera de alcance** y requeriría producto nuevo basado en aprendizajes, no fork.

## Alternativas evaluadas

### Alternativa A: Multi-tenant ready desde el día 1
- **Pros**: si BR alguna vez productiza, el código ya soporta.
- **Contras**:
  - Coste de over-engineering Fase 1: cada query, cada FK, cada índice paga overhead `tenant_id`.
  - RLS en Postgres añade complejidad operativa.
  - Auth + Authz se complican.
  - Riesgo de bugs cross-tenant (aunque haya un solo tenant, el código con tenant_id puede tener bugs que en single-tenant no existirían).
- **Veredicto**: descartada por sobrecargar Fase 1 con pasivo arquitectural sin caso de uso.

### Alternativa B: Schemas separados por tenant (Postgres schemas)
- **Pros**: aislamiento fuerte sin RLS.
- **Contras**: para 1 tenant es overkill. Migrations duplicadas.
- **Veredicto**: descartada.

### Alternativa C: Single-tenant con `org_id` "preparado" (siempre 1)
- **Pros**: si productiza, sólo hay que poblar `org_id`.
- **Contras**: pseudo-multi-tenant es lo peor de ambos mundos. Si se decide productizar, el refactor real (RLS, storage, auth) sigue siendo necesario; tener `org_id=1` no ahorra trabajo.
- **Veredicto**: descartada — no hay valor real.

## Consecuencias positivas

- Modelo de datos simple, queries simples.
- Performance: sin overhead `tenant_id` en índices.
- Auth + Authz simples.
- Footprint operacional mínimo.
- Coste BR de mantenimiento más bajo.

## Consecuencias negativas / riesgos

- Si BR alguna vez quiere productizar, no hay reuso directo del código. Mitigación: no es objetivo BR (declarado).
- Si MT abre subsidiarias (MT Saudi, MT Kuwait) que quieran instancia separada, requiere despliegue adicional. Mitigación: el coste de un segundo deploy MT-Saudi (otra DB, otro bucket) es bajo; mejor ese costo que multi-tenant prematuro.
- Si MT decide "compartir" la herramienta con un partner, no se puede sin refactor. Mitigación: no es escenario.

## Cuándo revisar

- **Si MT pide instancia para subsidiaria GCC** (Fase 4+): evaluar deploy independiente vs multi-tenant.
- **Si BR Innovation cambia estrategia** y quiere productizar: rediseñar como producto nuevo, no extender este.
