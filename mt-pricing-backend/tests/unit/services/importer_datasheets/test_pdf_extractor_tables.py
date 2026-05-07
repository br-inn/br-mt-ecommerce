"""Unit tests para extract_tables_from_pdf + extract_pdf_metadata (US-1A-06-04-V2 S6)."""

from __future__ import annotations

import pytest

from app.services.importer_datasheets.pdf_extractor import (
    _normalize_table,
    _normalize_table_row,
    extract_pdf_metadata,
    extract_tables_from_pdf,
)


class TestNormalizeTable:
    def test_empty_returns_none(self) -> None:
        assert _normalize_table([]) is None

    def test_only_blank_rows_returns_none(self) -> None:
        assert _normalize_table([["", None], [None, ""]]) is None

    def test_first_nonempty_row_is_header(self) -> None:
        result = _normalize_table([["DN", "PN", "Material"], ["50", "16", "Brass"]])
        assert result == {"headers": ["DN", "PN", "Material"], "rows": [["50", "16", "Brass"]]}

    def test_collapses_whitespace_and_handles_none_cells(self) -> None:
        result = _normalize_table([
            ["DN", "  PN  ", None],
            ["50", "16", "Brass\n  body"],
        ])
        assert result is not None
        assert result["headers"] == ["DN", "PN", ""]
        assert result["rows"] == [["50", "16", "Brass body"]]

    def test_strip_normalize_row_independently(self) -> None:
        assert _normalize_table_row([" a ", None, "  b\tc "]) == ["a", "", "b c"]


class TestExtractTables:
    def test_empty_payload_returns_empty_list(self) -> None:
        assert extract_tables_from_pdf(b"") == []

    def test_invalid_header_returns_empty(self) -> None:
        assert extract_tables_from_pdf(b"not a pdf") == []

    def test_minimal_pdf_no_tables(self) -> None:
        # PDF mínimo válido — pdfplumber no encontrará tablas estructuradas.
        payload = (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"%%EOF\n"
        )
        assert extract_tables_from_pdf(payload) == []


class TestExtractPdfMetadata:
    def test_empty_payload_returns_invalid(self) -> None:
        meta = extract_pdf_metadata(b"")
        assert meta["parse_method"] == "invalid"
        assert "empty_payload" in meta["warnings"]
        assert meta["tables"] == []
        assert meta["text"] == ""
        assert meta["page_count"] == 0

    def test_invalid_header_flagged(self) -> None:
        meta = extract_pdf_metadata(b"hello world")
        assert meta["parse_method"] == "invalid"
        assert "invalid_header" in meta["warnings"]

    def test_encrypted_marker_detected(self) -> None:
        # Construye un PDF mínimo con /Encrypt en el trailer.
        payload = (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog >> endobj\n"
            b"trailer << /Encrypt 5 0 R /Size 6 >>\n"
            b"%%EOF\n"
        )
        meta = extract_pdf_metadata(payload)
        assert meta["parse_method"] == "encrypted"
        assert "pdf_encrypted" in meta["warnings"]

    def test_minimal_pdf_returns_text_and_warnings(self) -> None:
        payload = (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog >> endobj\n"
            b"BT (DN50 PN16 Brass body) Tj ET\n"
            b"%%EOF\n"
        )
        meta = extract_pdf_metadata(payload)
        # parse_method depende de si pdfplumber pudo abrirlo.
        assert meta["parse_method"] in {"pdfplumber", "manual_text"}
        assert "DN50 PN16 Brass body" in meta["text"]
        assert isinstance(meta["tables"], list)
        assert isinstance(meta["warnings"], list)

    @pytest.mark.parametrize(
        "key", ["parse_method", "page_count", "text", "tables", "warnings"]
    )
    def test_metadata_schema_has_all_keys(self, key: str) -> None:
        meta = extract_pdf_metadata(b"")
        assert key in meta
