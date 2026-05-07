# ADR-029: Backend FastAPI Python 3.11

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT
- Supersedes: ADR-001 (parcial — capa backend); ADR-021 (parcial — ORM)

## Contexto

El backend de la plataforma MT Middle East debe:

- Ofrecer una API REST tipada con OpenAPI auto-gen.
- Tener tipado fuerte y validación de request/response.
- Acceso a un ecosistema científico/IA maduro (pgvector, embeddings, OCR, comparación de imágenes) para el research workstream del comparador y para Fase 1.5+.
- Integrarse limpiamente con Celery + Redis y SQLAlchemy + Alembic.
- Estar alineado con la arquitectura de referencia BR Innovation `hppt-iom`.

## Decisión

**Stack backend (alineado con hppt-iom — a verificar contra el repo de referencia):**

| Capa | Tecnología | Versión target |
|------|------------|----------------|
| Framework | **FastAPI** | 0.x (latest stable) |
| Runtime | **Python** | **3.11** |
| Validación / DTOs | **Pydantic v2** + **Pydantic Settings** | latest |
| ORM | **SQLAlchemy 2.0** + **Alembic** (alineado con hppt-iom — a verificar) | 2.0.x |
| Schedule jobs ligeros | **APScheduler** | latest |
| Worker async | **Celery** (broker Redis) — ver ADR-030 | latest |
| Server prod | **Gunicorn + Uvicorn workers** | latest |
| Lint / format | `ruff` | latest |
| Tipos | `mypy` strict | latest |
| Tests | `pytest` + `pytest-asyncio` + testcontainers | latest |
| Logging | Loguru / structlog (alineado con hppt-iom — a verificar) | latest |
| Métricas | `prometheus_client` | latest |
| Errores | Sentry SDK Python | latest |

**Estructura de carpetas** (alineada con hppt-iom — a verificar):

```
mt-pricing-backend/app/
  main.py            # FastAPI app
  worker.py          # Celery entry
  config.py          # Pydantic Settings
  deps.py            # FastAPI dependencies
  routers/           # endpoints por dominio
  services/<dominio>/
  db/{models,repositories}/
  schemas/           # Pydantic models
  tasks/             # Celery tasks por dominio
  connectors/        # adapters hexagonal
  scheduler/         # APScheduler jobs
```

**Healthchecks**: `/health/live` y `/health/ready`.

## Alternativas evaluadas

- **NestJS (TypeScript)**: alineado con frontend pero pierde acceso directo al ecosistema científico/IA Python (numpy, scikit-learn, OpenCV, transformers). Para el comparador se necesita Python.
- **Django + DRF**: maduro pero más opinionated; FastAPI da mejor performance, OpenAPI auto-gen y compatibilidad con async/await.
- **Flask + extensions**: requiere ensamblar todo manualmente; FastAPI ya viene con validación + OpenAPI + DI.
- **.NET 8 / ASP.NET Core**: alineamiento si TI MT España es shop Microsoft, pero pierde ecosistema IA Python.

## Consecuencias positivas

- **Tipado fuerte vía Pydantic** + IDE-friendly, equivalente Python a Zod.
- **OpenAPI auto-generado** servido en `/docs` (Swagger UI) → cliente frontend o tooling consume sin doc manual.
- **Acceso al ecosistema científico/IA** (NumPy, OpenCV, scikit-learn, transformers, sentence-transformers) sin context-switch — clave para el comparador.
- **APScheduler** in-process para schedules ligeros (refresh FX, digest, healthchecks) sin pagar Celery overhead.
- **Gunicorn + Uvicorn workers**: production-grade ASGI server; fácilmente escalable horizontalmente.
- **Alineado con hppt-iom** → reuso de patrones, plantillas, scripts deploy.

## Consecuencias negativas / riesgos

- **Dos lenguajes** (Python backend + TS frontend) → tipos no compartidos automáticamente; mitigación: generar TS clients desde OpenAPI o mantener Zod schemas espejo.
- **Equipo BR debe ser cómodo en Python** → confirmado.
- **Equipo MT post-handoff** necesita perfil Python si MT mantendrá in-house — definir en S0.

## Cuándo revisar

- **S0 — gating obligatorio**: TI MT firma o pide alternativa.
- Si hppt-iom adopta otra librería estándar (p.ej. otro ORM o validador), alinear.
- Antes de Fase 2.5 (capa IA): revisar si conviene aislar workloads ML pesados en servicio dedicado.
