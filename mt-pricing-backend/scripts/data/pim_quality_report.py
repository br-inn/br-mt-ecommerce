"""CLI — PIM Data Quality Report.

Uso::

    python -m scripts.data.pim_quality_report [--format json|table] [--output report.json]

Opciones:
    --format json   (default) Imprime JSON en stdout.
    --format table  Imprime tabla ASCII con gaps ordenados por % descendente.
    --output FILE   Escribe JSON al archivo (sin imprimir en stdout).

Exit code: siempre 0 (es diagnóstico, no falla).

Ejecutar desde la raíz del proyecto con las variables de entorno del .env.local
(o exportadas en shell).  El script reutiliza ``_compute_data_quality`` del
módulo de routes para garantizar paridad con el endpoint HTTP.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.data.pim_quality_report",
        description="Diagnostica gaps de calidad PIM en el catálogo.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="json",
        help="Formato de salida (json | table). Default: json.",
    )
    parser.add_argument(
        "--output",
        metavar="FILE",
        default=None,
        help="Ruta de archivo para guardar el JSON. Si se omite, stdout.",
    )
    return parser.parse_args()


def _render_table(data: dict) -> str:
    """Devuelve una tabla ASCII con los gaps ordenados por pct desc."""
    gaps: dict = data.get("gaps", {})
    rows = []
    for key, info in gaps.items():
        if isinstance(info, dict) and "pct" in info:
            rows.append(
                (
                    key,
                    info.get("count", 0),
                    info.get("pct", 0.0),
                    ", ".join(info.get("sample_skus", [])[:3]) or "-",
                )
            )

    # Ordenar por pct descendente
    rows.sort(key=lambda r: r[2], reverse=True)

    col_widths = [
        max(len("Gap"), max((len(r[0]) for r in rows), default=0)),
        max(len("Count"), max((len(str(r[1])) for r in rows), default=0)),
        max(len("Pct %"), 6),
        max(len("Sample SKUs"), max((len(r[3]) for r in rows), default=0)),
    ]

    def _fmt_row(cells: tuple) -> str:
        return "| " + " | ".join(str(c).ljust(col_widths[i]) for i, c in enumerate(cells)) + " |"

    sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    header = _fmt_row(("Gap", "Count", "Pct %", "Sample SKUs"))

    lines = [
        f"PIM Data Quality Report — {data.get('generated_at', '')}",
        f"Total SKUs: {data.get('total_skus', 0)}",
        "",
        sep,
        header,
        sep,
    ]
    for row in rows:
        lines.append(_fmt_row((row[0], row[1], f"{row[2]:.1f}%", row[3])))
    lines.append(sep)
    return "\n".join(lines)


async def _run(args: argparse.Namespace) -> None:
    """Punto de entrada async: conecta a DB y calcula el reporte."""
    # Carga .env.local si existe (desarrollo local).
    _dotenv_path = Path(__file__).parent.parent.parent / ".env.local"
    if _dotenv_path.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(_dotenv_path, override=False)
        except ImportError:
            pass  # python-dotenv no instalado — se asume que env vars ya están en entorno.

    # Import tardío para no romper si la app no está configurada.
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.api.routes.admin_pim_quality import _compute_data_quality

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "[ERROR] DATABASE_URL no definida. Exporta la variable o crea .env.local.",
            file=sys.stderr,
        )
        sys.exit(0)

    engine = create_async_engine(database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            data = await _compute_data_quality(session)
    finally:
        await engine.dispose()

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Reporte guardado en: {out_path}", file=sys.stderr)
    else:
        if args.format == "table":
            print(_render_table(data))
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False))


def main() -> None:
    args = _parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
