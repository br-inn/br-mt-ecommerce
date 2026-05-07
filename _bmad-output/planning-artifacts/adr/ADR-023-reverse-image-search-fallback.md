# ADR-023: Reverse image search como fallback del subsistema de comparación

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT
- Related: ADR-012, ADR-022, ADR-024, FR-CMP-REVIMG-01

## Contexto

Cuando todo el resto del pipeline falla (embedding bajo, OCR vacío, VLM judge `uncertain`), la pregunta útil es: *¿dónde más aparece esta foto en internet?* Esto es valioso para:

1. Detectar foto de catálogo reutilizada por múltiples vendors → señal de competidor legítimo o counterfeit.
2. Encontrar el producto original cuando un SKU desconocido aparece en un marketplace.
3. Cross-reference para enforcement MAP / MSRP en fases posteriores (Fase 4+).

La recomendación externa al sponsor (2026-05-06) propone añadir reverse image search **como fallback opcional** activable cuando el scorer + VLM devuelven `calibrated_confidence < 0,50`.

## Decisión

- **Implementar hooks Fase 1 detrás de feature flag `feature.reverse_image_search_enabled`**, con **default OFF**.
- **Puerto** `ReverseImageSearchService` (TypeScript) con adapters por proveedor.
- **Adapters Fase 1**:
  - `TinEyeAdapter` (oficial; ~$300/mes 50 000 búsquedas).
  - `GoogleLensSerpApiAdapter` (no oficial vía SerpAPI; ~$1,50 / 1 000 búsquedas; mejor cobertura web).
  - `BingVisualAdapter` (alternativa oficial Microsoft).
- **Trigger**: invocación automática desde el orquestador del scorer cuando `calibrated_confidence < 0,50`, **antes** del descarte.
- **Persistencia**: campos `competitor_listings.reverse_image_hits` (JSONB), `reverse_image_searched_at`, `reverse_image_provider`.
- **Re-scoring**: si una URL hit pertenece al `manufacturers_whitelist.canonical_domains` del SKU master, se re-dispara scoring con boost de confianza.
- **Rate limiting**: configurable por proveedor (default 200 búsquedas / día) para acotar coste cuando el flag esté ON.

Activación efectiva queda gateada a una decisión operativa post-G2: encender flag sólo si la cola humana está sostenible y el coste cabe en presupuesto.

## Alternativas evaluadas

- **No implementar Fase 1**: pierde la opción cuando el resto del pipeline no resuelve. Coste de implementación es bajo (puerto + 1 adapter + feature flag). Descartado.
- **Activar default ON**: añade coste y latencia sin haber medido valor real. Descartado para Fase 1; se evalúa post-POC.
- **Pinterest visual search**: cobertura lifestyle / consumer; débil en industrial. Descartado.

## Consecuencias positivas

- Hooks listos = activable sin refactor cuando el operador valide coste.
- Detección de fotos de catálogo reutilizadas → input directo para enforcement MAP/MSRP futuro (Fase 4+).
- Permite rescatar candidatos auténticos cuya foto es de baja calidad localmente pero aparece en el dominio del fabricante canónico.

## Consecuencias negativas / riesgos

- Vendor risk: Google Lens vía SerpAPI no es canal oficial Google (puede degradar / cambiar TOS).
- Coste si flag se activa sin rate limit: 100k búsquedas/mes en TinEye = ~$600/mes.
- Latencia adicional 1-3 s sobre los candidatos en zona < 0,50 (mitigable async).

## Cuándo revisar

- **G2 (S2-S3)**: decidir si encender flag con TinEye sobre 50 SKUs piloto y medir lift en cobertura.
- **G4 (S6)**: revalidar coste / valor con números reales.
- Cuando MT empiece a operar enforcement MAP / MSRP (Fase 4+): el adapter ya estará listo.
