"""export_dataset.py — exporta pares etiquetados de match_candidates a JSONL.

Uso:
    python -m scripts.poc.export_dataset \\
        --output datasets/labeled_pairs_YYYY-MM-DD.jsonl \\
        --min-pairs 1000

    python -m scripts.poc.export_dataset \\
        --validate datasets/labeled_pairs_2026-05-12.jsonl

Conecta a DB via DATABASE_URL (variable de entorno o .env en directorio raíz).

Exit codes:
    0 — éxito (total_pairs >= min_pairs, o validación OK)
    1 — insuficiente o validación fallida
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# .env loader — intenta cargar .env del directorio raíz del proyecto si existe
# ---------------------------------------------------------------------------
def _load_dotenv() -> None:
    """Carga .env si python-dotenv está disponible. Silencia import error."""
    try:
        from dotenv import load_dotenv  # type: ignore[import-untyped]

        root = Path(__file__).parent.parent.parent
        env_file = root / ".env"
        if env_file.exists():
            load_dotenv(env_file)
        env_local = root / ".env.local"
        if env_local.exists():
            load_dotenv(env_local, override=True)
    except ImportError:
        pass


_load_dotenv()

# ---------------------------------------------------------------------------
# DB query
# ---------------------------------------------------------------------------
_LABEL_MAP: dict[str, int] = {"accept": 1, "reject": 0}


async def _fetch_pairs(database_url: str) -> list[dict]:
    """Consulta match_candidates WHERE label IN ('accept','reject') AND status='validated'."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(database_url, echo=False)
    rows: list[dict] = []
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT
                        product_sku,
                        id::text   AS candidate_id,
                        title,
                        specs_jsonb,
                        label
                    FROM match_candidates
                    WHERE label IN ('accept', 'reject')
                      AND status = 'validated'
                    ORDER BY id
                    """
                )
            )
            for r in result.mappings():
                rows.append(
                    {
                        "sku_mt": r["product_sku"],
                        "candidate_id": r["candidate_id"],
                        "title": r["title"],
                        "specs_jsonb": r["specs_jsonb"]
                        if isinstance(r["specs_jsonb"], dict)
                        else json.loads(r["specs_jsonb"] or "{}"),
                        "label": _LABEL_MAP[r["label"]],
                    }
                )
    finally:
        await engine.dispose()
    return rows


# ---------------------------------------------------------------------------
# Write JSONL
# ---------------------------------------------------------------------------
def _write_jsonl(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _summary(rows: list[dict]) -> dict:
    accept = sum(1 for r in rows if r["label"] == 1)
    reject = sum(1 for r in rows if r["label"] == 0)
    skus = len({r["sku_mt"] for r in rows})
    return {
        "total_pairs": len(rows),
        "accept": accept,
        "reject": reject,
        "skus_unique": skus,
    }


# ---------------------------------------------------------------------------
# Validation logic
# ---------------------------------------------------------------------------
_REQUIRED_FIELDS = {"sku_mt", "candidate_id", "title", "specs_jsonb", "label"}


def _validate_file(path: Path) -> bool:
    """
    Valida el archivo JSONL en ``path``.

    Reglas:
    - Campos obligatorios presentes en cada línea.
    - ``label`` in {0, 1}.
    - Sin duplicados ``(sku_mt, candidate_id)``.
    - Ratio positivos/negativos ∈ [0.3, 0.7].

    Anomalías → WARNING.
    Campos faltantes → error + return False.
    """
    errors: list[str] = []
    warnings_list: list[str] = []

    seen: set[tuple[str, str]] = set()
    labels: list[int] = []
    line_number = 0

    with path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            line_number += 1
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                errors.append(f"Línea {line_number}: JSON inválido — {exc}")
                continue

            # Campos obligatorios
            missing = _REQUIRED_FIELDS - set(obj.keys())
            if missing:
                errors.append(f"Línea {line_number}: campos faltantes — {sorted(missing)}")
                continue

            # Label ∈ {0, 1}
            if obj["label"] not in (0, 1):
                errors.append(f"Línea {line_number}: label={obj['label']!r} no es 0 ni 1")

            # Duplicados
            key = (str(obj["sku_mt"]), str(obj["candidate_id"]))
            if key in seen:
                warnings_list.append(
                    f"Línea {line_number}: duplicado (sku_mt={obj['sku_mt']}, "
                    f"candidate_id={obj['candidate_id']})"
                )
            else:
                seen.add(key)

            labels.append(obj["label"])

    # Ratio positivos/negativos
    if labels:
        positive_ratio = sum(labels) / len(labels)
        if not (0.3 <= positive_ratio <= 0.7):
            warnings_list.append(
                f"Ratio positivos/negativos fuera de rango: "
                f"{positive_ratio:.3f} (esperado [0.3, 0.7])"
            )

    for w in warnings_list:
        print(f"WARNING: {w}", file=sys.stderr)

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return False

    total = len(labels)
    accept = sum(labels)
    reject = total - accept
    print(
        json.dumps(
            {
                "valid": True,
                "total_pairs": total,
                "accept": accept,
                "reject": reject,
                "skus_unique": len({k[0] for k in seen}),
                "warnings": len(warnings_list),
            }
        )
    )
    return True


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Exporta pares etiquetados de match_candidates a JSONL.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="mode")

    # Default mode: export
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path de salida JSONL (ej. datasets/labeled_pairs_2026-05-12.jsonl)",
    )
    parser.add_argument(
        "--min-pairs",
        type=int,
        default=1000,
        help="Mínimo de pares requeridos (default: 1000).",
    )
    parser.add_argument(
        "--validate",
        type=Path,
        default=None,
        metavar="PATH",
        help="Valida un archivo JSONL existente en lugar de exportar.",
    )
    return parser


async def _main_export(output: Path, min_pairs: int) -> int:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("ERROR: DATABASE_URL no definida.", file=sys.stderr)
        return 1

    rows = await _fetch_pairs(database_url)
    summary = _summary(rows)
    print(json.dumps(summary))

    if summary["total_pairs"] < min_pairs:
        print(
            f"ERROR: insufficient_pairs — disponibles={summary['total_pairs']}, "
            f"requeridos={min_pairs}",
            file=sys.stderr,
        )
        return 1

    _write_jsonl(rows, output)
    print(f"Escrito: {output} ({summary['total_pairs']} pares)")
    return 0


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.validate is not None:
        # Validation mode
        path = args.validate
        if not path.exists():
            print(f"ERROR: archivo no encontrado: {path}", file=sys.stderr)
            sys.exit(1)
        ok = _validate_file(path)
        sys.exit(0 if ok else 1)

    # Export mode
    if args.output is None:
        from datetime import date

        args.output = Path(f"datasets/labeled_pairs_{date.today().isoformat()}.jsonl")

    exit_code = asyncio.run(_main_export(args.output, args.min_pairs))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
