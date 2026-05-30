"""Task registration test for mt.pricing.auto_optimize_check (F8)."""

from __future__ import annotations


def test_auto_optimize_task_registered() -> None:
    # Importing the module registers the task on the celery app.
    import app.workers.tasks.pricing_auto_optimize  # noqa: F401
    from app.workers.worker import celery_app

    assert "mt.pricing.auto_optimize_check" in celery_app.tasks
