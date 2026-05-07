"""Celery tasks — un módulo por queue.

Convenciones:
- Naming canónico `mt.<module>.<task>` para que el routing en `worker.py`
  funcione automáticamente.
- Cada módulo expone al menos una task `health_ping` para verificar que el
  worker está vivo y autoload de tasks funciona.
"""
