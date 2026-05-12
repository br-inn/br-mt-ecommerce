# Deferred Work

## Deferred from: code review de US-F15-02-02 (2026-05-12)

- **F-09** JSONB merge `||` en `enqueue_vlm_uncertain` sobreescribe clave `vlm_judge` entera en reintento — no hay historial previo. Requiere decisión arquitectónica (append vs overwrite) antes de implementar retry flows. [`human_queue_service.py`]
- **F-20** `enqueue_vlm_uncertain` retorna 0 filas sin log ni error cuando no hay `MatchCandidate` pending para el SKU — silent no-op aceptable en Fase 1 donde la tabla puede estar vacía. Añadir logging cuando el pipeline esté activo en Fase 2. [`human_queue_service.py`]
- **F-21** `flush()` sin `commit()` en `confirm_match` — transacción gestionada por el caller. Si VLM call precede al flush y falla, el estado queda inconsistente. Revisar ownership de transacción cuando se integre el pipeline completo. [`adapters.py`]
- **F-24** `VlmJudgeFactory._is_enabled()` silencia `ImportError` de `flag_service` devolviendo `False` — feature se desactiva silenciosamente ante errores de dependencia. Patrón consistente con `ComparatorServiceFactory`. Añadir health check endpoint que exponga el estado real del factory. [`factory.py`]

## Deferred from: code review de us-rnd-01-11 + us-rnd-01-12 (2026-05-12)

- **W-2** `Neo4jGraphRepository.health_check()` siempre retorna `healthy: False` — misleading cuando Fase 2 active el adapter real; ops dashboards verán siempre unhealthy. Resolver cuando se active Neo4j en Fase 2. [`graph_repository.py`]
- **W-3** Test `test_neo4j_repo_health_check_reports_stub` aserta `healthy is False` sin marca de lifecycle — fallará limpiamente cuando Fase 2 reemplace el stub, pero confunde a reviewers futuros. Añadir `pytest.mark` o comentario de ciclo de vida. [`test_graph_repository.py`]
- **W-6** `ComparatorServiceFactory.create()` sincrónico devuelve objetos con métodos async — patrón normal FastAPI; callers usan `await`. Sin riesgo si todos los callers son async. Documentar si se expone desde contextos sync. [`comparator/factory.py`]
- **W-1** `_verdict()` boundary `len(failures) >= 2` se vuelve frágil si `passes_ac()` añade nuevas claves métricas — el threshold no escala automáticamente. Revisar cuando se amplíe el set de ACs del POC en Fase 1.5. [`scripts/poc/g4_report.py`]
- **W-4** `failures = [k for k, v in ac.items() if not v]` trata valores falsy no-booleanos como fallos — riesgo bajo mientras `passes_ac()` retorne sólo booleans. Revisar si se añaden métricas numéricas. [`scripts/poc/g4_report.py`]
- **W-5** Denominador cobertura en `aggregate()` usa `n_skus_total` (SKUs solicitados) en lugar de SKUs observados — comportamiento intencional (penaliza fetches fallidos), pero cobertura puede aparecer menor de la real. Documentado en spec. [`scripts/poc/metrics_collector.py`]
