def test_fx_task_registered() -> None:
    # Importing the task module triggers @celery_app.task registration
    # (same side-effect contract as the worker `include=[...]` list).
    import app.workers.tasks.fx  # noqa: F401
    from app.workers.worker import celery_app

    assert "mt.fx.sync_daily" in celery_app.tasks
