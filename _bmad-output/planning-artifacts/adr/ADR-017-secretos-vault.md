# ADR-017: Gestión de secretos (Doppler / 1Password / Vault)

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT

## Contexto

El sistema maneja:
- Credenciales DB (Postgres, Redis).
- Auth secrets (NEXTAUTH_SECRET, JWT_SECRET).
- API keys de servicios (Sentry, S3/R2, OpenAI Fase 1.5+).
- Credenciales connectors (Amazon SP-API LWA tokens, Noon API keys — Fase 3+).
- Credenciales de FX feed (Fase 1.5+: XE, OANDA).

Fase 1 single-tenant. Equipo: BR (1-3 devs) + TI MT (1-2). Entornos: dev / staging / prod.

## Decisión

**Doppler** como gestor de secretos default Fase 1, con integración GitHub Actions + runtime.

### Razones

- Setup mínimo (~ 1 hora).
- Plan free / cheap para equipo pequeño.
- Cliente CLI + SDK Node.js + integración nativa con Vercel / Railway / AWS / GitHub Actions.
- Branch separado para cada entorno (`dev`, `staging`, `prod`).
- Rotation supportada vía API.
- Audit log de quién accedió qué secret.

### Alternativas si TI MT exige

- **1Password Secrets Automation**: si MT ya usa 1Password corporate.
- **HashiCorp Vault**: si MT quiere self-hosted (overhead operativo significativo; recomendado solo si TI MT lo opera).
- **AWS Secrets Manager** (si stack en AWS): integración nativa.
- **Azure Key Vault** (si stack en Azure).

### Política

- **Nunca** secretos en `.env` committed al repo. `.env.example` con keys vacías.
- En dev: cada dev BR usa su propio token Doppler personal con scope `dev`.
- En CI/CD (GitHub Actions): `DOPPLER_TOKEN` como secret de repo, scope `staging` y `prod` separados.
- En runtime: el container / VM monta secrets via Doppler agent o vía variables de entorno inyectadas al iniciar.
- Rotación: trimestral mínimo para credenciales de DB y API keys de marketplaces; auto-rotación si el provider lo soporta.
- Acceso de lectura prod: sólo `admin` y TI MT. BR devs no tienen acceso a prod secrets en operación normal (break-glass procedure documentado).

### Encriptación at rest

- Database: encryption at rest del provider (RDS encryption / Azure Postgres encryption).
- Connector credentials en `channel_credentials.credentials_encrypted` cifradas con `pgcrypto` usando una key derivada del secret `DB_ENCRYPTION_KEY` (gestionado en Doppler).
- Secrets en S3: bucket encryption SSE-S3 / SSE-KMS.

### Datos sensibles en logs

- Filtro Pino redaction: `password`, `token`, `secret`, `authorization`, `cookie` redactados automáticamente.
- Auditoría manual de logs en S0 antes de prod.

## Alternativas evaluadas

### Alternativa A: `.env` files copiados manualmente
- **Pros**: cero infra.
- **Contras**: error humano, sin audit, sin rotación. Inviable para regulado UAE 2026.
- **Veredicto**: descartada.

### Alternativa B: GitHub Secrets only (sin gestor dedicado)
- **Pros**: built-in.
- **Contras**: no hay rotación, no hay audit decente, scope sólo CI no runtime, no hay branch separado por entorno con UI.
- **Veredicto**: descartada como única solución; usable como fallback.

### Alternativa C: HashiCorp Vault self-hosted
- **Pros**: máxima flexibilidad, dynamic secrets, leasing.
- **Contras**: complejidad operativa altísima para un equipo de 3-5 personas. Sin valor incremental Fase 1.
- **Veredicto**: descartada Fase 1.

## Consecuencias positivas

- Audit de acceso a secretos.
- Rotación factible.
- Separación dev / staging / prod limpia.
- Integración con stack moderno.

## Consecuencias negativas / riesgos

- Doppler es SaaS externo → dependencia (data residency: Doppler tiene regiones; configurar a EU si UAE no disponible).
- Si TI MT exige residencia UAE estricta para secretos, Doppler puede no cumplir → fallback a Vault self-hosted o key vault del cloud elegido.

## Cuándo revisar

- **S0**: confirmar con TI MT si Doppler aceptable o exige alternativa.
- **Antes de Fase 3** (cuando se añadan credenciales de marketplaces UAE): re-evaluar residency.
