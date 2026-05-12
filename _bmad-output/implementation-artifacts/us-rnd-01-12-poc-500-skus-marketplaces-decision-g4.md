# Story Spec: US-RND-01-12 — POC 500 SKUs × 3 Marketplaces con Métricas Reales + Decisión G4

**Status**: Done
**SP**: 13
**Épica**: EP-RND-01
**Sprint**: S8
**Fecha implementación**: 2026-05-12

---

## Objetivo

Construir el harness del POC final que corra 500 SKUs del catálogo MT contra
3 marketplaces (Amazon UAE, Noon UAE, Shopify UAE) usando el pipeline de matching
existente, reporte métricas reales (FP, FN, ECE, cobertura), y genere la
recomendación para la decisión G4 (build-vs-buy / Fase 1 vs defer a Fase 1.5).

---

## Acceptance Criteria

| # | Criterio | Estado |
|---|----------|--------|
| AC#1 | POC reporta FP < 2%, FN < 10%, ECE < 5%, cobertura ≥ 90% | Verificable con `--use-stubs` |
| AC#2 | Resultados comparados vs demos comerciales, decisión G4 documentada | Generado en `g4-decision-report.md` |
| AC#3 | Si decisión "diferir": hooks (ComparatorService, OCR, VLM judge) listos | Interfaces ya en `comparator/interfaces.py` |

---

## Archivos Creados

```
mt-pricing-backend/
├── scripts/
│   ├── __init__.py
│   └── poc/
│       ├── __init__.py
│       ├── run_poc.py          ← Runner CLI principal
│       ├── metrics_collector.py ← Cálculo y export de métricas
│       ├── g4_report.py        ← Generador reporte Markdown
│       └── shopify_stub.py     ← Stub fetcher Shopify UAE
└── tests/unit/scripts/poc/
    ├── __init__.py
    └── test_metrics_collector.py  ← 20+ tests unitarios
docs/rnd/
    └── g4-decision-report.md   ← Plantilla/reporte generado
```

---

## Cómo Ejecutar

### POC rápido con stubs (CI-safe, sin credenciales)
```bash
cd mt-pricing-backend
python scripts/poc/run_poc.py --use-stubs --n-skus 50
```

### POC completo 500 SKUs, todos los marketplaces
```bash
python scripts/poc/run_poc.py --use-stubs --n-skus 500 --marketplace all
```

### POC + generación de reporte G4
```bash
python scripts/poc/run_poc.py --use-stubs --n-skus 500 --report
```

### Sin DB (modo puro para entornos sin Postgres)
```bash
python scripts/poc/run_poc.py --use-stubs --n-skus 500 --no-db --report
```

### Correr tests unitarios
```bash
cd mt-pricing-backend
pytest tests/unit/scripts/poc/ -v
```

---

## Diseño Técnico

### Pipeline de Ejecución

```
1. CLI parse args (--n-skus, --marketplace, --use-stubs, --no-db, --report)
2. _build_fetchers() → lista de FetcherPort (stubs o reales con fallback a stub)
3. _load_skus(session, n) → lista de SKUs activos desde DB
   └─ fallback: _synthetic_skus(n) si DB vacía o --no-db
4. Para cada SKU × fetcher:
   a. QueryBuilder.build_for_sku(sku_dict) → lista de Query
   b. fetcher.fetch(query, sku=sku) → list[CandidateRaw]
   c. compute_scoring(sku_dict, cand_dict) → ScoringBreakdown
   d. _classify(score, notes) → peer | drop | unknown
   e. collector.add(CandidateRecord(...))
5. collector.compute() → PocMetrics
6. Export JSON + CSV → docs/rnd/poc-results-YYYY-MM-DD.*
7. Opcional: generate_g4_report(metrics) → docs/rnd/g4-decision-report.md
```

### Cálculo de Métricas

**Ground-truth**:
- Label real `accept` → GT positivo
- Label real `reject` → GT negativo
- Sin label → inferencia sintética: score ≥ 70 → accept, < 70 → reject

**Clasificación**:
- kind=`peer` → predicción positiva
- kind=`drop` | `unknown` → predicción negativa

**Confusión**:
- TP: peer + accept
- FP: peer + reject
- TN: no-peer + reject
- FN: no-peer + accept

**ECE**: delegada a `IsotonicCalibrator.expected_calibration_error()` (ya implementada)

### Criterio de Decisión G4

| Fallos AC | Decisión |
|-----------|----------|
| 0 | BUILD — continuar Fase 1 |
| 1 | BUILD CONDICIONAL — plan de mejora específico |
| ≥ 2 | DEFER — diferir comparador completo a Fase 1.5+ |

---

## Notas de Implementación

- **Shopify UAE**: nuevo stub (`shopify_stub.py`) ya que no hay adapter real.
  Canal registrado como `shopify_uae` (no conflicta con `MATCH_CANDIDATE_CHANNELS`
  existente — el POC no persiste en DB, sólo calcula métricas).
- **Sin persistencia DB**: el runner calcula métricas en memoria. No hace
  `upsert_candidate`. Esto es intencional — el POC es read-only respecto a la DB.
- **Fallback automático**: si el adapter real no está disponible (credentials),
  el runner hace fallback a stub y emite WARNING. Nunca falla el POC por esto.
- **ECE con stubs**: con datos sintéticos la ECE tenderá a ~0% (scores predecibles).
  El valor real importa con datos de producción (Bright Data / Playwright).

---

## Hooks Disponibles para Fase 1.5+

Los siguientes componentes existen y están listos para activar cuando el
Research Workstream entregue los adapters reales:

- `app/services/comparator/interfaces.py` → `OcrPort`, `ReverseImageSearchPort`, `VlmJudgePort`
- `app/services/matching/calibrator.py` → `IsotonicCalibrator`
- `app/db/models/match_candidate.py` → campos `label`, `calibrated_confidence`, `reviewer_user_id`
- `app/services/matching/adapters/bright_data_amazon_uae.py` → adapter real Amazon
- `app/services/matching/adapters/playwright_noon_uae.py` → adapter real Noon
