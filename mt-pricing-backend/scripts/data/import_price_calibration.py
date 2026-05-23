"""Importa rangos de calibración de precios desde CSV a price_calibration_ranges.

Uso:
    python -m scripts.data.import_price_calibration --csv path/to/ranges.csv
    python -m scripts.data.import_price_calibration --csv path/to/ranges.csv --dry-run
    python -m scripts.data.import_price_calibration --csv path/to/ranges.csv --currency USD

Formato CSV esperado (con headers):
    category_id,expected_min_p10,expected_max_p90,currency
    valve_family,15.00,850.00,AED
    fitting_family,2.50,320.00,AED
    default,5.00,500.00,AED

Lógica:
- Valida: expected_min_p10 > 0, expected_min_p10 < expected_max_p90, currency en whitelist.
- En --dry-run: imprime tabla de validación sin tocar DB.
- Sin --dry-run: UPSERT ON CONFLICT (category_id, currency) DO UPDATE.
- Exit 0 si OK, 1 si hay errores de validación.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_ALLOWED_CURRENCIES = {"AED", "USD", "EUR"}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
class _RowError:
    def __init__(self, line: int, field: str, msg: str) -> None:
        self.line = line
        self.field = field
        self.msg = msg

    def __str__(self) -> str:
        return f"Línea {self.line} [{self.field}]: {self.msg}"


def _validate_row(
    row: dict[str, str],
    *,
    line: int,
    default_currency: str = "AED",
) -> tuple[str, Decimal, Decimal, str] | _RowError:
    """Valida una fila CSV y devuelve (category_id, min_p10, max_p90, currency) o un error."""
    category_id = (row.get("category_id") or "").strip()
    if not category_id:
        return _RowError(line, "category_id", "vacío")

    currency = (row.get("currency") or default_currency).strip().upper()
    if currency not in _ALLOWED_CURRENCIES:
        return _RowError(
            line,
            "currency",
            f"'{currency}' no permitido. Válidos: {sorted(_ALLOWED_CURRENCIES)}",
        )

    raw_min = (row.get("expected_min_p10") or "").strip()
    raw_max = (row.get("expected_max_p90") or "").strip()

    try:
        min_p10 = Decimal(raw_min)
    except InvalidOperation:
        return _RowError(line, "expected_min_p10", f"'{raw_min}' no es un decimal válido")

    try:
        max_p90 = Decimal(raw_max)
    except InvalidOperation:
        return _RowError(line, "expected_max_p90", f"'{raw_max}' no es un decimal válido")

    if min_p10 <= 0:
        return _RowError(line, "expected_min_p10", f"{min_p10} debe ser > 0")

    if min_p10 >= max_p90:
        return _RowError(
            line,
            "expected_max_p90",
            f"{max_p90} debe ser > expected_min_p10 ({min_p10})",
        )

    return (category_id, min_p10, max_p90, currency)


def _parse_csv(
    csv_path: Path,
    *,
    default_currency: str = "AED",
) -> tuple[list[tuple[str, Decimal, Decimal, str]], list[str]]:
    """Parsea el CSV, valida filas y retorna (valid_rows, error_messages)."""
    valid: list[tuple[str, Decimal, Decimal, str]] = []
    errors: list[str] = []

    with csv_path.open(encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for line_num, row in enumerate(reader, start=2):  # fila 1 = header
            result = _validate_row(row, line=line_num, default_currency=default_currency)
            if isinstance(result, _RowError):
                errors.append(str(result))
            else:
                valid.append(result)

    return valid, errors


# ---------------------------------------------------------------------------
# Dry-run display
# ---------------------------------------------------------------------------
def _print_dry_run_table(
    valid_rows: list[tuple[str, Decimal, Decimal, str]],
    errors: list[str],
) -> None:
    print("\n=== DRY-RUN: validación CSV ===\n")
    if errors:
        print(f"ERRORES ({len(errors)}):")
        for e in errors:
            print(f"  ! {e}")
        print()

    if valid_rows:
        print(f"FILAS VÁLIDAS ({len(valid_rows)}):")
        header = f"  {'category_id':<30} {'min_p10':>12} {'max_p90':>12} {'currency':>8}"
        print(header)
        print("  " + "-" * 68)
        for cat, mn, mx, cur in valid_rows:
            print(f"  {cat:<30} {mn!s:>12} {mx!s:>12} {cur:>8}")
    else:
        print("Sin filas válidas.")
    print()


# ---------------------------------------------------------------------------
# DB upsert
# ---------------------------------------------------------------------------
async def _upsert_rows(
    valid_rows: list[tuple[str, Decimal, Decimal, str]],
) -> dict[str, int]:
    """Hace UPSERT en price_calibration_ranges y retorna contadores."""
    from sqlalchemy import select

    from app.db.engine import get_sessionmaker
    from app.db.models.comparator import PriceCalibrationRange

    now = datetime.now(tz=UTC)
    inserted = 0
    updated = 0

    async with get_sessionmaker()() as session, session.begin():
        for category_id, min_p10, max_p90, currency in valid_rows:
            existing_result = await session.execute(
                select(PriceCalibrationRange).where(
                    PriceCalibrationRange.category_id == category_id,
                    PriceCalibrationRange.currency == currency,
                )
            )
            existing = existing_result.scalar_one_or_none()

            if existing is not None:
                existing.expected_min_p10 = min_p10
                existing.expected_max_p90 = max_p90
                existing.updated_at = now
                updated += 1
            else:
                session.add(
                    PriceCalibrationRange(
                        category_id=category_id,
                        expected_min_p10=min_p10,
                        expected_max_p90=max_p90,
                        currency=currency,
                        updated_at=now,
                    )
                )
                inserted += 1

    return {"inserted": inserted, "updated": updated, "skipped": 0}


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Importa rangos de calibración de precios desde CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--csv", required=True, metavar="PATH", help="Ruta al CSV de entrada")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida sin escribir a DB",
    )
    parser.add_argument(
        "--currency",
        default="AED",
        metavar="CURRENCY",
        help="Divisa por defecto si la columna está ausente (default: AED)",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"ERROR: No existe el archivo '{csv_path}'", file=sys.stderr)
        sys.exit(1)

    default_currency = args.currency.strip().upper()
    if default_currency not in _ALLOWED_CURRENCIES:
        print(
            f"ERROR: --currency '{default_currency}' no válido. Opciones: {sorted(_ALLOWED_CURRENCIES)}",
            file=sys.stderr,
        )
        sys.exit(1)

    valid_rows, errors = _parse_csv(csv_path, default_currency=default_currency)

    if args.dry_run:
        _print_dry_run_table(valid_rows, errors)
        if errors:
            sys.exit(1)
        sys.exit(0)

    if errors:
        print("Errores de validación — no se escribió a DB:")
        for e in errors:
            print(f"  ! {e}")
        summary = {
            "inserted": 0,
            "updated": 0,
            "skipped": len(valid_rows),
            "errors": errors,
        }
        print(json.dumps(summary, ensure_ascii=False))
        sys.exit(1)

    counters = asyncio.run(_upsert_rows(valid_rows))
    summary = {**counters, "errors": []}
    print(json.dumps(summary, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
