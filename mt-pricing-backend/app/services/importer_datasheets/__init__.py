"""Importer datasheets PDF — Sprint 4 / US-1A-06-04.

Asocia archivos PDF (`MTFT_*` ficha técnica, `MTCE_*` compliance,
`MTMAN_*` manual) a SKUs por sufijo numérico del filename. Extracción semi-
automática de specs (DN, PN, material, seal) desde el texto del PDF para que
el VLM judge / la pantalla de detalle del producto puedan consumirlas.

Componentes:
- :mod:`pdf_extractor` — extrae texto plano de un PDF (puro Python; no
  depende de ``pdfplumber`` / ``PyPDF2`` que aún no están en deps).
- :mod:`spec_parser`   — regex sobre el texto extraído para inferir specs.
- :mod:`applier`       — aplica los datasheets a productos vía
  ``ProductService`` (Protocol mockeable).
- :mod:`importer_service` — orquesta preview + apply + status (mismo patrón
  que ``importer_costs``).
"""

from __future__ import annotations

from app.services.importer_datasheets.applier import (
    ApplyDatasheetsResult,
    DatasheetApplier,
    ProductServiceProtocol,
    apply_datasheet_diffs,
)
from app.services.importer_datasheets.importer_service import (
    DATASHEET_KIND_PREFIXES,
    DatasheetsRunState,
    ImporterDatasheetsService,
    reset_datasheets_run_store,
)
from app.services.importer_datasheets.pdf_extractor import (
    PDFExtractionError,
    extract_text_from_pdf,
)
from app.services.importer_datasheets.spec_parser import (
    DatasheetSpecs,
    parse_datasheet_filename,
    parse_specs_from_text,
)

__all__ = [
    "DATASHEET_KIND_PREFIXES",
    "ApplyDatasheetsResult",
    "DatasheetApplier",
    "DatasheetSpecs",
    "DatasheetsRunState",
    "ImporterDatasheetsService",
    "PDFExtractionError",
    "ProductServiceProtocol",
    "apply_datasheet_diffs",
    "extract_text_from_pdf",
    "parse_datasheet_filename",
    "parse_specs_from_text",
    "reset_datasheets_run_store",
]
