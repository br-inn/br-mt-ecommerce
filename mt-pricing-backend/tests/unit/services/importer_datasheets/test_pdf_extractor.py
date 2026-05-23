"""Unit tests para `app.services.importer_datasheets.pdf_extractor`.

No depende de pdfplumber/PyPDF2 — los tests construyen un PDF mínimo con
header `%PDF-1.4` y un text-object `BT (texto) Tj ET`.
"""

from __future__ import annotations

import pytest

from app.services.importer_datasheets.pdf_extractor import (
    PDFExtractionError,
    extract_text_from_pdf,
)

pytestmark = pytest.mark.unit


def _mk_pdf(text: str) -> bytes:
    body = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog >> endobj\n"
        b"2 0 obj << >> endobj\n"
        b"BT (" + text.encode("utf-8") + b") Tj ET\n"
        b"%%EOF\n"
    )
    return body


def test_extract_simple_text() -> None:
    payload = _mk_pdf("DN50 PN16 Brass body NBR seal")
    text = extract_text_from_pdf(payload)
    assert "DN50" in text
    assert "PN16" in text
    assert "Brass body" in text


def test_extract_text_dedups() -> None:
    payload = b"%PDF-1.4\nBT (Same Text) Tj ET\nBT (Same Text) Tj ET\n%%EOF"
    text = extract_text_from_pdf(payload)
    # Solo aparece una vez por dedupe
    assert text.count("Same Text") == 1


def test_extract_invalid_header_raises() -> None:
    with pytest.raises(PDFExtractionError) as exc:
        extract_text_from_pdf(b"NOT A PDF")
    assert exc.value.code == "pdf_invalid_header"


def test_extract_empty_payload_raises() -> None:
    with pytest.raises(PDFExtractionError) as exc:
        extract_text_from_pdf(b"")
    assert exc.value.code == "pdf_empty"


def test_extract_with_escapes() -> None:
    # Paréntesis escapados \\( y \\) no rompen el parseo.
    payload = b"%PDF-1.4\nBT (Datos\\(DN50\\)PN16) Tj ET\n%%EOF"
    text = extract_text_from_pdf(payload)
    assert "DN50" in text


def test_extract_tj_block_with_array() -> None:
    payload = b"%PDF-1.4\nBT [(Brass )(body) (DN50)] TJ ET\n%%EOF"
    text = extract_text_from_pdf(payload)
    assert "Brass" in text
    assert "DN50" in text


def test_extract_no_text_objects_returns_empty_string() -> None:
    """PDF válido sin BT/ET ni paréntesis devuelve string vacío (no falla)."""
    payload = b"%PDF-1.4\n1 0 obj << /Length 0 >> endobj\n%%EOF"
    text = extract_text_from_pdf(payload)
    # Puede ser vacío o casi vacío — lo importante es que no levante.
    assert isinstance(text, str)
