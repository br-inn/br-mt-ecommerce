from __future__ import annotations

import io
from decimal import Decimal
from typing import Any, Iterator

import openpyxl

from app.services.importer.column_mapper import CASTERS, ImportCastError, _cast_text
from app.services.importer.mapping_detector import ColumnMappingItem
from app.services.importer.parsed_product import ParsedProduct

SUPPORTED_LANGS: frozenset[str] = frozenset({"en", "es", "fr", "de", "it", "pt", "ar"})
JSONB_PREFIXES: frozenset[str] = frozenset({"dimensions", "packaging", "specs"})


class XlsxParser:
    """Parsea un xlsx usando un mapping flexible. Produce ParsedProduct por fila."""

    def __init__(
        self,
        xlsx_bytes: bytes,
        mapping: list[ColumnMappingItem],
        header_row_index: int = 0,
    ) -> None:
        self._bytes = xlsx_bytes
        self._mapping = mapping
        self._header_row_index = header_row_index
        self._rows_yielded: int = 0

    @property
    def rows_yielded(self) -> int:
        return self._rows_yielded

    def parse(self) -> Iterator[ParsedProduct]:
        wb = openpyxl.load_workbook(io.BytesIO(self._bytes), read_only=True, data_only=True)
        ws = wb.active
        col_index: dict[str, int] = {}

        try:
            for row_idx, raw_row in enumerate(ws.iter_rows(values_only=True)):
                if row_idx < self._header_row_index:
                    continue
                if row_idx == self._header_row_index:
                    col_index = {
                        str(v).strip(): i
                        for i, v in enumerate(raw_row)
                        if v is not None
                    }
                    continue
                row = list(raw_row)
                if not any(v is not None and v != "" for v in row):
                    continue  # fila vacía — no cuenta
                parsed = self._parse_row(row, col_index)
                self._rows_yielded += 1
                yield parsed
        finally:
            wb.close()

    def _parse_row(self, row: list[Any], col_index: dict[str, int]) -> ParsedProduct:
        scalars: dict[str, Any] = {}
        jsonb: dict[str, dict[str, Any]] = {
            "dimensions": {}, "packaging": {}, "specs": {}
        }
        translations: dict[str, str] = {}
        certifications: list[str] = []
        errors: list[str] = []

        for item in self._mapping:
            if item.target_field == "_skip":
                continue
            idx = col_index.get(item.excel_col)
            if idx is None or idx >= len(row):
                continue
            raw = row[idx]
            caster = CASTERS.get(item.transform, _cast_text)
            try:
                casted = caster(raw)
            except ImportCastError as exc:
                errors.append(f"col {item.excel_col!r}: {exc}")
                continue
            if casted is None:
                continue

            field = item.target_field

            if field.startswith("translations."):
                lang = field.split(".", 1)[1]
                if lang in SUPPORTED_LANGS:
                    translations[lang] = str(casted)
            elif field == "certifications":
                parts = [p.strip() for p in str(casted).split(",") if p.strip()]
                certifications.extend(parts)
            elif "." in field:
                prefix, key = field.split(".", 1)
                if prefix in JSONB_PREFIXES:
                    stored: Any = str(casted) if isinstance(casted, Decimal) else casted
                    jsonb[prefix][key] = stored
            else:
                scalars[field] = casted

        sku = str(scalars.pop("sku", "") or "").strip()
        if not sku:
            errors.append("SKU vacío — fila error.")

        return ParsedProduct(
            sku=sku,
            scalars=scalars,
            jsonb=jsonb,
            translations=translations,
            certifications=certifications,
            errors=errors,
        )
