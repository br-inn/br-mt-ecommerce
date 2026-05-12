"""Task Celery — fine-tune de embeddings con ≥1 000 pares (US-F15-03-02).

Task ``ml.finetune_embeddings`` — registrada en job_definitions o invocada
manualmente. Lee un dataset JSONL (local o desde bucket ``ml-datasets``),
valida que haya ≥1 000 pares, entrena un SentenceTransformer con
CosineSimilarityLoss, evalúa con EmbeddingSimilarityEvaluator sobre 20 %
hold-out, sube el modelo al bucket ``ml-models`` y registra el resultado en
``comparator_model_registry`` con status='candidate'.

Requiere:
    sentence-transformers>=2.7.0

Patrón: asyncio.run / get_sessionmaker (igual a price_sanity, calibrator).
NO hardcodear schedule en celery_config.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.workers.worker import celery_app

logger = logging.getLogger(__name__)

_BUCKET_DATASETS = "ml-datasets"
_BUCKET_MODELS = "ml-models"
_MIN_PAIRS = 1_000
_HOLDOUT_RATIO = 0.20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_jsonl_local(path: str) -> list[dict[str, Any]]:
    """Lee un archivo JSONL desde el sistema local de archivos."""
    pairs: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                pairs.append(json.loads(line))
    return pairs


def _read_jsonl_from_storage(storage_path: str) -> list[dict[str, Any]]:
    """Descarga un JSONL desde el bucket ``ml-datasets`` en Supabase Storage."""
    from app.core.supabase import get_supabase_client  # lazy import

    client = get_supabase_client()
    response = client.storage.from_(_BUCKET_DATASETS).download(storage_path)
    pairs: list[dict[str, Any]] = []
    for line in response.decode("utf-8").splitlines():
        line = line.strip()
        if line:
            pairs.append(json.loads(line))
    return pairs


def _load_pairs(dataset_path: str) -> list[dict[str, Any]]:
    """Carga pares desde dataset_path (local o storage://...)."""
    if dataset_path.startswith("storage://"):
        # Formato: storage://<ruta dentro del bucket ml-datasets>
        storage_key = dataset_path[len("storage://"):]
        return _read_jsonl_from_storage(storage_key)
    return _read_jsonl_local(dataset_path)


def _upload_model_to_storage(local_dir: Path, model_dir_name: str) -> str:
    """Sube todos los archivos del directorio local al bucket ``ml-models``.

    Returns:
        Ruta base en el bucket (prefijo ``embeddings/<model_dir_name>/``).
    """
    from app.core.supabase import get_supabase_client  # lazy import

    client = get_supabase_client()
    bucket_prefix = f"embeddings/{model_dir_name}"

    for file_path in sorted(local_dir.rglob("*")):
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(local_dir)
        object_key = f"{bucket_prefix}/{relative.as_posix()}"
        with open(file_path, "rb") as fh:
            client.storage.from_(_BUCKET_MODELS).upload(
                object_key,
                fh.read(),
                file_options={"upsert": "true"},
            )

    return bucket_prefix


async def _insert_registry(
    *,
    model_name: str,
    base_model: str,
    storage_path: str,
    eval_metrics: dict[str, Any],
) -> str:
    """Inserta fila en comparator_model_registry y devuelve el UUID como str."""
    from app.db.engine import get_sessionmaker
    from app.db.models.comparator import ComparatorModelRegistry

    async with get_sessionmaker()() as session:
        async with session.begin():
            record = ComparatorModelRegistry(
                model_name=model_name,
                base_model=base_model,
                storage_path=storage_path,
                eval_metrics_jsonb=eval_metrics,
                trained_at=datetime.now(tz=UTC),
                status="candidate",
            )
            session.add(record)
            await session.flush()
            return str(record.id)


# ---------------------------------------------------------------------------
# Core logic (sync — se ejecuta dentro de la task Celery)
# ---------------------------------------------------------------------------

def _run_finetune(
    *,
    dataset_path: str,
    model_base: str,
    epochs: int,
    batch_size: int,
) -> dict[str, Any]:
    """Entrena el modelo y devuelve métricas. Toda la lógica ML es síncrona."""
    try:
        from sentence_transformers import (  # type: ignore[import-not-found]
            InputExample,
            SentenceTransformer,
            evaluation,
            losses,
        )
        from torch.utils.data import DataLoader  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers no instalado. "
            "Agregar sentence-transformers>=2.7.0 a pyproject.toml."
        ) from exc

    # 1. Cargar dataset
    raw_pairs = _load_pairs(dataset_path)
    n_total = len(raw_pairs)

    if n_total < _MIN_PAIRS:
        raise _InsufficientDataError(available=n_total)

    # 2. Split train / holdout (80/20)
    n_holdout = max(1, int(n_total * _HOLDOUT_RATIO))
    train_pairs = raw_pairs[n_holdout:]
    eval_pairs = raw_pairs[:n_holdout]

    # 3. Construir InputExample
    train_examples = [
        InputExample(
            texts=[p["title_mt"], p["title_candidate"]],
            label=float(p["label"]),
        )
        for p in train_pairs
    ]
    eval_sentences1 = [p["title_mt"] for p in eval_pairs]
    eval_sentences2 = [p["title_candidate"] for p in eval_pairs]
    eval_scores = [float(p["label"]) for p in eval_pairs]

    # 4. Entrenar
    model = SentenceTransformer(model_base)
    train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=batch_size)
    train_loss = losses.CosineSimilarityLoss(model)

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "model"
        output_path.mkdir(parents=True, exist_ok=True)

        model.fit(
            train_objectives=[(train_dataloader, train_loss)],
            epochs=epochs,
            output_path=str(output_path),
            show_progress_bar=False,
        )

        # 5. Evaluar
        evaluator = evaluation.EmbeddingSimilarityEvaluator(
            sentences1=eval_sentences1,
            sentences2=eval_sentences2,
            scores=eval_scores,
            name="holdout",
        )
        eval_result = evaluator(model, output_path=str(output_path))
        # EmbeddingSimilarityEvaluator devuelve el cosine score (float)
        cosine_accuracy_val = float(eval_result)

        # Approximar eval_loss como 1 - cosine_accuracy (proxy razonable)
        eval_loss = float(1.0 - cosine_accuracy_val)

        # 6. Nombre del directorio en storage
        date_tag = datetime.now(tz=UTC).strftime("%Y%m%d")
        # Sanitizar model_base para usar como nombre de directorio
        safe_base = model_base.replace("/", "_").replace(":", "-")
        model_dir_name = f"{safe_base}-mt-finetuned-{date_tag}"

        storage_path = _upload_model_to_storage(output_path, model_dir_name)

    return {
        "storage_path": storage_path,
        "model_dir_name": model_dir_name,
        "cosine_accuracy_val": cosine_accuracy_val,
        "eval_loss": eval_loss,
        "n_train": len(train_examples),
        "n_eval": n_holdout,
    }


class _InsufficientDataError(Exception):
    """Lanzada cuando el dataset tiene menos de 1 000 pares."""

    def __init__(self, available: int) -> None:
        super().__init__(f"insufficient_data: {available} pairs available, {_MIN_PAIRS} required")
        self.available = available


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="ml.finetune_embeddings",
    bind=True,
    max_retries=0,
    queue="comparator",
)
def finetune_embeddings(  # type: ignore[no-untyped-def]  # noqa: ANN001
    self,
    *,
    dataset_path: str,
    model_base: str = "sentence-transformers/all-MiniLM-L6-v2",
    epochs: int = 3,
    batch_size: int = 16,
) -> dict[str, Any]:
    """Entrena un embedding fine-tuned sobre pares (title_mt, title_candidate).

    Args:
        dataset_path: Ruta local al JSONL o ``storage://<key>`` para descargarlo
            del bucket ``ml-datasets``. Cada línea: ``{"title_mt": ...,
            "title_candidate": ..., "label": <float 0-1>}``.
        model_base: Modelo HuggingFace base (default all-MiniLM-L6-v2).
        epochs: Épocas de entrenamiento (default 3).
        batch_size: Batch size (default 16).

    Raises:
        Retry: Si el dataset tiene menos de 1 000 pares (max_retries=0,
            se convierte en fallo inmediato con log estructurado).
    """
    t0 = time.monotonic()

    try:
        result = _run_finetune(
            dataset_path=dataset_path,
            model_base=model_base,
            epochs=epochs,
            batch_size=batch_size,
        )
    except _InsufficientDataError as exc:
        logger.warning(
            "finetune_aborted",
            extra={
                "event": "finetune_aborted",
                "reason": "insufficient_data",
                "available_pairs": exc.available,
                "required_pairs": _MIN_PAIRS,
                "dataset_path": dataset_path,
            },
        )
        raise self.retry(
            exc=exc,
            countdown=0,
        )
    except Exception:
        logger.exception(
            "finetune_failed",
            extra={"event": "finetune_failed", "dataset_path": dataset_path},
        )
        raise

    # Insertar en registry
    model_name = result["model_dir_name"]
    eval_metrics = {
        "cosine_accuracy_val": result["cosine_accuracy_val"],
        "eval_loss": result["eval_loss"],
        "n_train": result["n_train"],
        "n_eval": result["n_eval"],
    }
    model_id = asyncio.run(
        _insert_registry(
            model_name=model_name,
            base_model=model_base,
            storage_path=result["storage_path"],
            eval_metrics=eval_metrics,
        )
    )

    duration_s = int(time.monotonic() - t0)
    logger.info(
        "finetune_complete",
        extra={
            "event": "finetune_complete",
            "model_path": result["storage_path"],
            "eval_cosine_accuracy": round(result["cosine_accuracy_val"], 4),
            "duration_s": duration_s,
            "model_id": model_id,
            "n_train": result["n_train"],
            "n_eval": result["n_eval"],
        },
    )

    return {
        "model_id": model_id,
        "model_path": result["storage_path"],
        "eval_cosine_accuracy": result["cosine_accuracy_val"],
        "eval_loss": result["eval_loss"],
        "n_train": result["n_train"],
        "n_eval": result["n_eval"],
        "duration_s": duration_s,
    }


__all__ = ["finetune_embeddings"]
