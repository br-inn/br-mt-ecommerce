"""Exporta plantilla CSV para price_calibration_ranges.

Uso:
    python -m scripts.data.export_price_calibration_template --output template.csv

Comportamiento:
- Si la DB tiene rangos existentes, los exporta (modo backup).
- Si la DB está vacía, genera CSV con headers + filas de ejemplo.
- Siempre escribe los headers: category_id,expected_min_p10,expected_max_p90,currency
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# DB query
# ---------------------------------------------------------------------------
async def _fetch_existing_ranges() -> list[tuple[str, str, str, str]]:
    """Retorna todos los rangos existentes como (category_id, min_p10, max_p90, currency)."""
    from sqlalchemy import select

    from app.db.engine import get_sessionmaker
    from app.db.models.comparator import PriceCalibrationRange

    async with get_sessionmaker()() as session:
        result = await session.execute(
            select(PriceCalibrationRange).order_by(
                PriceCalibrationRange.category_id,
                PriceCalibrationRange.currency,
            )
        )
        rows = result.scalars().all()
        return [
            (
                row.category_id,
                str(row.expected_min_p10),
                str(row.expected_max_p90),
                row.currency,
            )
            for row in rows
        ]


# ---------------------------------------------------------------------------
# Write CSV
# ---------------------------------------------------------------------------
_EXAMPLE_ROWS = [
    ("valve_family", "15.00", "850.00", "AED"),
    ("fitting_family", "2.50", "320.00", "AED"),
    ("default", "5.00", "500.00", "AED"),
]

_HEADERS = ["category_id", "expected_min_p10", "expected_max_p90", "currency"]


def _write_csv(
    output_path: Path,
    data_rows: list[tuple[str, str, str, str]],
    *,
    is_example: bool,
) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(_HEADERS)
        for row in data_rows:
            writer.writerow(row)

    mode = "ejemplo (DB vacía)" if is_example else f"backup ({len(data_rows)} rangos)"
    print(f"Template exportado: {output_path} [{mode}]")


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Exporta plantilla CSV para price_calibration_ranges.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="PATH",
        help="Ruta del CSV de salida (ej. template.csv)",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="No consultar DB — genera solo filas de ejemplo",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.no_db:
        _write_csv(output_path, _EXAMPLE_ROWS, is_example=True)
        sys.exit(0)

    try:
        existing = asyncio.run(_fetch_existing_ranges())
    except Exception as exc:
        print(f"ADVERTENCIA: No se pudo conectar a DB ({exc}). Usando filas de ejemplo.")
        _write_csv(output_path, _EXAMPLE_ROWS, is_example=True)
        sys.exit(0)

    if existing:
        _write_csv(output_path, existing, is_example=False)
    else:
        _write_csv(output_path, _EXAMPLE_ROWS, is_example=True)

    sys.exit(0)


if __name__ == "__main__":
    main()
