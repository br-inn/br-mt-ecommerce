---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: []
workflowType: 'research'
lastStep: 6
research_type: 'technical'
research_topic: 'Amazon UAE In-House Scraper Stack 2025'
research_goals: 'Complementar plan existente con datos actuales verificados para tomar decisión de build vs buy y estimar costo mensual total del enfoque in-house'
user_name: 'psierra'
date: '2026-05-13'
web_research_enabled: true
source_verification: true
---

# Reporte Técnico: Amazon UAE In-House Scraper Stack

**Fecha:** 2026-05-13
**Autor:** psierra
**Tipo:** Investigación técnica complementaria
**Contexto:** Complementa investigación previa que estableció: patchright como estándar, 1 browser/worker, N contexts concurrentes en Celery, shm_size 2gb, imagen base mcr.microsoft.com/playwright/python:v1.44.0-jammy, proxy residencial UAE rotativo.

---

## Scope Confirmado

- A) patchright estado actual 2025 vs alternativas (camoufox, nodriver, botasaurus)
- B) Costos proxy residencial UAE — Webshare, Oxylabs, Smartproxy/Decodo + estimación GB
- C) Celery + Playwright en Docker — patrones de producción reales
- D) Amazon UAE especificidades (amazon.ae) — detección, selectores CSS, protecciones
- E) Amazon PA-API (SP-API pública) — uso para búsqueda de competidores

---

## A) patchright — Estado Actual 2025

### Paquete y Compatibilidad

- **Paquete pip:** `patchright` (nombre exacto en PyPI — `pip install patchright`)
- **Versión actual:** 1.59.1 (activamente mantenido, mirrors Playwright version numbering)
- **Python 3.11:** ✅ Compatible. Distribuido como wheels `py3`, sin restricción de minor version. Confirmado en PyPI.
- **Imagen Docker:** La imagen base `mcr.microsoft.com/playwright/python:v1.44.0-jammy` es compatible; patchright es drop-in replacement de playwright — misma API, mismos browsers.

### Cómo Funciona patchright

Patchright parchea Playwright a nivel de protocolo CDP para:
- Evitar `Runtime.enable` CDP call (principal señal de detección que usan Cloudflare, DataDome, Akamai)
- Ejecuta JavaScript en `ExecutionContexts` aislados en lugar del contexto global
- Añade `--disable-blink-features=AutomationControlled`
- Elimina `--enable-automation`
- Cambia User-Agent de `HeadlessChrome` a `Chrome`
- Soporte para interactuar con Closed Shadow Roots

**Limitación crítica:** Solo parchea **Chromium**. Firefox y WebKit no soportados.

### Confiabilidad en Producción para Amazon 2025

- **Nivel de confianza: MEDIO-ALTO** para amazon.ae con proxy residencial UAE
- Con la configuración correcta (proxy residencial rotativo + fingerprint randomizado), patchright pasa los anti-bot de Amazon en la mayoría de casos
- Amazon usa AWS WAF Bot Control con detección por browser interrogation, fingerprinting, y behavior heuristics — patchright mitiga el fingerprinting a nivel protocol, pero el comportamiento humano (mouse, delays, scroll) debe añadirse por encima
- **No es silver bullet:** Amazon puede bloquear por IP reputation, behavioral patterns, o session analysis — el proxy residencial UAE es tan importante como el stealth del browser

### Alternativas y Comparación

| Tool | Enfoque | Stealth Level | Python API | Prod-Ready Amazon | Nota |
|------|---------|---------------|------------|-------------------|------|
| **patchright** | Chromium + CDP patches | Alto | ✅ (playwright compat) | MEDIO-ALTO | Drop-in playwright; el más maduro para prod |
| **camoufox** | Firefox + patches C++ level | MUY ALTO (100% en tests) | ✅ (`pip install camoufox[geoip]`) | MEDIO | Bloqueado por Amazon CAPTCHA en tests reales con proxies baratos; Firefox puede recibir contenido diferente |
| **nodriver** | Chrome directo via CDP (sin Playwright) | Alto | ✅ | MEDIO | Evita detection vectors de Playwright; menos maduro en ecosistema; sin async nativo completo |
| **botasaurus** | Selenium-based + anti-detect | Medio-Alto | ✅ (`pip install botasaurus`) | MEDIO | Framework all-in-one; sobre Selenium (más pesado); no ideal para producción de alta concurrencia; mejor para scraper scripts one-shot |

**Recomendación confirmada:** patchright sigue siendo la mejor opción para producción con Python/Playwright/Celery en 2025. camoufox es el líder técnico en stealth pero en tests reales contra Amazon con proxies residenciales estándar fue bloqueado por CAPTCHA — la infraestructura de proxies importa tanto como el stealth del browser.

**Stack óptimo 2025:** `patchright` + proxy residencial UAE residencial rotativo de calidad + human behavior simulation (mouse movement, random delays) + session rotation cada N requests.

---

## B) Costos Proxy Residencial UAE

### Comparativa de Proveedores (Mayo 2025)

| Proveedor | Precio por GB | Plan mínimo | UAE targeting | Notas |
|-----------|--------------|-------------|---------------|-------|
| **Webshare Residential** | $1.40–$3.50/GB | $3.50/mes (1GB) | ✅ | Precio más bajo del mercado; hasta $1.12/GB en planes anuales grandes; actualmente con 50% descuento |
| **Oxylabs Residential** | $2.00–$4.00/GB | ~$45/mes (Micro) | ✅ 11M+ IPs UAE | $3.87/GB (13GB), $3.75/GB (40GB), $2.75/GB (318GB); calidad enterprise; pool UAE muy grande |
| **Smartproxy / Decodo** | $1.40–$8.50/GB | PAYG a $8.50/GB | ✅ city-level | $3.00/GB (10GB plan), $2.00/GB (100GB), $1.40/GB (300GB); rebrand reciente a Decodo; 3-day free trial |

**Nota sobre targeting UAE:** Los tres proveedores ofrecen targeting geográfico por país (UAE/AE) sin cargo adicional. Oxylabs tiene el pool UAE más grande (11M+ IPs) lo que reduce la probabilidad de reutilización de IPs y mejora la rotación.

### Estimación de Consumo de Datos

**Supuestos del brief:**
- 1 SERP page (~300KB compressed/transferida)
- 1 PDP page (~500KB compressed/transferida)
- 1,000 referencias de competidores a monitorear
- Ciclo mensual: cada referencia se trackea ~4 veces/mes (weekly pricing check)

**Cálculo detallado:**

```
Por ciclo de scraping:
- SERP pages: 1,000 refs × 0.3 KB = 300 MB (si se busca 1 SERP por referencia)
- PDP pages:  1,000 refs × 0.5 KB = 500 MB (1 PDP por referencia)
- Total por ciclo: ~800 MB ≈ 0.8 GB

Mensual (4 ciclos/mes):
- 4 × 0.8 GB = 3.2 GB/mes (dato del brief confirmado)

Con overhead real (retries, CAPTCHAs, navigation overhead, headers):
- Factor overhead: ×1.5–2.0
- Estimación conservadora: 3.2 × 1.5 = ~5 GB/mes
- Estimación pesimista (alta tasa de CAPTCHA/retry): ~8–10 GB/mes
```

**Recomendación:** Presupuestar **5–8 GB/mes** para tener margen.

### Costo Mensual de Proxy por Proveedor (5 GB/mes)

| Proveedor | 5 GB/mes estimado | 10 GB/mes (buffer) |
|-----------|------------------|-------------------|
| Webshare | $7–$17.50 | $14–$35 |
| Oxylabs | $18.75–$20 | $37.50–$40 |
| Smartproxy/Decodo | $15–$42.50 | $20–$85 |

**Mejor valor para este caso de uso:** Webshare Residential para comenzar (menor costo, funcional), Oxylabs si la tasa de éxito con Webshare es baja (mejor pool UAE = menos bloqueos = menos retries = menos GB consumidos).

---

## C) Celery + Playwright en Docker — Patrones Reales de Producción

### El Problema Fundamental

Playwright Python es nativo `asyncio`. Celery workers con pool `prefork` corren tareas en procesos separados, cada uno con su propio contexto — **no son async**. El conflicto: no se puede usar `async def` directamente como tarea Celery con prefork.

### Patrones Verificados en Producción 2025

#### Patrón 1: asyncio.run() en tarea síncrona (RECOMENDADO para prefork)

```python
# tasks.py
from celery import Celery
from patchright.sync_api import sync_playwright  # Usar sync_api directamente

app = Celery(...)

@app.task(bind=True, max_retries=3)
def scrape_product(self, url: str) -> dict:
    """Tarea síncrona — compatible con prefork pool"""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            proxy={"server": "http://proxy-host:port", ...}
        )
        page = context.new_page()
        try:
            page.goto(url, timeout=30000)
            # ... extraer datos
            return {"price": ..., "title": ...}
        except Exception as exc:
            raise self.retry(exc=exc, countdown=60)
        finally:
            context.close()
            browser.close()
```

**Ventaja:** 1 browser por tarea — simple, aislado, sin state compartido.
**Desventaja:** Overhead de launch/close por tarea — costoso en CPU/tiempo.

#### Patrón 2: Browser compartido por worker con @worker_ready (RECOMENDADO para alto volumen)

```python
# worker_init.py
from celery.signals import worker_ready, worker_shutdown
from patchright.sync_api import sync_playwright

_pw = None
_browser = None

@worker_ready.connect
def init_browser(sender, **kwargs):
    global _pw, _browser
    _pw = sync_playwright().start()
    _browser = _pw.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
    )

@worker_shutdown.connect
def shutdown_browser(sender, **kwargs):
    global _pw, _browser
    if _browser:
        _browser.close()
    if _pw:
        _pw.stop()
```

```python
# tasks.py — usando el browser del worker
from worker_init import _browser
from celery import Celery

app = Celery(...)

@app.task(bind=True, max_retries=3)
def scrape_product(self, url: str) -> dict:
    context = _browser.new_context(proxy={...})
    page = context.new_page()
    try:
        page.goto(url, timeout=30000)
        return extract_data(page)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
    finally:
        context.close()  # Siempre cerrar context, nunca el browser
```

**Con prefork:** `concurrency=1` por worker + N workers = N browsers en paralelo (1 por proceso). Cada tarea crea un nuevo Context (no un nuevo Browser).

#### Patrón 3: celery-aio-pool (para async nativo)

```bash
CELERY_CUSTOM_WORKER_POOL='celery_aio_pool.pool:AsyncIOPool' celery worker ...
```

Permite usar `async def` directamente como tareas Celery. Más complejo de configurar. **No recomendado** para este caso — añade complejidad sin beneficio real sobre el Patrón 2 con sync_api.

### Manejo de Crashes del Browser en Producción

```python
@worker_ready.connect
def init_browser(sender, **kwargs):
    _init_browser_with_retry(max_retries=3)

def _init_browser_with_retry(max_retries=3):
    global _pw, _browser
    for attempt in range(max_retries):
        try:
            if _pw:
                try: _pw.stop()
                except: pass
            _pw = sync_playwright().start()
            _browser = _pw.chromium.launch(headless=True, args=[...])
            return
        except Exception as e:
            logger.error(f"Browser init failed (attempt {attempt+1}): {e}")
            time.sleep(5)
    raise RuntimeError("Browser init failed after retries")

@app.task(bind=True, max_retries=3)
def scrape_product(self, url):
    try:
        context = _browser.new_context(...)
        # ...
    except Exception as exc:
        # Si el browser crasheó, reinicializarlo
        _init_browser_with_retry()
        raise self.retry(exc=exc, countdown=30)
```

### Librerías que Resuelven Celery + Playwright

- **`celery-aio-pool`** (GitHub: the-wondersmith/celery-aio-pool): Pool asyncio nativo para Celery. Funciona pero añade complejidad. Útil si todo el stack es async.
- **No existe** una librería "celery-playwright" oficial mantenida en 2025 — el patrón con `@worker_ready.connect` + `sync_api` es el estándar de facto documentado en producción.

### Configuración Docker Recomendada

```yaml
# docker-compose.dev.yml (sección worker)
worker:
  image: mcr.microsoft.com/playwright/python:v1.44.0-jammy
  shm_size: '2gb'  # CRÍTICO — Chrome usa /dev/shm para IPC
  environment:
    - CELERY_WORKER_CONCURRENCY=4  # 4 procesos prefork = 4 browsers
    - CELERY_WORKER_POOL=prefork
  command: celery -A tasks worker --pool=prefork --concurrency=4 --loglevel=info
```

---

## D) Amazon UAE (amazon.ae) — Especificidades Técnicas

### ¿Es amazon.ae diferente en detección?

**Nivel de confianza: MEDIO** (poca documentación pública específica para .ae)

- amazon.ae y amazon.com **comparten la misma infraestructura anti-bot**: AWS WAF Bot Control con detección por browser interrogation, fingerprinting, behavior heuristics y IP reputation.
- **No hay evidencia de que amazon.ae use protecciones diferentes** a amazon.com — es la misma plataforma Amazon, mismos sistemas de seguridad.
- La diferencia principal es **el volumen de tráfico**: amazon.ae tiene mucho menos tráfico que amazon.com, lo que puede significar que los threshold de rate limiting sean similares pero la competencia por IPs residenciales UAE es menor.
- **Mismos CAPTCHA triggers:** muchas requests desde una IP, navegación no-humana, ausencia de cookies de sesión válidas.

### Selectores CSS para Precios en amazon.ae (AED)

Amazon usa la misma estructura DOM en todas las regiones. Los selectores más robustos en 2025/2026:

```python
# Selectores en orden de prioridad (con fallbacks)
PRICE_SELECTORS = [
    # Selector principal — precio más baja en pantalla de escritorio
    "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
    # Alternativa — precio en feature div
    "#corePrice_feature_div .a-price .a-offscreen",
    # Para precios en PDP con variantes
    "span.priceToPay .a-offscreen",
    # Precio base (puede estar tachado)
    "span.basisPrice .a-offscreen",
    # Fallback genérico
    ".a-price .a-offscreen",
    # Último recurso (puede incluir precio tachado)
    "span.a-price span.a-offscreen",
]

# Extracción robusta
def extract_price(page) -> dict:
    for selector in PRICE_SELECTORS:
        el = page.query_selector(selector)
        if el:
            raw = el.inner_text().strip()
            # Para amazon.ae: "AED 1,234.56" o "1,234.56"
            price_text = raw.replace("AED", "").replace(",", "").strip()
            try:
                return {"price": float(price_text), "currency": "AED", "selector": selector}
            except ValueError:
                continue
    return {"price": None, "currency": "AED", "error": "price_not_found"}
```

**Notas sobre amazon.ae:**
- La moneda es AED (Dirham Emiratí). El texto puede aparecer como "AED 123.45" o solo "123.45" dependiendo del context del usuario.
- Para obtener precios **en AED con locale en_AE**, configurar el contexto del browser con `locale="en-AE"` y `timezone_id="Asia/Dubai"`.
- Los selectores `.a-offscreen` son los más estables — son el texto para screen readers y Amazon los usa consistentemente en todas las regiones.

### Configuración de Contexto Playwright para amazon.ae

```python
context = browser.new_context(
    locale="en-AE",           # Locale UAE inglés
    timezone_id="Asia/Dubai",  # Timezone Dubai
    geolocation={"latitude": 25.2048, "longitude": 55.2708},  # Dubai
    permissions=["geolocation"],
    extra_http_headers={
        "Accept-Language": "en-AE,en;q=0.9,ar;q=0.8",
    },
    proxy={"server": "http://uae-proxy:port", ...}
)
```

### Rate Limiting y Comportamiento Humano

Técnicas esenciales para amazon.ae:
1. **Randomizar delays** entre requests: `random.uniform(2.5, 7.0)` segundos entre páginas
2. **Simular mouse movement** antes de clicks (patchright tiene esto built-in parcialmente)
3. **Session warming:** Visitar amazon.ae homepage antes de navegar a productos
4. **Rotación de proxy** cada 5–10 requests (no cada request — cambios muy frecuentes son señal de bot)
5. **Cookies persistentes** por sesión de contexto: usar `storage_state` para simular usuario real

---

## E) Amazon PA-API — ¿Sirve para Competidores?

### Estado Actual (CRÍTICO)

> **PA-API 5.0 será deprecada el 15 de mayo de 2026.** Amazon está migrando a **Creators API**. Para implementaciones nuevas, evaluar migración directa a Creators API.

### ¿Se Puede Usar PA-API para Buscar Productos de Competidores?

**Respuesta: SÍ, con limitaciones importantes.**

La operación `SearchItems` permite buscar productos en el catálogo de Amazon por keywords, categorías, ASINs, etc. — incluyendo productos de cualquier seller/brand, no solo los propios.

```python
# Ejemplo SearchItems para buscar productos de competidores
from paapi5_python_sdk import DefaultApi, SearchItemsRequest, SearchItemsResource, PartnerType

def search_competitor_products(keyword: str, marketplace: str = "www.amazon.ae"):
    request = SearchItemsRequest(
        partner_tag="your-tag-20",
        partner_type=PartnerType.ASSOCIATES,
        marketplace=marketplace,
        keywords=keyword,
        search_index="All",
        resources=[
            SearchItemsResource.ITEMINFO_TITLE,
            SearchItemsResource.OFFERS_LISTINGS_PRICE,
            SearchItemsResource.ITEMINFO_BYLINEINFO,  # Brand/seller info
        ]
    )
    response = api.search_items(request)
    return response.search_result.items
```

### Limitaciones Críticas de PA-API para Competitor Tracking

| Limitación | Impacto |
|-----------|---------|
| **Requiere cuenta Amazon Associates** | Hay que ser afiliado Amazon del país objetivo |
| **Rate limit: 1 request/segundo** (TPS), burst de 10 | Con 1,000 refs y 4 checks/mes → factible pero lento |
| **Solo devuelve productos elegibles para Associates** | Puede excluir algunos productos de competidores |
| **Precios devueltos son precios "oferta" del momento** | Sin historial de precios |
| **amazon.ae marketplace** disponible en PA-API 5.0 | ✅ Confirmado soporte |
| **Datos limitados sobre sellers third-party** | Dificulta ver si el competidor es el vendedor principal |
| **Deprecación mayo 2026** | Necesita migrar a Creators API antes de esa fecha |

### Veredicto sobre PA-API

**PA-API es viable COMPLEMENTARIAMENTE** para:
- Descubrir ASINs de competidores por keyword search
- Obtener precios actuales de productos específicos por ASIN
- Datos básicos de producto (title, brand, category)

**PA-API NO reemplaza el scraper** para:
- Pricing histórico o intraday tracking
- Datos de reviews/ratings en detalle
- Información de Buy Box / seller detallada
- Productos que no están en el programa Associates
- Cualquier dato que Amazon no expone en la API

**Recomendación:** Usar PA-API como fuente complementaria de discovery de ASINs, y el scraper para pricing tracking. Planificar migración a Creators API antes de mayo 2026.

---

## Síntesis: Estimación de Costo Mensual In-House

### Stack Recomendado Final

```
patchright 1.59.1 (pip install patchright)
+ Docker: mcr.microsoft.com/playwright/python:v1.44.0-jammy, shm_size: 2gb
+ Celery prefork, concurrency=4, patrón @worker_ready.connect + sync_api
+ Proxy: Webshare Residential (inicial) / Oxylabs (si tasa de éxito < 80%)
```

### Costo Mensual Estimado (1,000 referencias, 4 checks/mes)

| Componente | Costo Estimado | Notas |
|-----------|---------------|-------|
| **Proxy residencial UAE** (5–8 GB/mes, Webshare) | $7–$28/mes | Webshare $1.40–$3.50/GB; escalar a Oxylabs si necesario (+$10–$20) |
| **Servidor Docker** (Hetzner CX31 o similar) | $15–$25/mes | 4 vCPU / 8 GB RAM — ya existente en infra |
| **Redis** (Celery broker) | $0–$10/mes | Ya existente en stack MT |
| **CAPTCHA solving** (opcional, si tasa de CAPTCHA > 5%) | $0–$20/mes | 2captcha/Anti-Captcha: ~$1–$3/1000 CAPTCHAs |
| **PA-API** (complemento discovery) | $0/mes | Gratuita con cuenta Associates |

**Total estimado mensual:** **$22–$83/mes**

- **Escenario optimista** (proxy Webshare, baja tasa CAPTCHA): ~$22–$40/mes
- **Escenario realista** (proxy Webshare + algo de CAPTCHA solving): ~$40–$60/mes
- **Escenario pesimista** (migrar a Oxylabs + CAPTCHA solving): ~$60–$83/mes

**Comparativa vs alternativas managed:**
- ScraperAPI / BrightData Amazon scraping API: $49–$500+/mes según volumen
- El in-house approach a $40–$60/mes es **significativamente más económico** a este volumen, con el tradeoff de maintenance overhead.

---

## Decisiones y Riesgos

### Riesgos Identificados

1. **Cambios en DOM de amazon.ae:** Los selectores CSS pueden cambiar sin aviso. Mitigación: múltiples selectores con fallback + alertas cuando `price_not_found > X%`.
2. **CAPTCHA surge inesperado:** Amazon puede aumentar agresividad anti-bot. Mitigación: CAPTCHA solving service standby + rate limiting adaptativo.
3. **PA-API deprecación mayo 2026:** Si se usa PA-API, planificar migración a Creators API — la estructura de autenticación cambia.
4. **Camoufox como alternativa futura:** Si patchright empieza a ser detectado consistentemente, camoufox (Firefox C++-level patching) es el upgrade natural — requiere refactor mínimo de la capa de scraping.
5. **IP pool UAE agotamiento:** Si Webshare tiene pool pequeño para UAE, las mismas IPs aparecerán frecuentemente — aumentar rotación o migrar a Oxylabs (11M+ IPs UAE).

### Próximos Pasos Recomendados

1. Implementar proof-of-concept con patchright + Webshare 5GB plan (~$7–$17)
2. Medir tasa de éxito real contra amazon.ae (target: >85% páginas sin CAPTCHA)
3. Si tasa < 85%, evaluar: (a) mejor proxy, (b) añadir CAPTCHA solving, (c) camoufox
4. Crear cuenta Amazon Associates UAE para acceso a PA-API como complemento
5. Planificar migración PA-API → Creators API antes de mayo 2026

---

## Fuentes

- [patchright PyPI](https://pypi.org/project/patchright/)
- [patchright GitHub — Kaliiiiiiiiii-Vinyzu](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright)
- [ZenRows — How to Scrape with Patchright](https://www.zenrows.com/blog/patchright)
- [The 2025 web scraping tech stack — The Web Scraping Club](https://substack.thewebscraping.club/p/the-2025-web-scraping-tech-stack)
- [anti-detect-browser-tools-tech-comparison — GitHub pim97](https://github.com/pim97/anti-detect-browser-tools-tech-comparison)
- [Best Patchright Alternatives 2026 — RoundProxies](https://roundproxies.com/blog/best-patchright-alternatives/)
- [camoufox PyPI](https://pypi.org/project/camoufox/)
- [camoufox GitHub — daijro](https://github.com/daijro/camoufox)
- [Webshare Residential Proxy Pricing](https://www.webshare.io/residential-proxy)
- [Oxylabs UAE Proxy](https://oxylabs.io/locations/united-arab-emirates)
- [Oxylabs Residential Pricing](https://oxylabs.io/pricing/residential-proxy-pool)
- [Decodo (Smartproxy) Residential Pricing](https://decodo.com/proxies/residential-proxies/pricing)
- [CVFactory Backend: Celery, FastAPI, Playwright at Scale — Medium](https://medium.com/@wintrover/behind-cvfactorys-backend-celery-fastapi-and-playwright-at-scale-156e95241004)
- [celery-aio-pool — GitHub the-wondersmith](https://github.com/the-wondersmith/celery-aio-pool)
- [Bypass Amazon Anti-Scraping 2025 — EasyParser](https://easyparser.com/blog/bypassing-amazon-anti-scraping)
- [Scrape Amazon Product Data Tutorial — SerpAPI](https://serpapi.com/blog/scrape-amazon-product-data-tutorial/)
- [Amazon PAAPI 5.0 Documentation](https://webservices.amazon.com/paapi5/documentation/)
- [Botasaurus GitHub — omkarcloud](https://github.com/omkarcloud/botasaurus)
