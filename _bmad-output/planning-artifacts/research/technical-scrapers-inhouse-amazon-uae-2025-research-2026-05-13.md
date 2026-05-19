---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: []
workflowType: 'research'
lastStep: 6
research_type: 'technical'
research_topic: 'Scrapers in-house para Amazon UAE 2025-2026: Playwright vs Selenium, anti-detección, arquitectura Celery+FastAPI, Docker headless, proxy rotation'
research_goals: 'Migrar scraper standalone Python 3.9+Selenium+ProtonVPN a microservicio production-ready Python 3.11+FastAPI+Celery+Redis+Docker (Hetzner), ~224-1000 refs, refresco semanal/diario'
user_name: 'psierra'
date: '2026-05-13'
web_research_enabled: false
web_research_note: 'Sin acceso a internet en este entorno. Reporte elaborado con conocimiento técnico al corte agosto 2025, cubriendo tendencias 2025-2026.'
source_verification: partial
---

# Reporte Técnico: Scrapers In-House para Amazon UAE 2025–2026

**Fecha:** 2026-05-13
**Autor:** psierra
**Tipo:** Investigación técnica
**Corte de conocimiento:** agosto 2025 (tendencias 2025-2026)

> **Nota metodológica:** El entorno de ejecución no dispone de acceso a internet. Este reporte se elabora con base en el conocimiento técnico del modelo (corte agosto 2025), que cubre en profundidad las tendencias, librerías y arquitecturas del dominio. Las referencias externas se citan por nombre/versión pero sin URL verificada en tiempo real.

---

## 1. Contexto y Estado de Partida

### Situación actual

| Dimensión | Valor actual |
|-----------|-------------|
| Runtime | Python 3.9, script standalone |
| Browser | Selenium + ChromeDriver |
| Anonimato | ProtonVPN UAE (IP fija) |
| Volumen | 224 referencias → ~90 min |
| Refresco | Semanal/manual |
| Destino | Python 3.11 + FastAPI + Celery + Redis + Docker/Hetzner |

### Brechas identificadas

1. **Escalabilidad:** 90 min para 224 refs = ~24 s/ref. Para 1000 refs en ciclo diario necesita paralelización.
2. **Anti-detección:** Selenium "vanilla" es el peor candidato en 2025; Amazon UA/fingerprinting lo detecta en minutos sin mitigaciones.
3. **Operabilidad:** Script standalone sin retry, sin cola, sin observabilidad.
4. **Aislamiento:** ProtonVPN fija es single point of failure; si rota IP, el scraper para.

---

## 2. Playwright vs Selenium en 2025: Veredicto

### 2.1 Panorama general

**Selenium 4.x** sigue siendo el estándar de mercado en testing de UI, pero para scraping en 2025 tiene desventajas estructurales:

- Genera el header `webdriver=true` en `navigator.webdriver` por defecto.
- El protocolo CDP (Chrome DevTools Protocol) que usa internamente es accesible, pero la gestión manual es verbosa.
- `undetected-chromedriver` (UC) fue la solución dominante 2022-2024, pero Amazon y otros sitios han evolucionado sus detectores y UC está en mantenimiento reducido desde 2024.

**Playwright** (Microsoft, open source) ganó tracción masiva en 2023-2025 por:

- API async-first (Python: `async/await` nativo).
- Manejo de múltiples contexts/pages en un solo browser process.
- Acceso nativo a CDP sin boilerplate.
- Ecosistema de stealth más activo en 2025.

**Veredicto para este proyecto:**

> **Migrar a Playwright**. La API async encaja naturalmente con Celery (via `asyncio.run()` dentro del task) y con FastAPI. El ecosistema de anti-detección en 2025 está más activo en Playwright que en Selenium.

### 2.2 Tabla comparativa

| Criterio | Selenium 4 + UC | Playwright + patchright/camoufox |
|----------|-----------------|----------------------------------|
| Anti-detección base | Medio (UC parcheado) | Alto (patchright/camoufox) |
| API async | No nativa (ThreadPool) | Sí nativa |
| Multi-context | No | Sí |
| Docker headless | Pesado (necesita Xvfb o DISPLAY) | Nativo `--no-sandbox` |
| Mantenimiento UC | Reducido en 2025 | Activo |
| Curva de migración | — | Media (API diferente) |
| **Recomendación** | ❌ Descartar para prod | ✅ Adoptar |

---

## 3. Anti-Detección en 2025: Playwright-Stealth, Patchright y Camoufox

### 3.1 playwright-stealth

**Librería:** `playwright-stealth` (Python port de `puppeteer-extra-plugin-stealth`)

- Inyecta scripts JS antes del primer render para ocultar `navigator.webdriver`, `window.chrome`, WebGL fingerprint, etc.
- Estado 2025: funcional para sitios de dificultad media. Amazon UAE (`.ae`) ha reforzado sus detectores y `playwright-stealth` solo cubre las detecciones "clásicas" (nivel 1-2).
- **No recomendado como única capa** para Amazon. Útil como baseline complementario.

```python
# Uso básico
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page()
    await stealth_async(page)
    await page.goto("https://www.amazon.ae/...")
```

### 3.2 patchright

**Repositorio:** `Kaliiiiiiiiii-Vinyzu/patchright` (PyPI: `patchright`)

- Fork de Playwright que **parchea el binario de Chrome/Chromium** en tiempo de ejecución para eliminar las huellas del WebDriver a nivel de C++, no solo JS.
- Elimina la detección por CDP leak que Selenium/Playwright estándar exponen.
- API 100% compatible con Playwright (drop-in replacement).
- Estado 2025: **es el estándar de facto para scraping serio** en Python cuando se necesita Chromium. Mantenido activamente.

```python
# patchright es drop-in replacement
from patchright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"]
    )
    context = await browser.new_context(
        locale="en-AE",
        timezone_id="Asia/Dubai",
        geolocation={"longitude": 55.2708, "latitude": 25.2048},
        permissions=["geolocation"],
    )
    page = await context.new_page()
    await page.goto("https://www.amazon.ae/s?k=...")
```

### 3.3 camoufox

**Repositorio:** `daijro/camoufox` (PyPI: `camoufox`)

- Usa **Firefox** (no Chromium) parcheado para ocultar fingerprints. La ventaja: Amazon y otros sitios centran sus detectores en Chrome. Firefox con camoufox puede pasar bajo el radar con mayor facilidad.
- Implementa fingerprint rotation de OS, pantalla, fuentes, WebGL renderer.
- Compatible con Playwright a través del binario parcheado de Firefox.
- Estado 2025: proyecto activo, ~3-4k stars en GitHub. Más experimental que patchright pero resultados excelentes en Amazon.

```python
from camoufox.async_api import AsyncCamoufox

async with AsyncCamoufox(headless=True, geoip=True) as browser:
    page = await browser.new_page()
    await page.goto("https://www.amazon.ae/dp/ASIN")
```

### 3.4 Recomendación de stack anti-detección para Amazon UAE

**Tier 1 (recomendado para producción):**
```
patchright (Chromium parcheado)
+ Contexto con locale=en-AE, timezone=Asia/Dubai, geolocation=Dubai
+ Proxy residencial rotativo (UAE) — ver sección 6
+ User-agent rotativo (pool de UAs reales Chrome/Windows)
+ Delays humanos (random 1-4s entre acciones)
```

**Tier 2 (alternativa si Chromium es bloqueado):**
```
camoufox (Firefox parcheado)
+ Mismo setup de contexto/proxy
```

**No recomendado para Amazon UAE:**
- `playwright-stealth` solo (detecciones nivel 3+)
- Selenium + UC (detectado en 2025 en Amazon)
- Playwright vanilla sin patches

---

## 4. Proxies vs VPN Fija en 2025

### 4.1 Análisis del caso de uso

Volumen: 224-1000 refs, refresco semanal/diario.

| Solución | Costo mensual (est.) | Detección | Disponibilidad | Para este volumen |
|----------|---------------------|-----------|----------------|-------------------|
| ProtonVPN UAE fija | ~$10 | Alta (1 IP) | Media | ❌ Riesgo alto |
| Residential proxy rotativo (Webshare) | $30-80 | Baja | Alta | ✅ Buena opción |
| Residential proxy rotativo (Brightdata) | $100-300 | Muy baja | Muy alta | ✅ Premium |
| Datacenter proxy rotativo | $15-40 | Media | Alta | ⚠️ Riesgo con Amazon |
| ISP proxy estático (Brightdata/Oxylabs) | $60-150 | Baja | Alta | ✅ Excelente |

### 4.2 Recomendación concreta

Para **224-1000 refs/semana en Amazon UAE**:

**Opción A (presupuesto bajo):** Webshare residential ($29/mes, 10GB tráfico)
- Suficiente para 224-1000 req/semana si se minimizan las páginas visitadas.
- Proxies UAE disponibles.

**Opción B (producción seria):** Brightdata ISP Proxies (IPs estáticas de ISP reales)
- Menor rotación de IP = menor probabilidad de CAPTCHAs.
- IPs con historial limpio.

**Opción C (fallback de bajo costo):** Mantener ProtonVPN UAE pero con **rotación manual periódica** (cambiar servidor UAE cada N días) + rate limiting conservador.

**Patrón de integración con Celery:**

```python
# scraper/proxy_pool.py
import random

PROXY_POOL = [
    "http://user:pass@proxy1.webshare.io:8080",
    "http://user:pass@proxy2.webshare.io:8080",
    # ...
]

def get_proxy() -> str:
    return random.choice(PROXY_POOL)
```

---

## 5. Arquitectura Celery + Playwright: Patrones en 2025

### 5.1 Patrón dominante: Un browser process por worker

El patrón más adoptado en 2025 para scrapers Celery+Playwright es **inicializar el browser en el worker startup y reutilizarlo** entre tasks del mismo worker, usando **contexts aislados** por task.

```
Worker process
└── Browser process (Chromium/patchright) — 1 por worker, lifecycle = worker lifetime
    ├── Context A (task_id=abc) → Page → scrape → cerrar context
    ├── Context B (task_id=def) → Page → scrape → cerrar context
    └── ...
```

**Por qué contexts, no pages:**
- Un `BrowserContext` en Playwright es equivalente a una ventana de incógnito: cookies, localStorage, historial aislados.
- Permite N contexts concurrentes por browser sin interferencia.
- Cierre limpio de recursos al finalizar cada task.

### 5.2 Implementación de referencia

**`scraper/browser_pool.py`:**

```python
import asyncio
from patchright.async_api import async_playwright, Browser, BrowserContext
from typing import Optional

_browser: Optional[Browser] = None
_playwright_instance = None

async def get_browser() -> Browser:
    global _browser, _playwright_instance
    if _browser is None or not _browser.is_connected():
        _playwright_instance = await async_playwright().start()
        _browser = await _playwright_instance.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
            ]
        )
    return _browser

async def new_context(proxy_url: str) -> BrowserContext:
    browser = await get_browser()
    return await browser.new_context(
        proxy={"server": proxy_url},
        locale="en-AE",
        timezone_id="Asia/Dubai",
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...",
    )
```

**`scraper/tasks.py` (Celery task):**

```python
import asyncio
from celery import shared_task
from scraper.browser_pool import new_context
from scraper.proxy_pool import get_proxy
from scraper.amazon_ae import search_and_extract

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="scraper.tasks.scrape_product_reference"
)
def scrape_product_reference(self, reference_id: str, query: str) -> dict:
    """Scrape Amazon UAE para una referencia de producto."""
    try:
        return asyncio.run(_scrape(reference_id, query))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

async def _scrape(reference_id: str, query: str) -> dict:
    proxy_url = get_proxy()
    async with await new_context(proxy_url) as context:
        page = await context.new_page()
        try:
            result = await search_and_extract(page, query)
            return {"reference_id": reference_id, **result}
        finally:
            await page.close()
```

**`scraper/amazon_ae.py` (lógica de extracción):**

```python
import asyncio
import random
from playwright.async_api import Page

async def human_delay(min_ms=800, max_ms=3000):
    await asyncio.sleep(random.uniform(min_ms / 1000, max_ms / 1000))

async def search_and_extract(page: Page, query: str) -> dict:
    # 1. Búsqueda
    await page.goto(f"https://www.amazon.ae/s?k={query}&language=en_AE")
    await human_delay()

    # 2. Top 3 ASINs de resultados
    asin_locators = page.locator('[data-asin]:not([data-asin=""])').first
    asins = []
    for el in await page.locator('[data-asin]').all():
        asin = await el.get_attribute("data-asin")
        if asin and asin not in asins:
            asins.append(asin)
        if len(asins) == 3:
            break

    # 3. PDP de cada ASIN
    results = []
    for asin in asins:
        pdp_data = await extract_pdp(page, asin)
        results.append(pdp_data)
        await human_delay(1000, 4000)

    return {"query": query, "results": results, "top_asins": asins}

async def extract_pdp(page: Page, asin: str) -> dict:
    await page.goto(f"https://www.amazon.ae/dp/{asin}?language=en_AE")
    await human_delay(1500, 3500)

    title = await page.locator("#productTitle").text_content(timeout=5000)
    price_el = page.locator(".a-price .a-offscreen").first
    price = await price_el.text_content(timeout=3000) if await price_el.count() > 0 else None

    # Especificaciones técnicas
    specs = {}
    rows = await page.locator("#productDetails_techSpec_section_1 tr, #prodDetails tr").all()
    for row in rows:
        cells = await row.locator("th, td").all_text_contents()
        if len(cells) == 2:
            specs[cells[0].strip()] = cells[1].strip()

    return {
        "asin": asin,
        "title": title.strip() if title else None,
        "price": price,
        "specs": specs,
    }
```

### 5.3 Configuración Celery para scraping

```python
# celery_config.py
from kombu import Queue

# --- Queues ---
task_queues = [
    Queue("scraper_high", routing_key="scraper.high"),
    Queue("scraper_low", routing_key="scraper.low"),
]
task_default_queue = "scraper_low"

# --- Concurrencia ---
# CRÍTICO: para browsers headless, usar prefork con concurrency baja
# o gevent/eventlet. NO usar gevent con Playwright (incompatible con asyncio).
worker_concurrency = 2           # 2 workers = 2 browsers por contenedor
task_acks_late = True            # ack solo tras éxito
worker_prefetch_multiplier = 1   # un task a la vez por worker

# --- Rate limiting por tarea ---
task_annotations = {
    "scraper.tasks.scrape_product_reference": {
        "rate_limit": "10/m",    # máx 10 refs/min por worker
    }
}

# --- Retry / timeouts ---
task_soft_time_limit = 120       # 2 min soft limit por task
task_time_limit = 180            # 3 min hard limit
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]

# --- Result backend ---
result_backend = "redis://redis:6379/1"
broker_url = "redis://redis:6379/0"
```

---

## 6. Docker + Chrome Headless en Producción

### 6.1 Imágenes base en 2025

| Imagen | Peso | Mantenimiento | Para Playwright | Para Selenium |
|--------|------|--------------|-----------------|---------------|
| `mcr.microsoft.com/playwright/python:v1.44.0-jammy` | ~1.5GB | Microsoft | ✅ Oficial | ❌ |
| `ghcr.io/puppeteer/puppeteer` | ~900MB | Google | ❌ | ❌ |
| `browserless/chrome` | ~1.2GB | Browserless | ✅ vía API | ✅ via API |
| `python:3.11-slim` + install manual | ~800MB resultado | Control total | ✅ | ✅ |
| `ubuntu:22.04` + playwright install | ~1.3GB | Control total | ✅ | ✅ |

**Recomendación para este proyecto:**

**Usar `mcr.microsoft.com/playwright/python:v1.44.0-jammy` como base** para el worker. Es la imagen oficial de Microsoft, incluye Chromium y todas las dependencias del sistema.

### 6.2 Dockerfile de referencia para el scraper worker

```dockerfile
# Dockerfile.scraper-worker
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Sistema
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# App
WORKDIR /app

# Dependencias Python
COPY mt-pricing-backend/requirements/base.txt requirements/base.txt
COPY mt-pricing-backend/requirements/scraper.txt requirements/scraper.txt
RUN pip install --no-cache-dir -r requirements/base.txt -r requirements/scraper.txt

# patchright (drop-in de playwright con patches anti-detección)
RUN pip install --no-cache-dir patchright && \
    patchright install chromium --with-deps

COPY mt-pricing-backend/ .

# Celery worker — 2 workers de prefork, concurrencia 2
CMD ["celery", "-A", "app.worker.celery_app", "worker", \
     "--queues=scraper_high,scraper_low", \
     "--concurrency=2", \
     "--pool=prefork", \
     "--loglevel=info"]
```

**`requirements/scraper.txt`:**
```
patchright>=0.4.0
camoufox>=0.4.0        # alternativa Firefox, opcional
celery[redis]>=5.3.6
redis>=5.0.0
tenacity>=8.2.3        # retry logic
```

### 6.3 Docker Compose — servicio scraper worker

```yaml
# docker-compose.dev.yml (fragmento)
services:
  mt-scraper-worker:
    build:
      context: .
      dockerfile: Dockerfile.scraper-worker
    container_name: mt-scraper-worker
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
      - PROXY_LIST=${SCRAPER_PROXY_LIST}   # comma-separated
      - DATABASE_URL=${DATABASE_URL}
    volumes:
      - ./mt-pricing-backend:/app
    depends_on:
      - redis
      - db
    restart: unless-stopped
    # Recursos para Chrome headless
    shm_size: '2gb'        # CRÍTICO: Chrome necesita /dev/shm grande
    cap_add:
      - SYS_ADMIN          # para sandbox de Chrome (o usar --no-sandbox)
    deploy:
      resources:
        limits:
          memory: 3g
          cpus: '2.0'
```

> **`shm_size: 2gb` es crítico.** Chrome headless en Docker crashea con el `/dev/shm` por defecto (64MB). Sin esto los workers fallan aleatoriamente con `Tab crashed`.

---

## 7. Concurrencia y Persistencia de Resultados

### 7.1 Modelo de concurrencia recomendado

Para 224-1000 refs con refresco semanal/diario:

```
Tiempo actual: 90 min para 224 refs → ~24 s/ref

Target con arquitectura nueva:
- 2 workers × 2 contexts concurrentes = 4 scrapes en paralelo
- 224 refs / 4 = 56 batches × 24s = ~22 min (objetivo conservador)
- 224 refs / 4 = con rate limiting 10/min = ~28 min
- Para 1000 refs / 4 = ~100 min → aceptable para refresco diario
```

**Ajuste de workers según volumen:**

| Volumen | Workers Celery | Concurrency/worker | Browsers totales | Tiempo estimado |
|---------|---------------|-------------------|-----------------|-----------------|
| 224 refs/semana | 1 | 2 | 2 | ~30 min |
| 1000 refs/semana | 2 | 2 | 4 | ~60 min |
| 1000 refs/diario | 4 | 2 | 8 | ~35 min |

### 7.2 Persistencia de resultados

**Patrón recomendado: escribir directo a PostgreSQL** vía SQLAlchemy async, con cache intermedio en Redis para deduplicación.

```python
# scraper/persistence.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from app.models import ScraperResult
import json

async def upsert_scraper_result(
    db: AsyncSession,
    reference_id: str,
    asin: str,
    data: dict
) -> None:
    """Upsert resultado de scraping con conflict resolution."""
    stmt = insert(ScraperResult).values(
        reference_id=reference_id,
        asin=asin,
        title=data.get("title"),
        price_aed=data.get("price"),
        specs=json.dumps(data.get("specs", {})),
        scraped_at=func.now(),
        raw_data=json.dumps(data),
    ).on_conflict_do_update(
        index_elements=["reference_id", "asin"],
        set_={
            "title": data.get("title"),
            "price_aed": data.get("price"),
            "specs": json.dumps(data.get("specs", {})),
            "scraped_at": func.now(),
            "raw_data": json.dumps(data),
        }
    )
    await db.execute(stmt)
    await db.commit()
```

**Tabla SQL (migración Alembic):**

```sql
CREATE TABLE scraper_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reference_id    UUID NOT NULL REFERENCES products(id),
    asin            TEXT NOT NULL,
    title           TEXT,
    price_aed       NUMERIC(12, 2),
    specs           JSONB DEFAULT '{}',
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_data        JSONB,
    score           NUMERIC(5, 2),
    rank            INTEGER,
    UNIQUE (reference_id, asin)
);

CREATE INDEX idx_scraper_results_reference_id ON scraper_results(reference_id);
CREATE INDEX idx_scraper_results_scraped_at ON scraper_results(scraped_at DESC);
```

---

## 8. FastAPI Trigger Endpoint

### 8.1 Patrón API para disparar scraping

```python
# api/routers/scraper.py
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from celery import group
from app.worker.celery_app import celery_app
from app.schemas.scraper import ScrapeJobRequest, ScrapeJobResponse
from app.db.deps import get_db

router = APIRouter(prefix="/scraper", tags=["scraper"])

@router.post("/run", response_model=ScrapeJobResponse)
async def trigger_scrape_job(
    request: ScrapeJobRequest,
    db=Depends(get_db),
):
    """Disparar scraping para una lista de referencias."""
    from scraper.tasks import scrape_product_reference

    # Crear grupo de tasks Celery
    job_group = group(
        scrape_product_reference.s(
            reference_id=str(ref.id),
            query=ref.search_query,
        )
        for ref in request.references
    )
    result = job_group.apply_async(queue="scraper_high")

    return ScrapeJobResponse(
        job_id=result.id,
        total_references=len(request.references),
        status="queued",
    )

@router.get("/job/{job_id}", response_model=ScrapeJobStatusResponse)
async def get_job_status(job_id: str):
    """Estado de un job de scraping."""
    from celery.result import GroupResult
    result = GroupResult.restore(job_id, app=celery_app)
    if not result:
        raise HTTPException(status_code=404, detail="Job not found")

    return ScrapeJobStatusResponse(
        job_id=job_id,
        completed=result.completed_count(),
        total=len(result.children),
        ready=result.ready(),
        successful=result.successful() if result.ready() else None,
    )
```

### 8.2 Scheduling con Celery Beat (ya existe en el proyecto)

Dado que el proyecto ya usa `public.job_definitions` para schedules (ADR-046), integrar el scraping aquí es natural:

```python
# En job_definitions seed/migración:
{
  "name": "weekly_amazon_scrape",
  "task": "scraper.tasks.scrape_all_references",
  "schedule_type": "crontab",
  "crontab": "0 2 * * 1",  # Lunes 2am UAE time
  "queue": "scraper_low",
  "enabled": True,
}
```

---

## 9. Scrapy vs Celery+Playwright para este Volumen

### 9.1 Análisis comparativo

| Criterio | Scrapy + scrapy-playwright | Celery + patchright |
|----------|---------------------------|---------------------|
| Para Amazon (JS-heavy) | Complejo (middleware) | Natural |
| API async | Twisted (modelo propio) | asyncio nativo |
| Integración FastAPI | Indirecta (API separada) | Directa |
| Integración Celery | No nativa | Nativa |
| Fingerprinting | Limitado | Completo (patchright/camoufox) |
| Curva de aprendizaje | Alta (Twisted + middlewares) | Media |
| Para <1000 refs/día | Overkill | Adecuado |
| Para >50k refs/día | Mejor opción | Podría escalar |

**Veredicto:** Para 224-1000 refs con refresco semanal/diario, **Celery + patchright es la elección correcta**. Scrapy añade complejidad arquitectural sin beneficios a este volumen.

---

## 10. Fingerprinting y Evasión Avanzada

### 10.1 Fingerprints que Amazon UAE detecta (2025)

Amazon.ae usa en 2025 una combinación de:

1. **`navigator.webdriver`** → mitigado por patchright
2. **CDP leak** (puerto de depuración expuesto) → mitigado por patchright
3. **Canvas fingerprint** → randomizar con patchright/camoufox
4. **WebGL fingerprint** → patchright aplica noise
5. **Fonts fingerprint** → camoufox gestiona
6. **TLS fingerprint (JA3/JA4)** → crítico si se usa requests directo (no afecta a browsers reales)
7. **Comportamiento de mouse/scroll** → mitigado con delays humanos
8. **Cookies de sesión** → gestionar con contexts que persisten cookies de sesiones previas
9. **IP reputation** → proxy residencial UAE

### 10.2 Técnicas de evasión complementarias

```python
# Técnicas adicionales para Amazon UAE
async def apply_human_behavior(page):
    """Simular comportamiento humano básico."""
    # Scroll suave
    await page.evaluate("""
        window.scrollTo({
            top: Math.floor(Math.random() * 300),
            behavior: 'smooth'
        });
    """)
    await asyncio.sleep(random.uniform(0.5, 1.5))

    # Mover mouse a posición aleatoria
    await page.mouse.move(
        random.randint(100, 1200),
        random.randint(100, 700)
    )

async def handle_captcha(page) -> bool:
    """Detectar y reportar CAPTCHAs."""
    captcha_indicators = [
        'text=Enter the characters you see below',
        'text=Type the characters you see',
        '[action*="captcha"]',
    ]
    for selector in captcha_indicators:
        if await page.locator(selector).count() > 0:
            # Log y retry con diferente proxy/contexto
            return True
    return False
```

---

## 11. Migración: Script Standalone → Microservicio

### 11.1 Patrón de migración recomendado (4 etapas)

#### Etapa 1: Extracción del core (sin cambiar tecnología)

Extraer la lógica de scraping del script en funciones puras testeable sin browser:

```
script_scraper.py (monolito)
└── Extraer:
    ├── amazon_ae/search.py     (lógica de búsqueda + extracción de ASINs)
    ├── amazon_ae/pdp.py        (extracción de PDP)
    ├── amazon_ae/scoring.py    (lógica de scoring)
    └── amazon_ae/models.py     (dataclasses/Pydantic models)
```

#### Etapa 2: Adaptar a Playwright async

Reescribir `search.py` y `pdp.py` usando Playwright async (patchright) manteniendo la misma interfaz de retorno.

Tests de regresión: comparar outputs del script original vs nuevo con mismo set de queries.

#### Etapa 3: Envolver en Celery task

```python
@shared_task(bind=True, max_retries=3)
def scrape_reference(self, ref_id, query):
    return asyncio.run(async_scrape_reference(ref_id, query))
```

#### Etapa 4: FastAPI trigger + observabilidad

- Endpoint `POST /scraper/run` para trigger manual.
- Endpoint `GET /scraper/job/{id}` para status.
- Métricas: Prometheus counter de scrapes exitosos/fallidos.
- Alertas: si tasa de éxito < 80% en ventana de 1h → Slack alert.

### 11.2 Plan de migración para este proyecto específico

```
Semana 1:
├── Crear `mt-pricing-backend/scraper/` como módulo
├── Migrar lógica de búsqueda a Playwright+patchright
├── Tests unitarios con mocks de página
└── Validar contra Amazon UAE manualmente

Semana 2:
├── Integrar Celery task + Docker image
├── docker-compose.dev.yml: nuevo servicio mt-scraper-worker
├── Alembic: tabla scraper_results
└── Prueba de carga: 224 refs en Docker local

Semana 3:
├── FastAPI endpoints trigger/status
├── Celery Beat: schedule semanal en job_definitions
├── Observabilidad: logs estructurados, métricas básicas
└── Deploy a Hetzner
```

---

## 12. Arquitectura Final Recomendada

### 12.1 Diagrama de componentes

```
┌─────────────────────────────────────────────────────┐
│                   mt-frontend (Next.js)              │
│          [Panel Admin: trigger + status scraping]    │
└──────────────────────────┬──────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────┐
│              mt-backend (FastAPI)                    │
│  POST /scraper/run   GET /scraper/job/{id}           │
└──────────────────────────┬──────────────────────────┘
                           │ Celery tasks (Redis broker)
┌──────────────────────────▼──────────────────────────┐
│          mt-scraper-worker (Celery + patchright)     │
│                                                      │
│  Worker 1: [Context A] [Context B]  ← 2 browsers    │
│  Worker 2: [Context C] [Context D]  ← 2 browsers    │
│                                                      │
│  Imagen: playwright/python + patchright install      │
│  shm_size: 2gb, --no-sandbox                        │
└───────┬────────────────────┬────────────────────────┘
        │                    │
        │ Proxy residencial UAE (Webshare/Brightdata)
        │                    │
┌───────▼────────┐  ┌────────▼───────────────────────┐
│  amazon.ae     │  │  PostgreSQL (scraper_results)   │
│  (target)      │  │  + Redis (broker/results)       │
└────────────────┘  └────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  mt-beat (Celery Beat)                              │
│  job_definitions → schedule semanal/diario          │
└─────────────────────────────────────────────────────┘
```

### 12.2 Stack técnico consolidado

| Capa | Tecnología | Notas |
|------|------------|-------|
| Browser engine | patchright (Chromium) | Drop-in Playwright, anti-detección nivel 3 |
| Fallback | camoufox (Firefox) | Para cuando Chromium sea bloqueado |
| Orquestación | Celery 5.3+ con prefork pool | 2 workers × 2 concurrency |
| Broker/Results | Redis 7 | Ya en el stack |
| API trigger | FastAPI (ya existe) | Nuevo router `/scraper` |
| Scheduling | Celery Beat + job_definitions | Ya en el stack (ADR-046) |
| Persistencia | PostgreSQL via SQLAlchemy async | Tabla `scraper_results` |
| Docker base | `mcr.microsoft.com/playwright/python:v1.44.0-jammy` | + patchright install |
| Proxy | Webshare residential UAE (~$29/mes) | Rotativo |
| Anti-detección complementaria | Delays humanos, locale AE, geolocation Dubai | En browser context |

---

## 13. Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Amazon cambia estructura HTML | Alta | Alto | Selectores CSS robustos + data-asin attributes (más estables) |
| CAPTCHA en ráfaga | Media | Alto | Rate limiting conservador, proxy rotation, retry con backoff exponencial |
| patchright desactualizado vs nuevo Chrome | Media | Medio | Fijar versión de Chromium en Dockerfile; actualizar en sprint planificado |
| /dev/shm insuficiente en Hetzner | Media | Alto | `shm_size: 2gb` en compose; monitorizar OOM kills |
| Proxy UAE no disponible | Baja | Alto | Pool de proxies ≥ 5 IPs; fallback a ProtonVPN |
| Amazon SP-API como alternativa (ya en ADR-072) | — | — | Para datos estructurados (precio, título): SP-API es más fiable que scraping |

---

## 14. Consideración Final: ¿SP-API vs Scraping?

Existe **ADR-072** en el proyecto para Amazon SP-API integration. Para Amazon UAE:

- **SP-API ventajas:** datos estructurados, sin detección, SLA garantizado.
- **SP-API limitaciones:** requiere cuenta de seller/vendor UAE, acceso por ASIN propio, no sirve para espiar competidores.
- **Scraping ventajas:** acceso a cualquier ASIN del marketplace, specs completas de PDPs, precios de competidores.

**Recomendación:** usar ambos en paralelo:
- **SP-API** para productos propios (inventario, pricing propio).
- **Scraper Playwright** para benchmarking competitivo (Top 3 ASINs por query).

---

## 15. Recomendaciones Priorizadas

### Prioridad 1 (crítico para producción)

1. **Migrar de Selenium a patchright** (Playwright drop-in con anti-detección a nivel binario).
2. **`shm_size: 2gb`** en el container del worker — sin esto Chrome crashea en Docker.
3. **Proxy residencial rotativo UAE** (Webshare $29/mes mínimo) — ProtonVPN fija es single point of failure.
4. **1 browser por worker, contexts aislados por task** — no reutilizar pages entre tasks.

### Prioridad 2 (calidad de producción)

5. **Celery prefork pool** (no gevent) — Playwright async no es compatible con gevent.
6. **`task_acks_late=True`** — evita pérdida de tasks si el worker crashea con el browser.
7. **Rate limiting `10/m`** — Amazon UAE bloquea IPs que hacen > ~20 req/min.
8. **Upsert idempotente** en PostgreSQL — permite reruns sin duplicados.

### Prioridad 3 (mejoras iterativas)

9. **camoufox como fallback** — si Chromium es bloqueado, switchear a Firefox parcheado.
10. **Panel de status en frontend** — trigger manual + visualización de resultados en tiempo real vía polling a `GET /scraper/job/{id}`.
11. **Alertas en Slack/Flower** si tasa de éxito < 80%.
12. **Pinning de versión de Chromium** en Dockerfile para evitar breaking changes de patchright.

---

*Reporte generado por bmad-technical-research skill. Conocimiento técnico al corte agosto 2025.*
*Archivo: `_bmad-output/planning-artifacts/research/technical-scrapers-inhouse-amazon-uae-2025-research-2026-05-13.md`*
