"""Dispatcher de formato para el importador PIM: xlsx vs XML.

Punto único de detección de formato. El wizard y el worker async llaman aquí
en vez de a un parser concreto.
"""
from __future__ import annotations

import io
from typing import Any

from app.services.importer.parser import ParseResult, parse_xlsx_stream
from app.services.importer.xml_parser import parse_xml_stream


def is_xml_filename(filename: str | None) -> bool:
    return filename is not None and filename.lower().endswith(".xml")


def parse_source(
    file_bytes: bytes,
    filename: str | None,
    *,
    custom_mapping: list[Any] | None = None,
    header_row_index: int | None = None,
) -> ParseResult:
    """Parsea el archivo eligiendo el parser por extensión.

    - `.xml` → parse_xml_stream (ignora custom_mapping/header_row_index).
    - resto → parse_xlsx_stream con los argumentos del wizard.
    """
    if is_xml_filename(filename):
        return parse_xml_stream(file_bytes)

    bio = io.BytesIO(file_bytes)
    if custom_mapping is not None:
        return parse_xlsx_stream(
            bio, header_row_index=header_row_index or 0, custom_mapping=custom_mapping
        )
    return parse_xlsx_stream(bio)
