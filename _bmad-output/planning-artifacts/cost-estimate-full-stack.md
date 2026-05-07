---
title: "Cost Estimate Full Stack — MT Middle East MDM + Pricing Fase 1"
status: "draft"
version: "1.0"
created: "2026-05-06"
project_name: "mt-pricing-mdm-phase1"
horizon: "Fase 1 (mes 0-7) + proyección Fase 2-3 año 1-2"
related: ["architecture-mt-pricing-mdm-phase1.md", "mt-observability-design.md", "research-spike-product-comparison.md"]
---

# Cost Estimate Full Stack — MT Middle East MDM + Pricing Fase 1

> **Convenciones**
> - Todos los importes están en **USD** salvo cuando se indique explícitamente EUR.
> - Conversión asumida: **1 EUR = 1.10 USD** (Hetzner factura en EUR; el resto en USD).
> - Margen de error declarado en todas las cifras: **±20 %**. Son estimaciones, no presupuestos firmados.
> - Pricing 2026 referenciado de las páginas oficiales de cada proveedor (URLs en cada sección). Cuando la página oficial no expone tier 2026 o el cambio respecto a 2025 sea ambiguo, se marca **TODO verificar pricing 2026**.
> - Este documento NO incluye mano de obra de desarrollo (BR Innovation factura aparte por SP).

---

## 1. Resumen ejecutivo

| Concepto | USD/mes | Nota |
|---|---|---|
| **Costo mínimo Fase 1 (S0–S2, single-tenant interno, sin POC comparador)** | **~169** | Sólo plataforma core + observabilidad mínima. |
| **Costo recomendado Fase 1 (S4–S7, todo activo, POC comparator en steady)** | **~734** | Incluye on-call, status page, etiquetado humano steady y buffer 25 %. |
| **Costo proyectado Fase 3 año 1 (50 k SKUs, marketplaces vivos, 50–100 users)** | **~3 258** | Supabase Team, Bright Data alto volumen, etiquetado 3–5 validators. |
| **Cap propuesto Fase 1 (con headroom 25 %)** | **~850** | Revisión mensual con Sponsor. |

**Distribución por categoría (escenario recomendado Fase 1, USD 734)**

| Categoría | USD/mes | % |
|---|---|---|
| Infraestructura (Hetzner) | 35 | 5 % |
| Database/Auth/Storage (Supabase) | 25 | 3 % |
| Backups (R2 + B2) | 5 | 1 % |
| Secrets (Doppler) | 50 | 7 % |
| Error tracking (Sentry) | 26 | 4 % |
| Logs + Uptime + On-call + Status (Better Stack) | 83 | 11 % |
| Métricas (Grafana) | 0 | 0 % |
| OCR (Google Vision) | 1 | 0 % |
| Embeddings + LLM (OpenAI / Gemini) | 27 | 4 % |
| Scraping (Bright Data) | 5 | 1 % |
| Email (Resend) | 0 | 0 % |
| GitHub | 22 | 3 % |
| Etiquetado humano comparador | 300 | 41 % |
| Misc | 5 | 1 % |
| Buffer 25 % | 150 | 20 % |
| **Total** | **734** | **100 %** |

**Lectura clave**: el rubro humano (etiquetado UAE freelance) es el **mayor componente** del cost recomendado (~41 %). Toda la plataforma técnica de Fase 1 cabe en USD ~280/mes antes de etiquetado y buffer.

---

## 2. Asunciones de carga

| Variable | Fase 1 (mes 0-7) | Fase 3 año 1 |
|---|---|---|
| SKUs en catálogo | 224 → 5 086 | hasta 50 000 |
| Usuarios concurrentes | 3–5 | 50–100 + tráfico marketplace |
| Imports / mes | 5–10 | 50–100 |
| Recálculos masivos pricing / mes | 10–20 | 100–500 |
| Comparator runs / mes | 1–2 batches × 500–5 000 SKUs | semanal × 50 000 SKUs |
| KB queries / día | 50–200 | 500–2 000 |
| Email transactional / mes | 100–300 | 5 000–20 000 |
| DB size estimado | 1–3 GB | 15–30 GB |
| Storage activos (imágenes/docs) | 5–20 GB | 100–300 GB |

---

## 3. Tabla maestra de costos por categoría

### 3.1 Infrastructure — Hetzner Cloud

Pricing oficial: <https://www.hetzner.com/cloud/> (2026, **TODO verificar pricing 2026** — la última pricing card pública es de 2025; asumimos sin cambio material).

| Servicio | Tier | Unidades clave | EUR/mes | USD/mes | Notas |
|---|---|---|---|---|---|
| Servidor dev | CX22 | 4 GB RAM, 2 vCPU, 40 GB SSD | 5 | 5.5 | Sin réplica. |
| Servidor staging | CX22 | 4 GB RAM, 2 vCPU, 40 GB SSD | 5 | 5.5 | Encendido durante Sprints. |
| Servidor prod | CX42 | 16 GB RAM, 8 vCPU, 160 GB SSD | 17 | 18.7 | Tier base recomendado Fase 1. |
| (Alternativa prod) | CCX13 dedicado | 8 GB RAM, 2 vCPU dedicado | 22 | 24.2 | Si se quiere CPU dedicada (no compartida). |
| Volumen block storage | 50 GB | Postgres data + Storage local | 2.4 | 2.6 | EUR 0.0476 / GB / mo. |
| Volumen block storage | 20 GB | Backups locales / cache | 0.95 | 1.0 | |
| Tráfico salida | 20 TB incluido | Sobreuso EUR 1 / TB | 0 | 0 | No hay sobreuso esperado Fase 1. |
| Snapshots automáticos | ~20 % del precio del server | EUR 5 + 14 + 14 | 3 | 3.3 | Hetzner factura 1 % por snapshot por día sobre tamaño. |
| Floating IP (prod) | 1 IPv4 | EUR 1/mo | 1 | 1.1 | Para failover futuro. |
| **Subtotal Hetzner Fase 1** | | | **~33** | **~36** | |

**Nota**: si Fase 3 requiere segundo nodo prod + réplica Postgres + servidor de jobs separado, el subtotal sube a EUR 100–140 / mo (~USD 110–155). Reflejado en sección 4.4.

### 3.2 Database & Auth & Storage — Supabase

Pricing oficial: <https://supabase.com/pricing> (2026).

| Tier | USD/mes | Incluye | Recomendación |
|---|---|---|---|
| Free | 0 | 500 MB DB, 1 GB Storage, 50 k MAU | NO usar — sin PITR ni backups serios. |
| **Pro** | **25** | 8 GB DB, 100 GB Storage, 100 k MAU, PITR 7 días, backups diarios | **Recomendado Fase 1**. |
| Team | 599 | + SOC2, SAML SSO, residencia, soporte prioritario | Solo si compliance UAE lo exige. |

Add-ons posibles (Pro):
- Compute upgrade (de Micro a Small/Medium): USD 10–60/mo extra. **TODO verificar pricing 2026 compute add-ons**.
- DB extra: USD 0.125 / GB / mo sobre los 8 GB incluidos.
- Storage extra: USD 0.021 / GB / mo sobre los 100 GB.
- Bandwidth extra: USD 0.09 / GB sobre los 250 GB incluidos.

**Subtotal Supabase Fase 1**: **USD 25–50 / mo** (Pro base + posible compute small upgrade).

### 3.3 Backups cross-provider (Cloudflare R2 + Backblaze B2)

Pricing R2: <https://developers.cloudflare.com/r2/pricing/>. Pricing B2: <https://www.backblaze.com/cloud-storage/pricing>.

Estrategia 3-2-1: 3 copias (Supabase nativos + R2 + B2), 2 medios distintos (R2 + B2), 1 off-site cross-provider.

Volumen estimado Fase 1:
- DB dump diario comprimido: ~500 MB → 15 GB / mes activos (con retención 30 días) + 6 monthly snapshots = ~18 GB.
- Storage assets backup: ~10 GB.
- Logs frío (rotated): ~5 GB.
- **Total**: ~33 GB activos en cada provider; ~150 GB acumulados con retención multi-period.

| Servicio | Pricing | Estimado | USD/mes |
|---|---|---|---|
| R2 storage | $0.015 / GB / mo | 33 GB activos | 0.5 |
| R2 Class A ops | $4.50 / M | ~10 k ops/mo | 0.05 |
| R2 egress | $0 | restore eventual | 0 |
| B2 storage | $0.006 / GB / mo | 33 GB | 0.2 |
| B2 egress | $0.01 / GB | restore | 0–1 |
| **Subtotal Fase 1** | | | **~5–10** |

Fase 3 con catálogo 10x: ~30 USD / mo.

### 3.4 Secrets & IaC — Doppler + Terraform Cloud

Pricing Doppler: <https://www.doppler.com/pricing>.
Pricing Terraform Cloud: <https://www.hashicorp.com/products/terraform/pricing>.

| Tier | USD/mo | Notas |
|---|---|---|
| Doppler Developer (Free) | 0 | 5 envs, sin SSO, sin team. **OK para S0-S1**. |
| Doppler Team | $18/user/mo | SSO, audit logs, RBAC. **Subir cuando entra TI MT como FTE**. **TODO verificar pricing 2026** (en 2025 era $16/user/mo). |
| Terraform Cloud Free | 0 | < 500 resources, OSS workflow, suficiente Fase 1. |

**Subtotal Fase 1 mínimo**: 0. **Subtotal Fase 1 recomendado** (3 users × $18): ~USD 54.

### 3.5 Error tracking — Sentry

Pricing oficial: <https://sentry.io/pricing/>.

| Tier | USD/mo | Incluye |
|---|---|---|
| Developer | 0 | 5 k errors, 10 k transactions, 1 user |
| **Team** | **26** | 50 k errors, 100 k transactions, unlimited users — recomendado Fase 1 |
| Business | 80 | 100 k+ errors, advanced insights, SAML — **Fase 3** |

**Subtotal Fase 1**: USD 26.

### 3.6 Logs centralizados — Better Stack Logs

Pricing oficial: <https://betterstack.com/logs/pricing>.

| Tier | USD/mo | Incluye |
|---|---|---|
| Free | 0 | 1 GB / mes, 3 días retención — insuficiente. |
| **Logs Starter** | **25** | 30 GB ingest / mes, 30 días retención |
| Pro | 130 | 100 GB ingest / mes, 90 días retención — Fase 3. |

**Subtotal Fase 1**: USD 25. Consistente con `mt-observability-design.md` (USD 145–180 declarados).

### 3.7 Uptime + On-call + Status Page — Better Stack

Pricing: <https://betterstack.com/uptime/pricing>, <https://betterstack.com/oncall/pricing>, <https://betterstack.com/status-page/pricing>.

| Servicio | Tier | USD/mo | Notas |
|---|---|---|---|
| Uptime | Starter | 24 | 50 monitors, 30 s checks, heartbeats |
| On-call | Starter | 16 | 1 schedule, escalation policies. **TODO verificar pricing 2026** (changeo de bundle). |
| Status Page | Starter | 18 | Public status page con dominio custom |

**Subtotal Fase 1 mínimo (sólo Uptime)**: USD 24.
**Subtotal Fase 1 recomendado (Uptime + On-call + Status)**: USD 58.

### 3.8 Métricas & dashboards — Grafana Cloud

Pricing oficial: <https://grafana.com/pricing/>.

| Tier | USD/mo | Incluye |
|---|---|---|
| **Free** | **0** | 10 k series active metrics, 50 GB logs, 50 GB traces, 14 días retención — **suficiente Fase 1** |
| Pro | desde 49 | extensible, 13 meses retención metrics — **upgrade Fase 3** |

**Subtotal Fase 1**: USD 0.

### 3.9 OCR — Google Cloud Vision OCR

Pricing oficial: <https://cloud.google.com/vision/pricing>.

| Banda | $/1000 imgs |
|---|---|
| Primeras 1 000 / mes | 0 (free tier) |
| 1 001 – 5 M / mes | 1.50 |

**Volumen Fase 1**:
- Bootstrap inicial 5 086 SKUs × 1.5 imgs promedio = ~7 600 imgs → USD ~10 una vez.
- Steady-state: 100 SKUs nuevos × 1.5 imgs = 150 imgs / mes → USD 0.

**Subtotal mensual Fase 1**: USD 0–1.

### 3.10 Embeddings — OpenAI text-embedding-3-large

Pricing oficial: <https://openai.com/api/pricing/>.

- text-embedding-3-large: **$0.13 / 1 M tokens** (con Matryoshka 1024d para optimizar storage en pgvector).

**Volumen Fase 1**:
- KB chunks: 5 086 SKUs × 2 chunks promedio × 500 tokens = ~5 M tokens → USD 0.65 inicial.
- Comparator (consultas + candidatos): 5 000 SKUs × (1 query × 100 tokens) + 500 candidatos × 100 tokens = ~25 M tokens batch → USD 3.25.
- Steady-state mensual: refresco delta + queries = ~10 M tokens / mes → USD 1.30.

**Subtotal Fase 1**:
- Bootstrap inicial one-time: ~USD 5–10.
- Mensual steady: **USD 2–5**.

Alternativa: **Cohere Embed v3** (<https://cohere.com/pricing>): $0.10 / 1 M tokens — ~25 % más barato si necesitamos B-plan o si OpenAI sufre rate limit.

### 3.11 LLM (VLM judge para comparador)

Pricing:
- Gemini 2.5 Flash: <https://ai.google.dev/pricing> — ~$0.075 / 1 M input + $0.30 / 1 M output (modelo recomendado por `research-spike-product-comparison.md`).
- OpenAI GPT-4o: <https://openai.com/api/pricing> — ~$2.50 / 1 M input + $10 / 1 M output.
- Claude Sonnet 4.7: ~$3 / 1 M input + $15 / 1 M output.

**Volumen Fase 1 POC** (single-batch 500 SKUs):
- 500 SKUs × 5 candidatos × ~5 k tokens promedio = 12.5 M tokens.
- Con Gemini Flash: 12.5 × $0.075 input + 1.25 × $0.30 output ≈ USD 1.3 (one-time).

**Steady-state Fase 1** (mensual, refresh ~500 SKUs):
- ~5 M tokens / mes con Gemini Flash → USD 0.5–2.
- Si se introduce tie-break con Claude/GPT-4o sobre 5–10 % de casos: +USD 5–25 / mo.

**Subtotal Fase 1**: USD 10–30 / mo (incluye margen para tie-break premium).

### 3.12 Scraping competidores — Bright Data

Pricing oficial: <https://brightdata.com/pricing>.

- Web Scraper API pay-per-success: **$1.50 / 1000 successful requests** (tier base).
- Volume discount > 100 k req/mo: ~$1.10 / 1000.

**Volumen Fase 1**:
- POC inicial: 500 SKUs × 5 candidatos = 2 500 reqs → USD 4.
- Steady mensual (refresh top SKUs): 1 000–3 000 reqs / mo → USD 2–5.

**Volumen Fase 3 año 1** (refresh semanal, 5 k SKUs activos × 5 candidatos × 4 sem = 100 k reqs / mo):
- Con volume discount: ~USD 110–200 / mo.

**Subtotal Fase 1**: USD 5 / mo. **Subtotal Fase 3**: USD 150–200 / mo.

**Riesgo**: si Amazon UAE / Noon UAE empiezan a bloquear más agresivamente, podríamos necesitar tier residential proxy ($8.40/GB) — uplift hasta 3x. **TODO verificar uplift Bright Data 2026 si ARM lo cataloga categoría restringida.**

### 3.13 Email transactional — Resend

Pricing oficial: <https://resend.com/pricing>.

| Tier | USD/mo | Incluye |
|---|---|---|
| **Free** | **0** | 3 000 emails / mes, 100 / día — **OK Fase 1** |
| Pro | 20 | 50 000 emails / mes |
| Scale | 90 | 100 000 emails / mes — **Fase 3** |

Alternativa: Postmark ($15/mo, 10 k emails) si quemar bounce rate o reputación con Resend.

**Subtotal Fase 1**: USD 0.

### 3.14 GitHub

Pricing oficial: <https://github.com/pricing>.

| Concepto | Pricing | USD/mo |
|---|---|---|
| GitHub Team | $4/user/mo × 3 users | 12 |
| Actions privados (incluido) | 3 000 min/mo | 0 |
| Actions overage | $0.008/min Linux | ~10 (estimado uso CI/CD activo) |
| GHCR (Container Registry) | incluido en Team | 0 |
| **Subtotal** | | **~22** |

Fase 3: 5–8 users + más Actions → USD 50–80.

### 3.15 DNS / Dominio

| Servicio | Pricing | USD/mo |
|---|---|---|
| Cloudflare DNS | Free | 0 |
| Hetzner DNS | Incluido con server | 0 |
| Dominio mtme.ae (renewal) | ~USD 60 / año | ~5 |

**Subtotal**: USD ~5 / mo (dominio amortizado). Nota: dominio ya existe, MT mantiene; se incluye en línea Misc.

### 3.16 Misc

| Concepto | USD/mo |
|---|---|
| Tailscale Free (5 users SSH access) | 0 |
| Sandbox / training accounts | 5–15 |
| Dominio mtme.ae prorrateado | 5 |
| **Subtotal Misc** | **5–20** |

### 3.17 Etiquetado humano comparador (POC + steady)

Según `research-spike-product-comparison.md` v1.2:
- POC: freelance UAE 10 h/sem × $15/h × 4 sem = **USD 600 / mes** durante S2-S3.
- Steady-state Fase 1 (S4-S7): 5 h/sem × $15/h × 4 sem = **USD 300 / mes**.
- Fase 3 (3–5 validators rotando coverage 50 k SKUs): ~USD 1 500 / mes.

---

## 4. Resumen total

### 4.1 Mínimo Fase 1 (S0–S2 — desarrollo + bootstrap, sin POC ni etiquetado)

| Categoría | USD/mo |
|---|---|
| Hetzner (dev + staging + prod base) | 35 |
| Supabase Pro | 25 |
| Backups (R2 + B2) | 5 |
| Doppler Free | 0 |
| Terraform Cloud Free | 0 |
| Sentry Team | 26 |
| Better Stack Logs Starter | 25 |
| Better Stack Uptime Starter | 24 |
| Grafana Cloud Free | 0 |
| OpenAI embeddings (mantenimiento mínimo) | 2 |
| GitHub Team | 22 |
| Misc | 5 |
| **Total mínimo Fase 1** | **~169** |

> Excluye comparator R&D y etiquetado humano hasta que arranque POC en S2-S3. Excluye on-call y status page (se agregan al pasar a steady).

### 4.2 Steady-state Fase 1 (S4–S7 — todo activo, comparator en steady, etiquetado activo)

| Categoría | USD/mo |
|---|---|
| Mínimo arriba | 169 |
| Better Stack On-call + Status | 34 |
| Doppler Team (3 users) | 54 |
| Google Vision OCR | 1 |
| OpenAI / Gemini VLM judge | 25 |
| Bright Data scraping (steady) | 5 |
| Resend Free | 0 |
| Etiquetado humano comparador (steady 5 h/sem) | 300 |
| Buffer 25 % sobre técnico (USD 288 × 0.25) | ~146 |
| **Total recomendado Fase 1** | **~734** |

### 4.3 POC comparator burst (S2–S3 picos one-time)

| Categoría | USD único |
|---|---|
| Embeddings bootstrap KB + comparator | 20 |
| Bright Data POC 500 SKUs × 3 marketplaces × 3 refreshes | 30 |
| OpenAI / Gemini VLM judge POC + tie-break premium | 50 |
| Etiquetado humano POC (3 meses × USD 600) | 1 800 |
| **Total POC** | **~1 900** |

> One-time investment durante S2-S3 para validar comparador; absorbido en presupuesto Fase 1.

### 4.4 Proyección Fase 3 año 1 (50 k SKUs, marketplaces vivos, 50–100 users)

| Categoría | USD/mo |
|---|---|
| Hetzner (prod CCX23 + réplica + jobs node + storage) | 150 |
| Supabase Team | 599 |
| Backups (R2 + B2, ~300 GB activos) | 30 |
| Doppler Team (5–8 users) | 80–144 |
| Sentry Business | 80 |
| Better Stack Pro (Logs + Uptime + On-call + Status) | 200 |
| Grafana Cloud Pro | 49 |
| Google Vision OCR (50 k SKUs × refresh) | 30 |
| OpenAI embeddings + cohere fallback | 30 |
| Gemini Flash + premium tie-break | 150 |
| Bright Data (100 k req/mo) | 200 |
| Resend Scale | 90 |
| GitHub Team (8 users + Actions) | 60 |
| Etiquetado humano (3–5 validators) | 1 500 |
| Misc + buffer 30 % | 200 |
| **Total Fase 3 año 1** | **~3 258** |

---

## 5. Costos one-time (no mensual)

| Concepto | USD | Quién paga | Cuándo |
|---|---|---|---|
| Setup inicial Hetzner + Supabase + Doppler | incluido en SP Sprint 0 | BR Innovation (mano de obra) | S0 |
| Renovación dominio mtme.ae | ~60 / año | MT (ya existe) | anual |
| Penetration test externo opcional pre-cutover | 3 000–8 000 | MT (si ARM lo exige) | pre-go-live Fase 1 |
| Auditoría compliance VAT UAE (legal) | 2 000–5 000 | MT | Fase 1 |
| DPO consultant externo (si MT no tiene FTE) | 3 000–10 000 / año | MT | continuo |
| Capacitación key users MT (10 h × $50/h) | 500 | BR (incluido en SP) | S6-S7 |

---

## 6. Costos NO incluidos en este estimate (responsabilidad MT)

- Mano de obra desarrollo BR Innovation (factura aparte por SP / sprint).
- Hardware del equipo dev y operadores MT.
- Licencias Office 365 / Google Workspace MT.
- Material de training producción MT.
- Marketing / comms del rollout interno.
- Costos legales MT (DPA con BR, DPO, compliance UAE PDPL, ARM compliance).
- Certificaciones SOC2 / ISO 27001 si MT las exige (no contemplado en Fase 1).

---

## 7. Recomendación de cap presupuestal

| Escenario | Cap mensual USD | Buffer | Frecuencia revisión |
|---|---|---|---|
| Fase 1 mínimo desarrollo | 200 | 20 % | Mensual |
| Fase 1 recomendado (steady-state) | 850 | 25 % | Mensual |
| POC comparator (S2-S3) | 1 500 picos puntuales | n/a | Por POC |
| Fase 2 transición | 1 500 | 25 % | Mensual |
| Fase 3 año 1 | 3 500 | 30 % | Mensual + alerta 80 % |

**Política de revisión**:
- Revisión obligatoria mes 4 para confirmar tier Supabase y on-call.
- Alerta automática Grafana cuando USD acumulado del mes > 80 % del cap.
- Re-baseline cada cierre de fase (S2 → S4 → S7).

---

## 8. Triggers de upgrade tier

| Servicio | De | A | Trigger |
|---|---|---|---|
| Supabase | Pro | Team | MAU > 50 k, DB > 8 GB, o requisito residencia/SSO compliance UAE |
| Sentry | Team | Business | errors > 50 k/mo, transactions > 100 k/mo, SAML requerido |
| Better Stack Logs | Starter | Pro | ingest > 30 GB/mo o retention > 30 días requerida |
| Doppler | Free | Team | > 1 user con acceso a producción |
| Grafana Cloud | Free | Pro | metrics active series > 10 k o retention > 14 días |
| Resend | Free | Pro | > 3 000 emails/mo o > 100/día |
| Hetzner | CX42 shared | CCX23 dedicated | CPU steal > 5 % sostenido o requisitos SLA estrictos |
| GitHub | Team | Enterprise | SAML, audit log retention, IP allowlist requeridos |
| Bright Data | Web Scraper pay-per-success | Residential proxy | Bloqueo > 30 % en Amazon UAE/Noon UAE |

---

## 9. Cost monitoring & alerting

- **Dashboard Grafana custom** con costo agregado por categoría (vía exporters / scrapes de billing API de cada provider donde sea posible: OpenAI usage API, Hetzner API, Supabase usage endpoint).
- **Alertas presupuestales**:
  - Hetzner billing notification ≥ EUR 50/mo.
  - Supabase email warn al 80 % de límites (DB/Storage/MAU).
  - OpenAI usage cap (hard limit) en USD 50/mo Fase 1, USD 200 Fase 3.
  - Bright Data alerta al 80 % de presupuesto mensual.
- **Review mensual** con Sponsor MT (template fijo, comparativa vs cap).
- **KPIs**:
  - USD / SKU activo / mes (target Fase 1: < USD 0.20).
  - USD / validación humana (target: < USD 1.50).
  - USD / 1 000 LLM calls (target: < USD 10 con Gemini Flash).
  - USD / 1 000 scraping reqs (target: < USD 2).

---

## 10. Optimizaciones futuras (Fase 1.5+)

- **Migrar embeddings a SigLIP self-host** sobre Hetzner CCX dedicado (ahorra USD 5–20 / mes en bursts grandes; cuesta ~10 h/mes de ops).
- **Reservar instancias Hetzner** anuales si se crece a multi-server (CCX dedicated): ahorro ~30 % vs mensual.
- **Self-host Grafana + Prometheus** sobre Hetzner si Free tier insuficiente (ahorra subscription Pro pero suma horas ops; analizar break-even mes 18).
- **Negociar enterprise pricing Supabase** si volumen Fase 3 lo justifica (Team @ $599 → contrato anual con descuento 15–20 %).
- **Mover scraping a self-host con Playwright + residential proxies de mercado abierto** si Bright Data > USD 300 / mo sostenido.
- **Cohere Embed v3 como primario** (~25 % más barato que OpenAI text-embedding-3-large) si la calidad para árabe/inglés UAE resulta equivalente.
- **Switch a Postmark** si Resend bounce rate degrada reputación UAE.

---

## 11. Cuestiones abiertas

| # | Pregunta | Owner | Decisión esperada |
|---|---|---|---|
| Q1 | ¿Cap mensual definitivo firmado por Sponsor MT? | Sponsor MT | S0 |
| Q2 | ¿Tier Supabase definitivo Fase 1 — Pro vs Team? Depende de exigencia de residencia UAE PDPL y SSO. | Sponsor + DPO MT | S1 |
| Q3 | ¿MT cubre infra directamente (cuenta Hetzner/Supabase a nombre MT) o BR Innovation factura todo? | BR Finance + MT Procurement | S0 |
| Q4 | Política de chargeback de costos LLM/scraping al cliente vs incluido en mantenimiento mensual fijo. | BR Comercial | S2 |
| Q5 | ¿On-call y Status Page Better Stack obligatorios desde S0 o se difieren a S4? | PM + Sponsor | S0 |
| Q6 | ¿Etiquetado humano POC contratado por BR (factura) o por MT (FTE temporal)? Impacta visibilidad fiscal y AED vs USD. | MT HR + BR PM | S2 |

---

## 12. TODOs verificación pricing 2026

- **TODO** verificar pricing Hetzner Cloud 2026 (CX22 / CX42 / CCX13). Página oficial 2025 → 2026 sin cambio publicado, pero confirmar con sales rep antes de firmar cap.
- **TODO** verificar pricing Doppler Team 2026 ($16 vs $18 vs nuevo tier por user).
- **TODO** verificar uplift Bright Data 2026 si ARM/PDPL UAE clasifica scraping de retailers locales como categoría restringida (residential proxy + compliance).

---

**Notas finales**

- Toda cifra mensual incluye margen ±20 % implícito.
- El item dominante del cost recomendado Fase 1 es **etiquetado humano** (USD 300/mo, 41 % del total). Si MT proporciona etiquetadores in-house en lugar de freelance externo, total Fase 1 baja a ~USD 434.
- El crecimiento crítico a vigilar es **Bright Data** y **Supabase** entre Fase 2 y Fase 3.
