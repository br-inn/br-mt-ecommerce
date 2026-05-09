"""Smoke tests — Stage 3 Pydantic schemas (divisions, series, materials)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.vocabularies import (
    DivisionCreate,
    DivisionPatch,
    MaterialCreate,
    SeriesCreate,
    SeriesPatch,
    SeriesTierCreate,
    SeriesTranslationUpsert,
)


# ---------------------------------------------------------------------------
# Division
# ---------------------------------------------------------------------------
class TestDivisionSchemas:
    def test_create_minimal(self) -> None:
        d = DivisionCreate(code="hidrosanitario", name="Hidrosanitario")
        assert d.code == "hidrosanitario"
        assert d.active is True
        assert d.sort_order == 0

    def test_create_rejects_uppercase_code(self) -> None:
        with pytest.raises(ValidationError):
            DivisionCreate(code="Hidrosanitario", name="x")

    def test_create_rejects_empty_name(self) -> None:
        with pytest.raises(ValidationError):
            DivisionCreate(code="industrial", name="")

    def test_patch_partial(self) -> None:
        p = DivisionPatch(name="New name")
        dumped = p.model_dump(exclude_unset=True)
        assert dumped == {"name": "New name"}


# ---------------------------------------------------------------------------
# SeriesTier
# ---------------------------------------------------------------------------
class TestSeriesTierSchemas:
    def test_create_with_rank(self) -> None:
        t = SeriesTierCreate(code="platinum", name="Platinum", rank=1)
        assert t.rank == 1

    def test_rank_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            SeriesTierCreate(code="x", name="X", rank=0)
        with pytest.raises(ValidationError):
            SeriesTierCreate(code="x", name="X", rank=100)


# ---------------------------------------------------------------------------
# Series
# ---------------------------------------------------------------------------
class TestSeriesSchemas:
    def test_create_minimal(self) -> None:
        s = SeriesCreate(code="pn40_platinum", name_en="PN40 Platinum Series")
        assert s.bullets_en == []
        assert s.features_tags == []
        assert s.tier_id is None

    def test_create_with_pressure_rating(self) -> None:
        s = SeriesCreate(
            code="pn40_platinum",
            name_en="PN40 Platinum",
            pressure_rating_pn=40,
            features_tags=["nofrost", "solar_ready"],
            bullets_en=["Latón DZR CW602N", "Sistema antihielo"],
        )
        assert s.pressure_rating_pn == 40
        assert "nofrost" in s.features_tags

    def test_pressure_rating_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SeriesCreate(
                code="x", name_en="X", pressure_rating_pn=-1
            )

    def test_temperature_bounds(self) -> None:
        s = SeriesCreate(
            code="x",
            name_en="X",
            temperature_min_c=-20,
            temperature_max_c=180,
        )
        assert s.temperature_min_c == -20
        assert s.temperature_max_c == 180

    def test_patch_with_tier_id(self) -> None:
        tid = uuid4()
        p = SeriesPatch(tier_id=tid)
        assert p.tier_id == tid


# ---------------------------------------------------------------------------
# SeriesTranslationUpsert
# ---------------------------------------------------------------------------
class TestSeriesTranslationSchemas:
    def test_lang_es(self) -> None:
        t = SeriesTranslationUpsert(
            lang="es",
            name="PN40 Platinum",
            bullets=["Latón DZR", "Sistema antihielo"],
        )
        assert t.lang == "es"

    def test_invalid_lang(self) -> None:
        with pytest.raises(ValidationError):
            SeriesTranslationUpsert(lang="fr", name="x")

    def test_lang_must_be_lowercase(self) -> None:
        with pytest.raises(ValidationError):
            SeriesTranslationUpsert(lang="ES", name="x")


# ---------------------------------------------------------------------------
# Material
# ---------------------------------------------------------------------------
class TestMaterialSchemas:
    def test_create_with_family_kind(self) -> None:
        m = MaterialCreate(
            code="laton", name="Latón", family_kind="metal", sort_order=10
        )
        assert m.family_kind == "metal"

    def test_create_invalid_code(self) -> None:
        with pytest.raises(ValidationError):
            MaterialCreate(code="LATÓN", name="Latón")
