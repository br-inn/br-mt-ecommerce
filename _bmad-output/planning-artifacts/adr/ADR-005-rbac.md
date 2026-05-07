# ADR-005: RBAC (3 roles base + reglas de excepción paramétricas)

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), Gerente Comercial

## Contexto

Fase 1 tiene 3 roles definidos:
- **Comercial Canal Online & Marketplaces** — CRUD catálogo, propone precios, traducciones.
- **Gerente Comercial** — aprueba excepciones, define reglas paramétricas.
- **TI de Integración** — configura connectors, gestiona usuarios/permisos.

Más roles secundarios:
- **Backup operator** (cross-trained) — mismas capacidades que Comercial, separado para auditoría.
- **Champion del cambio** — mismas capacidades que Comercial.
- **Admin / Sysadmin** — solamente BR Innovation o TI MT, para superusuario inicial.

El sistema necesita **autorización fina**: ¿este usuario puede aprobar este precio en este canal?, ¿puede ver este audit trail?, ¿puede importar?

VAT UAE 2026 exige trazabilidad de "quién aprobó qué" → autor + aprobador en audit, separation of duties cuando hay riesgo material.

## Decisión

### Modelo

**Role-Based Access Control con permisos finos** (RBAC + permission matrix), no ABAC complejo.

- Tabla `roles` (code, name, description). Roles iniciales:
  - `comercial`
  - `gerente_comercial`
  - `ti_integracion`
  - `admin` (sysadmin, BR Innovation y TI MT inicial)
- Tabla `users` (email, hashed_password, name, locale_pref, mfa_enabled, last_login, active, ...).
- Tabla `user_roles` (user_id, role_code) — many-to-many; un usuario puede tener varios roles (ej. backup operator = `comercial` + flag de auditoría).
- Tabla `permissions` (no es nuestra; es derivable de un mapa estático en código TypeScript). Permission = `resource.action` (`product.create`, `price.approve`, `audit.read`, ...).
- Tabla `role_permissions` — many-to-many (puede ser tabla, puede ser estructura en código si se quiere immutable).
- Cuando un usuario actúa, se cargan `permissions ∪ role.permissions` para sus roles activos.

### Matriz inicial (resumen — la matriz completa va en el documento principal sección Seguridad)

| Recurso × acción | comercial | gerente_comercial | ti_integracion | admin |
|------------------|:---------:|:-----------------:|:--------------:|:-----:|
| product.read | ✓ | ✓ | ✓ | ✓ |
| product.create / update | ✓ | ✓ | – | ✓ |
| product.delete | – | ✓ | – | ✓ |
| translation.read / update | ✓ | ✓ | – | ✓ |
| supplier.read | ✓ | ✓ | – | ✓ |
| supplier.create / update / delete | – | ✓ | – | ✓ |
| cost.read | ✓ | ✓ | – | ✓ |
| cost.create / update | ✓ | ✓ | – | ✓ |
| price.read | ✓ | ✓ | – | ✓ |
| price.propose | ✓ | ✓ | – | ✓ |
| price.approve / reject | – | ✓ | – | ✓ |
| price.export | – | ✓ | ✓ | ✓ |
| channel.read | ✓ | ✓ | ✓ | ✓ |
| channel.update_state | – | ✓ | ✓ | ✓ |
| currency.read | ✓ | ✓ | ✓ | ✓ |
| currency.update_fx | – | ✓ | ✓ | ✓ |
| import.run | ✓ | ✓ | – | ✓ |
| import.config | – | – | ✓ | ✓ |
| audit.read | – | ✓ | – | ✓ |
| user.manage | – | – | ✓ | ✓ |
| exception_rule.update | – | ✓ | – | ✓ |
| connector.config | – | – | ✓ | ✓ |

### Reglas de excepción paramétricas

Las **reglas de excepción** (auto_approve vs pending_review) se gestionan en tabla `exception_rules` separada de RBAC:

- `code` (e.g. `MARGIN_TOLERANCE`, `FX_SWING`, `MIN_MARGIN`)
- `scope` (`global` / `per_channel` / `per_scheme`)
- `params JSONB` (e.g. `{threshold_pct: 5}`)
- `enabled`
- Sólo `gerente_comercial` y `admin` pueden modificar (`exception_rule.update`).

Esto desacopla "quién hace qué" (RBAC) de "qué requiere aprobación" (reglas paramétricas).

### Implementación técnica

- Auth.js (NextAuth) v5 con session JWT.
- Middleware Next.js que carga `session.user.roles` y `session.user.permissions` (resueltos al login).
- Helper `requirePermission(perm: string)` server-side en cada Route Handler.
- Helper `<Can permission="price.approve">...</Can>` en UI para feature flags visuales.
- DB-level: políticas de RLS (Row Level Security) **opcionales Fase 1** — la app actúa como single tenant interno; RBAC se enforce a nivel app. RLS se evalúa Fase 2 si TI MT lo exige.

## Alternativas evaluadas

### Alternativa A: ABAC (atributo-based) full
- **Pros**: máxima flexibilidad (e.g. "comercial sólo puede aprobar precios SKUs de su brand asignado").
- **Contras**: complejidad UI + tooling + audit; overkill para 3 roles + 3-10 usuarios totales.
- **Veredicto**: descartada para Fase 1.

### Alternativa B: 1 sólo super-rol "todos pueden todo"
- **Pros**: trivial.
- **Contras**: viola separation of duties, viola requisitos de audit UAE 2026, sin protección contra error humano (cualquiera puede aprobar cualquier cambio).
- **Veredicto**: descartada.

### Alternativa C: 5+ roles más granulares (Comercial Junior / Senior, Gerente Junior / Senior, ...)
- **Pros**: más finura.
- **Contras**: equipo MT tiene 3 personas; cada rol necesita capacitación; más riesgo de error operativo.
- **Veredicto**: descartada Fase 1.

## Consecuencias positivas

- Matriz simple y entendible por el negocio.
- Separation of duties forzada (comercial propone, gerente aprueba — DB constraint).
- Audit trail tiene autor + aprobador siempre.
- Reglas de excepción paramétricas separan lógica de autorización de lógica de negocio.

## Consecuencias negativas / riesgos

- Si MT crece equipo (Fase 2-4) puede necesitar roles más finos. Mitigación: el modelo ya soporta múltiples roles por usuario y row-level segmentation por brand/channel sin rediseñar la matriz base.
- Single rol `admin` para superusuarios → riesgo si se compromete. Mitigación: MFA obligatorio para `admin` (ver ADR de seguridad en doc principal); rotación periódica.

## Cuándo revisar

- **Cierre Fase 1a**: validar matriz con el Gerente Comercial sobre uso real.
- **Fase 2-3**: añadir roles de Marketing, Customer Service, Operaciones.
- **Si MT exige RLS regulatorio**: añadir políticas en S0 antes de migración.
