"""Wave 8 — translations SEO + editorial fields tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.products import (
    ProductTranslationBase,
    ProductTranslationCreate,
    ProductTranslationPatch,
    ProductTranslationResponse,
)


def test_translation_base_accepts_seo_fields() -> None:
    p = ProductTranslationBase(
        name="Válvula bola",
        meta_title="Válvula bola PN16 latón DN50 — MT",
        meta_description="Válvula de bola en latón forjado, conexión BSP 2 pulgadas, presión nominal PN16, certificada WRAS.",
        applications_text="Idónea para agua potable y sistemas hidrosanitarios.",
        technical_limits="Temperatura: -20 a 100 °C. Presión: hasta 16 bar.",
        notes="Cumple normativa EN 1.4408.",
        marketing_features="**Tres puertos**\nResistente a corrosión.",
    )
    assert p.meta_title is not None and len(p.meta_title) <= 70


def test_meta_title_length_max_70() -> None:
    with pytest.raises(ValidationError):
        ProductTranslationBase(meta_title="x" * 71)


def test_meta_description_length_max_160() -> None:
    with pytest.raises(ValidationError):
        ProductTranslationBase(meta_description="x" * 161)


def test_translation_create_with_seo() -> None:
    p = ProductTranslationCreate(
        name="Válvula bola",
        meta_title="MT — válvula bola PN16",
        meta_description="Producto MT de la familia válvulas.",
    )
    assert p.status == "draft"


def test_translation_patch_only_seo_field() -> None:
    p = ProductTranslationPatch(meta_title="Updated SEO title")
    assert p.meta_title == "Updated SEO title"


def test_translation_patch_empty_rejected() -> None:
    with pytest.raises(ValidationError, match="vacío"):
        ProductTranslationPatch()


def test_translation_response_includes_seo_fields() -> None:
    fields = set(ProductTranslationResponse.model_fields.keys())
    assert {
        "meta_title",
        "meta_description",
        "applications_text",
        "technical_limits",
        "notes",
        "marketing_features",
    } <= fields
