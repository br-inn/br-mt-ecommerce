# ADR-003: Estrategia de monedas (moneda base AED + FX versionado)

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT, Gerente Comercial

## Contexto

MT Middle East opera en UAE (AED), compra a MT Valves España y a proveedores chinos (EUR/USD), planifica vender en GCC vecinos (SAR/KWD/OMR/BHD/QAR a futuro Fase 4). Hoy:

- El Excel maestro tiene **TC EUR/AED hardcoded en macro VBA** (1 EUR = 4,29 AED, abril/may 2026).
- Cualquier oscilación obliga a editar el macro y re-ejecutar manualmente.
- **No hay histórico** de la tasa aplicada en cada decisión de precio.
- VAT UAE 2026 + e-invoicing exigen auditabilidad de cada precio → debemos demostrar a la FTA "este precio se calculó con FX X el día Y".

Necesitamos:
- Una **moneda base** del sistema.
- Tabla de **tasas FX versionadas** (efectivas en intervalos temporales).
- Que cada `cost` y cada `price` **almacene el FX aplicado al momento de aprobación** (snapshot, no recálculo retroactivo).
- Política de actualización (manual Fase 1; feed externo Fase 1.5+).

## Decisión

1. **Moneda base del sistema = AED** (configurable en `settings`, default AED). Razón: la operación es UAE, el contable + factura final + e-invoicing son AED.
2. Tabla `currencies` con códigos ISO 4217 (AED, EUR, USD, SAR, KWD, OMR, BHD, QAR, GBP). Cada una `is_base` boolean (sólo una `true`).
3. Tabla `fx_rates` versionada con columnas:
   - `from_currency`, `to_currency`, `rate NUMERIC(18,8)`, `effective_from TIMESTAMPTZ`, `effective_to TIMESTAMPTZ NULL` (NULL = vigente), `source ENUM('manual','feed_xe','feed_oanda','feed_ecb')`, `entered_by`, `created_at`.
   - Constraint: no overlap de rangos para el mismo par (`from`, `to`).
   - Función `fx_rate_at(from, to, ts) RETURNS NUMERIC` que devuelve la tasa vigente en `ts` o lanza error.
4. Cada `costs.amount` y `prices.amount` se almacena en su moneda nativa **+ una columna `fx_at TIMESTAMPTZ`** con el timestamp en que se snapshoteó la tasa **+ columnas `amount_base NUMERIC` y `fx_rate_used NUMERIC(18,8)`** materializadas con la conversión a moneda base aplicando la tasa vigente en `fx_at`.
5. **Política de actualización Fase 1**: ingreso manual por usuario con rol `Gerente Comercial` o `TI Integración`. Cada cambio crea una nueva fila (no UPDATE) y cierra la anterior (`effective_to = now()`).
6. **Trigger de excepción FX**: si una nueva tasa difiere de la vigente en más de Y % (parametrizable en `exception_rules`, default 3 %), se dispara workflow de aprobación obligatoria (no auto_approved).
7. **Recálculo masivo de precios** tras nuevo FX: cuando se ingresa una tasa nueva, se encola un job `recompute_prices_after_fx` que reproyecta precios candidatos (no aprobados, mantiene los aprobados intactos) y muestra al Gerente Comercial el preview en una pantalla → aprobar todo / aprobar selección / rechazar.
8. **Política Fase 1.5+**: integrar feed externo (XE, OANDA, ECB) con cron diario; mismas reglas de excepción; manual sigue disponible como override.

## Alternativas evaluadas

### Alternativa A: Moneda base = EUR (alineado con MT Valves España)
- **Pros**: si Fase 2 integra ERP España, EUR como base reduce conversión.
- **Contras**: la operación legal y contable es UAE → AED. e-invoicing UAE requiere AED. Contradice la VAT UAE 2026. Forzar EUR como base obligaría a convertir en cada export a la FTA.
- **Veredicto**: descartada. AED gana por compliance.

### Alternativa B: Sin moneda base — cada coste/precio en su moneda nativa, conversiones on-the-fly
- **Pros**: simplicidad de modelo.
- **Contras**: queries operativas (margen agregado, recálculo masivo) requieren conversión en query → lento + audit-unfriendly. Imposible reproducir reportes pasados sin replay completo de FX.
- **Veredicto**: descartada.

### Alternativa C: Recalcular FX al consultar (no snapshot)
- **Pros**: precios siempre "actualizados".
- **Contras**: precio aprobado puede mover sin aprobación → viola la regla dura "no aprobado no integra". Imposible auditar "qué precio aprobó el Gerente el día X" porque cambia con el FX hoy.
- **Veredicto**: descartada — viola compliance UAE 2026.

## Consecuencias positivas

- Auditoría regulatoria UAE 2026: cada precio aprobado tiene FX inmutable + timestamp + autor.
- Recálculo masivo controlado: el motor sabe qué precios están "stale" (su `fx_at` < última tasa vigente) y los marca para revisión.
- Soporta crecimiento Fase 4 (multi-divisa GCC) sin rediseño — sólo añadir filas a `currencies` y `fx_rates`.
- Política de excepción FX ata al workflow de aprobación existente sin lógica especial.

## Consecuencias negativas / riesgos

- Sobrecarga de espacio: cada `prices` tiene `fx_at` + `fx_rate_used` + `amount_base` extras. Para 224 SKUs × 5 esquemas × 4 canales = 4480 filas, despreciable. Para 50k SKUs Fase 4 = ~1M filas, sigue manejable.
- Importer debe stampear FX as-of por batch — fuente de bugs si el importer usa "now()" en vez del timestamp del archivo origen. Mitigación: import explícito requiere `effective_at` parameter; default a `now()` con warning.
- Si el feed externo Fase 1.5+ tiene gaps, el sistema queda con tasa vieja vigente → trigger de alerta si última tasa > N días.

## Cuándo revisar

- **S3** (cuando se ingrese FX por primera vez): validar threshold de excepción Y % con el Gerente Comercial (default 3 % es supuesto BR).
- **Fase 1.5**: decidir feed externo (XE, OANDA, ECB) con presupuesto.
- **Fase 4**: añadir SAR/KWD/OMR/BHD/QAR; revisar si GCC pegs (KWD, BHD) merecen tratamiento distinto.
