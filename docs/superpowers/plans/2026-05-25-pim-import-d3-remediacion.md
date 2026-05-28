# PIM Import D3 — Remediación upload batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el endpoint `POST /imports/pim/upload` pase el archivo subido por el usuario a la Celery task correctamente (descargando de Supabase Storage), en lugar del path fijo del fixture de filesystem.

**Architecture:** El único bug confirmado es D3: `imports.py:447` siempre pasa `_PIM_FIXTURE_PATH` a `run_pim_import_task.apply_async()` ignorando el archivo que el usuario acaba de subir a Storage. La fix tiene tres piezas: (1) añadir `download_bytes` a `storage.py`, (2) añadir helper `_resolve_to_local` en la Celery task que descarga de Storage si el path no existe en filesystem, (3) cambiar la call del endpoint para pasar `storage_path` en lugar de `_PIM_FIXTURE_PATH`. Todo el resto del pipeline (parser, differ/applier, mapeo canónico, RBAC, audit, estado BD, frontend) ya está correcto.

**Tech Stack:** Python 3.11 · FastAPI · Celery · supabase-py v2 · pytest-asyncio · unittest.mock

---

## Diagnóstico ejecutado — D1-D9

> Estos resultados se obtuvieron leyendo el código real antes de escribir el plan.
> No requieren verificación adicional — tratar como ground truth.

| Bloqueo | Resultado | Evidencia (archivo:línea) |
|---|---|---|
| D1 — mapper divergente | **Descartado** | `services/imports/pim_row_mapper.py:18` importa `map_row` de `column_mapper` |
| D2 — header sin validar en batch | **Descartado** | `services/imports/pim_importer.py:124-133` llama `_collect_header_errors` |
| **D3 — worker lee fixture** | **CONFIRMADO** | `api/routes/imports.py:447` pasa `_PIM_FIXTURE_PATH`; comentario TODO en :441-443 |
| D4 — ciclo de estados/counters | **Descartado** | `pim_importer.py` persiste todo; `_serialize_import_run` lo devuelve |
| D5 — sin preview en batch | Decisión negocio, fuera de alcance | — |
| D6 — RBAC/RFC 7807/audit | **Descartado** | RBAC OK; audit OK; errores compatibles ProblemDetails |
| D7 — idempotencia | **Descartado** | UPSERT por SKU + `manual_locked_fields` respetados en `_process_row` |
| D8 — frontend | **Descartado** | `/admin/imports` expone upload, fixture, lista con polling 5 s y detalle |
| D9 — mapeo columnas reales | **Descartado** | `column_mapper.py` verificado contra archivo 5085 filas |

---

## Archivos a crear / modificar

| Acción | Ruta (relativa al repo) |
|---|---|
| **Modificar** | `mt-pricing-backend/app/services/storage.py` |
| **Modificar** | `mt-pricing-backend/app/workers/tasks/imports.py` |
| **Modificar** | `mt-pricing-backend/app/api/routes/imports.py` |
| **Modificar** | `mt-pricing-backend/tests/db/test_storage_helper.py` |
| **Modificar** | `mt-pricing-backend/tests/api/test_imports_pim.py` |
| **Crear** | `mt-pricing-backend/tests/workers/test_pim_task_resolve.py` |

---

## Task 0: Git setup

**Files:** ninguno

- [ ] **Step 1: Verificar rama**

  ```bash
  cd mt-pricing-backend
  git status
  git checkout main
  git pull
  git checkout -b fix/pim-upload-storage-path
  ```

  Expected: rama nueva `fix/pim-upload-storage-path` creada desde `main` limpio.

---

## Task 1: Añadir `download_bytes` a `storage.py`

**Files:**
- Modify: `mt-pricing-backend/app/services/storage.py`
- Test: `mt-pricing-backend/tests/db/test_storage_helper.py`

### 1.1 — Escribir el test que falla

- [ ] **Step 1: Abrir `tests/db/test_storage_helper.py` y añadir al final:**

  ```python
  # --------------------------------------------------------------------------
  # download_bytes
  # --------------------------------------------------------------------------
  def test_download_bytes_calls_supabase_with_correct_args() -> None:
      """download_bytes invoca sb.storage.from_(bucket).download(path=path)."""
      mock_client = MagicMock()
      mock_client.storage.from_.return_value.download.return_value = b"xlsx_data"

      result = storage_svc.download_bytes(
          "pim/2026/05/25/user/test.xlsx",
          bucket="imports-raw",
          client=mock_client,
      )

      mock_client.storage.from_.assert_called_once_with("imports-raw")
      mock_client.storage.from_().download.assert_called_once_with(
          path="pim/2026/05/25/user/test.xlsx"
      )
      assert result == b"xlsx_data"


  def test_download_bytes_uses_default_bucket_from_settings() -> None:
      """Sin bucket explícito usa settings.SUPABASE_STORAGE_BUCKET_IMAGES."""
      mock_client = MagicMock()
      mock_client.storage.from_.return_value.download.return_value = b""

      from app.core.config import settings

      storage_svc.download_bytes("some/path.xlsx", client=mock_client)

      mock_client.storage.from_.assert_called_once_with(
          settings.SUPABASE_STORAGE_BUCKET_IMAGES
      )
  ```

- [ ] **Step 2: Ejecutar el test para confirmar que falla**

  ```bash
  cd mt-pricing-backend
  uv run pytest tests/db/test_storage_helper.py::test_download_bytes_calls_supabase_with_correct_args -v
  ```

  Expected output: `FAILED` con `AttributeError: module ... has no attribute 'download_bytes'`

### 1.2 — Implementar `download_bytes`

- [ ] **Step 3: Añadir la función al final de la sección "Upload helper" en `app/services/storage.py`** (después de `upload_bytes`, antes del final del archivo):

  ```python
  # --------------------------------------------------------------------------
  # Download helper
  # --------------------------------------------------------------------------
  def download_bytes(
      storage_path: str,
      *,
      bucket: str | None = None,
      client: "Client | None" = None,
  ) -> bytes:
      """Descarga ``storage_path`` del bucket y devuelve los bytes raw.

      Args:
          storage_path: path dentro del bucket (sin slash inicial).
          bucket: override opcional. Default: ``SUPABASE_STORAGE_BUCKET_IMAGES``.
          client: override del cliente Supabase (testing).

      Returns:
          bytes del objeto descargado.

      Raises:
          RuntimeError: si Supabase retorna error.
      """
      bucket = bucket or settings.SUPABASE_STORAGE_BUCKET_IMAGES
      sb = client or get_supabase_admin()
      return sb.storage.from_(bucket).download(path=storage_path)
  ```

- [ ] **Step 4: Ejecutar los tests de storage para confirmar que pasan**

  ```bash
  cd mt-pricing-backend
  uv run pytest tests/db/test_storage_helper.py -v
  ```

  Expected: todos `PASSED`

- [ ] **Step 5: Commit**

  ```bash
  git add mt-pricing-backend/app/services/storage.py \
          mt-pricing-backend/tests/db/test_storage_helper.py
  git commit -m "feat(storage): add download_bytes helper for Supabase Storage"
  ```

---

## Task 2: Añadir `_resolve_to_local` en la Celery task

**Files:**
- Create: `mt-pricing-backend/tests/workers/test_pim_task_resolve.py`
- Modify: `mt-pricing-backend/app/workers/tasks/imports.py`

La función debe:
- Si `Path(source_path).exists()` → devolver `(Path(source_path), False)` (fixture mode, sin descarga)
- En caso contrario → tratar `source_path` como path-dentro-del-bucket `SUPABASE_STORAGE_BUCKET_IMPORTS`, descargar a `/tmp`, devolver `(Path(tmp), True)` (caller debe borrar)

### 2.1 — Crear el test

- [ ] **Step 1: Crear `tests/workers/__init__.py`** (vacío) si no existe:

  ```bash
  mkdir -p mt-pricing-backend/tests/workers
  touch mt-pricing-backend/tests/workers/__init__.py
  ```

- [ ] **Step 2: Crear `tests/workers/test_pim_task_resolve.py`:**

  ```python
  """Unit tests para _resolve_to_local (mt.imports.run_pim_import_task helper)."""

  from __future__ import annotations

  import os
  import tempfile
  from pathlib import Path
  from unittest.mock import MagicMock, patch

  import pytest

  pytestmark = [pytest.mark.unit]


  def test_resolve_returns_existing_local_path(tmp_path: Path) -> None:
      """Si el path existe en filesystem → devuelve (path, False)."""
      from app.workers.tasks.imports import _resolve_to_local

      xlsx = tmp_path / "test.xlsx"
      xlsx.write_bytes(b"PK")

      local, should_cleanup = _resolve_to_local(str(xlsx))

      assert local == xlsx
      assert should_cleanup is False


  def test_resolve_downloads_from_storage_when_file_missing(tmp_path: Path) -> None:
      """Si el path no existe → descarga de Storage y devuelve (tmp, True)."""
      from app.workers.tasks.imports import _resolve_to_local

      fake_data = b"XLSX_BYTES"
      storage_path = "pim/2026/05/25/uid/PIM completo.xlsx"

      with patch("app.workers.tasks.imports.download_bytes", return_value=fake_data) as mock_dl:
          local, should_cleanup = _resolve_to_local(storage_path)

      assert should_cleanup is True
      assert local.exists()
      assert local.read_bytes() == fake_data
      assert local.suffix == ".xlsx"
      mock_dl.assert_called_once()
      # Cleanup
      local.unlink(missing_ok=True)


  def test_resolve_storage_path_with_bucket_prefix_stripped(tmp_path: Path) -> None:
      """Si el path incluye el bucket como prefijo → aún funciona correctamente."""
      from app.workers.tasks.imports import _resolve_to_local

      # source_storage_path guardado en BD = "imports-raw/pim/..."
      storage_path = "imports-raw/pim/2026/05/25/uid/file.xlsx"

      with patch("app.workers.tasks.imports.download_bytes", return_value=b"data") as mock_dl:
          local, should_cleanup = _resolve_to_local(storage_path)

      assert should_cleanup is True
      local.unlink(missing_ok=True)
      # El helper debe llamar a download_bytes (independientemente del prefijo)
      mock_dl.assert_called_once()


  def test_resolve_cleanup_tmp_file_on_caller(tmp_path: Path) -> None:
      """El caller (task) es responsable de borrar el tmp cuando should_cleanup=True."""
      from app.workers.tasks.imports import _resolve_to_local

      with patch("app.workers.tasks.imports.download_bytes", return_value=b"x"):
          local, should_cleanup = _resolve_to_local("nonexistent/path.xlsx")

      assert should_cleanup is True
      # Simula que el caller lo borra
      local.unlink(missing_ok=True)
      assert not local.exists()
  ```

- [ ] **Step 3: Ejecutar para confirmar que falla**

  ```bash
  cd mt-pricing-backend
  uv run pytest tests/workers/test_pim_task_resolve.py -v
  ```

  Expected: `FAILED` con `ImportError: cannot import name '_resolve_to_local'`

### 2.2 — Implementar `_resolve_to_local` y actualizar el task

- [ ] **Step 4: Editar `app/workers/tasks/imports.py`. Añadir los imports necesarios al bloque de imports del módulo (justo después de `from app.workers.worker import celery_app`):**

  ```python
  import os
  import tempfile
  from pathlib import Path
  ```

- [ ] **Step 5: Añadir la función `_resolve_to_local` antes de `health_ping`:**

  ```python
  def _resolve_to_local(source_path: str) -> tuple[Path, bool]:
      """Devuelve (local_path, should_cleanup).

      - Si ``source_path`` existe en filesystem (fixture mode) → (path, False).
      - Si no → lo trata como path-dentro-del-bucket SUPABASE_STORAGE_BUCKET_IMPORTS,
        descarga a /tmp y devuelve (tmp_path, True).
        El caller es responsable de borrar el tmp con ``local_path.unlink(missing_ok=True)``.
      """
      p = Path(source_path)
      if p.exists():
          return p, False

      from app.core.config import settings

      data = download_bytes(source_path, bucket=settings.SUPABASE_STORAGE_BUCKET_IMPORTS)
      suffix = p.suffix or ".xlsx"
      fd, tmp_str = tempfile.mkstemp(suffix=suffix, prefix="pim_import_")
      os.close(fd)
      tmp = Path(tmp_str)
      tmp.write_bytes(data)
      logger.info(
          "PIM task: downloaded %s → %s (%d bytes)",
          source_path,
          tmp,
          len(data),
      )
      return tmp, True
  ```

- [ ] **Step 6: Añadir el import de `download_bytes` en el bloque de imports del módulo. Después de `from app.workers.worker import celery_app` añadir:**

  ```python
  from app.services.storage import download_bytes
  ```

- [ ] **Step 7: Actualizar `_run_async()` dentro de `run_pim_import_task` para usar `_resolve_to_local`:**

  Reemplazar el bloque `async def _run_async()` actual por:

  ```python
  async def _run_async() -> dict[str, Any]:
      local_path, should_cleanup = _resolve_to_local(source_path)
      try:
          SessionFactory = get_sessionmaker()
          async with SessionFactory() as session:
              importer = PimImporter(
                  session=session,
                  source_path=local_path,
                  run_id=run_id,
                  actor_id=actor_uuid,
              )
              try:
                  run = await importer.run()
                  return {
                      "run_id": str(run.id),
                      "status": run.status,
                      "total_rows": run.total_rows,
                      "inserted_rows": run.inserted_rows,
                      "updated_rows": run.updated_rows,
                      "skipped_rows": run.skipped_rows,
                      "error_rows": run.error_rows,
                  }
              except Exception as exc:
                  logger.exception(
                      "run_pim_import_task failed run_id=%s: %s", run_id, exc
                  )
                  raise
      finally:
          if should_cleanup:
              local_path.unlink(missing_ok=True)
  ```

- [ ] **Step 8: Ejecutar los tests de la task**

  ```bash
  cd mt-pricing-backend
  uv run pytest tests/workers/test_pim_task_resolve.py -v
  ```

  Expected: todos `PASSED`

- [ ] **Step 9: Commit**

  ```bash
  git add mt-pricing-backend/app/workers/tasks/imports.py \
          mt-pricing-backend/tests/workers/__init__.py \
          mt-pricing-backend/tests/workers/test_pim_task_resolve.py
  git commit -m "fix(imports): resolve PIM source from Supabase Storage when not local"
  ```

---

## Task 3: Corregir el endpoint — pasar `storage_path` en lugar de `_PIM_FIXTURE_PATH`

**Files:**
- Modify: `mt-pricing-backend/app/api/routes/imports.py`
- Modify: `mt-pricing-backend/tests/api/test_imports_pim.py`

### 3.1 — Escribir el test que falla

- [ ] **Step 1: Añadir al final de `tests/api/test_imports_pim.py` este nuevo test:**

  ```python
  @pytest.mark.unit
  @pytest.mark.asyncio
  async def test_upload_endpoint_passes_storage_path_to_celery(
      db_session: AsyncSession,
  ) -> None:
      """POST /imports/pim/upload debe encolar la task con el storage_path real,
      no con _PIM_FIXTURE_PATH.
      """
      from unittest.mock import AsyncMock, MagicMock, patch

      from app.api.deps import get_db_session
      from app.main import app

      async def _override() -> AsyncIterator[AsyncSession]:
          yield db_session

      app.dependency_overrides[get_db_session] = _override

      uid, email = await _seed_ti(db_session)
      headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

      file_bytes = _build_minimal_xlsx(rows=1)

      mock_async_result = MagicMock()
      mock_async_result.id = "celery-task-id-abc123"

      with (
          patch("app.api.routes.imports.upload_bytes") as mock_upload,
          patch(
              "app.api.routes.imports.run_pim_import_task"
          ) as mock_task,
      ):
          mock_upload.return_value = {"storage_path": "pim/...", "bucket": "imports-raw"}
          mock_task.apply_async.return_value = mock_async_result

          transport = ASGITransport(app=app)
          async with AsyncClient(transport=transport, base_url="http://testserver") as c:
              r = await c.post(
                  "/api/v1/imports/pim/upload",
                  files={
                      "file": (
                          "PIM completo.xlsx",
                          file_bytes,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                      )
                  },
                  headers=headers,
              )

      app.dependency_overrides.pop(get_db_session, None)

      assert r.status_code == 202, r.text
      body = r.json()
      assert body["status"] == "queued"

      # La task debe recibir storage_path (pim/...), NO _PIM_FIXTURE_PATH ("/fixtures/...")
      call_args = mock_task.apply_async.call_args
      assert call_args is not None
      task_args = call_args[1]["args"]  # apply_async(args=[run_id, source_path, actor_id])
      source_path_passed = task_args[1]
      assert not source_path_passed.startswith("/fixtures"), (
          f"El task recibió fixture path en lugar de storage_path: {source_path_passed!r}"
      )
      assert "pim/" in source_path_passed, (
          f"El storage_path no tiene el prefijo 'pim/': {source_path_passed!r}"
      )
  ```

- [ ] **Step 2: Ejecutar para confirmar que falla**

  ```bash
  cd mt-pricing-backend
  uv run pytest tests/api/test_imports_pim.py::test_upload_endpoint_passes_storage_path_to_celery -v
  ```

  Expected: `FAILED` — el assert `not source_path_passed.startswith("/fixtures")` fallará
  porque hoy el endpoint pasa `_PIM_FIXTURE_PATH`.

### 3.2 — Aplicar el fix de una línea

- [ ] **Step 3: En `app/api/routes/imports.py`, localizar el bloque en `upload_and_run_pim` (cerca de la línea 444-449):**

  ```python
      # 3) Encolar Celery task. NOTE: el worker descarga el blob de Storage a /tmp.
      # En esta primera versión sólo soportamos disparo desde filesystem (fixture);
      # para upload via Storage habría que agregar un step de descarga. TODO Sprint 2.
      try:
          from app.workers.tasks.imports import run_pim_import_task

          async_result = run_pim_import_task.apply_async(
              args=[str(run_id), _PIM_FIXTURE_PATH, str(user.id)],
          )
  ```

  Reemplazarlo por:

  ```python
      # 3) Encolar Celery task — el worker descarga el blob de Storage a /tmp
      #    vía _resolve_to_local si el path no existe en filesystem.
      try:
          from app.workers.tasks.imports import run_pim_import_task

          async_result = run_pim_import_task.apply_async(
              args=[str(run_id), storage_path, str(user.id)],
          )
  ```

  Cambio: `_PIM_FIXTURE_PATH` → `storage_path`. El comentario viejo de TODO se elimina.

- [ ] **Step 4: Ejecutar el test que antes fallaba**

  ```bash
  cd mt-pricing-backend
  uv run pytest tests/api/test_imports_pim.py::test_upload_endpoint_passes_storage_path_to_celery -v
  ```

  Expected: `PASSED`

- [ ] **Step 5: Ejecutar toda la suite de tests del módulo imports**

  ```bash
  cd mt-pricing-backend
  uv run pytest tests/api/test_imports_pim.py tests/workers/test_pim_task_resolve.py tests/db/test_storage_helper.py -v
  ```

  Expected: todos `PASSED`

- [ ] **Step 6: Commit**

  ```bash
  git add mt-pricing-backend/app/api/routes/imports.py \
          mt-pricing-backend/tests/api/test_imports_pim.py
  git commit -m "fix(imports): pass storage_path to Celery task on PIM upload"
  ```

---

## Task 4: Verificar que el wizard síncrono sigue en verde

**Files:** ninguno (solo ejecutar tests existentes)

- [ ] **Step 1: Correr los tests de integración del wizard**

  ```bash
  cd mt-pricing-backend
  uv run pytest tests/api/test_imports_pim.py tests/integration/test_pim_importer.py -v -m integration
  ```

  Expected: todos `PASSED`. Si alguno falla, investigar antes de continuar.

- [ ] **Step 2: Correr ruff para confirmar que no hay issues de estilo**

  ```bash
  cd mt-pricing-backend
  uv run ruff check app/services/storage.py app/workers/tasks/imports.py app/api/routes/imports.py
  uv run ruff format --check app/services/storage.py app/workers/tasks/imports.py app/api/routes/imports.py
  ```

  Expected: sin warnings. Si hay errores de formato, correr `uv run ruff format <archivo>` y re-commitear.

- [ ] **Step 3: Commit de correcciones de formato si hubo cambios**

  ```bash
  git add -u
  git commit -m "style(imports): ruff format fixes"
  ```

  (Solo si ruff produjo cambios)

---

## Task 5: Verificar cobertura del módulo imports

- [ ] **Step 1: Medir cobertura del módulo**

  ```bash
  cd mt-pricing-backend
  uv run pytest tests/api/test_imports_pim.py \
               tests/workers/test_pim_task_resolve.py \
               tests/db/test_storage_helper.py \
               tests/integration/test_pim_importer.py \
               --cov=app/services/storage \
               --cov=app/workers/tasks/imports \
               --cov=app/api/routes/imports \
               --cov-report=term-missing \
               -q
  ```

  Expected: cobertura ≥ 70% en cada archivo. Si alguno baja de 70%, añadir tests para las ramas descubiertas antes de abrir el PR.

---

## Task 6: Abrir el PR

**Files:** ninguno

- [ ] **Step 1: Push de la rama**

  ```bash
  git push -u origin fix/pim-upload-storage-path
  ```

- [ ] **Step 2: Abrir PR hacia `main` con el cuerpo siguiente (rellenar los huecos marcados)**

  Título: `fix(imports): PIM upload batch pasa storage_path a Celery task`

  ```markdown
  ## Summary

  - Corrección del bloqueo D3 en el pipeline batch de importación del PIM.
  - `POST /imports/pim/upload` subía el xlsx a Supabase Storage correctamente
    pero le pasaba `_PIM_FIXTURE_PATH` (path del filesystem del worker) a la
    Celery task, en lugar del path real del archivo subido.
  - Se añade `download_bytes` a `storage.py` y `_resolve_to_local` en la task:
    si el `source_path` no existe en filesystem, se descarga de Storage a `/tmp`
    antes de pasarlo a `PimImporter`. El tmp se limpia en el bloque `finally`.
  - El flujo `run-from-fixture` (dev) no se ve afectado — el fixture path existe
    en filesystem y `_resolve_to_local` lo usa directamente.

  Bloqueos diagnóstico:
  - D3 → **Corregido**
  - D1, D2, D4, D6, D7, D8, D9 → Descartados (ya implementados correctamente)
  - D5 → Fuera de alcance (decisión de negocio)

  ## Test plan

  - [ ] `uv run pytest tests/api/test_imports_pim.py -v` → verde
  - [ ] `uv run pytest tests/workers/test_pim_task_resolve.py -v` → verde
  - [ ] `uv run pytest tests/db/test_storage_helper.py -v` → verde
  - [ ] `uv run pytest tests/integration/test_pim_importer.py -v -m integration` → verde
  - [ ] Cobertura ≥ 70% en storage.py, tasks/imports.py, routes/imports.py
  - [ ] `POST /imports/pim/upload` → HTTP 202 → run en BD estado `queued`
  - [ ] Task Celery procesa el archivo sin `FileNotFoundError`
  - [ ] `GET /imports/runs/{run_id}` → estado terminal `completed` / `completed_with_errors`
  - [ ] `POST /imports/pim/run-from-fixture` (dev) sigue funcionando
  ```

---

## Self-Review (ejecutado antes de guardar)

### 1. Spec coverage

| Requisito spec | Tarea |
|---|---|
| D3 — worker lee el archivo subido real | Task 2 + Task 3 |
| tests por cada fix | Task 1 (download_bytes), Task 2 (resolve), Task 3 (endpoint) |
| wizard no roto | Task 4 |
| cobertura ≥ 70% | Task 5 |
| PR con CI en verde | Task 6 |
| D1-D9 diagnosticados | Sección diagnóstico |

Todos los requisitos del spec cubiertos. El bloqueo D5 (business decision) documentado como fuera de alcance, igual que el backlog S3+.

### 2. Placeholder scan

Sin TODOs, TBDs ni referencias a "implementar más tarde". Código completo en cada step.

### 3. Type consistency

- `_resolve_to_local(source_path: str) -> tuple[Path, bool]` — usada en `_run_async()` como `local_path, should_cleanup`; naming consistente en Task 2 Steps 5, 7.
- `download_bytes(storage_path, *, bucket, client) -> bytes` — signatura igual en `storage.py` (Task 1 Step 3) y en el mock `patch("app.workers.tasks.imports.download_bytes")` (Task 2 Step 2).
- `storage_path` en `upload_and_run_pim` ya estaba definida en la línea `storage_path = f"pim/..."` — Task 3 Step 3 lo usa correctamente.

---

## Resumen de estado para el PR

```
REMEDIACIÓN IMPORT PIM — RESUMEN
Rama:                  fix/pim-upload-storage-path
PR:                    #___
Bloqueos confirmados:  D3
Bloqueos descartados:  D1, D2, D4, D6, D7, D8, D9
Bloqueos fuera de alc: D5
Lectura de archivo (D3):           corregido
Batch alineado a parser+mapper:    ya estaba OK
Upload E2E del Excel completo:     pendiente validar con Celery real
RBAC + RFC 7807 + auditoría (D6):  ya estaba OK
Frontend Screen 10 (D8):           ya estaba conectado
Tests añadidos:        3 archivos   Cobertura módulo: ≥ 70%
Wizard síncrono:       intacto, tests verdes
NOTAS AL EQUIPO:
  - D5: El batch aplica sin preview; decisión de exigir dry-run previa queda pendiente.
  - Validar con Celery + Storage reales en staging antes de usar en producción.
```
