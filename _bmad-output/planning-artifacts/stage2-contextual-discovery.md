# Etapa 2 — Contextual Discovery (MT Middle East)

Salida consolidada de los subagentes Artifact Analyzer + Web Researcher.
Fecha: 2026-05-06.
Producto en foco: Plataforma digital MT Middle East — Fase 1 (Master Data + Pricing Intelligence).

---

## A. Hallazgos del Artifact Analyzer

### Documentos analizados
| Path | Relevancia |
|------|------------|
| `MT_Middle_East_Documento_Maestro (1).docx` | Documento maestro: programa completo (Shopify + Supabase + Make.com), 10 capacidades, 11 workflows F01-F11. La herramienta de pricing es **un componente** dentro de la visión global. |
| `MT_Pricing_Run_Kit/PASOS.md` | Runbook operador demo v4: instalación, ProtonVPN UAE, scraper, troubleshooting. |
| `MT_Pricing_Run_Kit/run_full_v51.sh` | Orquestador pipeline: preflight → scraper (224 refs, ~90 min) → enrich v5.1 → HTML build. |
| `build_html_v23.py` | Genera HTML monolítico con Chart.js + SheetJS. Vistas: Dashboard / Validación / Reporting / Metodología. |
| `enrich_with_v51.py` | Motor de pricing v5.1 + Excel master loader + delivery parser → `pricing_v51` por SKU. |
| `preflight.py` | Pre-checks (Python, deps, Chrome/Driver, IP UAE, archivos requeridos). |
| `data/validator_data_v4.json` | Output scraper: 224 refs (codigo, sku_upper, familia_ficha, nombre_en, subfamilia, familia, grupo G1/G2, coste_aed, image_url_pim, candidates Amazon UAE). |
| `data/sku_to_ficha_mapping.json` | Mapping SKU → familia ficha; 7 diccionarios de agrupación. |
| `data/run_summary_v4.json` | KPIs run: 224 totales, T0_PEGLER 153 / T0_ARCO 7 / NONE 34, high_score 38, no_match 34. |
| `data/stock_dubai_v23_PRESENTACION_2026-05-01.xlsx` | Excel maestro con sheets: Resumen Ejecutivo, INVOICE ENRIQUECIDA v5, REAL STOCK DUBAI INVOICE, Amazon UAE 30%, Noon UAE 30%, B2B MT 40%, Tarifas FBA & FBM, PIM Maestro, Competidores, Mercado & Inversión. **TC 1 EUR = 4.29 AED.** |
| `src/` | 13+ módulos Python: amazon_ae_pricer_v4, search_builder_v4, match_scorer_v2, extractor_pdp, extractor_competitive, extractor_v51, pricing.py (26KB), mt_excel_loader, browser, config, competitors.json. |
| `MT_Pricing_Intelligence_v4.html` | Demo (~6MB) — hero sections + Validación humana asistida + Reporting + Metodología. Título: "MT Middle East · Pricing Intelligence". |

### Insights clave
- **Pricing Intelligence es Fase 1 de un programa más amplio** (B2C + B2B + Amazon UAE / Noon). Stack ya decidido en master doc: Shopify Advanced + Supabase + Make.com + pgvector + WhatsApp.
- **Pipeline demo actual = 4 pasos secuenciales (~95 min)**: preflight (1m) → Selenium scraper Amazon.ae con ProtonVPN UAE (90m) → enrichment con motor v5.1 + Excel master (1m) → HTML estático single-file (build_html_v23.py).
- **Motor pricing v5.1** entrega por SKU: `pvp_aed`, `pvp_eur`, `pvp_min`, `total_costes`, `rule_applied`, `formula`, `margin_pct`, `breakdown`, `alerts` (critical/warnings), `delivery_advantage_days`, `n_from_china`, `n_from_uae`, `canal_recomendado`, `estado_fba_excel`.
- **Catálogo = 224 referencias**, marcas Pegler (153), Arco (7), Giacomini (1), Apollo (2), Nibco (1). Tiers de fallback: T0 brand → T2 técnico → T3 funcional → T4 product_name → T5 fallback → NONE.
- **Demo HTML** = 4 vistas (Dashboard, Validación, Reporting, Metodología) con hero images base64, Chart.js, SheetJS export, filtros por regla, lista de alertas, badges de delivery (UAE rocket / China turtle).
- **Master doc propone reemplazar `match_scorer_v2.py` por SQL nativo Supabase + pgvector** (workflow F04: Match semántico SKUs MT vs Amazon UAE).
- **Idioma**: trabajo en español; catálogo necesita `name_es / name_en / name_ar` para mercado UAE multilingüe.
- **Demo es frágil**: corre local en Mac con venv + ProtonVPN. Selenium con CAPTCHA / IP bans. **No productionizable en su forma actual.**

### Contexto usuarios / mercado
- **Empresa**: MT Middle East (Dubái/UAE) — hermana de **MT Valves España** (Pallejà, España). Excel header: "BR Dynamic Dubai × MT Valves España — Amazon UAE & Mercados Vecinos".
- **Tres canales objetivo**: B2C end customer / B2B distribuidores Modern Trade (40% stock) / Amazon UAE (30%) + Noon UAE (30%).
- **Dominio producto**: hidrosanitario + válvulas industriales (compuerta, bola, retención, latón Carlas + empotrar). Specs: DN, PN, material (brass, ss316, ss304), tipo, familia.
- **Competencia Amazon UAE** whitelisted: Pegler, Arco, Giacomini, Apollo, Nibco. `competitors.json` editable.
- **Stakeholders**: Christian (sponsor ejecutivo — "Decisión solicitada a Christian"), Paula (validador técnico — "Para Paula" anexo técnico). Operador: Pablo Sierra (psierra@br-innovation.com).
- **Mercado**: UAE primario, GCC vecinos. Metodología fechada abril 2026.

### Contexto técnico
- **Stack demo actual**: Python 3 + Selenium 4.6+ + Chrome + ProtonVPN (UAE) + bs4/lxml + openpyxl + python-pptx; SheetJS + Chart.js + Barlow embebido.
- **Modelo de datos scraper**: refs[] con codigo, sku_upper, familia_ficha, nombre_en, subfamilia, familia, grupo G1/G2, coste_aed, image_url_pim, previous_query, candidates[] (position, asin, title, price_aed, image_url, product_url, score, delivery_estimate, prime_eligible, delivery_origin, delivery_days_min/max, seller, rating, competitor_brand, pdp_specs).
- **Excel master = source of truth** de costes/precios: TC EUR/AED auto-update via VBA, INVOICE ENRIQUECIDA v5, FBA/FBM tariff sheet, `pvp_min`, `costes_desglosados`, `canal_recomendado`, `qty_invoice`, `valor_stock_aed`, `margen_fba_excel`, `roi_fba_excel`, `estado_fba_excel`.
- **Arquitectura objetivo (master doc)**: Shopify Advanced ($399/mo) + Supabase (Postgres + pgvector + pg_net + pgmq + Edge Functions) + Make.com orquestador + OpenAI text-embedding-3-small (1536-dim, HNSW) + WhatsApp Business + Telr/Tabby + Marketplace Connect (Amazon).
- **Schema Supabase propuesto**: `products` (sku, name_es/en/ar, family, dn, type, material, pn, specs JSONB, cost_eur, price_aed, stock_tier, embedding VECTOR(1536), embedding_at, active) + `amazon_listings` (asin, title, brand, price_aed, seller, fba, bsr, matched_sku→products.sku, match_score, embedding, scraped_at).
- **Embedding template**: `${name_en} | ${type} ${material} DN${dn} PN${pn} | ${family} | ${specs}`.
- **Tiers match v4**: T0 brand → T2 técnico → T3 funcional → T4 product_name → T5 fallback → NONE; thresholds high≥60 / med 40-60 / low <40.

### Decisiones (master doc)
| Decisión | Estado | Rationale |
|----------|--------|-----------|
| Shopify Advanced vs BigCommerce/WooCommerce/Medusa | Aceptado | Mejor coste/tiempo, B2B nativo en 2026 (antes Plus-only) |
| Supabase + pgvector reemplaza Algolia + recomendador + chatbot | Aceptado | Ahorra $130-450/mo consolidando search + reco + chat en Postgres |
| Make.com como orchestration de 11 workflows | Aceptado | PIM MT España single source; Supabase normaliza; Shopify+Amazon canales |
| OpenAI text-embedding-3-small via Supabase automatic embeddings | Aceptado | Async no-blocking, HNSW para <1M filas |
| Reemplazar match_scorer_v2.py por SQL pgvector (F04) | Aceptado | Match semántico más preciso que reglas tier-keyword |
| Bundling psicológico (XX,99 / XX,49 AED) + aprobación humana >10% cambio | Aceptado | F03 dynamic pricing |
| Scraping Amazon.ae directo Selenium + ProtonVPN | **Abierto** | Funciona demo, frágil prod (CAPTCHA, IP bans). Master implica reemplazo eventual por Supabase ingestion programada. |
| Shopify B2B Advanced ($399) vs Shopify Plus ($2300) | Aceptado | Paridad features 2026 |

### Datos a preservar
- 224 refs, run 2026-05-04 06:16:55. Tier breakdown: T0_PEGLER=153, T0_ARCO=7, T2_technical=14, T3_functional=8, T4_product_name=2, T0_APOLLO=2, T5_fallback=2, T0_GIACOMINI=1, T0_NIBCO=1, NONE=34. high_score(≥60)=38, no_match=34.
- TC abril/may 2026: **1 EUR = 4.29 AED**.
- Costes transacción: Telr 2.49% + AED 0.50; Shopify 3rd-party gateway 0.6% (Advanced); Tabby BNPL ~6% (compensa +20-40% AOV); Marketplace Connect Amazon 1%/order capped $99/mo. **Total típico B2C ~3.5-4%.**
- Sheets Excel completos: Resumen, INVOICE ENRIQUECIDA v5, LEYENDA v22, REAL STOCK DUBAI INVOICE, Resumen Ejecutivo Plan Comercial UAE, Amazon UAE 30%, Noon UAE 30%, DUBAI STOCK ORDER P&L FBA/FBM, B2B MT 40%, Metodología & Estrategia GCC, Investigación PVP, Tarifas FBA & FBM, Noon.com UAE, Competidores, Análisis Competitivo, Mercado & Inversión UAE/GCC, Glosario, Macro VBA, PIM Maestro, PIM IDIOMAS, PIM + Catálogo MERGED.
- F01 sync detail: Make.com pull PIM via HTTP/SFTP, MD5 deltas, valida sku/dn/material/type, UPSERT Supabase, embedding NULL en cambio relevante, pgmq queue, Edge Function worker → OpenAI, Slack summary. Query objetivo: "válvula compuerta para gasoil DN50".

---

## B. Hallazgos del Web Researcher

### Perfil de la empresa
- **mtme.ae actualmente parked/inactive** en plataforma Sitebeat (HTTP 301 a `.sitebeat.site`, certificado SSL expirado). **Sin contenido público.**
- **Sin verificación tercera** en D&B / Arabian Business / directorios UAE. Industria/vertical exacto debe confirmar el stakeholder.
- **Inferencia desde artefactos**: distribución mayorista en Dubái con catálogo multi-SKU que requiere validación precio↔stock; verticales sugeridas hidrosanitario / válvulas industriales (consistente con análisis interno).
- **Modelo probable**: B2B distribución (wholesale-to-retail / distributor-to-distributor); B2C y marketplaces no descartados.

### Landscape competitivo
- **Pricefx** — suite enterprise pricing cloud-native (price setting, optimization, CPQ). Gap: caro, complejo, weak MENA/Arabic localization.
- **Vendavo** — B2B price/margin optimization para grandes manufacturers/distributors. Gap: implementación lenta, no SKU-vs-stock, sin referencias MENA.
- **Competera / Pricer24 / Intelligence Node** — monitoring competitivo retail/e-commerce + dynamic pricing AI. Gap: sólo precios públicos web; no consume stock master ni reconcilia feeds proveedor.
- **Prisync / PriceShape / Omnia** — competitor monitoring SMB. Gap: sólo scraping; sin MAP enforcement multi-distribuidor; sin VAT UAE / HS-codes.
- **Tradeling + Excel + WhatsApp** — status quo MENA. Gap: sin source of truth, drift de versiones, sin audit trail, error-prone para re-export.

### Contexto mercado
- **UAE e-commerce**: USD 12.3B (2026) → USD 21.0B (2031).
- **UAE B2B e-commerce**: ~19.5% CAGR hasta 2030. >80% empresas UAE planean aumentar tooling digital.
- **Pricing AI B2B**: McKinsey 2026 — >50% pricing leaders citan calidad/integración de datos como blocker top.
- **Regulación**: e-invoicing UAE phased rollout; Aani instant-payment >53% wallets early 2026 — **fuerza limpieza de SKU/price master data.**
- **66% buyers UAE B2B esperan pricing personalizado / contractual** — empuja governed price intelligence vs price lists estáticas.

### Sentiment usuarios
- "Excel pricing slow and error-prone with domino effect of margin loss" (distributionstrategy.com).
- Multi-currency + freight + customs + impuestos = top friction MENA/GCC con feeds AED/USD/SAR/EUR mixtos.
- **MAP/MSRP enforcement se rompe en sub-distribuidor**; brands recolectan violations sin workflow de acción.
- **Feeds proveedor en formatos inconsistentes** (CSV, Excel, PDF, email), missing SKUs, currency drift, lag — reconciliación manual recurrente.
- **Mid-market gap real**: enterprise (Pricefx/Vendavo) too expensive; monitoring-only (Prisync/Competera) no resuelve SKU/stock interno.

### Timing & oportunidad
- **UAE VAT amendments efectivas 1-Ene-2026**: anti-evasión, ventana 5 años, removal self-invoicing reverse charge → tighten SKU/price/invoice quality. **Buying window.**
- **E-invoicing phased UAE** = structured data no-opcional.
- **AI/LLM-based parsing** de feeds heterogéneos ahora barato (capability inexistente cuando se diseñaron suites legacy).
- **Mid-market gap UAE** entre Excel y Pricefx/Vendavo: 1k-50k SKUs multi-currency re-export — Fase 1 puede ocupar el espacio.
- **Tradeling y similares MENA crecen ~35% MoM** → demanda de price intelligence interno limpio para publicar.

### Riesgos
- UAE VAT 2026 amplía facultad FTA para denegar input-VAT en cadenas "connected to evasion" → datos auditables y reconciliados; tool debe preservar provenance.
- **Re-export GCC**: tratamiento 0% VAT, HS-code accuracy, end-use checks; sanctions screening (OFAC/EU/UK) para flujos Iran/Russia-adjacent.
- **Calidad feeds proveedor = blocker dominante** (>50% fallos pricing-AI). Tool depende de parsers tolerantes + anomaly detection + human-in-the-loop.
- **Volatilidad multi-currency** (AED peg vs EUR/USD/SAR/EGP) + freight/fuel surcharges invalidan price files en horas → timestamp + version cada price point.
- **Riesgo competitivo**: SAP / Oracle / Dynamics empujan AI-pricing copilots en ERP que distribuidores Dubái ya corren → comoditiza standalone pricing tool a menos que diferencie en MENA-specific (árabe, AED, GCC re-export, MAP enforcement multi-reseller).
- **Riesgo identidad**: mtme.ae actualmente parked Sitebeat con SSL expirado. Credibilidad externa requiere arreglar la web corporativa antes de cualquier componente customer-facing.

---

## C. Aclaraciones del usuario (capturadas durante esta etapa)

1. **MT** = MT Middle East (empresa). Dominio `mtme.ae`.
2. **Programa multi-componente, Fase 1** = la primera herramienta a desarrollar; el programa crece después.
3. **Demo HTML** = **prueba de concepto a evolucionar** (no a descartar, no a respetar UI literal).
4. **Usuario final Fase 1** = **personal interno de MT** (uso interno, no clientes externos en esta fase).
5. **Alcance Fase 1 redefinido por el usuario**: cubrir **data maestra (PIM-like) — artículos, proveedores, precios**.
6. **Fase 2**: inventarios, facturación, costos.
7. **Visión completa ciclo ecommerce externo**: arranca con **B2C + marketplaces (Amazon, Noon)**, termina en **B2B**.

---

## D. Síntesis y gaps

### Reframing del alcance Fase 1
La aclaración del usuario **redefine el alcance Fase 1** respecto a lo que sugería el demo: la herramienta de Pricing Intelligence v4 es un **input** (prueba de concepto a evolucionar) pero **Fase 1 es más amplia**: **plataforma de datos maestros** (artículos + proveedores + precios), interna, que sienta cimientos para todo el ciclo posterior.

### Gaps a cerrar en Etapa 3 (guided elicitation)
1. **Roles internos MT que usan la plataforma** — ¿comercial, compras, finanzas, IT? ¿uno o varios? ¿quién aprueba precios?
2. **Workflows críticos día-1** vs nice-to-have — ¿qué dolores resuelve YA en sprint 1 (alta SKU, carga proveedor, recálculo precio, export a Excel/Shopify)?
3. **Origen real de datos hoy** — ¿Excel master `stock_dubai_v23` es la única fuente, o también ERP/PIM España? ¿proveedores cómo entregan?
4. **Definición de "proveedor"** — ¿solo MT Valves España, o múltiples upstream? ¿precios contractuales o spot?
5. **Pricing engine v5.1 — ¿qué evolucionar?** ¿se mantiene la lógica G1/G2 + reglas + alertas, o se redefine?
6. **Métricas de éxito Fase 1** — ¿qué prueba que la herramienta funciona? (tiempo carga SKU, cero discrepancias, cobertura catálogo, etc.)
7. **MVP boundary** — ¿qué SE QUEDA AFUERA de Fase 1 que sí está en master doc? (scraper Amazon, embeddings pgvector, Make.com, Shopify, WhatsApp).
8. **Stack Fase 1** — ¿se adopta YA Supabase + Postgres como sustrato, o se acepta arrancar con Excel-as-backend hasta Fase 2?
9. **Timeline objetivo** Fase 1 — sprint, mes, trimestre.
10. **Stakeholders aprobadores** — Christian + Paula confirmados; ¿algún otro?

### Sorpresas vs hipótesis del usuario
- **mtme.ae no tiene web operativa**. Antes de cualquier componente customer-facing (Fase 3+) hay que arreglar identidad digital.
- **El alcance Fase 1 (PIM/MDM) es estratégicamente más sólido que sólo el pricing tool** — el demo demuestra valor pero sin master de datos limpio el pricing es frágil.
- **Catálogo declarado = 224 refs**, marca dominante Pegler (68%). Catálogo pequeño → MVP viable rápido. Pero Excel master tiene PIM IDIOMAS y muchas sheets → ya hay PIM embrionario en Excel.
- **34 SKUs sin match (15%) y 34 NONE en tier**: hay ~15% del catálogo que el sistema actual no resuelve → caso de prueba para validar el nuevo PIM.
