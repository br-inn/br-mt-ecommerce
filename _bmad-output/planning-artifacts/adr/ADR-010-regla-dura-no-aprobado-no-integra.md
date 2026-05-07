# ADR-010: Regla dura "no aprobado no integra" (enforcement DB + runtime)

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT, Gerente Comercial

## Contexto

Regla de negocio explícita en el brief:
> Ninguna integración / export / publicación externa puede transmitir datos en estado distinto a `approved` o `auto_approved`. Aplica a productos, costes, precios, traducciones. Enforcement a nivel modelo (constraint DB) + runtime (connectors filtran por estado y rechazan registros no aprobados).

Esto es **regla dura** — bug que rompa esta regla es severity P0. Un precio `draft` que se publica al cliente final = error material + posible problema regulatorio UAE 2026.

## Decisión

**Defense in depth en cuatro capas**:

### Capa 1 — Modelo de datos (DB constraint)

Para cada tabla con `status` que puede integrar:
- `prices.status` ENUM con `approved`, `auto_approved` como únicos estados publicables.
- Cuando una operación de export inserta en `price_exports` (tabla de tracking), CHECK constraint:
  ```sql
  CONSTRAINT chk_export_status CHECK (
    EXISTS (
      SELECT 1 FROM prices p
      WHERE p.id = price_id
        AND p.status IN ('approved', 'auto_approved')
    )
  )
  ```
  (En Postgres no hay subqueries en CHECK. La implementación real es via TRIGGER `BEFORE INSERT ON price_exports` que rechaza con `RAISE EXCEPTION`.)

- Trigger `prevent_export_unapproved` en cualquier tabla de "salida" (publicación, connector, export):
  ```sql
  CREATE OR REPLACE FUNCTION prevent_export_unapproved() RETURNS TRIGGER AS $$
  DECLARE
    v_status TEXT;
  BEGIN
    SELECT status INTO v_status FROM prices WHERE id = NEW.price_id;
    IF v_status NOT IN ('approved','auto_approved','exported') THEN
      RAISE EXCEPTION 'Cannot export price % in status %', NEW.price_id, v_status;
    END IF;
    RETURN NEW;
  END;
  $$ LANGUAGE plpgsql;
  ```

- Mismo patrón para `products` (sólo `published_state IN ('publishable')`), `product_translations.status='approved'`, `costs.status='approved'`.

### Capa 2 — Repositorio (capa app)

- Métodos en service layer: `priceRepository.findExportableByChannel(channelCode)` filtra explícitamente:
  ```typescript
  WHERE status IN ('approved', 'auto_approved')
    AND channel_state IN ('pilot', 'live')
  ```
- No hay método público que devuelva precios en estado `draft` / `pending_review` para export. El acceso directo está prohibido por convención + lint rule.

### Capa 3 — Connectors (runtime filter)

- El puerto `ChannelPublisher.publish(records[])` en su implementación base filtra por estado y devuelve un objeto `{published: [], rejected: [{record, reason}]}`.
- Cada adapter (Amazon UAE, Noon UAE, Shopify, ...) hereda del base y **no puede saltar el filtro** (filter aplicado en el método base, los hijos sólo implementan el transport).
- Cualquier intento de publicar un record en estado inválido se loguea como **WARN** (no error fatal — el filtro ya hizo su trabajo) + métrica `publish_rejected_total{reason="status_invalid"}`.

### Capa 4 — UI (visibilidad)

- Vista de catálogo / preview de export muestra explícitamente badge "Listo para publicar" sólo si `status IN ('approved','auto_approved')`. Otros estados se marcan claramente.
- Botón "Export to channel X" deshabilitado si hay registros no publicables en el filtro actual; al hover muestra el motivo.

### Pruebas

- Test e2e por capa (DB trigger lanza excepción; service layer filter excluye; connector base filtra; UI deshabilita).
- Test de regresión: cualquier nueva ruta de export pasa por código review checklist "respeta status filter".

## Alternativas evaluadas

### Alternativa A: Sólo enforcement en runtime (sin DB constraint)
- **Pros**: simplicidad.
- **Contras**: cualquier acceso directo a la DB (script ad-hoc, hotfix, debug) puede emitir un export inválido. Pierde defense in depth.
- **Veredicto**: descartada.

### Alternativa B: Sólo enforcement en DB (sin runtime filter)
- **Pros**: simplicidad.
- **Contras**: error tarde (al INSERT en `price_exports`) sin chance de UX clara. Cliente final podría haber visto un loading state extraño.
- **Veredicto**: descartada — runtime filter da UX limpia + DB es backstop.

### Alternativa C: Tabla separada `publishable_prices` materializada (vista)
- **Pros**: queries de export trivialmente correctas.
- **Contras**: vista materializada requiere refresh; lag con la realidad.
- **Veredicto**: descartada Fase 1; consider Fase 4 si performance lo exige.

## Consecuencias positivas

- Imposible publicar un precio no aprobado por accidente.
- Defense in depth: una capa puede fallar, las otras protegen.
- Compliance UAE 2026 satisfecha por construcción.
- Cualquier intento de bypass deja huella (audit + log).

## Consecuencias negativas / riesgos

- Triggers añaden latencia (~ 1 ms). Despreciable.
- Mantenimiento: cuando se añadan nuevas entidades exportables (Fase 2: facturación), debe replicarse la regla. Mitigación: checklist de "publishable entity" en docs internos + lint rule.
- Si un cambio legítimo necesita "publicar emergency" un precio no aprobado, no es posible sin saltar la regla. Mitigación: workflow de "fast-track approval" — aprobación express con flag rojo en audit. **No** un bypass — un atajo controlado.

## Cuándo revisar

- **S5** (cuando se implementa workflow): validar fast-track approval flow con Gerente.
- **Fase 3** (primer connector real): probar end-to-end y medir latencia del filtro.
- **Auditoría externa primera FTA**: confirmar que la regla satisface a los auditores.
