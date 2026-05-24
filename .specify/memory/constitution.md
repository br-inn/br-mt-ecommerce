# Constitución del proyecto — br-mt-ecommerce

Versión 1.0 (borrador) · pendiente de ratificación del equipo.

Reglas no negociables del proyecto. Cada plan (`/speckit.plan`) se comprueba contra
ella; las excepciones se documentan, no se asumen. Contenido derivado de `CLAUDE.md`.

## Artículo 1 — Stack obligatorio
- Frontend: Next.js 16 + React 19 + TypeScript estricto + Tailwind v4 + Shadcn/ui.
- Backend: FastAPI + Python 3.11 + Pydantic + Gunicorn/Uvicorn.
- ORM: SQLAlchemy 2.0 async + Alembic (`public.*`). supabase-py solo para Auth y Storage.
- Worker: Celery + Redis; schedules en `public.job_definitions`, no hardcodeados.
- Auth: Supabase Auth, rol `mt_app`. Storage: bucket `product-images`.
- Deploy: AWS EC2 + Docker Compose. Prohibido: Vercel, Prisma, Auth.js, BullMQ, R2.

## Artículo 2 — Migraciones
Alembic para `public.*`; migraciones Supabase para `auth.*`/`storage.*`/RLS. Primero
Supabase, luego Alembic.

## Artículo 3 — Rendimiento backend
Nunca queries secuenciales donde quepa un subquery o JOIN. `selectinload` para
colecciones, `joinedload` para 1:1. No cabeceras `Cache-Control` manuales.
`include_total=False` por defecto en listados.

## Artículo 4 — Rendimiento frontend
`fetchPriority="high"` en la imagen hero; `loading="lazy"` en el resto. React Query con
`staleTime` por tipo de dato. Nunca N llamadas desde N componentes para el mismo
recurso. Páginas de detalle: skeleton inmediato.

## Artículo 5 — LLM / Anthropic
`cache_control` solo con corpus estático largo en el system prompt o pipelines
multi-turno; los prompts cortos actuales no son candidatos.

## Artículo 6 — Esquema de identificadores
Diez dominios: CAT, PRC, INV, PUR, SAL, BIL, FIN, CHN, SIC, PLT.
- Requisito funcional: `FR-<DOM>-NNN` (clave de unión de la matriz de trazabilidad).
- Requisito no funcional: `NFR-<DOM>-NNN`. Regla de negocio: `BR-<DOM>-NNN`.
- Spec / proceso: carpeta `specs/NNN-<dom>-<slug>/`. Decisión técnica: `ADR-NNN`.

## Artículo 7 — Definición de Listo y de Hecho
Spec lista: sin marcadores `[NEEDS CLARIFICATION]`; requisitos verificables; criterios
de éxito medibles; origen trazado al Manual.
Proceso hecho: todos los criterios de aceptación verificados contra la implementación;
pruebas en verde; matriz de trazabilidad actualizada a "Verificado".
Puertas: el plan se comprueba contra esta constitución; `/speckit.clarify` antes de
planificar; `/speckit.analyze` antes de implementar.

## Artículo 8 — Proceso de enmienda
Esta constitución se modifica solo por acuerdo explícito del equipo, con fecha y
motivo. La versión se incrementa en cada enmienda.
