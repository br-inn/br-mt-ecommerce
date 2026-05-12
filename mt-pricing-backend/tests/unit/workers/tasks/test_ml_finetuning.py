"""Unit tests para ml.finetune_embeddings Celery task (US-F15-03-02).

Tests:
1. test_finetune_aborts_with_insufficient_data — mock JSONL con 500 pares →
   verifica Retry lanzado y log correcto.
2. test_finetune_logs_completion — mock SentenceTransformer + Supabase Storage
   + DB → verifica log ``finetune_complete``.
3. test_promote_model_updates_status — mock DB con candidate + active previo →
   verifica transición correcta.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_jsonl_lines(n: int) -> list[str]:
    """Genera N líneas JSONL de pares de entrenamiento sintéticos."""
    return [
        json.dumps(
            {
                "title_mt": f"Product MT {i}",
                "title_candidate": f"Product Candidate {i}",
                "label": 0.9 if i % 2 == 0 else 0.1,
            }
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# AC#3 test 1 — abort si insuficientes datos
# ---------------------------------------------------------------------------

def test_finetune_aborts_with_insufficient_data(caplog: pytest.LogCaptureFixture) -> None:
    """Con 500 pares (< 1 000) la task debe lanzar Retry y emitir log de abort.

    Estrategia: patch _run_finetune para que lance _InsufficientDataError
    directamente (sin necesitar sentence-transformers instalado). La task
    captura el error y llama self.retry — que al tener max_retries=0 relanza
    la excepción original.
    """
    import app.workers.tasks.ml_finetuning as mod

    pairs_500 = [
        {"title_mt": f"MT {i}", "title_candidate": f"Cand {i}", "label": 0.8}
        for i in range(500)
    ]

    # Verificar que _InsufficientDataError se lanza correctamente con 500 pares
    # cuando sentence_transformers está mockeado
    mock_st = MagicMock()
    mock_st.InputExample = MagicMock(side_effect=lambda texts, label: MagicMock())
    mock_st.SentenceTransformer = MagicMock()
    mock_st.losses = MagicMock()
    mock_st.evaluation = MagicMock()
    mock_torch = MagicMock()
    mock_torch.utils.data.DataLoader = MagicMock()

    with (
        patch.dict(
            "sys.modules",
            {
                "sentence_transformers": mock_st,
                "torch": mock_torch,
                "torch.utils": mock_torch.utils,
                "torch.utils.data": mock_torch.utils.data,
            },
        ),
        patch.object(mod, "_load_pairs", return_value=pairs_500),
    ):
        with pytest.raises(mod._InsufficientDataError) as exc_info:
            mod._run_finetune(
                dataset_path="/tmp/fake_500.jsonl",
                model_base="sentence-transformers/all-MiniLM-L6-v2",
                epochs=1,
                batch_size=8,
            )

    assert exc_info.value.available == 500

    # Ahora verificar que la task lanza Retry + emite log de warning
    class _FakeRetryError(Exception):
        pass

    with (
        caplog.at_level(logging.WARNING, logger="app.workers.tasks.ml_finetuning"),
        patch.object(
            mod,
            "_run_finetune",
            side_effect=mod._InsufficientDataError(available=500),
        ),
    ):
        with pytest.raises(mod._InsufficientDataError):
            # Llama a la task con max_retries=0 — self.retry relanza la excepción
            mod.finetune_embeddings.run(  # type: ignore[attr-defined]
                dataset_path="/tmp/fake_500.jsonl",
            )

    # Verificar log estructurado de abort
    abort_records = [
        r for r in caplog.records
        if "finetune_aborted" in r.getMessage() or "insufficient_data" in r.getMessage()
    ]
    assert len(abort_records) >= 1, (
        f"Se esperaba log 'finetune_aborted', records: {[r.getMessage() for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# AC#3 test 2 — log finetune_complete al terminar exitosamente
# ---------------------------------------------------------------------------

def test_finetune_logs_completion(caplog: pytest.LogCaptureFixture) -> None:
    """Mock SentenceTransformer + Storage + DB → verifica log finetune_complete."""
    import app.workers.tasks.ml_finetuning as mod

    # Dataset con 1200 pares
    pairs = [
        {"title_mt": f"MT {i}", "title_candidate": f"Cand {i}", "label": 0.8}
        for i in range(1200)
    ]

    # Mock SentenceTransformer
    fake_model = MagicMock()
    fake_model.fit = MagicMock()

    fake_evaluator_instance = MagicMock()
    fake_evaluator_instance.return_value = MagicMock(return_value=0.87)
    # EmbeddingSimilarityEvaluator.__call__ devuelve float
    fake_evaluator_instance.__call__ = MagicMock(return_value=0.87)

    mock_st_module = MagicMock()
    mock_st_module.SentenceTransformer.return_value = fake_model
    mock_st_module.InputExample = MagicMock(
        side_effect=lambda texts, label: MagicMock(texts=texts, label=label)
    )
    mock_st_module.losses.CosineSimilarityLoss.return_value = MagicMock()
    mock_st_module.evaluation.EmbeddingSimilarityEvaluator.return_value = (
        fake_evaluator_instance
    )

    mock_dataloader = MagicMock()

    fake_model_id = str(uuid.uuid4())

    with (
        patch.object(mod, "_load_pairs", return_value=pairs),
        patch.dict(
            "sys.modules",
            {
                "sentence_transformers": mock_st_module,
                "sentence_transformers.losses": mock_st_module.losses,
                "sentence_transformers.evaluation": mock_st_module.evaluation,
                "torch": MagicMock(),
                "torch.utils": MagicMock(),
                "torch.utils.data": MagicMock(DataLoader=MagicMock(return_value=mock_dataloader)),
            },
        ),
        patch.object(mod, "_upload_model_to_storage", return_value="embeddings/test-model-20260519"),
        patch.object(mod, "_insert_registry", new=AsyncMock(return_value=fake_model_id)),
        caplog.at_level(logging.INFO, logger="app.workers.tasks.ml_finetuning"),
    ):
        # Necesitamos que _run_finetune funcione con el mock de sentence_transformers
        # Hacemos un patch más directo de _run_finetune para retornar resultados fijos
        fake_run_result = {
            "storage_path": "embeddings/all-MiniLM-L6-v2-mt-finetuned-20260519",
            "model_dir_name": "all-MiniLM-L6-v2-mt-finetuned-20260519",
            "cosine_accuracy_val": 0.87,
            "eval_loss": 0.13,
            "n_train": 960,
            "n_eval": 240,
        }
        with patch.object(mod, "_run_finetune", return_value=fake_run_result):
            result = mod.finetune_embeddings.run(  # type: ignore[attr-defined]
                dataset_path="/tmp/fake_1200.jsonl",
                model_base="sentence-transformers/all-MiniLM-L6-v2",
                epochs=3,
                batch_size=16,
            )

    # Verificar resultado
    assert result["model_id"] == fake_model_id
    assert result["model_path"] == fake_run_result["storage_path"]
    assert result["eval_cosine_accuracy"] == 0.87
    assert result["n_train"] == 960
    assert result["n_eval"] == 240
    assert "duration_s" in result

    # Verificar log finetune_complete
    complete_logs = [r for r in caplog.records if "finetune_complete" in r.getMessage()]
    assert len(complete_logs) >= 1, "Se esperaba al menos un log 'finetune_complete'"


# ---------------------------------------------------------------------------
# AC#4 test 3 — promote_model actualiza status correctamente
# ---------------------------------------------------------------------------

def test_promote_model_updates_status() -> None:
    """Mock DB con candidate + active previo → verifica transición correcta."""
    from scripts.poc.promote_model import _promote

    candidate_id = uuid.uuid4()
    active_id = uuid.uuid4()

    # Modelos fake
    class _FakeModel:
        def __init__(self, mid: uuid.UUID, status: str) -> None:
            self.id = mid
            self.status = status

    candidate_model = _FakeModel(candidate_id, "candidate")
    active_model = _FakeModel(active_id, "active")

    # Session mock
    async def _mock_execute(stmt: Any) -> Any:
        # Determinar qué consulta se está haciendo por el WHERE
        # Simplificación: primera vez devuelve candidate, segunda devuelve active
        return _mock_execute

    call_count: list[int] = [0]

    fake_session = MagicMock()

    async def _execute(stmt: Any) -> Any:
        result_mock = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            # Primera ejecución: buscar por id → candidate
            result_mock.scalar_one_or_none.return_value = candidate_model
        else:
            # Segunda ejecución: buscar active
            result_mock.scalar_one_or_none.return_value = active_model
        return result_mock

    fake_session.execute = _execute
    fake_session.begin = MagicMock()
    fake_session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    fake_session.begin.return_value.__aexit__ = AsyncMock(return_value=None)

    class _FakeSessionMaker:
        def __call__(self) -> Any:
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(return_value=fake_session)
            ctx.__aexit__ = AsyncMock(return_value=None)
            return ctx

    import asyncio

    result = asyncio.run(
        _promote(
            model_id=str(candidate_id),
            env="staging",
            sessionmaker=_FakeSessionMaker(),
        )
    )

    # candidate_model debe haber sido promovido a active
    assert candidate_model.status == "active"
    # active_model anterior debe haber sido retirado
    assert active_model.status == "retired"

    # Resultado JSON correcto
    assert result["promoted"] == str(candidate_id)
    assert result["retired"] == str(active_id)
    assert result["env"] == "staging"
