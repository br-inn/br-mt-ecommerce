"""Unit tests para llm_query_generator._build_product_summary."""
from __future__ import annotations
import pytest

pytestmark = pytest.mark.unit


def test_build_product_summary_includes_model_thread_standard() -> None:
    from app.services.matching.llm_query_generator import _build_product_summary

    product_data = {
        "erp_name": "Ball Valve DN50 BSP",
        "product_type": "Ball Valve M-F PN25",
        "material": "brass",
        "dn": "DN50",
        "pn": "PN25",
        "connection": "BSP",
        "model_thread_standard": "BSP",
        "model_connection_type": "thread_bsp",
        "model_code": "4295",
    }
    summary = _build_product_summary(product_data)
    assert "BSP" in summary
    assert "4295" in summary


def test_build_product_summary_without_model_still_works() -> None:
    from app.services.matching.llm_query_generator import _build_product_summary

    product_data = {
        "erp_name": "Ball Valve DN50 BSP",
        "product_type": "Ball Valve M-F PN25",
        "material": "brass",
        "dn": "DN50",
        "pn": "PN25",
        "connection": "BSP",
        "model_code": None,
        "model_thread_standard": None,
        "model_connection_type": None,
    }
    summary = _build_product_summary(product_data)
    assert "brass" in summary.lower()
    assert "Ball Valve" in summary
