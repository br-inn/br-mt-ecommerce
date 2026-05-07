---
id: "ADR-054"
title: "Estrategia de rate limiting y WAF (slowapi + Redis + Caddy + Cloudflare opcional)"
status: "proposed"
date: "2026-05-06"
project_name: "mt-pricing-mdm-phase1"
deciders:
  - "Pablo Sierra (BR Innovation)"
  - "Christian (MT Middle East — sponsor)"
  - "TI MT (firma stack en Sprint 0)"
related: ["ADR-019", "ADR-029", "ADR-031", "ADR-032", "ADR-035"]
supersedes: []
superseded_by: []
language: "es"
---

# ADR-054 — Estrategia de rate limiting y WAF

## Contexto

La plataforma MT (FastAPI + Next.js detrás de Caddy en Hetzner) expone:

- Endpoints autenticados para 3 usuarios principales internos (Comercial, Gerente, TI MT) y un Admin BR.
- Endpoints sensibles a abuso (login / magic-link / password reset, importer URL probe, futuros endpoints LLM/embeddings).
- Endpoints "costosos" en Fase 1.5+ (OCR pipeline, VLM judge, reverse image search) cuyo coste por request es no trivial.

Riesgos identificados en el threat model (STRIDE):

- **Denial of Service** trivial sobre endpoints públicos (`/api/v1/auth/*`, `/health/*`, formularios de password reset).
- **Brute force** contra Supabase Auth vía nuestro backend (aunque Supabase aplica su propio rate limit, queremos defensa en profundidad).
- **Abuso de cuota** en endpoints que consumen LLM/Vision/embedding APIs externas (coste $$$).
- **Scraping** del catálogo si en algún momento se exponen rutas semipúblicas.
- **SSRF amplification** vía URL probe del importer si no se rate-limita por usuario.

Decisiones a tomar:

1. ¿Dónde aplicamos rate limit (edge / proxy / app)?
2. ¿Qué librería usamos en FastAPI?
3. ¿Storage del bucket (in-memory vs Redis)?
4. ¿Tiers de cuota?
5. ¿WAF? ¿Caddy nativo vs Cloudflare en frente?

## Decisión

### 1. Defensa en tres capas (defense in depth)

```
Cliente
  │
  ▼
[Cloudflare opcional]   ← Capa 1: WAF + DDoS volumétrico (opt-in Sprint 1, decisión TI MT)
  │
  ▼
[Caddy + plugin caddy-ratelimit]   ← Capa 2: rate limit a nivel proxy (anon, /auth/*)
  │
  ▼
[FastAPI + slowapi + Redis]   ← Capa 3: rate limit per-user, per-endpoint, per-tier
  │
  ▼
[Supabase Auth]   ← Capa 4 (gestionada): rate limit nativo en login / magic-link / password reset
```

**Capa 1 — Cloudflare (opt-in):** se evalúa en Sprint 0 con TI MT. Beneficio: WAF managed, anti-DDoS L3/L4/L7, cache estática del frontend. Coste: dependencia adicional, residencia de datos a verificar contra PDPL UAE. **Decisión inicial: NO obligatorio Fase 1**, queda como toggle. Si TI MT lo aprueba, se mete en Sprint 1.

**Capa 2 — Caddy:** plugin oficial `mholt/caddy-ratelimit` para limitar tráfico anónimo y endpoints de auth ANTES de llegar a FastAPI. Razón: que un atacante consuma slots de Uvicorn workers o conexiones DB no debe ser barato.

**Capa 3 — FastAPI + slowapi:** rate limit fino con conocimiento del JWT (per-user, per-permission, per-endpoint).

**Capa 4 — Supabase Auth:** ya viene con rate limit propio para login / signup / OTP / password reset (configurable en dashboard).

### 2. Librería en FastAPI: **slowapi** + storage Redis

`slowapi` (port de Flask-Limiter para Starlette/FastAPI) es maduro, tiene decoradores limpios, soporta storage Redis, y permite key functions arbitrarias (por user, por IP, por API key…).

Alternativas descartadas:

- `fastapi-limiter` — más simple pero menos flexible para keys custom.
- Implementación propia con `redis-py` + token bucket — innecesaria reinventar la rueda.
- `aiohttp-ratelimiter` — no aplica.

### 3. Storage: **Redis** (compartido con Celery broker)

Razón: ya tenemos Redis en el stack (broker Celery + cache FX + embeddings cache). Reutilizamos. Algoritmo: **sliding window log** (el default de slowapi con storage Redis es preciso y barato a este volumen).

### 4. Tiers de cuota

| Tier | Cuota | Aplicación | Key |
|---|---|---|---|
| **Anónimo global** | 30 req/min | Default para cualquier ruta sin JWT | IP (`X-Forwarded-For` validado contra trusted proxy) |
| **Auth global** | 300 req/min | Default usuario autenticado | `auth.uid()` del JWT |
| **Login / password reset / magic-link** | 5 req/min | `/api/v1/auth/*` | IP |
| **Importer (POST /imports)** | 10 batches/h | Importer | `auth.uid()` |
| **LLM / Embeddings / OCR / VLM** | 100 req/h | Endpoints comparador Fase 1.5+ | `auth.uid()` |
| **Health checks** | sin límite | `/health/live`, `/health/ready` | (whitelist) |

### 5. Headers de respuesta

Todos los endpoints rate-limited devuelven:

- `X-RateLimit-Limit: <int>` — cuota total para la ventana.
- `X-RateLimit-Remaining: <int>` — slots restantes.
- `X-RateLimit-Reset: <epoch>` — segundos hasta reset.
- En 429: `Retry-After: <segundos>`.

### 6. Monitoreo y alertas

- Métrica Prometheus / Better Stack: `ratelimit_429_total{endpoint, tier}`.
- Alerta Sentry / Better Stack: si pico de 429s sobre baseline → potencial abuso, abrir incident.
- Dashboard en `/admin/security` con top IPs / top users por 429s últimas 24 h (visible solo a `admin` y `ti_integracion`).

### 7. Configuración slowapi (snippet)

```python
# app/middleware/rate_limit.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from fastapi import Request
from app.core.config import settings
from app.core.auth import current_user_id_from_jwt_or_none

def _key_user_or_ip(request: Request) -> str:
    uid = current_user_id_from_jwt_or_none(request)
    return f"user:{uid}" if uid else f"ip:{get_remote_address(request)}"

limiter = Limiter(
    key_func=_key_user_or_ip,
    storage_uri=settings.RATE_LIMIT_REDIS_URI,  # ej. redis://redis:6379/2
    strategy="moving-window",
    default_limits=["300/minute"],
    headers_enabled=True,
)

# main.py
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Decoradores per endpoint
@router.post("/auth/password-reset")
@limiter.limit("5/minute", key_func=lambda r: f"ip:{get_remote_address(r)}")
async def password_reset(request: Request, ...): ...

@router.post("/imports")
@limiter.limit("10/hour")
async def create_import(request: Request, ...): ...

@router.post("/comparator/ocr/{listing_id}")
@limiter.limit("100/hour")
async def ocr(...): ...
```

### 8. Caddyfile snippet (Capa 2)

```caddyfile
{
  order rate_limit before reverse_proxy
}

api.mt.mtme.ae {
  encode zstd gzip
  rate_limit {
    zone anon_global {
      key {http.request.remote_host}
      events 30
      window 1m
    }
    zone auth_endpoints {
      match {
        path /api/v1/auth/*
      }
      key {http.request.remote_host}
      events 5
      window 1m
    }
  }
  reverse_proxy api:8000
}
```

## Consecuencias

### Positivas

- Defensa en profundidad: aunque un atacante evada una capa, las otras siguen.
- Coste 0 incremental (Redis ya está en stack; slowapi y caddy-ratelimit son OSS).
- Headers estándar (`X-RateLimit-*`) facilitan integración cliente.
- Per-user limits previenen que un usuario MT comprometido agote presupuesto LLM.

### Negativas

- Test de carga deberá incluir verificación de que los tiers no bloquean uso legítimo.
- Necesidad de propagar `X-Forwarded-For` correctamente desde Caddy → FastAPI (`ProxyHeadersMiddleware`).
- Alerta sobre 429s requiere baseline de 1 semana antes de calibrar.
- Cloudflare opcional implica una decisión adicional de TI MT en Sprint 0 (residencia de datos).

### Riesgos residuales

- **Lockout legítimo de Comercial** si introduce password 5 veces seguidas — acceptable (UX clara con mensaje `Retry-After`).
- **Distributed brute force** desde múltiples IPs — mitigado parcialmente; Cloudflare WAF lo cubre si se activa.
- **Redis caída** — slowapi en `fail-open` por defecto; lo cambiamos a `fail-closed` solo en endpoints `/auth/*` para no convertir Redis en SPOF de la app entera.

## Alternativas consideradas

1. **Solo Caddy rate-limit, sin slowapi.** Descartada: no tiene contexto de JWT, no permite per-user.
2. **Solo slowapi, sin Caddy rate-limit.** Descartada: tráfico anónimo malicioso consumiría workers Uvicorn.
3. **WAF Caddy + reglas custom (sin Cloudflare).** Aceptada como baseline; Cloudflare queda como upgrade path.
4. **NGINX en lugar de Caddy.** Descartada por ADR-035.

## Implementación

- **EP-1A-15 / Story SEC-01** — instalar slowapi + plugin caddy-ratelimit, configurar tiers, escribir tests de cuota (~3 SP).
- **EP-1A-15 / Story SEC-02** — dashboard `/admin/security` con métricas 429 (~2 SP).
- **Sprint 1** — go-live con Capa 2 + Capa 3 activas; Capa 1 (Cloudflare) decisión TI MT.
