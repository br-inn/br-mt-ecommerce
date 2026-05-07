# ADR-035: Reverse proxy Caddy

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT
- Supersedes: —

## Contexto

Con el pivot a Hetzner + Docker Compose (ADR-034), se requiere un reverse proxy en frente de:

- Frontend Next.js 16 (`/`, rutas de página).
- Backend FastAPI (`/api/*`).

Funciones requeridas:

- TLS automático (Let's Encrypt).
- HTTP → HTTPS redirect.
- Headers de seguridad (HSTS, CSP, etc.).
- Routing simple por path.
- Rate limit básico (capa adicional al backend).

## Decisión

**Adoptar Caddy** como reverse proxy (alineado con hppt-iom — a verificar contra el repo de referencia).

| Aspecto | Decisión |
|---------|----------|
| Versión | Caddy 2.x (latest stable) |
| Config | `Caddyfile` versionado en repo de infraestructura |
| TLS | automático Let's Encrypt; renovación automática |
| Routing | `/` → frontend; `/api/*` → backend |
| Headers de seguridad | HSTS, X-Content-Type-Options, X-Frame-Options DENY, Referrer-Policy, CSP, Permissions-Policy |
| Logs | structured JSON al stdout, scrapeable por Better Stack |
| Despliegue | contenedor en `docker-compose.prod.yml`, volúmenes para certs y Caddyfile |

## Alternativas evaluadas

- **Nginx**: más universal pero requiere config manual de TLS (certbot) y más boilerplate. Configuración más verbose.
- **Traefik**: feature-rich pero más overhead; auto-discovery de Docker es útil pero no necesario para 4-5 servicios fijos.
- **Cloudflare frente** (CDN/WAF): complementario; Caddy local sigue siendo necesario para el origin.

## Consecuencias positivas

- **TLS automático** sin scripts.
- **Caddyfile** humano-legible.
- **Alineado con hppt-iom**.
- HTTP/3 nativo si se quiere activar.

## Consecuencias negativas / riesgos

- **Menos universal** que Nginx → algunos plugins de terceros pueden no existir.
- **Estado de certs en disco** → backup del volumen de Caddy importante.
- Si TI MT estandariza otro proxy, pivotar es trabajo de un día.

## Cuándo revisar

- **S0 — gating**: TI MT firma reverse proxy.
- Si feature complejo de Nginx/Traefik se vuelve necesario, evaluar pivot.
