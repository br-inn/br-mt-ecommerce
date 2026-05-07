"""Domain services — orquestan repositorios + emiten eventos Celery (ADR-045).

Cada subpaquete corresponde a un dominio:
- pricing/      motor v5.1 + simulate + exception_rules
- comparator/   matching pipeline (research → fase 1.5+)
- imports/      diff/apply de PIM, costs, excel
- kb/           knowledge base (fase 1.5+)
- users/        invite, role assignment, force-logout
- audit/        audit_events ingestion + queries
"""
