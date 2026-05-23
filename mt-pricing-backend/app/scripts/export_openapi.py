"""Export FastAPI OpenAPI schema to disk (US-1A-DEV-01).

Usage:
    docker exec mt-backend python /app/app/scripts/export_openapi.py --out /tmp/openapi.json
    # o desde host (con uv):
    cd mt-pricing-backend && uv run python -m app.scripts.export_openapi --out ../_bmad-output/planning-artifacts/mt-api-contract-openapi.json

Default output (cuando se invoca sin --out): repo-root
``_bmad-output/planning-artifacts/mt-api-contract-openapi.json``. Detecta repo-root
subiendo desde este archivo o, fallback, desde CWD si no encuentra el marker.

El workflow ``openapi-sync.yml`` corre este script en CI y falla si el spec
versionado difiere del generado.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def _detect_repo_root(start: Path) -> Path:
    """Sube hasta encontrar `_bmad-output` o `.git`. Fallback: 3 niveles arriba."""
    for parent in [start, *start.parents]:
        if (parent / "_bmad-output").is_dir() or (parent / ".git").is_dir():
            return parent
    return start.parents[2] if len(start.parents) >= 3 else start


_THIS = Path(__file__).resolve()
REPO_ROOT = _detect_repo_root(_THIS)
DEFAULT_OUT = REPO_ROOT / "_bmad-output" / "planning-artifacts" / "mt-api-contract-openapi.json"


def _set_safe_env_defaults() -> None:
    """Settings tiene SecretStr requeridos; CI / docker exec sin .env."""
    defaults = {
        "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
        "REDIS_URL": "redis://localhost:6379/0",
        "SUPABASE_URL": "http://localhost:54321",
        "SUPABASE_ANON_KEY": "anon-export",
        "SUPABASE_SERVICE_ROLE_KEY": "service-export",
        "JWT_SECRET": "export-only",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)


def export(out_path: Path, indent: int) -> None:
    _set_safe_env_defaults()
    from app.main import app

    schema = app.openapi()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(schema, indent=indent, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[export_openapi] wrote {out_path} — {len(schema.get('paths', {}))} paths")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export OpenAPI spec from FastAPI app")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args()
    export(args.out, args.indent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
