# ADR-009: Estados de canal y simulación what-if

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), Gerente Comercial

## Contexto

Los canales (Amazon UAE FBA, Amazon UAE FBM, Noon UAE, B2B, B2C directo, Marketplace listado) salen en vivo en **fechas distintas y asincrónicas**. Fase 1 ocurre antes de cualquier go-live (Fase 3+).

Necesidades:
- El sistema no debe **proponer recomendaciones de canal** entre canales que aún no están `live`.
- El sistema sí debe permitir **simular what-if** ("si activo Noon UAE mañana, ¿qué precio publicaría con las reglas actuales?").
- El connector base **no debe publicar** a canales no-live, ni precios no aprobados (regla dura ADR-010).
- Estados deben tener efectos en cascada (un canal `paused` suprime recomendaciones; `deprecated` congela precios existentes).

## Decisión

### Estados de canal

Tabla `channels` con columna `state ENUM`:

| State | Significado | Efecto |
|-------|-------------|--------|
| `inactive` | Canal definido pero nunca activado. | Precios calculables (what-if) pero no aprobables; connector ignora. |
| `pre_launch` | Configuración en preparación, fecha de go-live planeada. | Precios pueden pasar a `pending_review` y ser aprobados; pero connector no publica. |
| `pilot` | Go-live limitado / soft launch. | Precios `approved` se publican vía connector; volumen limitado / canal interno; alertas más estrictas. |
| `live` | Producción full. | Precios `approved` se publican; entran en recomendación de canal óptimo. |
| `paused` | Pausado temporal (fix urgente, dispute marketplace). | Precios congelados; connector no publica nuevos; recomendación lo excluye. |
| `deprecated` | Canal descontinuado. | Precios existentes en estado terminal; no se permiten nuevas propuestas; archivado. |

### Tabla soporte

```sql
CREATE TABLE channel_state_history (
  id BIGSERIAL PRIMARY KEY,
  channel_code TEXT NOT NULL REFERENCES channels(code),
  from_state TEXT,
  to_state TEXT NOT NULL,
  changed_by UUID REFERENCES users(id),
  changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  reason TEXT
);
```

### Transiciones permitidas

```
inactive → pre_launch → pilot → live
                                  ↓ ↑
                                paused
                                  ↓
                              deprecated  (terminal, no return)
```

- Sólo `gerente_comercial` o `ti_integracion` pueden ejecutar transiciones.
- `live → deprecated` requiere confirmación adicional (modal "¿estás seguro? esto es terminal").
- `paused → live` es libre.
- Cada transición dispara reglas de excepción (ej. `CHANNEL_STATE_CHANGE` → todos los precios del canal pasan a `pending_review` para re-validar reglas con el nuevo state).

### Recomendación de canal óptimo (feature flag)

- Flag `feature.channel_recommendation_enabled` en `settings`.
- Default Fase 1: **OFF** (no hay canales `live`).
- Encendido cuando ≥ 2 canales en `live` (Fase 3 prevista).
- Lógica: para un SKU, computar score de cada canal `live` según función objetivo configurable (margen / ROI / velocidad de rotación) y devolver ranking.
- **No se propone recomendación entre canales `inactive` / `pre_launch` / `pilot`** — si flag está ON pero ningún canal cumple, devuelve "ningún canal recomendable".

### Simulación what-if

- Endpoint `POST /api/pricing/simulate` con body:
  ```json
  {
    "sku": "VLV-001",
    "scenarios": [
      {"channel": "amazon_uae", "scheme": "FBA", "as_of": "2026-06-01", "fx_override": null, "cost_override": null},
      {"channel": "noon_uae",   "scheme": "marketplace", "as_of": "2026-06-01"},
      {"channel": "b2b",        "scheme": "direct_b2b", "as_of": "2026-06-01"}
    ]
  }
  ```
- Devuelve precio computado, breakdown, regla aplicada, alertas — **sin persistir** (no crea filas en `prices`).
- Funciona independientemente del estado del canal (whe-if no respeta state machine — es exploratorio).
- Sólo `comercial`, `gerente_comercial`, `admin` pueden simular.

### Bulk recompute

Cuando cambia FX o costos, job `recompute_prices_after_fx` (o `recompute_prices_after_cost`):
- Identifica precios afectados (todos los `draft` o `pending_review` del SKU/canal/esquema impactado).
- **No toca `approved` ni `auto_approved`** (esos siguen vigentes hasta nueva propuesta).
- Genera nuevas propuestas en `draft` para review.
- Encola notificación al Gerente Comercial.

## Alternativas evaluadas

### Alternativa A: Sólo dos estados (`active` / `inactive`)
- **Pros**: simplicidad.
- **Contras**: pierde paused / pilot / pre_launch / deprecated. Go-live escalonado de Fase 3 no representable.
- **Veredicto**: descartada.

### Alternativa B: Estados libres (texto)
- **Pros**: máxima flexibilidad.
- **Contras**: imposible aplicar transiciones / efectos. Rompe el motor de pricing.
- **Veredicto**: descartada.

### Alternativa C: Estados sólo en código (no en DB)
- **Pros**: refactor simple.
- **Contras**: no auditable; queries operativas no pueden filtrar; multi-source-of-truth.
- **Veredicto**: descartada.

## Consecuencias positivas

- Go-live asincrónico Fase 3 representable de fábrica.
- Simulación what-if válida desde Fase 1 → permite a Comercial preparar precios antes del go-live.
- Recomendación de canal protegida por feature flag → no aparece prematuramente.
- Auditoría de cambios de estado completa.

## Consecuencias negativas / riesgos

- Transiciones de estado afectan muchos precios → side-effect masivo. Mitigación: job en cola con preview, no inline.
- `paused → live` puede dejar precios desactualizados si el canal estuvo pausado mucho tiempo. Mitigación: trigger que marca todos los precios del canal como `stale` si `paused > N días`.

## Cuándo revisar

- **S6** (cuando se implementa connector base): validar que el filtro por estado funciona end-to-end.
- **Cierre Fase 1b**: simular state machine completa con Gerente Comercial.
- **Fase 3** (primer go-live): activar feature flag de recomendación; calibrar función objetivo.
