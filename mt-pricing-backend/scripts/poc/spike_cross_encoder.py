"""spike_cross_encoder.py — Spike de evaluación de Cross-Encoder / Cohere Reranker.

Evalúa dos opciones de reranking para el pipeline de matching MT:
  - Cohere Reranker v3 (cloud, multilingüe)
  - cross-encoder/ms-marco-MiniLM-L-6-v2 (local, open-source)

Uso:
    python scripts/poc/spike_cross_encoder.py \\
        --dataset datasets/labeled_pairs_latest.jsonl \\
        --candidates 5

    # Modo sintético (sin dataset real):
    python scripts/poc/spike_cross_encoder.py --synthetic --candidates 5

Requisitos:
    - COHERE_API_KEY en env para evaluar Cohere (opcional — skip con WARNING si no está)
    - sentence-transformers instalado para cross-encoder local (opcional — skip con WARNING)
    - Dataset JSONL con ≥500 pares (o --synthetic para datos sintéticos)

Salida:
    - Tabla comparativa en stdout
    - docs/rnd/spike-cross-encoder-results-{YYYY-MM-DD}.json
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import random
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MIN_PAIRS_REQUIRED = 500
MAX_SKUS_SAMPLE = 100
COHERE_COST_PER_CALL_USD = 0.001  # $0.001 per rerank call (Cohere pricing)
LOCAL_COST_PER_CALL_USD = 0.00


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------


def _load_dataset(path: Path, max_skus: int = MAX_SKUS_SAMPLE) -> list[dict[str, Any]]:
    """Carga hasta max_skus SKUs del JSONL.

    Formato esperado por línea:
        {"sku": "...", "query": "...", "candidates": [...], "relevant_index": N}

    Returns:
        Lista de dicts con claves: sku, query, candidates, relevant_index
    """
    records: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning("Línea JSONL inválida: %s", exc)

    if not records:
        logger.error("Dataset vacío: %s", path)
        sys.exit(1)

    # Sample hasta max_skus
    if len(records) > max_skus:
        records = records[:max_skus]

    return records


def _generate_synthetic_data(n_skus: int = 50, n_candidates: int = 5) -> list[dict[str, Any]]:
    """Genera datos sintéticos para modo --synthetic."""
    random.seed(42)
    products = [
        ("valve DN50 PN16 bronze BSP", "Válvula de bola DN50 PN16 bronce"),
        ("fitting elbow 90° DN25 stainless", "Codo 90° DN25 acero inox"),
        ("gate valve DN100 PN10 cast iron", "Compuerta DN100 PN10 fundición"),
        ("check valve DN40 PN16 bronze", "Válvula retención DN40 PN16"),
        ("ball valve DN80 PN25 stainless", "Válvula bola DN80 PN25 inox"),
    ]
    records = []
    for i in range(n_skus):
        q_text, _ = products[i % len(products)]
        candidates = []
        relevant_index = random.randint(0, n_candidates - 1)
        for j in range(n_candidates):
            if j == relevant_index:
                candidates.append(f"{q_text} — producto equivalente confirmado")
            else:
                alt = products[(i + j + 1) % len(products)][0]
                candidates.append(f"{alt} — candidato alternativo {j}")
        records.append(
            {
                "sku": f"SYNTH-{i:04d}",
                "query": q_text,
                "candidates": candidates,
                "relevant_index": relevant_index,
            }
        )
    return records


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------


def _precision_at_1(results: list[tuple[int, list[int]]]) -> float:
    """Precision@1: fracción de queries donde el top-1 es el relevante."""
    if not results:
        return 0.0
    hits = sum(1 for relevant_idx, ranked in results if ranked[0] == relevant_idx)
    return hits / len(results)


def _ndcg_at_k(results: list[tuple[int, list[int]]], k: int = 3) -> float:
    """nDCG@k sobre los resultados rerankeados."""
    if not results:
        return 0.0

    def dcg(ranked: list[int], relevant_idx: int, k: int) -> float:
        score = 0.0
        for pos, idx in enumerate(ranked[:k]):
            if idx == relevant_idx:
                score += 1.0 / math.log2(pos + 2)
        return score

    ideal_dcg = 1.0 / math.log2(2)  # relevante siempre en pos 0

    total = 0.0
    for relevant_idx, ranked in results:
        total += dcg(ranked, relevant_idx, k) / ideal_dcg
    return total / len(results)


def _latency_percentile(latencies_ms: list[float], p: int) -> float:
    """Calcula percentil p de latencias."""
    if not latencies_ms:
        return 0.0
    sorted_lat = sorted(latencies_ms)
    idx = int(math.ceil(p / 100.0 * len(sorted_lat))) - 1
    return sorted_lat[max(0, min(idx, len(sorted_lat) - 1))]


# ---------------------------------------------------------------------------
# Cohere Reranker
# ---------------------------------------------------------------------------


def _run_cohere(
    records: list[dict[str, Any]],
    n_candidates: int,
) -> dict[str, Any] | None:
    """Evalúa Cohere Rerank v3. Retorna métricas o None si no disponible."""
    api_key = os.environ.get("COHERE_API_KEY", "")
    if not api_key:
        logger.warning("COHERE_API_KEY no configurada — saltando evaluación Cohere Reranker")
        return None

    try:
        import httpx
    except ImportError:
        logger.warning("httpx no instalado — saltando Cohere Reranker")
        return None

    results: list[tuple[int, list[int]]] = []
    latencies_ms: list[float] = []
    errors = 0

    for record in records:
        query = record["query"]
        candidates = record["candidates"][:n_candidates]
        relevant_index = record.get("relevant_index", 0)

        payload = {
            "model": "rerank-multilingual-v3.0",
            "query": query,
            "documents": candidates,
            "top_n": n_candidates,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        t0 = time.perf_counter()
        try:
            resp = httpx.post(
                "https://api.cohere.ai/v1/rerank",
                json=payload,
                headers=headers,
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Cohere API error: %s", exc)
            errors += 1
            continue
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies_ms.append(elapsed_ms)

        ranked_indices = [r["index"] for r in data.get("results", [])]
        results.append((relevant_index, ranked_indices))

    if not results:
        logger.warning("Cohere: sin resultados válidos (todos fallaron)")
        return None

    n_calls = len(records)
    cost_per_1k = COHERE_COST_PER_CALL_USD * 1000

    return {
        "precision_at_1": round(_precision_at_1(results), 4),
        "ndcg_at_3": round(_ndcg_at_k(results, k=3), 4),
        "latency_p50_ms": round(_latency_percentile(latencies_ms, 50), 2),
        "latency_p99_ms": round(_latency_percentile(latencies_ms, 99), 2),
        "cost_per_1k_skus_usd": round(cost_per_1k, 4),
        "sample_size": len(results),
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Local Cross-Encoder
# ---------------------------------------------------------------------------


def _run_local_cross_encoder(
    records: list[dict[str, Any]],
    n_candidates: int,
) -> dict[str, Any] | None:
    """Evalúa cross-encoder/ms-marco-MiniLM-L-6-v2 local. Retorna métricas o None."""
    try:
        from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]
    except ImportError:
        logger.warning(
            "sentence-transformers no instalado — saltando evaluación Cross-Encoder local. "
            "Instalar con: pip install sentence-transformers"
        )
        return None

    model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    logger.info("Cargando modelo local: %s", model_name)
    try:
        model = CrossEncoder(model_name)
    except Exception as exc:
        logger.warning("Error cargando modelo %s: %s", model_name, exc)
        return None

    results: list[tuple[int, list[int]]] = []
    latencies_ms: list[float] = []

    for record in records:
        query = record["query"]
        candidates = record["candidates"][:n_candidates]
        relevant_index = record.get("relevant_index", 0)

        pairs = [(query, c) for c in candidates]

        t0 = time.perf_counter()
        scores = model.predict(pairs)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies_ms.append(elapsed_ms)

        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results.append((relevant_index, ranked_indices))

    if not results:
        return None

    return {
        "precision_at_1": round(_precision_at_1(results), 4),
        "ndcg_at_3": round(_ndcg_at_k(results, k=3), 4),
        "latency_p50_ms": round(_latency_percentile(latencies_ms, 50), 2),
        "latency_p99_ms": round(_latency_percentile(latencies_ms, 99), 2),
        "cost_per_1k_skus_usd": LOCAL_COST_PER_CALL_USD,
        "sample_size": len(results),
        "errors": 0,
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _print_comparison_table(
    cohere_metrics: dict[str, Any] | None,
    local_metrics: dict[str, Any] | None,
) -> None:
    """Imprime tabla comparativa en stdout."""
    header = (
        f"{'Opción':<45} {'precision@1':>12} {'ndcg@3':>8} "
        f"{'p50_ms':>8} {'p99_ms':>8} {'cost/1k USD':>12}"
    )
    sep = "-" * len(header)
    print()
    print("=" * len(header))
    print("SPIKE CROSS-ENCODER — Tabla Comparativa")
    print("=" * len(header))
    print(header)
    print(sep)

    def fmt_row(name: str, m: dict[str, Any] | None) -> str:
        if m is None:
            return f"{name:<45} {'N/A':>12} {'N/A':>8} {'N/A':>8} {'N/A':>8} {'N/A':>12}"
        return (
            f"{name:<45} "
            f"{m['precision_at_1']:>12.4f} "
            f"{m['ndcg_at_3']:>8.4f} "
            f"{m['latency_p50_ms']:>8.1f} "
            f"{m['latency_p99_ms']:>8.1f} "
            f"{m['cost_per_1k_skus_usd']:>12.4f}"
        )

    print(fmt_row("Cohere Rerank v3 (cloud)", cohere_metrics))
    print(fmt_row("cross-encoder/ms-marco-MiniLM-L-6-v2 (local)", local_metrics))
    print(sep)
    print()


def _save_results(
    output_dir: Path,
    cohere_metrics: dict[str, Any] | None,
    local_metrics: dict[str, Any] | None,
    sample_size: int,
) -> Path:
    """Guarda JSON de resultados en docs/rnd/spike-cross-encoder-results-{date}.json."""
    today = date.today().isoformat()
    output_path = output_dir / f"spike-cross-encoder-results-{today}.json"
    output_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "cohere": cohere_metrics,
        "cross_encoder_local": local_metrics,
        "run_at": datetime.now(UTC).isoformat(),
        "sample_size": sample_size,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Spike: evalúa Cross-Encoder vs Cohere Reranker para matching MT"
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("datasets/labeled_pairs_latest.jsonl"),
        help="Path al JSONL de pares etiquetados",
    )
    parser.add_argument(
        "--candidates",
        type=int,
        default=5,
        help="Número de candidatos por SKU a reranquear (default: 5)",
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Usa datos sintéticos en lugar del dataset real",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/rnd"),
        help="Directorio de salida para el JSON de resultados (default: docs/rnd)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    # --- Cargar / validar dataset ---
    if args.synthetic:
        logger.info("Modo sintético — generando datos de prueba")
        records = _generate_synthetic_data(n_skus=MAX_SKUS_SAMPLE, n_candidates=args.candidates)
    else:
        dataset_path: Path = args.dataset
        if not dataset_path.exists():
            logger.error(
                "Dataset no encontrado: %s\n"
                "El spike requiere un dataset etiquetado con ≥%d pares.\n"
                "Usa --synthetic para pruebas sin datos reales.",
                dataset_path,
                MIN_PAIRS_REQUIRED,
            )
            return 1

        # Contar pares totales antes de samplear
        total_lines = sum(1 for line in dataset_path.open(encoding="utf-8") if line.strip())
        if total_lines < MIN_PAIRS_REQUIRED:
            logger.error(
                "Dataset insuficiente: %d pares encontrados, se requieren ≥%d.\n"
                "Genera más datos etiquetados (US-F15-03-01) o usa --synthetic.",
                total_lines,
                MIN_PAIRS_REQUIRED,
            )
            return 1

        logger.info(
            "Cargando dataset: %s (%d pares totales, muestra ≤%d SKUs)",
            dataset_path,
            total_lines,
            MAX_SKUS_SAMPLE,
        )
        records = _load_dataset(dataset_path, max_skus=MAX_SKUS_SAMPLE)

    logger.info("Muestra: %d SKUs × %d candidatos", len(records), args.candidates)

    # --- Evaluar opciones ---
    logger.info("Evaluando Cohere Reranker v3...")
    cohere_metrics = _run_cohere(records, args.candidates)

    logger.info("Evaluando Cross-Encoder local (ms-marco-MiniLM-L-6-v2)...")
    local_metrics = _run_local_cross_encoder(records, args.candidates)

    if cohere_metrics is None and local_metrics is None:
        logger.error(
            "Ninguna opción disponible para evaluar. "
            "Configura COHERE_API_KEY y/o instala sentence-transformers."
        )
        # No forzamos exit 1 — el script completó (ambas opciones saltadas con WARNING)

    # --- Mostrar tabla ---
    _print_comparison_table(cohere_metrics, local_metrics)

    # --- Guardar JSON ---
    output_path = _save_results(
        args.output_dir,
        cohere_metrics,
        local_metrics,
        sample_size=len(records),
    )
    logger.info("Resultados guardados en: %s", output_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
