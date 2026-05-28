# Prompt Queue Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir una app web local (no deployada) que reemplaza el watcher PowerShell con un dashboard en el browser — muestra la cola `_Cola.md` con estados en vivo y paneles de consola por ejecución de Claude.

**Architecture:** FastAPI sirve API REST + SSE + el HTML estático desde un solo proceso. El frontend es un único `index.html` con Alpine.js + Tailwind vía CDN — sin build step. Cada prompt que se ejecuta corre `claude -p` como subproceso async y streama su stdout línea a línea vía SSE al browser. El dashboard vive en `C:\MT-ME\MT-ME\_Prompts\dashboard\` — es una herramienta del developer, no va al servidor ni al repo.

**Tech Stack:** Python 3.11, FastAPI, uvicorn, asyncio subprocesses, SSE (text/event-stream), Alpine.js CDN, Tailwind CDN, watchdog (file watcher)

---

## File Structure

```
C:\MT-ME\MT-ME\_Prompts\
  dashboard/
    app.py              # FastAPI backend — toda la lógica servidor
    index.html          # SPA — Alpine.js + Tailwind CDN, sin build
    requirements.txt    # fastapi uvicorn watchdog
    run.bat             # Launcher: crea venv, instala deps, abre browser
    tests/
      test_queue.py     # Tests unitarios para parse_cola, update_cola_row, get_nombre
```

---

## Task 1: Scaffold — estructura base y servidor mínimo

**Files:**
- Create: `C:\MT-ME\MT-ME\_Prompts\dashboard\requirements.txt`
- Create: `C:\MT-ME\MT-ME\_Prompts\dashboard\app.py`
- Create: `C:\MT-ME\MT-ME\_Prompts\dashboard\index.html`

- [ ] **Step 1: Crear requirements.txt**

```
C:\MT-ME\MT-ME\_Prompts\dashboard\requirements.txt
```
```
fastapi==0.115.5
uvicorn[standard]==0.32.1
watchdog==6.0.0
```

- [ ] **Step 2: Crear app.py mínimo — solo sirve index.html**

```python
# C:\MT-ME\MT-ME\_Prompts\dashboard\app.py
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

HERE = Path(__file__).parent
BASE = Path("C:/MT-ME/MT-ME/_Prompts")
PENDIENTES  = BASE / "Pendientes"
EJECUTADOS  = BASE / "Ejecutados"
LOGS_DIR    = BASE / "_Logs"
COLA_FILE   = BASE / "_Cola.md"
REPO_DIR    = Path("C:/BR-Github/br-mt/br-mt-ecommerce")

app = FastAPI(title="Prompt Queue Dashboard")


@app.get("/")
async def root() -> HTMLResponse:
    return HTMLResponse((HERE / "index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8765, reload=True)
```

- [ ] **Step 3: Crear index.html mínimo — placeholder**

```html
<!-- C:\MT-ME\MT-ME\_Prompts\dashboard\index.html -->
<!doctype html>
<html lang="es" class="dark">
<head>
  <meta charset="UTF-8" />
  <title>Prompt Queue Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
</head>
<body class="bg-gray-950 text-gray-100 min-h-screen p-6">
  <h1 class="text-2xl font-bold text-cyan-400">Prompt Queue Dashboard</h1>
  <p class="text-gray-400 mt-2">Cargando...</p>
</body>
</html>
```

- [ ] **Step 4: Instalar dependencias y verificar que el servidor arranca**

```powershell
cd "C:\MT-ME\MT-ME\_Prompts\dashboard"
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python app.py
```

Abrir `http://localhost:8765` — debe mostrar "Prompt Queue Dashboard / Cargando..."

- [ ] **Step 5: Commit inicial**

```powershell
# Este proyecto vive fuera del repo — no hay git commit aquí.
# Guardar el estado es suficiente con los archivos en disco.
```

---

## Task 2: Capa de datos — parse y update de `_Cola.md`

**Files:**
- Modify: `C:\MT-ME\MT-ME\_Prompts\dashboard\app.py`
- Create: `C:\MT-ME\MT-ME\_Prompts\dashboard\tests\test_queue.py`

- [ ] **Step 1: Escribir tests para parse_cola, update_cola_row, get_nombre**

```python
# C:\MT-ME\MT-ME\_Prompts\dashboard\tests\test_queue.py
import sys
from pathlib import Path
import tempfile, textwrap

sys.path.insert(0, str(Path(__file__).parent.parent))
from app import parse_cola, update_cola_row, get_nombre  # noqa: E402


SAMPLE_COLA = textwrap.dedent("""\
    # _Cola.md
    | Orden | Prompt | Qué hace | Estado | Depende de | Resultado / nota | Log |
    |---|---|---|---|---|---|---|
    | 1 | Main_Verde | Sanear repo | Ejecutado | — | F0 cerrada | |
    | 8 | Docs_Estrategia_y_Frontera | Migrar docs | Pendiente | repo sano | Proximo | |
    | — | Docs_Estrategia_y_Frontera *(obsoleta)* | Vieja version | Superado | — | Reemplazada | |
""")


def make_cola(tmp_path: Path) -> Path:
    f = tmp_path / "_Cola.md"
    f.write_text(SAMPLE_COLA, encoding="utf-8")
    return f


def test_parse_cola_returns_rows(tmp_path):
    cola = make_cola(tmp_path)
    rows = parse_cola(cola)
    assert len(rows) == 3


def test_parse_cola_fields(tmp_path):
    cola = make_cola(tmp_path)
    row = parse_cola(cola)[0]
    assert row["orden"] == "1"
    assert row["nombre"] == "Main_Verde"
    assert row["estado"] == "Ejecutado"
    assert row["resultado"] == "F0 cerrada"


def test_parse_cola_obsoleta_row(tmp_path):
    cola = make_cola(tmp_path)
    rows = parse_cola(cola)
    obsoleta = next(r for r in rows if "obsoleta" in r["nombre"])
    assert obsoleta["estado"] == "Superado"


def test_update_cola_row_estado(tmp_path):
    cola = make_cola(tmp_path)
    update_cola_row(cola, "Docs_Estrategia_y_Frontera", "Ejecutado", "Completado", "")
    rows = parse_cola(cola)
    target = next(r for r in rows if r["nombre"] == "Docs_Estrategia_y_Frontera")
    assert target["estado"] == "Ejecutado"
    assert target["resultado"] == "Completado"


def test_update_cola_row_no_match_is_noop(tmp_path):
    cola = make_cola(tmp_path)
    original = cola.read_text(encoding="utf-8")
    update_cola_row(cola, "Nombre_Inexistente", "X", "Y", "")
    assert cola.read_text(encoding="utf-8") == original


def test_update_cola_row_skips_obsoleta(tmp_path):
    """La fila obsoleta tiene nombre distinto — no debe ser modificada."""
    cola = make_cola(tmp_path)
    update_cola_row(cola, "Docs_Estrategia_y_Frontera", "Ejecutado", "OK", "")
    rows = parse_cola(cola)
    obsoleta = next(r for r in rows if "obsoleta" in r["nombre"])
    assert obsoleta["estado"] == "Superado"  # sin cambios


def test_get_nombre_es():
    assert get_nombre("Prompt_ClaudeCode_F1_CAT_Piloto_ES.md") == "F1_CAT_Piloto"


def test_get_nombre_en():
    assert get_nombre("Prompt_ClaudeCode_Docs_Estrategia_y_Frontera_EN.md") == "Docs_Estrategia_y_Frontera"
```

- [ ] **Step 2: Ejecutar tests — deben FALLAR (funciones no existen aún)**

```powershell
cd "C:\MT-ME\MT-ME\_Prompts\dashboard"
.venv\Scripts\pip install pytest -q
.venv\Scripts\pytest tests/test_queue.py -v
```

Esperado: `ImportError` o `AttributeError` — las funciones no existen todavía.

- [ ] **Step 3: Implementar parse_cola, update_cola_row, get_nombre en app.py**

Añadir después de las constantes de configuración en `app.py`:

```python
import re
import shutil
import uuid
import json
import asyncio
from datetime import datetime
from typing import Optional


def get_nombre(filename: str) -> str:
    """Prompt_ClaudeCode_F1_CAT_Piloto_ES.md -> F1_CAT_Piloto"""
    name = Path(filename).stem
    name = re.sub(r"^Prompt_ClaudeCode_", "", name)
    name = re.sub(r"_(ES|EN)$", "", name)
    return name


def parse_cola(cola_path: Path = COLA_FILE) -> list[dict]:
    """Parsea la tabla markdown de _Cola.md y retorna lista de dicts."""
    if not cola_path.exists():
        return []
    rows = []
    for line in cola_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.split("|")]
        # cols[0]="" cols[1]=Orden cols[2]=Prompt ... cols[8]=""
        if len(cols) < 8:
            continue
        if re.match(r"^-+$", cols[1]):  # fila separadora |---|---|...|
            continue
        if "Orden" in cols[1]:          # fila header
            continue
        rows.append({
            "orden":      cols[1],
            "nombre":     cols[2],
            "que_hace":   cols[3],
            "estado":     cols[4],
            "depende_de": cols[5],
            "resultado":  cols[6],
            "log":        cols[7] if len(cols) > 7 else "",
        })
    return rows


def update_cola_row(
    cola_path: Path,
    nombre: str,
    nuevo_estado: str,
    resultado: str,
    log_rel: str,
) -> bool:
    """Actualiza Estado y Resultado/nota de la primera fila cuyo Prompt == nombre."""
    if not cola_path.exists():
        return False
    lines = cola_path.read_text(encoding="utf-8").splitlines()
    updated = False
    for i, line in enumerate(lines):
        if not line.startswith("|"):
            continue
        cols = line.split("|")
        if len(cols) < 7:
            continue
        if cols[2].strip() != nombre:
            continue
        cols[4] = f" {nuevo_estado} "
        cols[6] = f" {resultado} "
        log_cell = f" [log]({log_rel}) " if log_rel else " "
        if len(cols) >= 9:
            cols[7] = log_cell
        else:
            cols = cols[:7] + [log_cell, ""]
        lines[i] = "|".join(cols)
        updated = True
        break
    if updated:
        cola_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return updated
```

- [ ] **Step 4: Ejecutar tests — deben pasar**

```powershell
.venv\Scripts\pytest tests/test_queue.py -v
```

Esperado: `8 passed`

---

## Task 3: Motor de ejecución — async subprocess + validación

**Files:**
- Modify: `C:\MT-ME\MT-ME\_Prompts\dashboard\app.py`

- [ ] **Step 1: Añadir constantes de prompts y state de ejecuciones**

Añadir en `app.py` después de las funciones de cola:

```python
# ── Prompts de instrucciones ──────────────────────────────────────────────────

INSTRUCCIONES = """\
<execution-instructions>
ANTES DE EMPEZAR - obligatorio:

1. Skills: Usa la herramienta Skill para invocar cualquier skill relevante.
   Si hay un 1% de probabilidad de que una skill aplique, invocala.

2. Agentes paralelos: Si la tarea tiene subtareas independientes, usa Agent
   para despacharlas en un solo mensaje con multiples llamadas concurrentes.

3. Verificacion: Antes de reportar completo, verifica que los cambios funcionan.
</execution-instructions>

---

"""

VALIDATION_PREFIX = """\
Eres un validador de tareas. Determina si el trabajo descrito en el
PROMPT A VALIDAR ya fue completamente implementado en el repositorio actual.

INSTRUCCIONES:
- Revisa codigo, archivos existentes, git log y git status del repo.
- Busca evidencia concreta: archivos creados, funciones implementadas,
  PRs fusionados, documentacion generada, migraciones aplicadas, etc.
- NO implementes nada. Solo observa y evalua.
- Si la tarea esta PARCIALMENTE hecha, responde PENDIENTE.
- Ante cualquier duda, responde PENDIENTE.

Responde UNICAMENTE con una de estas dos palabras (sin puntuacion):
IMPLEMENTADO
PENDIENTE

--- PROMPT A VALIDAR ---

"""

# ── Estado global de ejecuciones ─────────────────────────────────────────────

# {execution_id: {"queue": asyncio.Queue, "status": str, "nombre": str, ...}}
executions: dict[str, dict] = {}

# Subscribers SSE para eventos de filesystem
file_event_subs: list[asyncio.Queue] = []
```

- [ ] **Step 2: Implementar run_execution — el motor async completo**

Añadir en `app.py`:

```python
async def run_execution(
    execution_id: str,
    filepath: Path,
    skip_permissions: bool,
) -> None:
    ex = executions[execution_id]
    q: asyncio.Queue = ex["queue"]
    nombre = ex["nombre"]
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    log_file = LOGS_DIR / f"{filepath.stem}_{timestamp}.md"

    async def send(line: str, kind: str = "output") -> None:
        await q.put({"type": kind, "line": line})

    raw_content = filepath.read_text(encoding="utf-8")

    # ── 1. Validación ────────────────────────────────────────────────────────
    await send("=== Validando si ya fue implementado... ===", "status")
    ex["status"] = "validating"
    update_cola_row(COLA_FILE, nombre, "Validando", f"Iniciado {fecha}", "")

    val_args = ["claude", "-p", VALIDATION_PREFIX + raw_content, "--output-format", "text"]
    if skip_permissions:
        val_args.append("--dangerously-skip-permissions")

    val_proc = await asyncio.create_subprocess_exec(
        *val_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(REPO_DIR),
    )
    val_lines: list[str] = []
    async for raw in val_proc.stdout:  # type: ignore[union-attr]
        line = raw.decode("utf-8", errors="replace").rstrip()
        val_lines.append(line)
        await send(line)
    await val_proc.wait()

    val_text = re.sub(r"[^A-Z]", "", " ".join(val_lines).upper())
    if val_text.startswith("IMPLEMENTADO"):
        await send("=== Ya implementado — archivando sin ejecutar ===", "status")
        shutil.move(str(filepath), str(EJECUTADOS / filepath.name))
        update_cola_row(COLA_FILE, nombre, "Ya implementado", f"Validacion: ya hecho ({fecha})", "")
        ex["status"] = "skipped"
        await q.put({"type": "done", "exit_code": 0, "skipped": True})
        return

    await send("=== Pendiente — procediendo con ejecucion ===", "status")

    # ── 2. Ejecución ─────────────────────────────────────────────────────────
    ex["status"] = "running"
    update_cola_row(COLA_FILE, nombre, "En curso", f"Iniciado {fecha}", "")

    exec_args = [
        "claude", "-p", INSTRUCCIONES + raw_content,
        "--output-format", "text",
    ]
    if skip_permissions:
        exec_args.append("--dangerously-skip-permissions")

    await send("=== Ejecutando claude -p ===", "status")
    proc = await asyncio.create_subprocess_exec(
        *exec_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(REPO_DIR),
    )
    output_lines: list[str] = []
    async for raw in proc.stdout:  # type: ignore[union-attr]
        line = raw.decode("utf-8", errors="replace").rstrip()
        output_lines.append(line)
        await send(line)
    await proc.wait()
    exit_code: int = proc.returncode or 0

    # ── 3. Guardar log ───────────────────────────────────────────────────────
    LOGS_DIR.mkdir(exist_ok=True)
    status_label = "Completado" if exit_code == 0 else f"Fallido (exit {exit_code})"
    log_content = (
        f"# Log: {filepath.stem}\n"
        f"- **Ejecutado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"- **Estado:** {status_label}\n\n"
        "---\n\n## Prompt\n\n" + raw_content +
        "\n\n---\n\n## Output\n\n" + "\n".join(output_lines)
    )
    log_file.write_text(log_content, encoding="utf-8")
    log_rel = f"_Logs/{log_file.name}"

    # ── 4. Finalizar ─────────────────────────────────────────────────────────
    if exit_code == 0:
        short = [l.strip() for l in output_lines
                 if l.strip() and not l.startswith("#") and len(l.strip()) <= 60]
        resultado = short[-1] if short else f"Ejecutado {fecha} - ver log"
        shutil.move(str(filepath), str(EJECUTADOS / filepath.name))
        update_cola_row(COLA_FILE, nombre, "Ejecutado", resultado, log_rel)
        ex["status"] = "done"
        await send("=== Completado (exit 0) ===", "status")
    else:
        resultado = f"Fallido exit {exit_code} - ver log {timestamp}"
        update_cola_row(COLA_FILE, nombre, "Fallido", resultado, log_rel)
        ex["status"] = "failed"
        await send(f"=== Fallido (exit {exit_code}) ===", "status")

    ex["exit_code"] = exit_code
    await q.put({"type": "done", "exit_code": exit_code})
```

- [ ] **Step 3: Verificación manual** — ejecutar la app y confirmar que importa sin error

```powershell
.venv\Scripts\python -c "from app import run_execution, executions; print('OK')"
```

Esperado: `OK`

---

## Task 4: API endpoints REST + SSE

**Files:**
- Modify: `C:\MT-ME\MT-ME\_Prompts\dashboard\app.py`

- [ ] **Step 1: Añadir modelos Pydantic y endpoints en app.py**

Añadir después del motor de ejecución:

```python
from pydantic import BaseModel


# ── Startup: crear dirs + lanzar file watcher ─────────────────────────────────

@app.on_event("startup")
async def startup() -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    asyncio.create_task(_file_watcher())


async def _file_watcher() -> None:
    """Polling cada 2s de Pendientes\ — notifica a suscriptores SSE."""
    known: set[str] = {f.name for f in PENDIENTES.glob("*.md")}
    while True:
        await asyncio.sleep(2)
        current: set[str] = {f.name for f in PENDIENTES.glob("*.md")}
        for fname in current - known:
            await _broadcast({"type": "new_file", "filename": fname})
        known = current
        await _broadcast({"type": "queue_refresh"})


async def _broadcast(event: dict) -> None:
    for q in file_event_subs:
        await q.put(event)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/queue")
async def api_queue() -> dict:
    rows = parse_cola()
    pendientes = sorted(f.name for f in PENDIENTES.glob("*.md"))
    return {"rows": rows, "pendientes": pendientes}


@app.get("/api/logs/{log_path:path}")
async def api_log(log_path: str) -> dict:
    path = BASE / log_path
    if not path.exists():
        from fastapi import HTTPException
        raise HTTPException(404, "Log no encontrado")
    return {"content": path.read_text(encoding="utf-8")}


class ExecuteRequest(BaseModel):
    filename: str
    skip_permissions: bool = False


@app.post("/api/execute")
async def api_execute(req: ExecuteRequest) -> dict:
    from fastapi import HTTPException
    filepath = PENDIENTES / req.filename
    if not filepath.exists():
        raise HTTPException(404, f"Archivo no encontrado: {req.filename}")
    eid = str(uuid.uuid4())
    nombre = get_nombre(req.filename)
    executions[eid] = {
        "queue": asyncio.Queue(),
        "status": "starting",
        "filename": req.filename,
        "nombre": nombre,
        "exit_code": None,
    }
    asyncio.create_task(run_execution(eid, filepath, req.skip_permissions))
    return {"execution_id": eid, "nombre": nombre}


@app.get("/api/stream/{eid}")
async def api_stream(eid: str):
    from fastapi import HTTPException
    from fastapi.responses import StreamingResponse
    if eid not in executions:
        raise HTTPException(404, "Ejecucion no encontrada")

    async def generator():
        q: asyncio.Queue = executions[eid]["queue"]
        while True:
            msg = await q.get()
            yield f"data: {json.dumps(msg)}\n\n"
            if msg.get("type") == "done":
                break

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/events")
async def api_events():
    from fastapi.responses import StreamingResponse
    q: asyncio.Queue = asyncio.Queue()
    file_event_subs.append(q)

    async def generator():
        try:
            while True:
                event = await q.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            try:
                file_event_subs.remove(q)
            except ValueError:
                pass

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/executions")
async def api_executions() -> dict:
    return {
        eid: {k: v for k, v in ex.items() if k != "queue"}
        for eid, ex in executions.items()
    }
```

- [ ] **Step 2: Verificar endpoints con el servidor corriendo**

```powershell
.venv\Scripts\python app.py
# En otra terminal:
curl http://localhost:8765/api/queue
```

Esperado: JSON con `{"rows": [...], "pendientes": [...]}`

---

## Task 5: Frontend — tabla de cola

**Files:**
- Modify: `C:\MT-ME\MT-ME\_Prompts\dashboard\index.html`

- [ ] **Step 1: Reemplazar index.html con la SPA completa — parte cola**

```html
<!doctype html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Prompt Queue Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = { darkMode: 'class' }
  </script>
  <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
  <style>
    .console-panel { font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace; }
    .ansi-status   { color: #22d3ee; }   /* cyan-400  */
    .ansi-output   { color: #d1d5db; }   /* gray-300  */
    [x-cloak]      { display: none !important; }
  </style>
</head>
<body class="dark bg-gray-950 text-gray-100 h-screen flex flex-col overflow-hidden">

<!-- ── Header ─────────────────────────────────────────────────────────── -->
<header class="flex-shrink-0 bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center gap-4">
  <span class="text-cyan-400 font-bold text-lg">Prompt Queue Dashboard</span>
  <span class="text-gray-600 text-sm flex-1">C:\MT-ME\MT-ME\_Prompts</span>
  <label class="flex items-center gap-2 text-sm text-yellow-400 cursor-pointer">
    <input type="checkbox" x-model="skipPermissions" class="accent-yellow-400" />
    Skip permissions
  </label>
  <button @click="refreshQueue()"
    class="text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 px-3 py-1.5 rounded border border-gray-700">
    ↺ Actualizar
  </button>
</header>

<!-- ── Main ───────────────────────────────────────────────────────────── -->
<main class="flex-1 flex flex-col overflow-hidden" x-data="dashboard()" x-init="init()" x-cloak>

  <!-- Cola -->
  <section class="flex-shrink-0 border-b border-gray-800" style="max-height:45vh;overflow-y:auto">
    <div class="px-6 py-2 bg-gray-900 sticky top-0 z-10 flex items-center gap-3">
      <span class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Cola</span>
      <span class="text-xs text-gray-600" x-text="`${queue.length} filas · ${pendientes.length} pendientes`"></span>
    </div>
    <table class="w-full text-sm">
      <thead class="bg-gray-900 text-gray-500 text-xs uppercase tracking-wider sticky top-8 z-10">
        <tr>
          <th class="px-4 py-2 text-left w-10">#</th>
          <th class="px-4 py-2 text-left">Prompt</th>
          <th class="px-4 py-2 text-left w-32">Estado</th>
          <th class="px-4 py-2 text-left">Resultado</th>
          <th class="px-4 py-2 text-left w-12">Log</th>
          <th class="px-4 py-2 text-left w-28">Acción</th>
        </tr>
      </thead>
      <tbody>
        <template x-for="row in queue" :key="row.nombre + row.orden">
          <tr class="border-t border-gray-800 hover:bg-gray-900/50"
              :class="row.estado === 'Superado' ? 'opacity-40' : ''">
            <td class="px-4 py-2 text-gray-500 text-xs" x-text="row.orden"></td>
            <td class="px-4 py-2">
              <span class="font-mono text-xs text-gray-200" x-text="row.nombre"></span>
              <span x-show="row.depende_de && row.depende_de !== '—'"
                class="ml-2 text-xs text-gray-600">
                deps: <span x-text="row.depende_de"></span>
              </span>
            </td>
            <td class="px-4 py-2">
              <span class="px-2 py-0.5 rounded text-xs font-medium" :class="statusClass(row.estado)"
                    x-text="row.estado"></span>
            </td>
            <td class="px-4 py-2 text-xs text-gray-400" x-text="row.resultado"></td>
            <td class="px-4 py-2">
              <a x-show="row.log && row.log.includes('log]')"
                 :href="`/api/logs/${extractLogPath(row.log)}`"
                 target="_blank"
                 class="text-xs text-cyan-600 hover:text-cyan-400">📄</a>
            </td>
            <td class="px-4 py-2">
              <button x-show="isPendiente(row.nombre)"
                      @click="executePrompt(row)"
                      :disabled="isRunning(row.nombre)"
                      class="text-xs bg-cyan-900 hover:bg-cyan-800 disabled:opacity-40
                             disabled:cursor-not-allowed text-cyan-200 px-3 py-1 rounded border
                             border-cyan-700 transition-colors">
                ▶ Ejecutar
              </button>
              <span x-show="isRunning(row.nombre)"
                    class="text-xs text-blue-400 animate-pulse">En curso...</span>
            </td>
          </tr>
        </template>
        <tr x-show="queue.length === 0">
          <td colspan="6" class="px-4 py-8 text-center text-gray-600 text-sm">Sin datos — ¿está corriendo el servidor?</td>
        </tr>
      </tbody>
    </table>
  </section>

  <!-- Consolas -->
  <section class="flex-1 flex flex-col overflow-hidden">
    <div class="flex-shrink-0 bg-gray-900 border-b border-gray-800 flex items-center gap-1 px-4 py-1 overflow-x-auto">
      <span class="text-xs text-gray-500 mr-2 whitespace-nowrap">Consolas:</span>
      <template x-for="ex in execList" :key="ex.id">
        <button @click="activeTab = ex.id"
                :class="activeTab === ex.id
                  ? 'bg-gray-800 text-gray-100 border-cyan-600'
                  : 'bg-transparent text-gray-500 hover:text-gray-300 border-transparent'"
                class="flex items-center gap-1.5 px-3 py-1 rounded text-xs border transition-colors whitespace-nowrap">
          <span :class="tabDot(ex.status)" class="w-2 h-2 rounded-full flex-shrink-0"></span>
          <span x-text="ex.nombre"></span>
        </button>
      </template>
      <span x-show="execList.length === 0" class="text-xs text-gray-700 italic">
        Ninguna ejecución aún — presiona Ejecutar en una fila
      </span>
    </div>

    <div class="flex-1 overflow-hidden relative">
      <template x-for="ex in execList" :key="ex.id">
        <div x-show="activeTab === ex.id"
             class="absolute inset-0 overflow-y-auto p-4 console-panel text-xs leading-5 bg-gray-950"
             :id="`console-${ex.id}`">
          <template x-for="(msg, idx) in ex.lines" :key="idx">
            <div :class="msg.type === 'status' ? 'ansi-status font-semibold' : 'ansi-output'"
                 x-text="msg.line"></div>
          </template>
          <div x-show="ex.status === 'done'" class="mt-2 text-green-400 font-bold">✓ Completado</div>
          <div x-show="ex.status === 'failed'" class="mt-2 text-red-400 font-bold">✗ Fallido</div>
          <div x-show="ex.status === 'skipped'" class="mt-2 text-purple-400 font-bold">↷ Ya implementado — archivado</div>
          <div x-show="['validating','running','starting'].includes(ex.status)"
               class="mt-2 text-blue-400 animate-pulse">● Ejecutando...</div>
        </div>
      </template>
    </div>
  </section>

</main>

<script>
function dashboard() {
  return {
    queue: [],
    pendientes: [],
    execList: [],       // [{id, nombre, status, lines[]}]
    activeTab: null,
    skipPermissions: false,

    async init() {
      await this.refreshQueue();
      this.listenFileEvents();
      // Poll la cola cada 10s como fallback
      setInterval(() => this.refreshQueue(), 10_000);
    },

    async refreshQueue() {
      try {
        const res = await fetch('/api/queue');
        const data = await res.json();
        this.queue = data.rows || [];
        this.pendientes = data.pendientes || [];
      } catch (e) {
        console.error('Error cargando cola:', e);
      }
    },

    listenFileEvents() {
      const es = new EventSource('/api/events');
      es.onmessage = async (e) => {
        const event = JSON.parse(e.data);
        if (event.type === 'queue_refresh' || event.type === 'new_file') {
          await this.refreshQueue();
        }
      };
      es.onerror = () => setTimeout(() => this.listenFileEvents(), 5000);
    },

    async executePrompt(row) {
      const filename = this.pendientes.find(f => f.includes(row.nombre));
      if (!filename) return;

      const res = await fetch('/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename, skip_permissions: this.skipPermissions }),
      });
      const data = await res.json();

      const ex = {
        id: data.execution_id,
        nombre: data.nombre,
        filename,
        status: 'starting',
        lines: [],
      };
      this.execList.unshift(ex);
      this.activeTab = ex.id;
      this.streamExecution(ex);
      await this.refreshQueue();
    },

    streamExecution(ex) {
      const es = new EventSource(`/api/stream/${ex.id}`);
      es.onmessage = async (e) => {
        const msg = JSON.parse(e.data);
        if (msg.type === 'output' || msg.type === 'status') {
          ex.lines.push(msg);
          this.$nextTick(() => this.scrollConsole(ex.id));
        }
        if (msg.type === 'done') {
          ex.status = msg.skipped ? 'skipped' : (msg.exit_code === 0 ? 'done' : 'failed');
          es.close();
          await this.refreshQueue();
        }
      };
      es.onerror = () => { ex.status = 'failed'; es.close(); };
    },

    scrollConsole(id) {
      const el = document.getElementById(`console-${id}`);
      if (el) el.scrollTop = el.scrollHeight;
    },

    isPendiente(nombre) {
      return this.pendientes.some(f => f.includes(nombre));
    },

    isRunning(nombre) {
      return this.execList.some(ex =>
        ex.nombre === nombre && ['starting','validating','running'].includes(ex.status)
      );
    },

    statusClass(estado) {
      const map = {
        'Ejecutado':       'bg-green-900/60 text-green-300 border border-green-700',
        'Pendiente':       'bg-yellow-900/60 text-yellow-300 border border-yellow-700',
        'En curso':        'bg-blue-900/60 text-blue-300 border border-blue-700 animate-pulse',
        'Validando':       'bg-blue-900/60 text-blue-300 border border-blue-700 animate-pulse',
        'Fallido':         'bg-red-900/60 text-red-300 border border-red-700',
        'Ya implementado': 'bg-purple-900/60 text-purple-300 border border-purple-700',
        'Por confirmar':   'bg-gray-700/60 text-gray-300 border border-gray-600',
        'Superado':        'bg-gray-800/40 text-gray-500 border border-gray-700',
      };
      return map[estado] || 'bg-gray-700/60 text-gray-400 border border-gray-600';
    },

    tabDot(status) {
      const map = {
        starting:   'bg-gray-500',
        validating: 'bg-blue-400 animate-pulse',
        running:    'bg-cyan-400 animate-pulse',
        done:       'bg-green-400',
        failed:     'bg-red-400',
        skipped:    'bg-purple-400',
      };
      return map[status] || 'bg-gray-500';
    },

    extractLogPath(logCell) {
      // "[log](_Logs/Prompt_...md)" -> "_Logs/Prompt_...md"
      const match = logCell.match(/\[log\]\(([^)]+)\)/);
      return match ? match[1] : '';
    },
  };
}
</script>

</body>
</html>
```

- [ ] **Step 2: Reiniciar el servidor y probar en el browser**

```powershell
.venv\Scripts\python app.py
```

Abrir `http://localhost:8765`:
- La tabla debe mostrar las filas de `_Cola.md`
- Los estados deben tener colores correctos
- El botón "Ejecutar" debe aparecer solo en filas con archivo en `Pendientes\`

---

## Task 6: Launcher `run.bat`

**Files:**
- Create: `C:\MT-ME\MT-ME\_Prompts\dashboard\run.bat`

- [ ] **Step 1: Crear run.bat**

```batch
@echo off
cd /d "%~dp0"
echo Prompt Queue Dashboard
echo ----------------------

if not exist ".venv" (
    echo Creando entorno virtual...
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt -q
)

echo Abriendo http://localhost:8765 ...
start "" "http://localhost:8765"

echo Iniciando servidor (Ctrl+C para detener)
.venv\Scripts\uvicorn app:app --host 127.0.0.1 --port 8765 --reload
```

- [ ] **Step 2: Probar doble-click en run.bat**

Debe abrir una ventana de consola + el browser en `http://localhost:8765`.

---

## Task 7: Prueba de integración completa

- [ ] **Step 1: Copiar un `.md` de prueba a `Pendientes\`** y verificar que:
  1. La tabla de cola se actualiza automáticamente (< 10 s)
  2. Al hacer click en "Ejecutar" aparece una nueva tab de consola
  3. El estado de la fila cambia a "Validando" → "En curso"
  4. El output de Claude aparece línea a línea en la consola
  5. Al terminar, el estado cambia a "Ejecutado" o "Fallido"
  6. El archivo se mueve de `Pendientes\` a `Ejecutados\`
  7. `_Cola.md` tiene la fila actualizada con estado y resultado

- [ ] **Step 2: Verificar caso "Ya implementado"**

Crear un prompt que pida algo que ya existe en el repo. Debe:
- Mostrar "Validando..." en consola
- Mostrar "Ya implementado — archivado"
- Estado en cola: `Ya implementado`
- Archivo movido a `Ejecutados\` sin log de ejecución

- [ ] **Step 3: Verificar múltiples ejecuciones concurrentes**

Hacer click en "Ejecutar" en dos prompts distintos rápidamente:
- Deben aparecer dos tabs
- Ambos deben stremar simultáneamente
- Cada uno debe actualizar su propia fila en la cola

---

## Notas de implementación

### Windows + asyncio subprocess

Si `asyncio.create_subprocess_exec` falla con `NotImplementedError` en Windows, añadir al inicio de `app.py`:

```python
import sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
```

### `claude` no encontrado en PATH

Si el subprocess falla con `FileNotFoundError`, buscar la ruta exacta:

```powershell
(Get-Command claude).Source
```

Y reemplazar `"claude"` por la ruta completa en `val_args` y `exec_args`.

### Actualización del `_Cola.md` desde el browser

Si quieres editar la cola desde el frontend (cambiar estado manual), añadir:

```python
class UpdateRowRequest(BaseModel):
    nombre: str
    estado: str
    resultado: str

@app.post("/api/queue/update")
async def api_update_row(req: UpdateRowRequest) -> dict:
    ok = update_cola_row(COLA_FILE, req.nombre, req.estado, req.resultado, "")
    return {"updated": ok}
```
