---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments:
  - "_bmad-output/planning-artifacts/adr/ADR-070-bright-data-scraping-policy.md"
  - "_bmad-output/planning-artifacts/adr/ADR-071-playwright-self-host-noon.md"
  - "_bmad-output/planning-artifacts/adr/ADR-072-amazon-sp-api-integration.md"
workflowType: 'research'
lastStep: 6
research_type: 'technical'
research_topic: 'Amazon UAE Scraping 2025-2026: Python Tools vs AI Browser Agents'
research_goals: 'Evaluar opciones para reemplazar Bright Data con solución in-house controlada para extraer ASIN, título, precio AED, marca, imágenes y specs técnicas de Amazon UAE (~500-1000 SKUs, refresco semanal/diario)'
user_name: psierra
date: '2026-05-13'
web_research_enabled: true
source_verification: true
---

# Investigación Técnica: Amazon UAE Scraping 2025-2026
## Python Tradicional vs Agentes de Browser con IA

**Fecha:** 2026-05-13
**Autor:** psierra
**Tipo:** Technical Research

---

## Resumen Ejecutivo

Esta investigación evalúa las opciones técnicas para extraer datos de productos de Amazon UAE (`amazon.ae`) en el contexto del proyecto br-mt-ecommerce. El análisis considera el contexto existente (ADR-070 usa Bright Data como adapter oficial) y evalúa si tiene sentido migrar a una solución in-house.

**Conclusión anticipada:** Para Amazon UAE específicamente, ninguna solución in-house open-source supera de forma confiable las defensas anti-bot de Amazon en 2025-2026 sin proxy residencial. La decisión de ADR-070 (Bright Data) sigue siendo técnicamente sólida. Sin embargo, existen alternativas más económicas que merecen evaluación según el volumen real del proyecto.

---

## 1. El Problema: Amazon UAE Anti-Bot en 2025-2026

### 1.1 Capas de Defensa de Amazon

Amazon implementa las defensas anti-bot más sofisticadas del ecosistema e-commerce, operadas sobre **AWS WAF Bot Control** (modo "Targeted Bots"):

| Capa | Mecanismo | Efectividad |
|------|-----------|-------------|
| **IP reputation** | Bloquea datacenters (Hetzner, AWS, GCP) de inmediato | Alta |
| **TLS/JA3 fingerprinting** | Detecta clientes no-browser por su TLS handshake | Alta |
| **CDP detection** | Detecta uso del Chrome DevTools Protocol (Playwright, Selenium) | Alta (2024+) |
| **Browser fingerprinting** | Canvas, WebGL, fonts, navigator.webdriver | Muy Alta |
| **Behavioral scoring** | Patrones de scroll, timing, mouse, cadencia de requests | Alta |
| **CAPTCHA adaptativo** | Se activa cuando el scoring supera umbral | Muy Alta |
| **Proxy detection ML** | Detecta y bloquea residential proxies conocidos (2023+) | Media-Alta |

**Dato crítico:** Desde septiembre 2023, AWS WAF Bot Control para "Targeted Bots" añadió protección específica contra **distributed proxy-based attacks**, incluyendo residential y mobile proxies. Amazon usa estas reglas para amazon.ae.

### 1.2 Resultado Práctico para Scrapers DIY

- `httpx`/`requests` simples desde IP datacenter: **bloqueados al 100%** (verificado)
- Playwright headless sin stealth desde IP datacenter: **bloqueados en <1 min**
- Playwright + stealth plugins desde datacenter: **bloqueados en 5-15 min** (behavioral scoring)
- Camoufox/Patchright + datacenter IP: **bloqueados** (Amazon CAPTCHA gate activo)
- Playwright + residential proxy sin stealth: **variable, ~40-60% success**
- Playwright + residential proxy + stealth: **~60-75% success** (no confiable para producción)
- Bright Data Web Scraper API: **~98.44% success** (benchmark independiente 2026)

---

## 2. Evaluación de Herramientas Python Tradicionales

### 2.1 `httpx` + `BeautifulSoup` / `selectolax`

**Descripción:** Cliente HTTP asíncrono + parser HTML. Sin rendering JavaScript.

| Aspecto | Evaluación |
|---------|-----------|
| Viabilidad Amazon UAE | ❌ Inviable sin proxy residencial premium |
| Velocidad | ✅ Muy rápida (~50-200ms/request) |
| Costo infraestructura | ✅ Mínimo |
| Mantenimiento | ⚠️ Alto (parsers frágiles ante cambios DOM) |
| TLS fingerprint | ⚠️ Detectable (JA3 default httpx ≠ Chrome) |

**Con `curl_cffi`** (reemplaza httpx): mejora el TLS fingerprint impersonando Chrome/Firefox exactamente (BoringSSL/NSS), pero no resuelve IP reputation ni behavioral scoring. Logra ~80% en sitios protegidos por Cloudflare básico; Amazon es otro nivel.

**Veredicto:** Solo viable como **fallback de última instancia** con proxy residencial. No recomendado como solución principal para Amazon UAE.

### 2.2 Scrapy + Playwright/Splash

**Descripción:** Framework completo de crawling async + rendering JavaScript bajo demanda.

| Aspecto | Evaluación |
|---------|-----------|
| Viabilidad Amazon UAE | ⚠️ Posible con middleware proxy residencial |
| Escalabilidad | ✅ Excelente para volumen alto (>10K páginas/día) |
| Costo desarrollo | ⚠️ Alto (pipeline complejo, middleware stealth) |
| Mantenimiento | ⚠️ Alto (cambios DOM + anti-bot updates) |
| Integración Celery | ✅ Compatible pero redundante con Celery existente |

**Veredicto:** Sobredimensionado para 500-1000 SKUs/semana. La potencia de Scrapy no compensa el costo de mantenimiento del anti-bot layer para este volumen.

### 2.3 `playwright-stealth` + Chromium

**Descripción:** Playwright headless con patches de fingerprint (puerto de `puppeteer-extra-plugin-stealth`).

| Aspecto | Evaluación |
|---------|-----------|
| Viabilidad Amazon UAE | ⚠️ Limitada (40-60% con residential proxy) |
| Detección CDP | ❌ Vulnerable a CDP detection (Amazon activo 2024+) |
| Mantenimiento stealth | ❌ Muy alto (Amazon actualiza detecciones frecuentemente) |
| Patchright (alternativa) | ⚠️ Mejor que stealth base, pero no prueba Amazon |

**Ya implementado en proyecto:** ADR-071 usa Playwright para Noon UAE (anti-bot menos agresivo). El propio ADR-071 nota: "Si Noon agrega CAPTCHA persistente, escalar a Bright Data". Amazon tiene defensas 5-10x más agresivas que Noon.

**Veredicto:** No recomendado para Amazon UAE como solución standalone. El overhead de mantenimiento de stealth para Amazon es alto y la confiabilidad es insuficiente para producción.

### 2.4 `undetected-chromedriver`

**Descripción:** ChromeDriver parchado que evita señales básicas de detección.

| Aspecto | Evaluación |
|---------|-----------|
| Mantenimiento 2025 | ⚠️ Proyecto menos activo, sucedido por Patchright/Nodriver |
| CDP detection bypass | ⚠️ Parcial (Nodriver/Patchright son superiores) |
| Integración Python async | ❌ Principalmente síncrono |
| Amazon UAE | ❌ No suficiente sin proxy residencial |

**Veredicto:** Tecnología legacy en 2025. Reemplazado por Camoufox/Patchright para casos de uso similares.

---

## 3. Evaluación de Agentes de Browser con IA

### 3.1 `browser-use` (Python)

**Descripción:** Librería Python open-source que permite a LLMs controlar un browser Playwright. El LLM navega, interactúa y extrae datos basado en instrucciones en lenguaje natural.

**Estado 2025-2026:**
- BU 2.0 lanzado: +12% accuracy (74.7% → 83.3%), ~62s promedio por tarea
- Modelo `bu-ultra` disponible vía Browser Use Cloud: 78% accuracy en benchmark
- Open source: gratis + costos LLM del proveedor elegido

| Aspecto | Evaluación |
|---------|-----------|
| Anti-bot bypass Amazon | ❌ Usa Playwright internamente → mismas limitaciones |
| Costo por extracción | ❌ Alto: $0.01-0.10/página (LLM tokens) |
| Latencia | ❌ 30-120s por producto (inaceptable para 1000 SKUs) |
| Robustez DOM changes | ✅ Excelente (LLM semántico, no selectores frágiles) |
| Integración Python/Celery | ✅ Compatible (Python nativo) |
| Caso de uso ideal | Automatización de formularios, flujos complejos |

**Análisis de costo para 1000 SKUs/día:**
- 1000 páginas × ~$0.05 promedio (tokens GPT-4o) = **$50/día = $1,500/mes**
- Vs Bright Data: ~$30-50/mes total para este volumen
- Vs Scrapfly/ScraperAPI: ~$15-50/mes

**Veredicto:** browser-use NO es una herramienta de scraping de alto volumen. Es un agente de automatización. Para extracción de 1000 productos es **50-100x más caro** que APIs de scraping especializadas y significativamente más lento. Solo considerarlo para flujos de navegación complejos que no pueden ser hardcodeados.

### 3.2 Stagehand (TypeScript + Browserbase)

**Descripción:** Framework TypeScript de Browserbase que combina Playwright tradicional con acciones LLM opcionales (`extract()`, `act()`, `observe()`). Stagehand v3 usa arquitectura CDP-nativa (eliminó dependencia Playwright), 44% mejora en DOM interactions complejas.

| Aspecto | Evaluación |
|---------|-----------|
| Lenguaje | ❌ TypeScript (proyecto es Python) |
| Anti-bot bypass | ⚠️ Browserbase ofrece stealth + proxies gestionados |
| Costo Browserbase | ❌ $50-200/día para 10K extracciones |
| Costo LLM adicional | ❌ Por cada `extract()` con LLM |
| Robustez | ✅ Mejor que Playwright puro para layouts cambiantes |
| Integración stack | ❌ Requiere runtime Node.js |

**Veredicto:** Descartado por incompatibilidad de stack (TypeScript vs Python) y costo elevado de Browserbase para el volumen objetivo.

### 3.3 AgentQL

**Descripción:** Query language semántico + SDK Python/JS para extracción estructurada web. En lugar de XPath/CSS, se usan queries en lenguaje natural: `{ products[] { name price(integer) brand specifications[] } }`. Motor AI interpreta semánticamente el DOM.

**Estado 2025-2026:**
- SDK Python disponible + REST API + browser debugger
- Integra con Playwright (como extension)
- Resultados deterministas (no varía por sesión como LLMs generativos)
- ScrapeGraphAI vs AgentQL: ambos compiten en el espacio "AI-powered structured extraction"

| Aspecto | Evaluación |
|---------|-----------|
| Anti-bot bypass Amazon | ❌ Usa browser subyacente → mismas limitaciones |
| Calidad de extracción | ✅ Alta (semántico, adapta a cambios DOM) |
| Costo | ⚠️ API de pago para producción; precio no publicado |
| Latencia | ⚠️ ~2-5s por página (mejor que browser-use) |
| Integración Python | ✅ SDK Python oficial |
| Caso de uso ideal | Extracción estructurada en páginas con DOM cambiante |

**Veredicto:** AgentQL resuelve el problema de **parsing robusto** pero no el problema de **anti-bot bypass de Amazon**. Podría ser útil como capa de parsing sobre un proxy service, pero no reemplaza la infraestructura de evasión.

### 3.4 Skyvern

**Descripción:** Agente de automatización web con LLM + computer vision. Usa modelos visuales para entender páginas sin DOM scraping. Open source + cloud.

| Aspecto | Evaluación |
|---------|-----------|
| Costo cloud | ⚠️ $0.10/step; tareas complejas = $0.50-2.00/producto |
| Costo open-source | ✅ Gratis (self-host, pagas LLM) |
| Anti-bot bypass | ❌ No resuelve Amazon WAF |
| Velocidad | ❌ Lento para volumen alto |
| Caso de uso ideal | Formularios, flujos complejos multi-paso |

**Veredicto:** Orientado a automatización de flujos (RPA replacement), no scraping de catálogo. No apto para extracción masiva de Amazon.

### 3.5 Playwright MCP (Model Context Protocol)

**Descripción:** Servidor MCP que expone Playwright como herramienta para LLMs en Claude/Cursor. Permite a Claude Code controlar un browser.

| Aspecto | Evaluación |
|---------|-----------|
| Caso de uso | Automatización interactiva asistida por LLM |
| Anti-bot bypass | ❌ No aporta nada adicional |
| Integración producción/Celery | ❌ No diseñado para workers batch |
| Costo | ✅ Gratis (usa browser local) |

**Veredicto:** Herramienta de desarrollo/exploración, no de producción para scraping batch.

---

## 4. Soluciones Híbridas: Python + LLM para Parsing

La combinación más prometedora NO es "LLM para navegar" sino **"proxy API para bypassear anti-bot + LLM/AI para parsear estructuradamente"**:

### 4.1 Patrón Recomendado: Proxy API + Parser Semántico

```
Celery Worker → Proxy API (Bright Data/Scrapfly/ScraperAPI)
                    → HTML crudo
                    → Parser semántico (selectolax + reglas explícitas)
                    → DTO estructurado (ASIN, precio, specs, imgs)
```

**Por qué no LLM para parsing en producción:**
- Amazon HTML es altamente estructurado y predecible (ASIN en URL, precios en spans específicos)
- LLM parsing: $0.001-0.01/página vs parser determinista: $0/página (solo compute)
- Para 1000 SKUs/día: $30-300/mes adicionales en LLM vs $0 con parser fijo
- Parser determinista con fixtures HTML capturados = tests herméticamente verificables

### 4.2 ScrapeGraphAI como Alternativa Evaluable

**ScrapeGraphAI** (open-source Python, GitHub 17K+ stars) usa LLMs para extraer campos definidos por schema desde HTML:

```python
from scrapegraphai.graphs import SmartScraperGraph

graph = SmartScraperGraph(
    prompt="Extrae ASIN, título, precio AED, marca, especificaciones técnicas",
    source="https://www.amazon.ae/dp/B09XYZ123",
    config={"llm": {"model": "openai/gpt-4o-mini"}}
)
result = graph.run()
# → {"asin": "B09XYZ123", "title": "...", "price": 299.0, "specs": {...}}
```

| Aspecto | Evaluación |
|---------|-----------|
| Costo (OpenAI gpt-4o-mini) | ~$0.001-0.003/página |
| Latencia | ~2-5s/página |
| Robustez DOM changes | ✅ Alta |
| Anti-bot bypass | ❌ No incluido |
| Para 1000 SKUs/semana | ~$5-15/mes adicionales (aceptable) |

**Conclusión:** ScrapeGraphAI es interesante para el parsing layer, no para el anti-bot layer.

---

## 5. Comparativa de Servicios de Proxy/Scraping API para Amazon

Para Amazon UAE específicamente, la solución real pasa por un **proxy API especializado**:

| Servicio | Success Rate Amazon | Precio/1K requests | Amazon AE soporte | Estructurado |
|----------|--------------------|--------------------|-------------------|--------------|
| **Bright Data Web Scraper** | 98.44% | $0.90-1.50 | ✅ Dataset oficial | ✅ JSON |
| **Scrapfly** | ~95% | $1.00-2.00 | ✅ ASP mode | ⚠️ HTML |
| **ScraperAPI** | ~80% | $0.25-1.00 | ⚠️ Genérico | ⚠️ HTML |
| **Oxylabs** | ~95% | $1.00-2.00 | ✅ E-commerce API | ✅ JSON |
| **Zyte API** | ~90% | $0.80-1.50 | ⚠️ Parcial | ⚠️ HTML |

**Contexto de costo para el proyecto:**
- Volumen Fase 1b: ~6,700 calls/mes (224 SKUs × 30 días)
- Volumen objetivo máximo (1000 SKUs diarios): ~30,000 calls/mes
- Bright Data a $0.90/K: **~$27/mes (Fase 1b)** → **~$27/mes (1000/día)** ✅
- Scrapfly a $1.50/K: ~$40-50/mes para máximo volumen ✅

---

## 6. browser-use vs Playwright Directo: ¿Cuándo usar cada uno?

| Criterio | Playwright Directo | browser-use (LLM) |
|----------|-------------------|------------------|
| Páginas/día | 1000+ | < 50 |
| Estructura DOM conocida | ✅ Usar Playwright | ❌ Usar LLM |
| DOM cambia frecuentemente | ⚠️ Mantenimiento | ✅ LLM adapta |
| Costo por página | ~$0 (compute) | $0.01-0.10 |
| Latencia | 2-8s | 30-120s |
| Flujos multi-paso complejos | ⚠️ Hardcoding complejo | ✅ LLM razona |
| Producción/Celery | ✅ Ideal | ❌ No escalable |
| Amazon UAE scraping | ⚠️ Requiere proxy | ❌ Demasiado lento/caro |

**Regla práctica:** Usar `browser-use` cuando la tarea requiere **razonamiento** (navegar login flows desconocidos, rellenar formularios variables, seguir flujos multi-paso). Usar **Playwright directo** cuando el objetivo es extracción de datos estructurados de páginas conocidas a escala.

---

## 7. Mantenimiento y Confiabilidad Comparados

### Carga de Mantenimiento (1 = bajo, 5 = muy alto)

| Enfoque | Mantenimiento | Por qué |
|---------|--------------|---------|
| Bright Data Web Scraper API | ⭐ 1 | Parser actualizado por BD; robustez gestionada |
| Scrapfly ASP + parser propio | ⭐⭐ 2 | Parser HTML a mantener; bypass gestionado por SF |
| Playwright + proxy residencial propio | ⭐⭐⭐⭐ 4 | Stealth updates, DOM changes, CAPTCHA solving |
| browser-use / AgentQL | ⭐⭐ 2 | Parser autosanador; caro en LLM |
| httpx/curl_cffi + proxy | ⭐⭐⭐ 3 | TLS ok, behavioral blocking no resuelto |

### Riesgo de Outage

- **Bright Data:** Bajo. SLA comercial, redundancia, fallback stub en ADR-070.
- **Self-host Playwright:** Alto. Amazon puede bloquear el fingerprint en horas sin previo aviso.
- **browser-use:** Medio. Depende de disponibilidad LLM provider + browser.

---

## 8. Recomendación Final para Stack Python/Celery

### 8.1 Para Amazon UAE (Decisión Principal)

**Mantener Bright Data (ADR-070) como solución principal.** La investigación confirma que:

1. Amazon UAE usa AWS WAF Bot Control en modo "Targeted" — ninguna solución open-source la supera consistentemente en producción
2. Bright Data es el único provider con **dataset oficial Amazon AE** + 98.44% success rate
3. El costo ($27-50/mes para el volumen objetivo) es marginal vs. el costo de desarrollo/mantenimiento de una solución in-house
4. El ADR-070 ya tiene scaffold, circuit breaker, retry y fallback stub implementados

**Alternativa evaluable si se quiere reducir vendor lock-in:**
Migrar a **Scrapfly** (ASP mode) como segunda opción — similar tasa de éxito, precio comparable, pero requiere mantener parser HTML propio vs. JSON estructurado de Bright Data.

### 8.2 Mejoras Recomendadas sobre ADR-070

Si el objetivo es más **control in-house** manteniendo confiabilidad:

```
Tier 1 (primario): Bright Data Web Scraper API → JSON estructurado
Tier 2 (fallback): Scrapfly ASP + parser selectolax propio → HTML → parser
Tier 3 (degraded): AmazonUaeStubFetcher (ya implementado)
```

Esto reduce dependencia de un solo vendor sin sacrificar confiabilidad.

### 8.3 Para Parsing Robusto (Mejora Opcional)

Si Amazon cambia estructura con frecuencia, considerar:
- **ScrapeGraphAI** (open-source) como capa de parsing sobre el HTML de Bright Data
- Costo adicional: ~$5-15/mes para 1000 SKUs/semana con `gpt-4o-mini`
- Beneficio: parser auto-sanador, sin mantenimiento de selectores

### 8.4 Lo que NO hacer

- ❌ Reemplazar Bright Data con Playwright self-host para Amazon — confiabilidad insuficiente
- ❌ Usar `browser-use` para scraping masivo — 50-100x más caro, latencia inaceptable
- ❌ Usar `httpx`/`curl_cffi` directo sin proxy — bloqueado inmediatamente
- ❌ Confiar en `playwright-stealth` para Amazon — Amazon actualiza detecciones frecuentemente

### 8.5 Cuándo Reconsiderar

La recomendación de mantener Bright Data cambia si:
- Volumen escala a >50,000 requests/mes (costo empieza a ser significativo, ~$45-75/mes)
- Amazon lanza API pública de datos de producto para UAE (Amazon SP-API hoy no cubre competidores)
- Q-NEW-S3 (legal sign-off) tiene restricciones que impiden Bright Data

En ese escenario, evaluar: **Scrapfly Pro** (ASP mode con parser propio) o **Oxylabs E-commerce API** (similar precio, JSON estructurado).

---

## 9. Árbol de Decisión de Implementación

```
¿Necesitas datos de competidores Amazon UAE?
├── Sí → ¿Confías en Bright Data contractualmente (Q-NEW-S3)?
│   ├── Sí → Mantener ADR-070 Bright Data + mejoras opcionales (Tier 2 fallback)
│   └── No → Evaluar Scrapfly ASP + parser selectolax (Tier 2 como primario)
└── No (solo tus propios listings) → Amazon SP-API (ADR-072, ya implementado)

¿Necesitas scraping Noon UAE?
└── Sí → Mantener ADR-071 Playwright self-host (Noon anti-bot es manejable)
    └── Si Noon añade CAPTCHA agresivo → Bright Data Custom Scraper o Scrapfly

¿Quieres parsing más robusto ante cambios DOM de Amazon?
└── Sí → Añadir ScrapeGraphAI como parser layer sobre HTML de Bright Data
    └── Costo: ~$5-15/mes adicional para volumen Fase 1b
```

---

## 10. Referencias y Fuentes

### Fuentes Investigadas

- [Scrape Amazon Guide 2026 — Scrape.do](https://scrape.do/blog/amazon-scraping/) — guía completa anti-bot Amazon 2026
- [Playwright Stealth Bypass — Scrapfly](https://scrapfly.io/blog/posts/playwright-stealth-bypass-bot-detection) — limitaciones stealth vs. Amazon WAF
- [Stagehand vs Browser Use vs Playwright 2026 — NxCode](https://www.nxcode.io/resources/news/stagehand-vs-browser-use-vs-playwright-ai-browser-automation-2026) — comparativa AI browser agents
- [Browser Use Changelog + Benchmark](https://browser-use.com/changelog) — BU 2.0 accuracy +12%
- [AgentQL GitHub](https://github.com/tinyfish-io/agentql) — SDK + REST API, Python support
- [Camoufox + Amazon — ScrapingBee](https://www.scrapingbee.com/blog/how-to-scrape-with-camoufox-to-bypass-antibot-technology/) — CAPTCHA gate en Amazon
- [curl_cffi TLS bypass — Capsolver](https://www.capsolver.com/blog/All/web-scraping-with-curl-cffi) — impersonación TLS Chrome/Firefox
- [AWS WAF Bot Control Residential Proxy Protection — AWS](https://aws.amazon.com/about-aws/whats-new/2023/09/aws-waf-bot-control-protects-against-distributed-proxy-based-attacks/) — detección residential proxies
- [Best Amazon Scrapers 2026 — Bright Data](https://brightdata.com/blog/web-data/best-amazon-scrapers) — benchmarks 98.44% success
- [ScrapeGraphAI vs AgentQL 2026](https://scrapegraphai.com/blog/sgai-vs-agentql) — comparativa AI scrapers
- [Skyvern pricing + enterprise automation 2025](https://www.skyvern.com/pricing) — $0.10/step pricing
- [Patchright — ZenRows](https://www.zenrows.com/blog/patchright) — Playwright undetectable fork
- [Best Amazon Scraping APIs 2026 — EasyParser](https://easyparser.com/blog/best-amazon-scraper-api-comparison-guide-2026) — comparativa detallada con pricing
- [Stagehand v3 launch — Browserbase](https://www.browserbase.com/blog/stagehand-v3) — CDP-native, 44% mejora performance
- [Scraper API vs Bright Data cost 2026](https://www.scrapingdog.com/blog/best-amazon-scraping-apis/) — análisis costo/beneficio

### Contexto Interno del Proyecto

- [ADR-070 — Bright Data scraping policy para Amazon UAE](/_bmad-output/planning-artifacts/adr/ADR-070-bright-data-scraping-policy.md)
- [ADR-071 — Playwright self-host para Noon UAE](/_bmad-output/planning-artifacts/adr/ADR-071-playwright-self-host-noon.md)
- [ADR-072 — Amazon SP-API integration](/_bmad-output/planning-artifacts/adr/ADR-072-amazon-sp-api-integration.md)
