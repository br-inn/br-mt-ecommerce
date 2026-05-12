# Deferred Work

## Deferred from: code review de us-rnd-01-11 + us-rnd-01-12 (2026-05-12)

- **W-2** `Neo4jGraphRepository.health_check()` siempre retorna `healthy: False` — misleading cuando Fase 2 active el adapter real; ops dashboards verán siempre unhealthy. Resolver cuando se active Neo4j en Fase 2. [`graph_repository.py`]
- **W-3** Test `test_neo4j_repo_health_check_reports_stub` aserta `healthy is False` sin marca de lifecycle — fallará limpiamente cuando Fase 2 reemplace el stub, pero confunde a reviewers futuros. Añadir `pytest.mark` o comentario de ciclo de vida. [`test_graph_repository.py`]
- **W-6** `ComparatorServiceFactory.create()` sincrónico devuelve objetos con métodos async — patrón normal FastAPI; callers usan `await`. Sin riesgo si todos los callers son async. Documentar si se expone desde contextos sync. [`comparator/factory.py`]
- **W-1** `_verdict()` boundary `len(failures) >= 2` se vuelve frágil si `passes_ac()` añade nuevas claves métricas — el threshold no escala automáticamente. Revisar cuando se amplíe el set de ACs del POC en Fase 1.5. [`scripts/poc/g4_report.py`]
- **W-4** `failures = [k for k, v in ac.items() if not v]` trata valores falsy no-booleanos como fallos — riesgo bajo mientras `passes_ac()` retorne sólo booleans. Revisar si se añaden métricas numéricas. [`scripts/poc/g4_report.py`]
- **W-5** Denominador cobertura en `aggregate()` usa `n_skus_total` (SKUs solicitados) en lugar de SKUs observados — comportamiento intencional (penaliza fetches fallidos), pero cobertura puede aparecer menor de la real. Documentado en spec. [`scripts/poc/metrics_collector.py`]
