# ADR-024: VLM judge audit-grade — razonamiento natural-language como output de primera clase

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), Comercial Online MT, TI MT
- Related: ADR-012, ADR-007 (audit trail), FR-CMP-JUDGE-01

## Contexto

El stack original del spike (v1.0) trataba el VLM (Gemini 2.5 Flash) como un **modelo más** del cascade: imagen + reglas → tie-break "match / no-match", devolviendo prácticamente sólo un score binario.

La recomendación externa al sponsor (2026-05-06) propone reframing del VLM judge: dejar de tratarlo como scoring step y empezar a tratarlo como **generador de razonamiento auditable** del sistema.

Motivaciones:
1. **Auditabilidad VAT UAE 2026**: cada decisión que afecta precio / canal debe ser trazable a una causa explicable. "El modelo dijo 0,72" no es trazable; "el modelo dijo no-match porque el sello es PTFE en uno y metal-metal en el otro" sí lo es.
2. **UI humana**: el validador trabaja mejor con hipótesis de duda ("aquí dudo porque…") que con un score numérico opaco. Mostrar el rationale antes que el score reduce anchor bias.
3. **Debugging del calibrator**: identificar patrones de error (el VLM siempre confunde "ball" con "globe" en cierto modelo de cámara) requiere trazas natural-language, no scores.
4. **Alineamiento con el driver D5 (audit-first)** de la arquitectura.

## Decisión

El servicio `VlmJudgeService` (paquete `comparator`) **DEBE** retornar un payload estructurado obligatorio:

```typescript
interface JudgeOutput {
  verdict: 'match' | 'no_match' | 'uncertain';
  rationale: string;                       // 1-3 frases natural language
  imageRegions: Array<{
    sku_or_candidate: 'sku' | 'candidate';
    description: string;
    boundingBox?: { x: number; y: number; w: number; h: number };
  }>;
  dealBreakersTriggered: string[];
  modelVersion: string;
  judgedAt: Date;
}
```

Persistencia obligatoria en `match_decisions`:

- `judge_rationale TEXT`
- `judge_image_regions JSONB`
- `deal_breakers_triggered TEXT[]`
- `judge_model_version TEXT`
- `judge_at TIMESTAMPTZ`

Consumo aguas abajo:

1. **UI de validación humana** muestra `rationale` como hipótesis de duda ANTES del score numérico (anti-anchor bias).
2. **Exports de auditoría VAT** incluyen `rationale` y `dealBreakersTriggered`.
3. **Análisis de errores del calibrator** usa `rationale` + `imageRegions` para identificar patrones de fallo.

Coste incremental: ~+30 % output tokens por llamada (50-150 tokens reasoning + JSON regiones). A 10k llamadas/mes → ~$13/mes vs $10/mes proyectado. Asumible.

## Alternativas evaluadas

- **Mantener VLM como scoring puro (status quo v1.0)**: pierde auditabilidad y reduce productividad humana. Descartado.
- **Logging del rationale en logs estructurados sin persistirlo en `match_decisions`**: separa el rationale del registro auditable; los logs no son fuente de auditoría. Descartado.
- **Usar Claude Sonnet 4.6 vision en lugar de Gemini 2.5 Flash**: Sonnet entrega rationale más rico pero a 3-5× coste. Reservado para Fase 1.5+ si la calidad de rationale de Gemini Flash no satisface al validador.

## Consecuencias positivas

- Auditabilidad nativa, alineada con VAT UAE 2026.
- Productividad humana mejor: validador entiende el "por qué" antes del "cuánto".
- Debug del calibrator más rápido cuando emerjan sesgos sistemáticos.
- Exportable a digest del Gerente como contexto.

## Consecuencias negativas / riesgos

- +30 % output tokens / llamada (~+$3/mes a 10k llamadas; despreciable).
- El rationale puede ser **alucinado** por el modelo. Mitigación: el rationale acompaña, no decide; el verdict + dealBreakers + score son la fuente de verdad operativa.
- Privacidad: el rationale puede contener marcas / part-numbers de competidores; control de acceso por RBAC (sólo admin / Gerente / validador).
- Latencia +0,5-1 s por llamada (asumible en cascada).

## Cuándo revisar

- **S5**: muestra de 50 rationales validar legibilidad y utilidad real con la validadora humana. Si < 70 % útiles, ajustar prompt o switchear modelo.
- **G4 (S6)**: revalidar coste real.
- Cuando se evalúen modelos vision en Fase 1.5 (Claude Sonnet, Gemini 3 Flash, GPT-5 vision).
