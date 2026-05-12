"""g4_report.py — genera reporte Markdown con decisión G4 build-vs-buy.

Inputs:
    metrics: PocMetrics con resultados del POC (calculados por MetricsCollector)
    output_path: Path donde escribir el .md (default: docs/rnd/g4-decision-report.md)

El reporte incluye:
    1. Tabla de métricas por marketplace vs umbrales AC
    2. Análisis de brechas (gaps vs demos comerciales)
    3. Recomendación G4: BUILD (continuar Fase 1) o DEFER (Fase 1.5+)
    4. Hooks de infraestructura disponibles si se difiere

Criterio de decisión automatizado:
    - Si todas las métricas agregadas pasan AC → BUILD
    - Si >= 2 métricas fallan → DEFER
    - Borderline (1 métrica falla) → BUILD condicional con plan de mejora
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from scripts.poc.metrics_collector import (
    AC_COV_MIN,
    AC_ECE_MAX,
    AC_FN_MAX,
    AC_FP_MAX,
    MarketplaceMetrics,
    PocMetrics,
)


def _verdict(
    ac_results: dict[str, bool | int | float],
    fail_threshold: int = 2,
) -> str:
    """Retorna veredicto G4.

    Args:
        ac_results: Diccionario {nombre_ac: resultado}. Un AC falla si:
            - Es bool False (explícito)
            - Es int/float negativo (< 0)
        fail_threshold: Número de ACs fallidos para retornar "DEFER" (default 2,
            mantiene el comportamiento original: si >= 2 → DEFER, si 1 → BUILD_CONDITIONAL,
            si 0 → BUILD).

    Returns:
        'BUILD' | 'DEFER' | 'BUILD_CONDITIONAL'
    """
    failures = [k for k, v in ac_results.items() if _is_failure(v)]

    if not failures:
        return "BUILD"
    if len(failures) >= fail_threshold:
        return "DEFER"
    return "BUILD_CONDITIONAL"


def _is_failure(v: bool | int | float) -> bool:
    """Determina si un valor de AC representa un fallo.

    Solo `False` explícito (bool) o valores numéricos negativos son fallos.
    Valores falsy no-bool como 0, 0.0 NO son fallos (fix W-1).
    """
    if isinstance(v, bool):
        return v is False
    if isinstance(v, (int, float)):
        return v < 0
    return False


def _verdict_from_metrics(metrics: PocMetrics) -> tuple[str, str]:
    """Devuelve (decision, rationale) a partir de PocMetrics.

    Wrapper que calcula el veredicto y genera el rationale textual.
    decision: 'BUILD' | 'DEFER' | 'BUILD_CONDITIONAL'
    """
    agg = metrics.aggregate()
    ac = agg.passes_ac()
    decision = _verdict(ac)
    failures = [k for k, v in ac.items() if not v]

    if decision == "BUILD":
        rationale = (
            "Todas las métricas del agregado superan los umbrales de aceptación. "
            "El pipeline de matching existente es suficiente para Fase 1 "
            "sin necesidad de herramientas comerciales adicionales."
        )
    elif decision == "DEFER":
        rationale = (
            f"El pipeline falla en {len(failures)} métricas ({', '.join(failures)}). "
            "Se recomienda diferir el comparador completo a Fase 1.5+ y activar "
            "los hooks existentes (ComparatorService, OCR, VLM judge) cuando "
            "el research workstream haya mejorado los embeddings y el calibrador."
        )
    else:  # BUILD_CONDITIONAL
        rationale = (
            f"El pipeline falla en 1 métrica ({failures[0]}). "
            "Se puede continuar Fase 1 con un plan de mejora específico para esa métrica "
            "antes del lanzamiento a producción. Revisar con el equipo RND en S9."
        )
    return decision, rationale


def _metrics_table(marketplaces: list[MarketplaceMetrics]) -> str:
    header = (
        "| Marketplace | Cands | FP% | FN% | ECE% | Cobertura | AC |\n"
        "|-------------|------:|----:|----:|-----:|----------:|:--:|"
    )
    rows = []
    for m in marketplaces:
        ac_icon = "✅" if m.all_ac_pass() else "❌"
        rows.append(
            f"| {m.marketplace} | {m.n_candidates} "
            f"| {m.fp_rate * 100:.1f}% "
            f"| {m.fn_rate * 100:.1f}% "
            f"| {m.ece * 100:.1f}% "
            f"| {m.cobertura * 100:.1f}% "
            f"| {ac_icon} |"
        )
    return header + "\n" + "\n".join(rows)


def _thresholds_table() -> str:
    return (
        "| Métrica | Umbral AC | Fuente |\n"
        "|---------|-----------|--------|\n"
        f"| FP rate | < {AC_FP_MAX * 100:.0f}% | Story US-RND-01-12 AC#1 |\n"
        f"| FN rate | < {AC_FN_MAX * 100:.0f}% | Story US-RND-01-12 AC#1 |\n"
        f"| ECE | < {AC_ECE_MAX * 100:.0f}% | Story US-RND-01-12 AC#1 |\n"
        f"| Cobertura | ≥ {AC_COV_MIN * 100:.0f}% | Story US-RND-01-12 AC#1 |"
    )


def generate_g4_report(metrics: PocMetrics, output_path: Path) -> str:
    """Genera el reporte Markdown y lo escribe en `output_path`.

    Devuelve el contenido del reporte como string.
    """
    decision, rationale = _verdict_from_metrics(metrics)
    agg = metrics.aggregate()
    today = date.today().isoformat()

    decision_badge = {
        "BUILD": "🟢 **BUILD** — Continuar Fase 1",
        "DEFER": "🔴 **DEFER** — Diferir a Fase 1.5+",
        "BUILD_CONDITIONAL": "🟡 **BUILD CONDICIONAL** — Continuar Fase 1 con plan de mejora",
    }[decision]

    content = f"""# Reporte de Decisión G4 — Matching Pipeline

**Fecha**: {today}
**POC**: {metrics.n_skus_total} SKUs × {len(metrics.marketplaces)} marketplaces
**Modo**: {"Stubs (sin credenciales externas)" if metrics.use_stubs else "Adapters reales"}
**Elapsed**: {metrics.elapsed_seconds:.1f}s

---

## Decisión G4

### {decision_badge}

{rationale}

---

## Métricas por Marketplace

{_metrics_table(metrics.marketplaces)}

### Agregado Global

| Métrica | Valor | Umbral | Estado |
|---------|------:|--------|--------|
| FP rate | {agg.fp_rate * 100:.1f}% | < {AC_FP_MAX * 100:.0f}% | {"✅" if agg.fp_rate < AC_FP_MAX else "❌"} |
| FN rate | {agg.fn_rate * 100:.1f}% | < {AC_FN_MAX * 100:.0f}% | {"✅" if agg.fn_rate < AC_FN_MAX else "❌"} |
| ECE | {agg.ece * 100:.1f}% | < {AC_ECE_MAX * 100:.0f}% | {"✅" if agg.ece < AC_ECE_MAX else "❌"} |
| Cobertura | {agg.cobertura * 100:.1f}% | ≥ {AC_COV_MIN * 100:.0f}% | {"✅" if agg.cobertura >= AC_COV_MIN else "❌"} |
| Precisión | {agg.precision * 100:.1f}% | — | — |
| Recall | {agg.recall * 100:.1f}% | — | — |

---

## Umbrales de Aceptación (Story AC#1)

{_thresholds_table()}

---

## Comparación vs Demos Comerciales

| Aspecto | Pipeline MT (POC) | Algopix / Helium 10 / Keepa |
|---------|------------------|------------------------------|
| FP rate | {agg.fp_rate * 100:.1f}% | ~1-3% (según demos) |
| FN rate | {agg.fn_rate * 100:.1f}% | ~5-15% (según demos) |
| Cobertura PVF industrial | {agg.cobertura * 100:.1f}% | 20-40% (catálogo genérico) |
| Customización specs | Alta (DN/PN/material) | Baja (genérico) |
| Coste mensual | In-house | USD 500-2000/mes |
| Latencia integración | 0 (ya integrado) | 2-4 semanas |

> **Nota**: Los valores de demos comerciales son estimaciones basadas en
> demos públicos y documentación. No se han corrido benchmarks directos.

---

## Estado de Hooks (AC#3)

Si la decisión fuera DEFER, los siguientes componentes **ya existen** listos para Fase 1.5+:

| Componente | Estado | Archivo |
|------------|--------|---------|
| `ComparatorPort` (interfaz) | ✅ Listo | `app/services/comparator/interfaces.py` |
| `NoopComparatorService` | ✅ Listo | `app/services/comparator/noop.py` |
| `OcrPort` (interfaz) | ✅ Listo | `app/services/comparator/interfaces.py` |
| `ReverseImageSearchPort` | ✅ Listo | `app/services/comparator/interfaces.py` |
| `VlmJudgePort` | ✅ Listo | `app/services/comparator/interfaces.py` |
| `IsotonicCalibrator` | ✅ Listo | `app/services/matching/calibrator.py` |
| `MatchCandidate.label` | ✅ Listo | `app/db/models/match_candidate.py` |

---

## Recomendación de Próximos Pasos

{"### Si se aprueba BUILD" if decision in ("BUILD", "BUILD_CONDITIONAL") else "### Camino DEFER"}

"""

    if decision == "BUILD":
        content += """\
1. Activar Bright Data en staging para Amazon UAE real (backlog S9).
2. Activar Playwright Noon UAE real.
3. Iterar embeddings + calibrador en background (Research Workstream).
4. Monitorear FP/FN en producción con el dashboard de métricas.
"""
    elif decision == "BUILD_CONDITIONAL":
        content += """\
1. Identificar la causa raíz de la métrica que falla.
2. Crear ticket técnico en backlog S9 con plan de mitigación.
3. Establecer revisión de métricas en sprint review antes de go-live.
4. Continuar con Fase 1 activando adapters reales gradualmente.
"""
    else:  # DEFER
        content += """\
1. Mantener `NoopComparatorService` activo en Fase 1 (sin comparación automática).
2. El equipo humano continúa validando manualmente vía Human Queue.
3. Research Workstream continúa iterando embeddings + calibrador en paralelo.
4. Activar comparador completo en Fase 1.5 cuando ECE < 5% y FN < 10%.
5. Revisar G4 decision en Sprint 12 con métricas actualizadas.
"""

    content += f"""
---

## Metadata del POC

- **Errores de fetch**: {len(metrics.errors)}
- **Candidatos totales**: {agg.n_candidates}
- **TP/FP/TN/FN**: {agg.tp}/{agg.fp}/{agg.tn}/{agg.fn}
- **Run date**: {metrics.run_date}

---

*Generado automáticamente por `scripts/poc/g4_report.py`*
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return content


__all__ = ["generate_g4_report", "_verdict", "_is_failure"]
