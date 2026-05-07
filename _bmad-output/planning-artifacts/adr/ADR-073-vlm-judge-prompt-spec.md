---
adr: "ADR-073"
title: "VLM Judge — visual matching MT canonical vs candidato (OpenAI default + Anthropic fallback)"
status: "proposed"
date: "2026-05-07"
author: "Pablo Sierra (Comercial · Online)"
deciders: ["Champion MT", "Paula (validador)", "TI MT", "Equipo R&D BR (matcher)"]
related:
  - "ADR-038-roadmap-rag-hybrid-graphrag.md"
  - "ADR-055-ssrf-policy-image-probe.md"
  - "ADR-074-graphrag-evolution-roadmap.md"
sprint: "S4"
project: "mt-pricing-mdm-phase1"
supersedes: []
superseded_by: []
---

# ADR-073 — VLM Judge prompt spec

## 1. Contexto

US-1A-09-06 (Sprint 4) introduce un **Visual Language Model (VLM) judge** como etapa 7 del matching pipeline (`mt-product-matching-pipeline-detail.md` §10). Función: dado el SKU canónico MT y un candidato (Amazon UAE / Noon UAE), decidir si las dos imágenes representan el mismo producto. Útil cuando los matching scores textuales (etapas 4-5) caen en la zona gris (~0.70-0.85) — el VLM resuelve el empate.

Constraints:
- **Provider switching**: queremos poder cambiar entre OpenAI Vision (default) y Anthropic Vision (fallback) sin redeploy.
- **Cost**: ~$0.005-0.02 per call (gpt-4o-mini / claude-3.5-sonnet vision). Volumen Fase 1b: ~10 % de candidatos pasan por VLM = ~600 calls/mes ≈ $5-15/mes.
- **Output schema**: el comparador downstream necesita un veredicto enum + confidence numérica + reasoning (audit + UX).
- **Calibración**: scores VLM crudos no están calibrados (gpt-4o tiende a optimismo). Necesitamos isotonic post-judgment (ADR-073 + `calibrator.py`).
- **Fallback gracioso**: si LLM provider está down o falla, derivar al `human_queue` (no inventar veredicto).

## 2. Decisión

Adoptamos un **diseño hexagonal** con `Protocol` `VLMClient` + dos adapters (`OpenAIVisionJudge`, `AnthropicVisionJudge`) + servicio orquestador `VLMJudge` que selecciona por env. Calibración post-judgment con `IsotonicCalibrator`.

### 2.1 Provider selection

Setting `VLM_JUDGE_PROVIDER` (default `openai`):

- `openai` → `OpenAIVisionJudge` con `OPENAI_API_KEY`. Modelo default `gpt-4o-mini` (más barato; switchable a `gpt-4o` para benchmarks).
- `anthropic` → `AnthropicVisionJudge` con `ANTHROPIC_API_KEY`. Modelo default `claude-3-5-sonnet-latest`.

`_resolve_client` en `VLMJudge`:
1. Si `client` inyectado en constructor → usarlo (tests).
2. `provider = env.VLM_JUDGE_PROVIDER`.
3. Si provider es openai pero no hay `OPENAI_API_KEY` → `None` (caller cae a fallback).
4. Idem anthropic.
5. Si `None` → `JudgeResult(verdict='uncertain', confidence=0.5, reasoning='VLM provider not configured — derive to human queue.')`.

**Default es OpenAI** porque `gpt-4o-mini` ofrece coste/precisión óptimo en benchmarks vision actuales (2026-Q1) según interna BR. Anthropic queda como fallback estratégico ante outage o cambio comercial.

### 2.2 Prompt template

```
You are an industrial PVF (pipes/valves/fittings) catalog auditor. Compare
two product images and decide if they represent the same SKU. Respond ONLY
with a JSON object with these fields:
  "verdict": one of "match" | "drift" | "reject" | "uncertain"
  "confidence": float in [0.0, 1.0]
  "reasoning": short string in Spanish, max 280 chars.
Canonical image: {canonical}
Candidate image: {candidate}
Context: {context}
```

Justificación:

- **Dominio explícito** ("industrial PVF") sesga el modelo a fijarse en features relevantes (DN, conexión, material) en lugar de cosméticas (color packaging).
- **Verdict ∈ {match, drift, reject, uncertain}**:
  - `match`: alta confianza mismo SKU.
  - `drift`: mismo producto pero con cambio incremental (variante color/marca menor) — útil para flag "cross-list" en S5.
  - `reject`: claramente productos distintos.
  - `uncertain`: imagen mala/ambigua — deriva al `human_queue`.
- **Confidence float [0,1]**: necesario para isotonic calibrator. Restringido a este rango por `parse_judge_response` (max(0, min(1, ...))).
- **Reasoning en español, max 280 chars**: caben en UI human review queue (S5) sin overflow. Español por audiencia Comercial MT.
- **Chain-of-thought NO explícito**: en lugar del prompt "razona paso a paso", limitamos a 280 chars por motivos de coste y latencia. La calidad sobre PVF es suficiente con el dominio explícito en el system message.

Temperatura `0.0` (OpenAI) para reducir variance run-to-run. Anthropic no se setea explícitamente (default 1.0) — TODO observar variance en S5 y bajar si rompe calibración.

### 2.3 Output parser robusto

`parse_judge_response(text)`:
- Busca `{` inicial y `}` final → soporta LLMs que ponen pre/post text.
- Si JSON parse falla → fallback `JudgeResult(uncertain, 0.5, reasoning=text[:280])`.
- Verdict no en allowlist → coerce a `uncertain`.
- Confidence no float → coerce a 0.5.
- Reasoning truncado a 280 chars.

Robustez intencionada: el LLM puede romper schema, NO queremos que el pipeline se caiga.

### 2.4 Gating con `MT_LIVE_NETWORK`

Mientras `MT_LIVE_NETWORK != true`:
- `VLMJudge.judge(...)` devuelve `JudgeResult(uncertain, 0.5, reasoning='VLM judge disabled (MT_LIVE_NETWORK=false) — derive to human queue.')`.
- NO se hacen llamadas reales a OpenAI/Anthropic.
- CI verde sin API keys.

Esto permite mergear sin gastar API budget durante el desarrollo Sprint 4.

### 2.5 Calibración isotonic post-judgment

Pipeline: VLM emite `confidence` crudo → `IsotonicCalibrator.calibrate(score)` ajusta a calibrated probability. La función `IsotonicCalibrator.fit(scores, labels)` se entrena con labels humanos del `human_queue` (S5) y se persiste como JSON en tabla `competitor_calibrators.model_artifact`.

Decisión Sprint 4: el `IsotonicCalibrator` está implementado (ver `calibrator.py`) pero la integración VLM → calibrator vive en S5 cuando haya labels reales. Sprint 4 expone solo el VLM raw output.

### 2.6 Errores y métricas (TODO Sprint 5)

- Captura `RetryError` y `httpx.HTTPError` → `JudgeResult(uncertain, 0.5, reasoning='VLM provider error: ...')`.
- TODO métricas Prometheus: `vlm_judge_calls_total{provider, verdict}`, `vlm_judge_latency_seconds{provider}`, `vlm_judge_cost_usd_total{provider}`.

## 3. Alternativas consideradas

### 3.1 Solo OpenAI sin abstracción

**Rechazada**. Sin Protocol+adapter pattern, cambiar provider requiere refactor. Dado que estamos en preview y los costes son comparables, la abstracción cuesta ~30 LOC y nos da resiliencia.

### 3.2 Gemini 2.5 Flash (mencionado en backlog)

**Considerada**. El backlog Sprint 4 menciona "Gemini 2.5 Flash" como provider. Tras evaluación:
- API JSON output más estricto vs OpenAI/Anthropic (require formato específico).
- Coste competitivo (~$0.001/call).
- Pero: ecosistema BR no tiene credenciales Google Cloud todavía.
- **Decisión**: arrancar con OpenAI default (creds existentes BR) + Anthropic fallback. **TODO Sprint 5** evaluar Gemini si OpenAI cost escala y crear `GeminiVisionJudge` adapter.

### 3.3 Imagen embeddings (CLIP) sin LLM

**Rechazada**. CLIP encuentra similitud visual pero NO razona sobre features estructurales (DN, conexión rosca BSP vs NPT). PVF requiere semantic reasoning, no solo similarity. CLIP queda como fallback Tier 0 si LLM down — defer Sprint 6.

### 3.4 Self-host LLaVA / Qwen-VL en GPU

**Rechazada**. Coste GPU dedicada (~$200/mes Hetzner GPU) >> coste API ($5-15/mes). Solo justificable a >10k calls/mes (volumen Fase 2-3).

### 3.5 Single provider con failover automático en runtime

**Defer Sprint 5**. Sprint 4 selección por env config. En S5 evaluar failover automático OpenAI→Anthropic en caso de 5xx persistente. Trade-off: complejidad (manejar 2 keys activos siempre) vs. resiliencia.

## 4. Consecuencias

### Positivas

- **Provider swap por env** sin redeploy → resiliente a cambios comerciales OpenAI.
- **Output schema estricto + parser robusto** → pipeline downstream confiable.
- **Coste bajo** (~$15/mes Fase 1b).
- **Chain-of-thought lite** (280 chars reasoning) suficiente para UX human review sin disparar costes.
- **Testabilidad**: `VLMClient` Protocol mockeable, `parse_judge_response` testable independientemente.

### Negativas

- **Calibración pendiente**: hasta tener labels humanos S5, los `confidence` crudos del VLM están sin calibrar. Workaround: el comparador downstream usa thresholds conservadores (auto-match ≥0.95, human queue 0.80-0.95).
- **Latencia**: ~2-4s por VLM call (network + LLM inference). Mitigable con paralelización en S5 (asyncio.gather sobre batches).
- **Cost monitoring deferred** Sprint 5 (TODO métricas). Riesgo si pipeline se desborda y dispara 10x volumen → coste 10x. Mitigación: alarma en `match_candidates.kind='vlm_judged'` count >2k/día.
- **OpenAI default → vendor exposure**. Si OpenAI sube precios o API breaking change, switch a Anthropic vía env requiere re-validar prompt (LLMs interpretan prompts ligeramente distinto). TODO eval prompt en ambos providers Sprint 5.

## 5. Open questions

- **Q1 (TODO Sprint 5)**: dataset etiquetado para fit `IsotonicCalibrator` — necesitamos ≥ 200 (canonical, candidate, label) tuplas etiquetadas por Paula. Cost ~10h Paula.
- **Q2 (TODO Sprint 5)**: evaluar Gemini 2.5 Flash adapter — si coste OpenAI > $50/mes en steady state, justifica swap.
- **Q3 (TODO Champion MT)**: confirmar que reasoning en español es lo correcto vs inglés. UX queue S5 podría preferir bilingüe (es+ar).
- **Q4 (TODO TI MT)**: provisionar `OPENAI_API_KEY` y `ANTHROPIC_API_KEY` en Doppler. **BLOQUEANTE** activación real.

## 6. Implementation status

- `mt-pricing-backend/app/services/matching/vlm_judge.py` — implementado (Sprint 4 scaffold):
  - `Verdict = Literal["match", "drift", "reject", "uncertain"]` (línea 41).
  - `JudgeResult` dataclass (líneas 44-49).
  - `VLMClient` Protocol (líneas 52-57).
  - `_PROMPT_TEMPLATE` (líneas 60-70) — prompt domain-specific PVF.
  - `parse_judge_response` (líneas 73-102) — parser robusto JSON.
  - `OpenAIVisionJudge` (líneas 105-176) — adapter gpt-4o-mini con `response_format={type:json_object}`.
  - `AnthropicVisionJudge` (líneas 179-255) — adapter claude-3.5-sonnet vision.
  - `VLMJudge` (líneas 258-314) — orquestador con `_resolve_client` por env `VLM_JUDGE_PROVIDER`, fallback graceful a `uncertain`.
- Calibrator: `mt-pricing-backend/app/services/matching/calibrator.py`:
  - `IsotonicCalibrator` (líneas 28-161) — Pool Adjacent Violators puro Python (sin sklearn).
  - `serialize` / `deserialize` JSON-only (líneas 142-161).
  - `brier_score` (línea 167), `expected_calibration_error` (línea 178).
- Tests esperados: `tests/services/matching/test_vlm_judge.py` (parser robusto + fake VLMClient + gating off → uncertain) + `test_calibrator.py` (PAV correctness, ECE bins, serialize roundtrip).

## 7. Trazabilidad

- Sprint 4 backlog US-1A-09-06.
- `mt-product-matching-pipeline-detail.md` §10 (VLM judge stage 7) + §8 (calibrator stage 6).
- ADR-038 — roadmap RAG → Hybrid → GraphRAG (VLM es complemento al retrieval, no sustituto).
- ADR-055 — SSRF aplica al fetch de imágenes que se pasan al VLM.
- Risk register: R-vlm-cost-spike (mitigado parcial por gating + alarmas), R-llm-prompt-drift (mitigación: lock model version + temperature 0.0).
