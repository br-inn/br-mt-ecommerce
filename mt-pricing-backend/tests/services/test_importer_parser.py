"""Unit tests para `app.services.importer.parser` (sin DB).

Valida streaming sobre el archivo PIM real (5085 rows × 17 cols).
Si el archivo no está disponible, los tests se saltan con razón clara.
"""

from __future__ import annotations

import os

import pytest

from app.services.importer.parser import parse_xlsx_stream

PIM_REAL_PATH = (
    r"c:\BR-Github\br-mt\br-mt-ecommerce\Documentos referencia de articulos"
    r"\PIM completo.xlsx"
)


def _has_pim() -> bool:
    return os.path.exists(PIM_REAL_PATH)


pytestmark = pytest.mark.skipif(
    not _has_pim(), reason=f"PIM real no disponible en {PIM_REAL_PATH}"
)


def test_parse_real_pim_max_50_rows() -> None:
    res = parse_xlsx_stream(PIM_REAL_PATH, max_rows=50)
    assert res.header_ok, res.header_errors
    assert res.total_data_rows == 50
    assert res.duplicate_skus == []
    # Todas las filas (50) deben pasar parse OK con el header real.
    ok_rows = [r for r in res.rows if r.ok]
    assert len(ok_rows) == 50
    skus = {r.sku for r in ok_rows}
    assert len(skus) == 50  # uniq dentro del archivo


def test_parse_real_pim_full_count() -> None:
    """El PIM real tiene 5085 filas de datos según sprint0 mapping."""
    res = parse_xlsx_stream(PIM_REAL_PATH)
    assert res.header_ok
    assert res.total_data_rows == 5085, (
        f"Esperaba 5085 rows; got {res.total_data_rows}. Revisar archivo."
    )
    # SKU es PK natural — no esperamos duplicados en el PIM real.
    assert res.duplicate_skus == [], f"Duplicados inesperados: {res.duplicate_skus[:5]}"
    # Sprint0 §1 documenta que ~22 % rows del PIM real no tienen `Nombre ERP`
    # → caen como error "name_en no derivable" (esperado; promueven a partial
    # tras backfill manual o LLM en fases siguientes). Toleramos hasta 30 %.
    ok = sum(1 for r in res.rows if r.ok)
    err = res.total_data_rows - ok
    assert err / res.total_data_rows < 0.30, (
        f"Más del 30 % de rows con error de parse: {err}/{res.total_data_rows}"
    )
    # ~78 % deberían pasar OK con erp_name presente.
    assert ok / res.total_data_rows > 0.70
