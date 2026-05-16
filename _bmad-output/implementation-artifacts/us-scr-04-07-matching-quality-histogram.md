# US-SCR-04-07 — Monitor Calidad Matching — Histograma Confidence 7d

**Epic**: EP-SCR-04 — Monitoreo Autónomo + Price Intelligence  
**Sprint**: S15  
**Story Points**: 3 SP  
**Estado**: review  
**Fecha**: 2026-05-16

## Verificación de existencia

Componente existía implementado en el backend y frontend.

## Componentes implementados

### Backend — Endpoint
- **Archivo**: `mt-pricing-backend/app/api/routes/price_intelligence.py` (línea 229)

#### GET `/api/v1/price-intelligence/quality`
- Histograma de `confidence_score` de `match_candidates` últimos 7 días
- Bins: `[0-0.2, 0.2-0.4, 0.4-0.6, 0.6-0.8, 0.8-1.0]`
- Retorna: `histogram[{bin, count}]`, `median_confidence`, `pct_above_80`, `total`, `total_with_confidence`, `period_days`
- RBAC: `products:read`

### Frontend — Sección en página Intelligence
- **Archivo**: `mt-pricing-frontend/app/(app)/comparator/intelligence/page.tsx`
- Sección "Calidad del matching — últimos 7 días"
- Barras del histograma con componente `HistogramBar`
- Métricas destacadas: `% > 0.8` y `Mediana`
- Estado vacío: mensaje `quality.noData`

### i18n
- Keys `comparator.intelligence.quality.*` completos en los tres idiomas
