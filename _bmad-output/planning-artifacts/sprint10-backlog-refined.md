# Sprint 10 — Backlog refinado

*Generado: 2026-05-12 — Inicio Fase 1.5 Comparator R&D Extension*

---

## 1. Estado al inicio de S10

### Fase 1 cerrada al finalizar S9

| Épica | Estado | Notas |
|-------|--------|-------|
| EP-1A-01 a EP-1A-08 | ✅ done | Setup + PIM + proveedores + costes + FX + importers + RBAC + scheduler |
| EP-1B-01 a EP-1B-05 | ✅ done | Pricing + workflow aprobación + canales + connectors + hardening |
| EP-RND-01 | ✅ done | Comparator R&D — decisión G4 tomada; hooks listos para Fase 1.5 |

### Épicas Fase 1.5 al inicio de S10

| Épica | Estado | Stories totales | SP totales |
|-------|--------|-----------------|------------|
| EP-F15-01 KG Foundation | backlog | 6 | 34 SP |
| EP-F15-02 Pipeline Activation | backlog | 5 | 34 SP |
| EP-F15-03 Precision Enhancement | backlog | 5 | 31 SP |

### Pendientes externos (no bloqueantes para S10)

| Item | Owner | Estado |
|------|-------|--------|
| Doppler creds Hetzner → terraform apply | psierra + MT TI | Pendiente externo |
| Firma Translation Owner AR | psierra | Pendiente externo |
| Training-log / drill-log / cutover-signoff | psierra + MT TI | Postergado al final |

### Velocity de referencia

| Sprint | SP comprometidos | SP entregados | SP stretch |
|--------|-----------------|---------------|------------|
| S7 | 43 | 43 committed | 21 stretch |
| S8 | ~53 | ~53 committed | ~16 stretch |
| S9 | 21 | 21 committed (R&D focus) | 0 stretch |
| **S10 target** | **29** | — | **13** |

---

## 2. Tabla maestra de stories S10

### Stories comprometidas (P0/P1) — 29 SP

| ID | Épica | Descripción | SP | Agente | Depende de | Wave |
|----|-------|-------------|-----|--------|------------|------|
| US-F15-01-01 | EP-F15-01 | Neo4j setup + data residency UAE | 3 | A | — | Wave 1 |
| US-F15-01-02 | EP-F15-01 | Schema KG + seed 657 materiales | 5 | A | 01-01 | Wave 2 |
| US-F15-01-03 | EP-F15-01 | CDC Postgres → Neo4j (Celery) | 8 | B | 01-01 | Wave 3 |
| US-F15-02-01 | EP-F15-02 | Amazon SP API fetcher real | 8 | C | — | Wave 3 |
| US-F15-01-04 | EP-F15-01 | Activar Neo4jGraphRepository + fix W-2/W-3 | 5 | A | 01-01, 01-02, 01-03 | Wave 4 |

### Stories stretch (P2) — 13 SP

| ID | Épica | Descripción | SP | Agente | Depende de | Wave |
|----|-------|-------------|-----|--------|------------|------|
| US-F15-01-05 | EP-F15-01 | product_equivalences + ingestión fichas PDF | 8 | B | 01-04 | Wave 5 |
| US-F15-01-06 | EP-F15-01 | Dashboard monitoreo KG + integridad nightly | 5 | C | 01-03, 01-04 | Wave 5 |

**Total comprometido: 29 SP | Total stretch: 13 SP | Total target: 42 SP**

---

## 3. Fichas detalladas

### US-F15-01-01 — Neo4j setup + validación residencia datos UAE

**Épica**: EP-F15-01 | **SP**: 3 | **Agente sugerido**: A | **Depende de**: — (blocker de todo S10)

Confirmar servicio `neo4j` en `docker-compose.dev.yml` (imagen 5.20, puertos 17474/17687). Variables `.env.example`: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`, timeouts, pool size. Documento `docs/runbooks/neo4j-data-residency-uae.md` (región EU/AE, sin Aura cloud, backups Hetzner). Healthcheck con `cypher-shell`.

**Riesgo**: Bajo — Neo4j ya dockerizado localmente. Principalmente documentación + validación.

---

### US-F15-01-02 — Schema KG + seed Compatibilidad Materiales (657 filas)

**Épica**: EP-F15-01 | **SP**: 5 | **Agente sugerido**: A | **Depende de**: US-F15-01-01

Script `scripts/seed_kg_materials.py` idempotente (MERGE). Constraints en 4 node types. CSV seed `scripts/seed_data/kg_materials_seed.csv` con 657+ filas `material_a,material_b,pressure_bar,temperature_range,standard,confidence`. Tests `@pytest.mark.neo4j_real`.

**Riesgo**: Medio — requiere CSV con datos reales de compatibilidad de materiales. Si el CSV no existe, se genera sintéticamente para bootstrap.

---

### US-F15-01-03 — CDC Postgres → Neo4j (Supabase Realtime → Celery → Cypher)

**Épica**: EP-F15-01 | **SP**: 8 | **Agente sugerido**: B | **Depende de**: US-F15-01-01

Task Celery `sync_product_to_kg`. Supabase Realtime habilitado para `products` y `competitor_listings`. Propagación < 5s. Retry backoff exponencial (3 intentos, 10s/30s/90s). Modelo `cdc_event.py`. Tests: propagación exitosa, retry en fallo, idempotencia.

**Riesgo**: Medio — Supabase Realtime requiere configuración correcta en `supabase/config.toml`. Fallback manual si Realtime no escala.

---

### US-F15-02-01 — Amazon SP API fetcher real

**Épica**: EP-F15-02 | **SP**: 8 | **Agente sugerido**: C | **Depende de**: — (independiente de KG)

`AmazonSPApiAdapter` real con LWA OAuth2, endpoint `https://sellingpartnerapi-eu.amazon.com`, marketplace `A2VIGQ35RCS4UG` (UAE). Token cache TTL 3500s. Rate limit 2 req/s via `aiolimiter` + Redis. Retry `tenacity` (3 intentos). Fallback a stub si `MT_LIVE_NETWORK != true`. Registro `competitor_fetch_errors`.

**Riesgo**: Alto — requiere credenciales SP API (`SP_API_REFRESH_TOKEN`, `SP_API_LWA_CLIENT_ID`, `SP_API_LWA_CLIENT_SECRET`, `SP_API_SELLER_ID`). Story completable con stubs si credenciales no disponibles; activación real requiere credenciales MT.

---

### US-F15-01-04 — Activar Neo4jGraphRepository + fix health_check

**Épica**: EP-F15-01 | **SP**: 5 | **Agente sugerido**: A | **Depende de**: US-F15-01-01, 01-02, 01-03

Implementar `get_product_neighbors` y `get_competitor_context` con Cypher real en `graph_repository.py`. Fix W-2: `health_check()` retorna `healthy: True` cuando Neo4j responde. Fix W-3: `@pytest.mark.neo4j_real` en tests de integración. `GET /graphrag/health` responde 200.

**Riesgo**: Bajo — lógica bien definida en story spec. Cypher queries simples (MATCH + traversal).

---

### US-F15-01-05 — product_equivalences + ingestión fichas técnicas (STRETCH)

**Épica**: EP-F15-01 | **SP**: 8 | **Agente sugerido**: B | **Depende de**: US-F15-01-04

Migración Alembic tabla `product_equivalences`. Task Celery `ingest_equivalences_from_pdf` con pdfplumber + regex. Sync a Neo4j como aristas `EQUIVALENT_TO`. Tests con PDF fixture.

**Contingencia**: Si no hay PDFs disponibles en el bucket, story se implementa con fixtures sintéticos y se activa cuando lleguen las fichas reales.

---

### US-F15-01-06 — Dashboard monitoreo KG + integridad nightly (STRETCH)

**Épica**: EP-F15-01 | **SP**: 5 | **Agente sugerido**: C | **Depende de**: US-F15-01-03, 01-04

`GET /graphrag/metrics` con nodos, aristas, `orphan_nodes`, `cdc_lag_seconds`. HTTP 503 si lag > 300s. Celery Beat task `kg_integrity_check` (02:00 UTC). Tabla `kg_integrity_results`. Alerta en fallo.

---

## 4. Orden de ejecución y paralelismo

```
Wave 1 (blocker)
└── Agente A: US-F15-01-01 (3 SP) — Neo4j setup

Wave 2 (secuencial)
└── Agente A: US-F15-01-02 (5 SP) — KG seed + schema

Wave 3 (PARALELO)
├── Agente B: US-F15-01-03 (8 SP) — CDC Postgres→Neo4j
└── Agente C: US-F15-02-01 (8 SP) — Amazon SP API fetcher

Wave 4 (secuencial, después de Wave 3)
└── Agente A: US-F15-01-04 (5 SP) — Activar GraphRepository

─── COMPROMETIDAS: 29 SP ───────────────────────────────────

Wave 5 stretch (PARALELO, después de Wave 4)
├── Agente B: US-F15-01-05 (8 SP) — product_equivalences
└── Agente C: US-F15-01-06 (5 SP) — Dashboard monitoreo KG

─── STRETCH: 13 SP ─────────────────────────────────────────
```

**Wave 3 es el corazón del sprint**: CDC y Amazon SP API corren en paralelo, representando 16 SP simultáneos.

---

## 5. Riesgos S10

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Credenciales SP API no disponibles para Wave 3 | Media | Medio | US-F15-02-01 completable con stubs; activación real en S11 |
| CSV materiales 657 filas no curado | Media | Bajo | Generar sintético para bootstrap; refinar en S11 |
| Supabase Realtime no escala para CDC | Baja | Alto | Fallback a polling Celery Beat cada 60s |
| Neo4j 5.20 conflicto con stack Docker existente | Baja | Medio | Servicio ya dockerizado localmente — riesgo mínimo |
| Wave 4 bloqueada si Wave 3 se extiende | Media | Medio | US-F15-01-04 puede empezar parcialmente en modo test con Neo4j vacío |

---

## 6. Stories S11+ (no comprometidas en S10)

| ID | Épica | SP | Notas |
|----|-------|-----|-------|
| US-F15-02-02 | EP-F15-02 | 8 | VLM Judge (necesita KG activado) |
| US-F15-02-03 | EP-F15-02 | 5 | Reverse Image Search |
| US-F15-02-04 | EP-F15-02 | 5 | Price Sanity Check |
| US-F15-02-05 | EP-F15-02 | 8 | Tradeling API |
| US-F15-03-01 | EP-F15-03 | 5 | Dataset etiquetado (necesita matches reales de S10+) |
| US-F15-03-02 | EP-F15-03 | 8 | Embedding fine-tune |
| US-F15-03-03 | EP-F15-03 | 8 | Conformal Prediction |
| US-F15-03-04 | EP-F15-03 | 5 | Cross-Encoder spike |
| US-F15-03-05 | EP-F15-03 | 5 | Weight tuning + fix W-1/W-4 |

---

## 7. Próximos pasos

1. Ejecutar `bmad-dev-story` para US-F15-01-01 (Wave 1 — blocker)
2. Con Neo4j operativo, lanzar Wave 2 (01-02)
3. Lanzar Wave 3 en paralelo: Agente B → 01-03, Agente C → 02-01
4. Wave 4: 01-04 tras Wave 3 completada
5. Stretch Wave 5 si hay capacidad: 01-05 + 01-06 en paralelo

*Sprint 10 — Fase 1.5 KG Foundation. Target: Neo4j operativo con CDC + Amazon SP API real al finalizar.*
