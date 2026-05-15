"""Unit tests for `app.services.matching.query_builder`.

Cobertura:
- DN métrico se traduce a pulgadas correctas.
- Brand + spec query se genera cuando hay brand.
- Spec EN siempre se genera con material/family/inch/PN.
- AR query se genera para familias conocidas.
- Norm query sólo cuando `norma` está poblada.
- Part number query siempre que haya sku code.
- Channels override es respetado.
- SKU vacío no falla, devuelve algo razonable o vacío.
"""

from __future__ import annotations

import pytest

from app.services.matching.query_builder import (
    DN_TO_INCH,
    QueryBuilder,
    build_queries,
)

pytestmark = pytest.mark.unit


SAMPLE_SKU = {
    "sku": "MTBR4001050",
    "name_en": "Brass ball valve DN50 PN25 BSP",
    "family": "ball_valve",
    "dn": "DN50",
    "pn": "PN25",
    "material": "brass",
    "connection": "BSP",
    "brand": "Pegler",
    "norma": "EN13828",
}


def test_build_for_sku_returns_queries_per_channel() -> None:
    qb = QueryBuilder()
    queries = qb.build_for_sku(SAMPLE_SKU)
    sources = {q.source for q in queries}
    assert sources == {"amazon_uae", "noon_uae"}


def test_build_for_sku_emits_brand_spec_query() -> None:
    queries = build_queries(SAMPLE_SKU)
    brand_specs = [q for q in queries if q.type == "brand_spec"]
    assert len(brand_specs) >= 1
    q = brand_specs[0]
    assert "Pegler" in q.text
    assert "brass" in q.text
    assert "ball valve" in q.text


def test_build_for_sku_translates_dn_to_inch() -> None:
    queries = build_queries(SAMPLE_SKU)
    spec_q = next(q for q in queries if q.type == "spec")
    # DN50 → 2"
    assert DN_TO_INCH[50] in spec_q.text


def test_build_for_sku_emits_arabic_query() -> None:
    queries = build_queries(SAMPLE_SKU)
    ar = [q for q in queries if q.lang == "ar"]
    assert ar, "expected at least one AR query for ball_valve family"
    assert ar[0].type == "spec_ar"


def test_build_for_sku_emits_norm_query_when_norma_present() -> None:
    queries = build_queries(SAMPLE_SKU)
    norm = [q for q in queries if q.type == "norm"]
    assert norm
    assert "EN13828" in norm[0].text


def test_build_for_sku_skips_norm_when_absent() -> None:
    sku = dict(SAMPLE_SKU)
    sku.pop("norma")
    queries = build_queries(sku)
    norm = [q for q in queries if q.type == "norm"]
    assert not norm


def test_build_for_sku_part_number_includes_brand_when_known() -> None:
    queries = build_queries(SAMPLE_SKU)
    pn = next(q for q in queries if q.type == "part_number")
    assert "Pegler" in pn.text
    assert "MTBR4001050" in pn.text


def test_build_for_sku_no_brand_still_works() -> None:
    sku = dict(SAMPLE_SKU)
    sku.pop("brand")
    queries = build_queries(sku)
    # Sin brand, no brand_spec query.
    assert not any(q.type == "brand_spec" for q in queries)
    # Spec query sigue presente.
    assert any(q.type == "spec" for q in queries)


def test_build_for_sku_channels_override() -> None:
    queries = build_queries(SAMPLE_SKU, channels=["amazon_uae"])
    assert {q.source for q in queries} == {"amazon_uae"}


def test_build_for_sku_minimal_returns_at_least_one_query() -> None:
    minimal = {"sku": "MT-X-001", "name_en": "Some product"}
    queries = build_queries(minimal)
    assert queries, "expected at least one fallback query"


def test_build_for_sku_handles_int_dn() -> None:
    sku = dict(SAMPLE_SKU)
    sku["dn"] = 50  # int
    queries = build_queries(sku)
    spec_q = next(q for q in queries if q.type == "spec")
    assert '2"' in spec_q.text or "DN50" in spec_q.text


def test_build_for_sku_uses_model_thread_standard_in_spec_query() -> None:
    """Cuando model_thread_standard está presente, aparece en el spec query."""
    sku = dict(SAMPLE_SKU)
    sku["model_thread_standard"] = "BSP"
    sku["model_connection_type"] = "thread_bsp"

    queries = build_queries(sku)
    spec_q = next(q for q in queries if q.type == "spec")
    assert "BSP" in spec_q.text, f"Expected BSP in spec query, got: {spec_q.text!r}"


def test_build_for_sku_model_fields_none_does_not_crash() -> None:
    """Cuando model_* son None, el builder funciona igual que antes."""
    sku = dict(SAMPLE_SKU)
    sku["model_code"] = None
    sku["model_connection_type"] = None
    sku["model_thread_standard"] = None

    queries = build_queries(sku)
    assert any(q.type == "spec" for q in queries)
