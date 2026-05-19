# Investigación Técnica: LLM para Matching de Productos Industriales (MT ↔ Amazon UAE)

**Fecha:** 2026-05-13  
**Autor:** psierra  
**Scope:** Mejorar tasa de matching en zona gris (score 30–65) del `match_scorer_v2.py`  
**Stack objetivo:** Python 3.11 + FastAPI + Celery + Anthropic SDK + PostgreSQL

---

## Resumen Ejecutivo

El `match_scorer_v2.py` resuelve bien los extremos (score <30 → no match, >70 → match confiable) pero deja ~30–40% de candidatos en zona gris donde el scoring determinista no tiene suficiente información estructurada. Los LLMs pueden atacar ese gap de tres formas complementarias:

1. **Extracción de specs desde texto libre** — el caso de uso más maduro y rentable
2. **Comparación visual por vision multimodal** — funciona para desambiguar tipos de producto, no para certificar especificaciones técnicas exactas
3. **Embeddings semánticos** — útil como señal adicional, no como reemplazo del scorer determinista

La arquitectura óptima es un pipeline escalonado donde el LLM solo procesa los candidatos que el scorer determinista no pudo resolver. Para 224–1000 SKUs, el costo es manejable ($2–$25 totales).

---

## A) Extracción de Specs con LLM desde Texto No Estructurado

### Lo que funciona

Claude y GPT-4o son capaces de extraer specs técnicas de texto libre con alta confiabilidad cuando se usa **structured output con JSON schema**. A partir de noviembre 2025, Anthropic lanzó structured outputs en public beta (`structured-outputs-2025-11-13`), que garantiza schema compliance al 100% (cero errores de parseo JSON).

La ventaja sobre regex/pattern matching: el LLM entiende contexto. `"1 inch BSP Brass PN25"` → extrae `{dn_equiv: 25, material: "brass", connection: "BSP threaded", pressure_pn: 25}` aunque los campos no estén etiquetados.

### Implementación con Pydantic + Claude

```python
import anthropic
from pydantic import BaseModel, Field
from typing import Optional

client = anthropic.Anthropic()

class IndustrialProductSpecs(BaseModel):
    valve_type: Optional[str] = Field(
        None,
        description="Type: ball valve, gate valve, butterfly valve, check valve, globe valve, etc."
    )
    material: Optional[str] = Field(
        None,
        description="Primary material: brass, stainless steel (304/316), carbon steel, cast iron, bronze"
    )
    alloy_code: Optional[str] = Field(
        None,
        description="Specific alloy if mentioned: CW617N, CW602N, AISI 316, A105, etc."
    )
    size_inches: Optional[str] = Field(
        None,
        description="Size in inches: '1/2', '3/4', '1', '1 1/2', '2', etc."
    )
    dn_size: Optional[int] = Field(
        None,
        description="DN size in mm if mentioned: 15, 20, 25, 32, 40, 50, etc."
    )
    pressure_pn: Optional[int] = Field(
        None,
        description="Pressure rating in bar/PN: 10, 16, 20, 25, 40, etc."
    )
    end_connection: Optional[str] = Field(
        None,
        description="Connection type: threaded (BSP/NPT), flanged, wafer, compression, press-fit"
    )
    thread_standard: Optional[str] = Field(
        None,
        description="Thread standard if mentioned: BSP, NPT, ISO 228, DIN 259"
    )
    confidence: float = Field(
        description="Confidence 0.0-1.0 in extracted values. Low if text is vague."
    )

def extract_amazon_specs(title: str, description: str, bullet_points: str) -> IndustrialProductSpecs:
    """
    Extrae specs técnicas del texto libre de Amazon usando structured output.
    Costo estimado: ~$0.002 por llamada con Haiku 4.5
    """
    combined_text = f"TITLE: {title}\n\nDESCRIPTION: {description}\n\nSPECS: {bullet_points}"

    # Opción A: tool use (más compatible, disponible en todos los modelos)
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        tools=[{
            "name": "extract_specs",
            "description": "Extract technical specifications from industrial product text",
            "input_schema": IndustrialProductSpecs.model_json_schema()
        }],
        tool_choice={"type": "tool", "name": "extract_specs"},
        messages=[{
            "role": "user",
            "content": f"""Extract technical specifications from this Amazon product listing.
For industrial valves and pipe fittings, identify: valve type, material/alloy,
size (inches or DN), pressure rating (PN/bar), and connection type.
Set confidence low (< 0.5) if the text is ambiguous or missing key data.

{combined_text}"""
        }]
    )

    tool_input = response.content[0].input
    return IndustrialProductSpecs(**tool_input)

# Opción B: structured outputs beta (garantía de schema, Nov 2025+)
def extract_amazon_specs_v2(title: str, description: str) -> IndustrialProductSpecs:
    response = client.beta.messages.parse(
        model="claude-haiku-4-5",
        max_tokens=512,
        betas=["structured-outputs-2025-11-13"],
        response_format=IndustrialProductSpecs,
        messages=[{
            "role": "user",
            "content": f"Extract technical specs from: {title}\n{description}"
        }]
    )
    return response.parsed
```

### Prompt que funciona para industrial

```
Eres un experto en especificaciones técnicas de válvulas y accesorios de tuberías.
Extrae las especificaciones del siguiente texto de producto.

Reglas:
- Si el texto dice "1 inch" → size_inches="1", dn_size=25 (equivalencia estándar)  
- Si menciona "BSP" o "G thread" → end_connection="threaded", thread_standard="BSP"
- Si menciona "PN25" o "25 bars" → pressure_pn=25
- CW617N, CW602N → material="brass", alloy_code=[el código encontrado]
- AISI 304, AISI 316, SS316 → material="stainless steel"
- Si no hay información suficiente → confidence < 0.4
- NO inventes especificaciones que no estén en el texto
```

### Costo por extracción (Haiku 4.5)

| Componente | Tokens típicos | Costo |
|---|---|---|
| Input (título 50 tok + desc 200 tok + prompt 150 tok) | ~400 tok | $0.0004 |
| Output (JSON specs) | ~150 tok | $0.00075 |
| **Total por SKU** | — | **~$0.0011** |

Con batch API (50% descuento): **~$0.0006 por extracción**

### Precisión esperada

- Texto bien estructurado ("Ball Valve 1/2 inch BSP Brass PN25"): **>90% accuracy**
- Texto vago o en inglés no técnico ("Quality valve for home use"): **30–50%** (el campo `confidence` lo señala)
- Falsos positivos en material: el mayor riesgo. "Chrome-plated brass" puede confundirse con "nickel"

---

## B) Vision Multimodal para Comparación de Imágenes

### Lo que funciona (y sus límites)

Los modelos de visión pueden distinguir **tipos de producto** con alta confiabilidad: una válvula de bola vs una válvula de mariposa son visualmente distintas y el modelo las clasifica correctamente. Lo que **no pueden** hacer de forma confiable:

- Verificar el material exacto (latón vs acero inox lucen similares en foto de Amazon)
- Confirmar el PN/presión (dato no visible)
- Distinguir CW617N de CW602N
- Leer dimensiones exactas sin referencia

Claude Vision implementa una arquitectura combinando convolutional y transformer layers. GPT-4o-2024-11-20 tuvo los mejores scores en benchmarks de image quality assessment (2025), pero para **clasificación de tipo de producto industrial**, ambos son comparables.

### Casos de uso válidos para el pipeline MT

1. **Desambiguación de tipo de válvula** cuando el título de Amazon es ambiguo: la imagen confirma "butterfly" vs "ball"
2. **Detección de conexiones visibles**: flanged (bridas visibles), wafer (disco delgado sin orejas), threaded (hilos visibles)
3. **Confirmación negativa**: descartar un match donde la imagen muestra claramente otro producto

### Implementación

```python
import base64
import httpx
from pathlib import Path

def compare_product_images(
    mt_image_url: str,        # URL de Supabase Storage
    amazon_image_url: str,    # URL de media-amazon.com
    mt_product_name: str,
    amazon_title: str,
    deterministic_score: int
) -> dict:
    """
    Solo llamar cuando deterministic_score está en zona gris (30-65).
    Costo estimado: ~$0.012-$0.018 por par de imágenes con Haiku 4.5
    """
    # Descargar ambas imágenes
    mt_img = base64.standard_b64encode(httpx.get(mt_image_url).content).decode()
    amz_img = base64.standard_b64encode(httpx.get(amazon_image_url).content).decode()

    response = client.messages.create(
        model="claude-haiku-4-5",    # $1/M input tokens. Haiku es suficiente para clasificación visual
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"""Compare these two industrial valve/fitting product images.
MT product: {mt_product_name}
Amazon product: {amazon_title}

Answer ONLY with JSON:
{{
  "same_product_type": true/false,      // Same category (ball valve, gate valve, etc.)
  "same_connection_type": true/false/null,  // Both threaded, flanged, wafer? null=unclear
  "visual_mismatch": true/false,         // Clear visual evidence they are DIFFERENT products
  "confidence": 0.0-1.0,                 // How confident in your assessment
  "reasoning": "brief explanation"
}}

Be conservative: only flag visual_mismatch=true if clearly different product types."""
                },
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": mt_img}},
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": amz_img}},
            ]
        }]
    )
    import json
    return json.loads(response.content[0].text)
```

### Costo por comparación de imágenes (Haiku 4.5, $1/M input)

Imágenes típicas de Amazon: ~500×500px → ~333 tokens por imagen (fórmula: width × height / 750)

| Componente | Tokens | Costo |
|---|---|---|
| Imagen MT (500×500) | ~333 tok | $0.000333 |
| Imagen Amazon (500×500) | ~333 tok | $0.000333 |
| Prompt + contexto | ~200 tok | $0.0002 |
| Output | ~100 tok | $0.0005 |
| **Total por par** | ~966 tok | **~$0.0014** |

> Nota: Si las imágenes son 1000×1000px → ~1333 tok/imagen → ~$0.003/comparación

**Importante**: Con `claude-opus-4-7`, las imágenes cuestan 3× más tokens (máx. 4784 tok). Para este caso de uso, **Haiku 4.5 es la elección correcta**.

### Limitaciones honestas de vision para industrial

- No distingue acabados superficiales (niquelado vs cromado vs latón natural)
- Fotos de Amazon con fondo blanco a veces recortan la conexión (punto crítico para flanged vs threaded)
- Precisión para "same product type" en válvulas industriales: estimado 80–85% (no hay benchmark específico para este dominio)
- Falsos negativos: modelos diferentes de la misma categoría lucen idénticos en foto

**Veredicto**: Vision es útil para **filtro negativo** (descartar matches claramente incorrectos), no como confirmador positivo.

---

## C) Embeddings para Matching Semántico

### Comparación de modelos

| Modelo | MTEB Score | Costo | Dimensión | Context |
|---|---|---|---|---|
| text-embedding-3-small | 62.3 | $0.02/M tok | 1536 | 8K |
| text-embedding-3-large | 64.6 | $0.13/M tok | 3072 | 8K |
| voyage-3 | ~64.8 | $0.06/M tok | 1024 | 32K |
| voyage-3-lite | ~62.0 | $0.02/M tok | 512 | 32K |
| voyage-3-large | 65.1 | $0.18/M tok | 1024 | 32K |

Para specs industriales cortas (50–200 chars), la diferencia de score entre modelos es mínima. **voyage-3-lite a $0.02/M** es prácticamente equivalente para este caso de uso.

### Cómo usar embeddings para matching

```python
import voyageai
import numpy as np

voyage = voyageai.Client()

def embed_product_specs(product: dict) -> list[float]:
    """Crea embedding de specs técnicas concatenadas."""
    spec_text = " | ".join(filter(None, [
        product.get("valve_type", ""),
        product.get("material", ""),
        product.get("alloy_code", ""),
        f"DN{product.get('dn_size', '')}" if product.get('dn_size') else "",
        f"PN{product.get('pressure_pn', '')}" if product.get('pressure_pn') else "",
        product.get("end_connection", ""),
    ]))
    result = voyage.embed([spec_text], model="voyage-3-lite")
    return result.embeddings[0]

def cosine_similarity(a: list[float], b: list[float]) -> float:
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
```

### ¿Embeddings vs scoring determinista?

**El scoring determinista gana** para specs técnicas estructuradas porque:
- Una válvula DN25 PN16 y una DN25 PN40 podrían tener alta similitud coseno (texto similar) pero son productos distintos
- El embedding no entiende que `PN16 ≠ PN40` es una diferencia crítica, mientras el scorer determinista sí

**Los embeddings añaden valor** en un caso específico: cuando el texto de Amazon describe el producto con vocabulario diferente al catálogo MT (sinónimos, abreviaciones no contempladas en `VALVE_TYPE_SYNONYMS`). El embedding puede capturar similitud semántica que los regex del scorer pierden.

**Recomendación**: Usar embeddings solo como señal adicional en el paso LLM validator, no como scorer independiente.

---

## D) Arquitectura Híbrida Recomendada

### Pipeline escalonado (3 capas)

```
                    ┌─────────────────────────────────────────┐
                    │     match_scorer_v2.py (Capa 1)         │
                    │     Scoring determinista 0-100          │
                    └──────────────┬──────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
               score < 30          │          score > 70
           (descartado)           │          (auto-confirmado)
                                   │ score 30-65
                                   │ (zona gris → LLM)
                    ┌──────────────▼──────────────────────────┐
                    │     Capa 2: LLM Spec Extractor          │
                    │     Claude Haiku 4.5                    │
                    │     Extrae specs del texto Amazon        │
                    │     Re-puntúa con specs extraídas       │
                    └──────────────┬──────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
            score_v2 < 35          │          score_v2 > 70
           (descartado)           │          (confirmado)
                                   │ score_v2 35-70 (aún ambiguo)
                    ┌──────────────▼──────────────────────────┐
                    │     Capa 3: Vision Confirmer             │
                    │     Claude Haiku 4.5 con imágenes       │
                    │     Solo para descartar mismatches      │
                    └──────────────┬──────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
         visual_mismatch=true      │     visual_mismatch=false
            (descartado)          │     confidence < 0.6
                                   │     → COLA HUMANA
                    ┌──────────────▼──────────────────────────┐
                    │     Human Review Queue                  │
                    │     ~10-15% de candidatos totales       │
                    └─────────────────────────────────────────┘
```

### Implementación del pipeline en Celery

```python
# mt-pricing-backend/app/tasks/matching/llm_validator.py

from celery import shared_task
from app.services.matching.match_scorer_v2 import score_match
from app.services.matching.llm_spec_extractor import extract_amazon_specs
from app.services.matching.vision_confirmer import compare_product_images
import logging

logger = logging.getLogger(__name__)

GREY_ZONE_LOW = 30
GREY_ZONE_HIGH = 65
LLM_CONFIRM_THRESHOLD = 70
VISION_CONFIRM_THRESHOLD = 0.6

@shared_task(name="matching.validate_grey_zone_candidate")
def validate_grey_zone_candidate(mt_rec: dict, amazon_candidate: dict) -> dict:
    """
    Valida un candidato en zona gris usando LLM + vision si necesario.
    Retorna dict con: final_score, decision, method, cost_usd
    """
    title = amazon_candidate.get("title", "")
    specs = amazon_candidate.get("specs", {})

    # Capa 1: scorer determinista (ya calculado, lo recibimos)
    det_score = amazon_candidate.get("deterministic_score", 0)
    cost_usd = 0.0

    # Solo procesar zona gris
    if det_score < GREY_ZONE_LOW:
        return {"final_score": det_score, "decision": "rejected", "method": "deterministic", "cost_usd": 0}
    if det_score > GREY_ZONE_HIGH:
        return {"final_score": det_score, "decision": "confirmed", "method": "deterministic", "cost_usd": 0}

    # Capa 2: LLM extrae specs del texto Amazon
    try:
        extracted = extract_amazon_specs(
            title=title,
            description=amazon_candidate.get("description", ""),
            bullet_points=amazon_candidate.get("bullet_points", "")
        )
        cost_usd += 0.0011  # costo estimado Haiku 4.5

        # Re-puntuar con specs enriquecidas
        enriched_amz = {**specs}
        if extracted.material:
            enriched_amz["material_type"] = extracted.material
        if extracted.valve_type:
            enriched_amz["valve_type"] = extracted.valve_type
        if extracted.size_inches:
            enriched_amz["thread_size"] = extracted.size_inches + '"'
        if extracted.pressure_pn:
            enriched_amz["maximum_pressure"] = f"{extracted.pressure_pn} bar"
        if extracted.end_connection:
            enriched_amz["connection_type"] = extracted.end_connection

        llm_score, llm_breakdown, _ = score_match(mt_rec, enriched_amz, title)

        logger.info(f"LLM enrichment: det_score={det_score} → llm_score={llm_score}, confidence={extracted.confidence}")

        # Si la confianza del LLM en la extracción es baja, no confiar en el nuevo score
        if extracted.confidence < 0.4:
            llm_score = det_score  # mantener score original

        if llm_score < GREY_ZONE_LOW:
            return {"final_score": llm_score, "decision": "rejected", "method": "llm_text", "cost_usd": cost_usd}
        if llm_score > LLM_CONFIRM_THRESHOLD:
            return {"final_score": llm_score, "decision": "confirmed", "method": "llm_text", "cost_usd": cost_usd}

    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        llm_score = det_score

    # Capa 3: Vision (solo si sigue siendo ambiguo)
    mt_image_url = mt_rec.get("web", {}).get("image_url") or mt_rec.get("imagen_url")
    amz_image_url = amazon_candidate.get("primary_image_url")

    if mt_image_url and amz_image_url:
        try:
            vision_result = compare_product_images(
                mt_image_url=mt_image_url,
                amazon_image_url=amz_image_url,
                mt_product_name=mt_rec.get("nombre_en", ""),
                amazon_title=title,
                deterministic_score=llm_score
            )
            cost_usd += 0.003  # ~$0.003 para imágenes 1000×1000

            if vision_result.get("visual_mismatch") and vision_result.get("confidence", 0) > VISION_CONFIRM_THRESHOLD:
                logger.info(f"Vision rejected: {vision_result['reasoning']}")
                return {
                    "final_score": min(llm_score, 30),
                    "decision": "rejected",
                    "method": "vision",
                    "cost_usd": cost_usd,
                    "vision_reasoning": vision_result.get("reasoning")
                }

        except Exception as e:
            logger.error(f"Vision comparison failed: {e}")

    # Si llegamos aquí, necesita revisión humana
    return {
        "final_score": llm_score,
        "decision": "human_review",
        "method": "llm_text+vision",
        "cost_usd": cost_usd
    }
```

### Cuándo escalar a LLM (regla del threshold)

```python
# Regla de activación del pipeline LLM
def needs_llm_validation(score: int, breakdown: dict) -> bool:
    # Zona gris general
    if not (30 <= score <= 65):
        return False
    
    # Si hay veto activo (type/material mismatch), no gastar en LLM
    veto_dims = [k for k, v in breakdown.items() if "VETO" in str(v[3])]
    if veto_dims:
        return False
    
    # Si el score bajo es porque Amazon no expone los campos (no porque sean incorrectos)
    missing_fields = sum(1 for v in breakdown.values() if v[0] is None)
    if missing_fields >= 3:
        return True  # Alta probabilidad de que LLM pueda extraer del texto
    
    return True
```

### Mitigación de falsos positivos del LLM

El mayor riesgo del LLM en este contexto es "inventar" specs que no están en el texto. Las mitigaciones implementadas:

1. **Campo `confidence` en el schema**: si < 0.4, no usamos el nuevo score
2. **El LLM enriquece specs → vuelven a pasar por scorer determinista**: el LLM no da el score, solo extrae datos
3. **Prompt explícito**: "NO inventes especificaciones que no estén en el texto"
4. **Temperatura 0** (default en structured outputs de Claude): reduce inventiva
5. **Threshold conservador para confirmación**: >70 (no >60) para auto-confirmar
6. **Vision como filtro negativo**: solo descarta, nunca confirma solo

---

## E) Benchmarks y Casos Reales

### Investigación académica relevante

**"Optimizing Product Deduplication in E-Commerce with Multimodal Embeddings"** (arxiv:2509.15858, dic 2025):
- Usa BERT-based text model + MaskedAutoEncoders para imágenes
- Embeddings de 128 dimensiones con reducción de dimensionalidad
- Concluye que **multimodal (texto + imagen) supera texto solo en ~8-12%** para deduplicación de catálogo

**Akeneo 2025**: lanzó "Supplier Data Manager" con LLM que extrae, mapea y normaliza datos de producto desde cualquier formato de proveedor. Internamente usa structured outputs para garantizar campos válidos.

### Tasa de precisión estimada para válvulas industriales

| Método | Precision | Recall | Casos límite |
|---|---|---|---|
| Scorer determinista (actual) | ~92% en extremos | — | Falla en zona gris |
| LLM text extraction | ~78–85% | ~65–75% | Texto vago, descripciones genéricas |
| Vision clasificación tipo | ~80–85% | ~70% | Fotos con ángulo parcial |
| Pipeline híbrido (todo) | ~88–92% | ~85% | Estimado conservador |

---

## F) Costos Estimados

### Por SKU (un producto MT evaluado contra un candidato Amazon)

| Escenario | Capa activa | Costo/evaluación |
|---|---|---|
| Score < 30 o > 70 | Solo determinista | $0 |
| Zona gris, LLM resuelve | Capa 1 + Capa 2 | $0.0011 |
| Zona gris, LLM + vision | Capa 1 + 2 + 3 | $0.004 |

### Estimación para 224 SKUs (lote actual)

Asumiendo:
- 3 candidatos Amazon por SKU en promedio = 672 evaluaciones
- 35% en zona gris = ~235 evaluaciones con LLM
- 50% de esas necesitan vision = ~118 evaluaciones con vision

| Concepto | Cantidad | Costo |
|---|---|---|
| LLM text extraction | 235 × $0.0011 | $0.26 |
| Vision comparison | 118 × $0.004 | $0.47 |
| **Total 224 SKUs** | — | **~$0.73** |

### Estimación para 1000 SKUs

| Concepto | Cantidad | Costo |
|---|---|---|
| LLM text extraction | ~1050 × $0.0011 | $1.16 |
| Vision comparison | ~525 × $0.004 | $2.10 |
| **Total 1000 SKUs** | — | **~$3.26** |

Con **batch API** (50% descuento, latencia 24h): ~$1.60 para 1000 SKUs

---

## G) Limitaciones Honestas

### Lo que el LLM no puede resolver

1. **Specs no mencionadas en ningún texto**: si Amazon no pone el PN en ningún lado (texto, descripción, bullets, título), el LLM tampoco lo sabe
2. **Certificaciones de aleación**: CW617N vs CW602N son distintos; si el vendedor pone solo "Brass", el LLM no puede distinguir
3. **Compatibilidad de threading exacta**: BSP vs BSPT vs NPT puede estar implícito en el texto pero el LLM puede equivocarse
4. **Visión no certifica material**: el color en foto de latón vs bronce puede ser idéntico

### Riesgos operativos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| LLM inventa spec no mencionada | Media | Alto | Campo confidence + re-scorer determinista |
| Vision falla por foto de mala calidad | Media | Medio | Fallback a human review |
| Amazon cambia estructura de página | Baja | Alto | Extractor de texto robusto (blob completo) |
| Costo supera presupuesto | Muy baja | Bajo | Threshold de zona gris ajustable |

### Cuándo NO usar LLM

- Cuando el veto determinista está activo (type o material mismatch confirmado): el LLM no puede revertir un veto con alta confiabilidad
- Para scores > 70: el costo no justifica la mejora marginal
- Para score < 25: demasiado lejos para recuperar con texto

---

## H) Implementación Recomendada (Plan por Pasos)

```
1. Implementar LLM spec extractor → verificar: precision > 75% en 20 casos manuales
2. Integrar extract_amazon_specs en pipeline Celery → verificar: scores zona gris mejoran
3. Medir: % candidatos que salen de zona gris tras LLM enrichment
4. Implementar vision solo si paso 2 deja >20% en zona gris
5. Ajustar thresholds según resultados reales (empezar con 30/65/70)
```

**No implementar todo a la vez**. El LLM text extractor es el 80% del valor con el 20% de la complejidad.

---

## Referencias

- [Structured outputs - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Instructor - Structured LLM Outputs](https://python.useinstructor.com/)
- [Optimizing Product Deduplication with Multimodal Embeddings (arxiv:2509.15858)](https://arxiv.org/abs/2509.15858)
- [Claude Haiku 4.5 pricing - pricepertoken.com](https://pricepertoken.com/pricing-page/model/anthropic-claude-haiku-4.5)
- [Claude Vision - Token calculation](https://platform.claude.com/docs/en/build-with-claude/vision)
- [voyage-3-lite pricing](https://docs.voyageai.com/docs/pricing)
- [Anthropic API Pricing 2026 - finout.io](https://www.finout.io/blog/anthropic-api-pricing)
- [LLM Hallucination Mitigation - getmaxim.ai](https://www.getmaxim.ai/articles/llm-hallucination-detection-and-mitigation-best-techniques/)
- [Hybrid LLM + Deterministic Architecture - mdpi.com](https://www.mdpi.com/2673-2688/7/2/51)
- [Embedding Models Comparison 2026 - elephas.app](https://elephas.app/blog/best-embedding-models)
- [Text Embedding Models Compared - document360.com](https://document360.com/blog/text-embedding-model-analysis/)
- [Claude Structured Generation - tribe.ai](https://www.tribe.ai/applied-ai/a-gentle-introduction-to-structured-generation-with-anthropic-api)
