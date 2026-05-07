# ADR-033: Storage Supabase Storage

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT
- Supersedes: ADR-013 (storage imágenes — Cloudflare R2)

## Contexto

El proyecto necesita almacenar:

- Imágenes de producto (mirror desde MT España, recortes, thumbs).
- **Fichas técnicas PDF** (descubiertas en `Documentos referencia de articulos/`: `MTFT_*.pdf`, `MTCE_*.pdf`, `MTMAN_*.pdf`).
- Archivos de import (PIM, costos, FX) crudos para auditabilidad.
- Exports generados (CSV/XLSX para canales, audit reports).
- Documentos de referencia / estándares (API 598, ISO 7-1, UNE-EN 1074-3).
- `MT-Catalogo.pdf` (18 MB) y `CHATBOT.docx` (contexto futuro).

Con el pivot a Supabase (ADR-031, ADR-032), tener storage en el mismo BaaS reduce piezas y simplifica políticas de acceso (RLS aplicable a Storage).

## Decisión

**Adoptar Supabase Storage** con cuatro buckets segregados por dominio:

| Bucket | Contenido | Política de acceso |
|--------|-----------|--------------------|
| `product-images` | imágenes mirror de SKUs + thumbs | read: comercial+; write: comercial+ |
| `product-datasheets` | PDFs de fichas técnicas (`MTFT_*`, `MTCE_*`, `MTMAN_*`), estándares (API 598, ISO 7-1, UNE-EN 1074-3), `MT-Catalogo.pdf` | read: comercial+; write: comercial+ |
| `import-batches` | archivos crudos de imports (XLSX/CSV) | read: comercial+; write: comercial+ (tras upload preview) |
| `exports` | CSV/XLSX generados para canales, audit reports, shadow-publish outputs | read: ti_integracion+/gerente+; write: backend service role |

Acceso vía **signed URLs** desde backend FastAPI (TTL corto). RLS policies en `storage.objects` controlan acceso por rol.

## Alternativas evaluadas

- **Cloudflare R2** (ADR-013 original): muy barato, pero pierde integración con RLS Supabase y agrega un servicio más a operar.
- **AWS S3 / Azure Blob**: similar a R2 — caro y desintegrado.
- **MinIO self-host en Hetzner**: añade operación; viable si Supabase no cumple residencia UAE.

## Consecuencias positivas

- **Integración nativa con Supabase Auth y RLS**.
- **Signed URLs** + transformaciones de imagen built-in (Supabase image transformation).
- **Una sola plataforma BaaS** (Auth + DB + Storage).
- **Alineado con hppt-iom**.

## Consecuencias negativas / riesgos

- **Lock-in a Supabase**.
- **Costo egress** si las imágenes se sirven a alto volumen (Fase 3+ con storefront B2C público) → considerar CDN externo (Cloudflare) en frente.
- **Tamaño de archivos** PDF grandes (18 MB `MT-Catalogo.pdf`) — verificar límites del plan Supabase.

## Cuándo revisar

- **S0**: confirmar plan Supabase storage (cuotas + egress).
- **Fase 3+**: si tráfico público crece, evaluar CDN externo + cache.
- Si residencia UAE bloquea Supabase, considerar MinIO self-host.
