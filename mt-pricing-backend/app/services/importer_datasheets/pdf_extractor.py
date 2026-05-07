"""PDF extractor — extrae texto plano de un PDF binario.

Estrategia (Sprint 4 / US-1A-06-04):

- Si ``pdfplumber`` o ``PyPDF2`` están instalados, los usamos (precisión alta).
- Si no, **fallback puro Python** que escanea los bytes en busca de literal
  strings dentro de objetos ``BT...ET`` (PDF text objects). Esto cubre los
  PDFs simples generados por catálogos MT (`MTFT_*.pdf`, `MTCE_*.pdf`).

El fallback es intencionadamente conservador — extrae sólo strings entre
paréntesis dentro de bloques ``BT ... ET`` y un fallback adicional buscando
strings que aparecen tras `Tj` o `TJ` operators. No interpreta CMaps, ni
streams comprimidos zlib (los PDFs de catálogo MT son no-comprimidos —
verificado en el directorio ``Documentos referencia de articulos/``).

Esto significa que los tests pueden construir un PDF mínimo así:

    payload = (
        b"%PDF-1.4\\n"
        b"1 0 obj << /Type /Catalog >> endobj\\n"
        b"BT (DN50 PN16 Brass body) Tj ET\\n"
        b"%%EOF"
    )

…y la extracción retorna ``"DN50 PN16 Brass body"``.
"""

from __future__ import annotations

import logging
import re
import zlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    pass

logger = logging.getLogger(__name__)


class PDFExtractionError(Exception):
    """Error recoverable al extraer texto de un PDF."""

    def __init__(self, message: str, *, code: str = "pdf_extract_failed") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# Header magic — PDFs reales empiezan así. Lo usamos como heurística de
# validación rápida sin parsear el documento entero.
_PDF_MAGIC = b"%PDF-"

# Regex para localizar text objects ``BT ... ET`` y dentro extraer paréntesis.
# Trabajamos sobre bytes — el contenido suele ser ASCII Latin-1.
_BT_ET_RE = re.compile(rb"BT\s(.*?)\sET", re.DOTALL)
# String literal en PDF: ``(...)``. Permite ``\(`` y ``\)`` escapados.
# Pattern: paren abierta, luego cualquier cantidad de [carácter escapado | char no `(` ni `)`], paren cerrada.
_PAREN_RE = re.compile(rb"\((?:\\.|[^()\\])*\)", re.DOTALL)
_TJ_BLOCK_RE = re.compile(rb"\[(.*?)\]\s*TJ", re.DOTALL)


_BACKSLASH = b"\\"  # literal single backslash byte
_PAREN_OPEN = b"("
_PAREN_CLOSE = b")"


def _decode_pdf_string(literal: bytes) -> str:
    """Decodifica un PDF string ``(...)`` aplicando los escapes mínimos."""
    inner = (
        literal[1:-1]
        if literal.startswith(_PAREN_OPEN) and literal.endswith(_PAREN_CLOSE)
        else literal
    )
    out = bytearray()
    i = 0
    while i < len(inner):
        ch = inner[i : i + 1]
        if ch == _BACKSLASH:
            if i + 1 < len(inner):
                nxt = inner[i + 1 : i + 2]
                if nxt == b"n":
                    out += b"\n"
                elif nxt == b"r":
                    out += b"\r"
                elif nxt == b"t":
                    out += b"\t"
                elif nxt in (_PAREN_OPEN, _PAREN_CLOSE, _BACKSLASH):
                    out += nxt
                else:
                    out += nxt
                i += 2
                continue
        out += ch
        i += 1
    try:
        return out.decode("utf-8", errors="replace")
    except Exception:  # pragma: no cover  # noqa: BLE001
        return out.decode("latin-1", errors="replace")


def _extract_with_pdfplumber(payload: bytes) -> str | None:
    try:
        import pdfplumber  # type: ignore  # noqa: I001
    except Exception:  # noqa: BLE001
        return None
    try:
        import io as _io

        with pdfplumber.open(_io.BytesIO(payload)) as pdf:  # pragma: no cover
            chunks: list[str] = []
            for page in pdf.pages:
                txt = page.extract_text() or ""
                if txt.strip():
                    chunks.append(txt)
            return "\n".join(chunks)
    except Exception as exc:  # pragma: no cover  # noqa: BLE001
        logger.warning("pdfplumber failed, fallback to manual: %s", exc)
        return None


def _extract_with_pypdf(payload: bytes) -> str | None:
    try:
        from PyPDF2 import PdfReader  # type: ignore
    except Exception:  # noqa: BLE001
        try:
            from pypdf import PdfReader  # type: ignore
        except Exception:  # noqa: BLE001
            return None
    try:
        import io as _io

        reader = PdfReader(_io.BytesIO(payload))  # pragma: no cover
        chunks: list[str] = []
        for page in reader.pages:
            try:
                txt = page.extract_text() or ""
            except Exception:  # noqa: BLE001
                txt = ""
            if txt.strip():
                chunks.append(txt)
        return "\n".join(chunks)
    except Exception as exc:  # pragma: no cover  # noqa: BLE001
        logger.warning("pypdf failed, fallback to manual: %s", exc)
        return None


def _extract_streams_plaintext(payload: bytes) -> bytes:
    """Junta el contenido entre `stream` ... `endstream`, aplicando inflate
    con tolerancia (algunos PDFs no comprimen, otros sí).
    """
    out = bytearray(payload)  # incluye header — el regex BT/ET trabaja igual
    # Decompress streams that look like FlateDecode (zlib magic 0x78).
    cursor = 0
    while True:
        s_idx = payload.find(b"stream", cursor)
        if s_idx < 0:
            break
        e_idx = payload.find(b"endstream", s_idx)
        if e_idx < 0:
            break
        body_start = s_idx + len(b"stream")
        # PDFs estándar tienen \n o \r\n tras "stream"
        if payload[body_start : body_start + 2] == b"\r\n":
            body_start += 2
        elif payload[body_start : body_start + 1] in (b"\n", b"\r"):
            body_start += 1
        body = payload[body_start:e_idx].rstrip(b"\r\n ")
        if body[:2] == b"\x78\x9c" or body[:1] == b"\x78":
            try:
                inflated = zlib.decompress(body)
                out += b"\n" + inflated + b"\n"
            except Exception:  # noqa: BLE001
                pass
        cursor = e_idx + len(b"endstream")
    return bytes(out)


def _extract_manual(payload: bytes) -> str:
    """Fallback puro: busca BT...ET y operadores Tj / TJ y rescata literales."""
    decompressed = _extract_streams_plaintext(payload)
    chunks: list[str] = []
    seen: set[str] = set()

    for block in _BT_ET_RE.findall(decompressed):
        for match in _PAREN_RE.finditer(block):
            txt = _decode_pdf_string(match.group(0)).strip()
            if txt and txt not in seen:
                seen.add(txt)
                chunks.append(txt)
        for tj in _TJ_BLOCK_RE.findall(block):
            for match in _PAREN_RE.finditer(tj):
                txt = _decode_pdf_string(match.group(0)).strip()
                if txt and txt not in seen:
                    seen.add(txt)
                    chunks.append(txt)

    if not chunks:
        # Ultimate fallback — recorrer todo el payload buscando paréntesis
        # con caracteres imprimibles.
        for match in _PAREN_RE.finditer(decompressed):
            txt = _decode_pdf_string(match.group(0)).strip()
            if not txt:
                continue
            printable = sum(1 for c in txt if c.isprintable())
            if printable < 3 or len(txt) < 3:
                continue
            if txt in seen:
                continue
            seen.add(txt)
            chunks.append(txt)

    return "\n".join(chunks)


def extract_text_from_pdf(payload: bytes) -> str:
    """Intenta pdfplumber → pypdf → manual fallback. Lanza
    :class:`PDFExtractionError` sólo si el header no parece PDF.
    """
    if not payload:
        raise PDFExtractionError("Payload vacío", code="pdf_empty")
    if not payload.lstrip().startswith(_PDF_MAGIC):
        raise PDFExtractionError(
            "Header inválido — no comienza con %PDF-", code="pdf_invalid_header"
        )

    # Estrategia: probamos pdfplumber/pypdf, pero si el resultado está vacío
    # (PDF mínimo construido en tests, no compatible con esos parsers),
    # caemos al fallback manual igual.
    via_pp = _extract_with_pdfplumber(payload)
    if via_pp and via_pp.strip():
        return via_pp
    via_pyp = _extract_with_pypdf(payload)
    if via_pyp and via_pyp.strip():
        return via_pyp
    return _extract_manual(payload)


# ---------------------------------------------------------------------------
# Sprint 6 — US-1A-06-04-V2 stretch: structured tables + metadata
# ---------------------------------------------------------------------------


def _normalize_table_row(row: list) -> list[str]:
    """Limpia una fila pdfplumber: None→'', strip, colapsa whitespace."""
    return [
        " ".join((cell or "").split()) if cell is not None else ""
        for cell in row
    ]


def _normalize_table(raw_rows: list[list]) -> dict | None:
    """Convierte el output de ``page.extract_tables()`` a ``{headers, rows}``.

    La primera fila no vacía se asume header. Filas con todos los cells vacíos
    se descartan. Devuelve ``None`` si la tabla quedó vacía tras limpieza.
    """
    cleaned = [_normalize_table_row(r) for r in raw_rows if r]
    cleaned = [r for r in cleaned if any(c for c in r)]
    if not cleaned:
        return None
    headers = cleaned[0]
    rows = cleaned[1:]
    return {"headers": headers, "rows": rows}


def extract_tables_from_pdf(payload: bytes) -> list[dict]:
    """Extrae tablas estructuradas usando pdfplumber.

    Returns:
        Lista de ``{page: int (1-indexed), headers: list[str], rows: list[list[str]]}``.
        Si pdfplumber no está disponible o falla, devuelve ``[]`` (no excepción).

    El extractor de tablas REQUIERE pdfplumber (no hay fallback puro Python
    que detecte tabular layouts de forma robusta). Para PDFs escaneados o
    sin tablas, retorna lista vacía sin error.
    """
    if not payload or not payload.lstrip().startswith(_PDF_MAGIC):
        return []
    try:
        import pdfplumber  # type: ignore  # noqa: I001
    except Exception:  # noqa: BLE001
        logger.info("pdfplumber unavailable — tables extraction skipped")
        return []
    try:
        import io as _io

        out: list[dict] = []
        with pdfplumber.open(_io.BytesIO(payload)) as pdf:  # pragma: no cover
            for page_idx, page in enumerate(pdf.pages, start=1):
                try:
                    raw_tables = page.extract_tables() or []
                except Exception as exc:  # noqa: BLE001
                    logger.warning("page %d extract_tables failed: %s", page_idx, exc)
                    continue
                for raw in raw_tables:
                    norm = _normalize_table(raw)
                    if norm is not None:
                        out.append({"page": page_idx, **norm})
        return out
    except Exception as exc:  # pragma: no cover  # noqa: BLE001
        logger.warning("extract_tables_from_pdf failed: %s", exc)
        return []


def _is_pdf_encrypted(payload: bytes) -> bool:
    """Detecta encryption sin parsear todo. Heurística: busca ``/Encrypt`` en trailer."""
    return b"/Encrypt" in payload[-4096:] if len(payload) > 4096 else b"/Encrypt" in payload


def extract_pdf_metadata(payload: bytes) -> dict:
    """Devuelve metadata + parsed_content compatible con ``product_datasheets.parsed_content``.

    Schema:
        {
            "parse_method": "pdfplumber" | "manual_text" | "encrypted" | "invalid",
            "page_count": int,
            "text": str,
            "tables": list[{page, headers, rows}],
            "warnings": list[str],
        }

    NO lanza — para PDFs inválidos retorna parse_method='invalid' con warning.
    """
    warnings: list[str] = []
    if not payload:
        return {
            "parse_method": "invalid",
            "page_count": 0,
            "text": "",
            "tables": [],
            "warnings": ["empty_payload"],
        }
    if not payload.lstrip().startswith(_PDF_MAGIC):
        return {
            "parse_method": "invalid",
            "page_count": 0,
            "text": "",
            "tables": [],
            "warnings": ["invalid_header"],
        }
    if _is_pdf_encrypted(payload):
        return {
            "parse_method": "encrypted",
            "page_count": 0,
            "text": "",
            "tables": [],
            "warnings": ["pdf_encrypted"],
        }

    page_count = 0
    parse_method = "manual_text"
    try:
        import pdfplumber  # type: ignore
        import io as _io

        with pdfplumber.open(_io.BytesIO(payload)) as pdf:  # pragma: no cover
            page_count = len(pdf.pages)
            parse_method = "pdfplumber"
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"pdfplumber_unavailable: {exc.__class__.__name__}")

    try:
        text = extract_text_from_pdf(payload)
    except PDFExtractionError as exc:
        text = ""
        warnings.append(exc.code)

    tables = extract_tables_from_pdf(payload)
    if not tables and parse_method == "pdfplumber":
        warnings.append("no_tables_detected")

    return {
        "parse_method": parse_method,
        "page_count": page_count,
        "text": text,
        "tables": tables,
        "warnings": warnings,
    }


__all__ = [
    "PDFExtractionError",
    "extract_pdf_metadata",
    "extract_tables_from_pdf",
    "extract_text_from_pdf",
]
