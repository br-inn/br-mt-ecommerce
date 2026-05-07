# ADR-006: Workflow de aprobación por excepción (state machine + reglas)

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), Gerente Comercial

## Contexto

Aprobar cada cambio de precio manualmente es teatro para un equipo de 3 personas con 224 SKUs × 5 esquemas × 4 canales (= 4480 combinaciones). Pero permitir cualquier cambio sin control es incompatible con VAT UAE 2026 + e-invoicing.

Decisión: **aprobación por excepción**. Cambios pequeños / dentro de tolerancia se auto-aprueban con audit; cambios grandes / críticos escalan al Gerente Comercial.

Reglas de excepción **no son hard-coded** — son parametrizables por canal × esquema, ajustables sin redespliegue.

## Decisión

### State machine de `prices`

Estados (column `prices.status`):
- `draft` — propuesta inicial, no integrable.
- `pending_review` — propuesta que requiere aprobación humana.
- `auto_approved` — propuesta dentro de tolerancia, aprobada automáticamente con autor + reglas registradas.
- `approved` — aprobada por `gerente_comercial`.
- `rejected` — rechazada por `gerente_comercial`.
- `revised` — autor crea nueva versión tras un `rejected`.
- `exported` — el connector ya emitió este precio al canal externo (Fase 3+; Fase 1 marca readiness).
- `superseded` — fue reemplazado por una versión más nueva (snapshot histórico).

### Transiciones

| De | Acción | Reglas | A |
|----|--------|--------|---|
| `draft` | submit | si pasa `evaluate_exception_rules` → `auto_approved`; si no → `pending_review` | `auto_approved` o `pending_review` |
| `pending_review` | approve | sólo `gerente_comercial` o `admin` | `approved` |
| `pending_review` | reject | sólo `gerente_comercial` o `admin` | `rejected` |
| `rejected` | revise | `comercial` o `gerente_comercial`; crea nueva fila | `draft` (nueva fila) y la anterior pasa a `superseded` |
| `auto_approved` | escalate | `gerente_comercial` puede revertir a revisión hasta N días post auto-approve | `pending_review` |
| `approved` o `auto_approved` | export | sólo connector / job; verifica estado canal `live` o `pilot` | `exported` |
| cualquiera (excepto exported / superseded) | obsolete (porque hay versión nueva) | trigger automático | `superseded` |

### Reglas de excepción evaluadas en `submit`

Conjunto **default Fase 1** (todas parametrizables en `exception_rules`):

| Code | Default | Significado | Si excede → |
|------|---------|-------------|-------------|
| `MARGIN_TOLERANCE` | 5 % (B2C), 10 % (B2B) | variación de margen vs propuesta vigente | `pending_review` |
| `FX_SWING` | 3 % | cambio de FX vigente vs el `fx_at` del precio anterior | `pending_review` |
| `MIN_MARGIN_FLOOR` | 8 % B2C, 5 % B2B | margen calculado por debajo de mínimo absoluto | `pending_review` (o `rejected` automático si `< 0 %`) |
| `RULE_CHANGED` | bool | cambia la regla de pricing aplicada (ej. de "FBA fee tier 1" a "FBA fee tier 2") | `pending_review` |
| `COST_DELTA` | 10 % | cambio de costes subyacentes desde último approved | `pending_review` |
| `CRITICAL_ALERT` | siempre `pending_review` | alerta del motor de pricing tipo "margin negative" / "alert critical" | `pending_review` |
| `CHANNEL_STATE_CHANGE` | bool | el canal pasa de `inactive` a `pre_launch`/`pilot`/`live` | todos los precios del canal pasan a `pending_review` |

### Side-effects en transiciones

- En cada transición se inserta fila en `audit_events` con `actor_id`, `before`, `after`, `reason`, `rules_evaluated`.
- En `auto_approved`: se calcula y persiste `auto_approve_reason` con la lista de reglas evaluadas y sus valores.
- En `approved` / `rejected`: se notifica al autor (in-app + email opcional).
- En `exported`: se valida en código y en DB constraint que `status IN ('approved','auto_approved')`. Si no, se rechaza la operación (regla dura ADR-010).

### Bulk review

- Vista `Approvals Inbox` para Gerente Comercial:
  - Lista paginada de `pending_review` con filtros (canal, esquema, regla disparada).
  - Acción bulk `approve_all_filtered`, `reject_all_filtered` con campo `reason` obligatorio.
  - Cada aprobación bulk inserta 1 fila por precio en `audit_events` (no batch silencioso).
- **Digest diario** (cron 08:00 hora UAE):
  - Email + in-app summary al Gerente Comercial con `auto_approved` del día anterior + `pending_review` abiertos > 24 h.

### State machine implementación

- Librería: `xstate` o implementación manual con tabla de transiciones (TypeScript discriminated union).
- DB-level: CHECK constraint sobre `prices.status` (enum). Trigger `prices_status_transition_check` valida transiciones permitidas (rechaza `draft → exported` directo, etc.).
- Service `PriceApprovalService` con métodos `propose`, `approve`, `reject`, `revise`, `export` — único entry point.

## Alternativas evaluadas

### Alternativa A: Aprobación obligatoria de cada cambio (no por excepción)
- **Pros**: máximo control.
- **Contras**: equipo de 3 → cuello de botella inevitable; viola criterio "minutos a segundos".
- **Veredicto**: descartada explícitamente en brief.

### Alternativa B: Aprobación 100 % automática
- **Pros**: cero fricción.
- **Contras**: viola compliance UAE 2026 + sin guardia para cambios grandes; un error de coste se publica directo al cliente final.
- **Veredicto**: descartada.

### Alternativa C: Workflow externo (Camunda, Temporal, n8n)
- **Pros**: state machine externa con UI, retries, escalations.
- **Contras**: añade infra + lock-in + curva aprendizaje. Para un workflow lineal con 7 estados es overkill.
- **Veredicto**: descartada Fase 1; puede revisarse Fase 3 si se complica.

## Consecuencias positivas

- Equipo escala: lo importante escala, lo trivial fluye.
- Compliance UAE: cada cambio (auto o manual) tiene autor + reglas + diff en audit.
- Reglas paramétricas → ajuste sin redespliegue.
- State machine en DB constraint = imposible publicar un precio en estado inválido.

## Consecuencias negativas / riesgos

- Si las reglas default son muy laxas, demasiados cambios pasan a auto. Mitigación: monitor "tasa auto_approve" como KPI; alerta si > X %.
- Si son muy estrictas, todo va a `pending_review` → cuello de botella. Mitigación: Sprint 0 + S5 calibran defaults con el Gerente Comercial.
- Bulk review puede llevar a "click sin leer". Mitigación: UI exige scroll mínimo y campo `reason` obligatorio en bulk reject; bulk approve queda registrado.

## Cuándo revisar

- **S5** (cuando se entrega): calibrar thresholds default con el Gerente Comercial sobre dataset real.
- **Cierre Fase 1b**: medir tasa auto_approve en parallel run; ajustar.
- **Fase 3** (canales en vivo): re-evaluar `CHANNEL_STATE_CHANGE` y reglas específicas por marketplace.
