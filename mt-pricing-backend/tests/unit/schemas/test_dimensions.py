"""Unit tests for Pydantic schemas — Fase 3 dimension tables + P-T points.

Covers:
- StandardCreate / Patch validations (code pattern, edition default).
- DimensionColumnCreate code pattern + label/unit lengths.
- DimensionCellCreate model validator (requires value_number or value_text).
- DimensionRowCreate with nested cells.
- PressureTemperaturePointCreate non-negative pressure + decimal handling.
- Composite responses (DimensionTableResponse, PressureTemperatureCurveResponse).
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.dimensions import (
    ActuationCodeResponse,
    DimensionCellCreate,
    DimensionCellPatch,
    DimensionCellResponse,
    DimensionColumnCreate,
    DimensionColumnPatch,
    DimensionColumnResponse,
    DimensionRowCreate,
    DimensionRowPatch,
    DimensionRowWithCells,
    DimensionTableResponse,
    PressureTemperatureCurveResponse,
    PressureTemperaturePointCreate,
    PressureTemperaturePointPatch,
    PressureTemperaturePointResponse,
    StandardCreate,
    StandardPatch,
)

pytestmark = pytest.mark.unit


# ===========================================================================
# StandardCreate / Patch
# ===========================================================================
class TestStandardCreate:
    def test_valid_minimal(self) -> None:
        m = StandardCreate(code="ASTM A105", title_en="Carbon steel forgings")
        assert m.code == "ASTM A105"
        assert m.edition == ""
        assert m.reference_url is None

    def test_valid_full(self) -> None:
        m = StandardCreate(
            code="EN 10204",
            edition="2004",
            title_en="Inspection documents",
            reference_url="https://example.com/en10204",
        )
        assert m.edition == "2004"

    def test_invalid_code_pattern_empty(self) -> None:
        with pytest.raises(ValidationError):
            StandardCreate(code="", title_en="X")

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            StandardCreate(
                code="ISO 5211",
                title_en="X",
                extra="nope",  # type: ignore[call-arg]
            )


class TestStandardPatch:
    def test_partial(self) -> None:
        m = StandardPatch(edition="2015")
        assert m.edition == "2015"
        assert m.code is None


# ===========================================================================
# DimensionColumnCreate
# ===========================================================================
class TestDimensionColumnCreate:
    def test_valid(self) -> None:
        m = DimensionColumnCreate(
            code="dn",
            label_en="Nominal DN",
            unit="mm",
            order_index=10,
        )
        assert m.code == "dn"
        assert m.order_index == 10

    def test_invalid_code_starts_with_digit(self) -> None:
        with pytest.raises(ValidationError):
            DimensionColumnCreate(code="1dn", label_en="X")

    def test_order_index_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DimensionColumnCreate(code="dn", label_en="X", order_index=-1)


class TestDimensionColumnPatch:
    def test_only_label(self) -> None:
        m = DimensionColumnPatch(label_en="Updated label")
        assert m.label_en == "Updated label"
        assert m.unit is None


# ===========================================================================
# DimensionCellCreate / Patch
# ===========================================================================
class TestDimensionCellCreate:
    def test_valid_numeric(self) -> None:
        m = DimensionCellCreate(column_id=uuid4(), value_number=Decimal("42.5"))
        assert m.value_number == Decimal("42.5")
        assert m.value_text is None

    def test_valid_text(self) -> None:
        m = DimensionCellCreate(column_id=uuid4(), value_text="N/A")
        assert m.value_text == "N/A"

    def test_no_value_raises(self) -> None:
        with pytest.raises(ValidationError):
            DimensionCellCreate(column_id=uuid4())

    def test_empty_text_only_raises(self) -> None:
        with pytest.raises(ValidationError):
            DimensionCellCreate(column_id=uuid4(), value_text="")


class TestDimensionCellPatch:
    def test_valid(self) -> None:
        m = DimensionCellPatch(value_number=Decimal("1"))
        assert m.value_number == Decimal("1")

    def test_empty_raises(self) -> None:
        with pytest.raises(ValidationError):
            DimensionCellPatch()


# ===========================================================================
# DimensionRowCreate
# ===========================================================================
class TestDimensionRowCreate:
    def test_valid_minimal(self) -> None:
        m = DimensionRowCreate(size_label="DN50", dn=50)
        assert m.dn == 50
        assert m.cells == []

    def test_valid_with_cells(self) -> None:
        col_id = uuid4()
        m = DimensionRowCreate(
            size_label="DN50",
            dn=50,
            cells=[DimensionCellCreate(column_id=col_id, value_number=Decimal("100"))],
        )
        assert len(m.cells) == 1
        assert m.cells[0].column_id == col_id

    def test_dn_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            DimensionRowCreate(dn=-1)

    def test_size_label_too_long(self) -> None:
        with pytest.raises(ValidationError):
            DimensionRowCreate(size_label="X" * 65)


class TestDimensionRowPatch:
    def test_partial(self) -> None:
        m = DimensionRowPatch(order_index=5)
        assert m.order_index == 5
        assert m.size_label is None


# ===========================================================================
# PressureTemperaturePointCreate / Patch
# ===========================================================================
class TestPressureTemperaturePointCreate:
    def test_valid(self) -> None:
        m = PressureTemperaturePointCreate(
            temperature_c=Decimal("20"),
            pressure_max_bar=Decimal("16"),
        )
        assert m.temperature_c == Decimal("20")
        assert m.pressure_max_bar == Decimal("16")
        assert m.series_variant_code is None

    def test_negative_pressure_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PressureTemperaturePointCreate(
                temperature_c=Decimal("0"),
                pressure_max_bar=Decimal("-1"),
            )

    def test_with_variant_and_condition(self) -> None:
        m = PressureTemperaturePointCreate(
            series_variant_code="PN16",
            temperature_c=Decimal("100"),
            pressure_max_bar=Decimal("10"),
            condition_en="saturated steam",
        )
        assert m.series_variant_code == "PN16"
        assert m.condition_en == "saturated steam"


class TestPressureTemperaturePointPatch:
    def test_partial(self) -> None:
        m = PressureTemperaturePointPatch(pressure_max_bar=Decimal("12.5"))
        assert m.pressure_max_bar == Decimal("12.5")
        assert m.temperature_c is None

    def test_patch_negative_pressure_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PressureTemperaturePointPatch(pressure_max_bar=Decimal("-0.01"))


# ===========================================================================
# Composite responses
# ===========================================================================
class TestDimensionTableResponse:
    def test_empty(self) -> None:
        m = DimensionTableResponse(
            product_sku="SKU-001",
            family_id=uuid4(),
            columns=[],
            rows=[],
        )
        assert m.product_sku == "SKU-001"
        assert m.columns == []
        assert m.rows == []

    def test_with_data(self) -> None:
        fam = uuid4()
        col = DimensionColumnResponse(
            id=uuid4(),
            family_id=fam,
            code="dn",
            label_en="Nominal DN",
            unit="mm",
            order_index=0,
        )
        from datetime import datetime, timezone

        row_id = uuid4()
        row = DimensionRowWithCells(
            id=row_id,
            product_sku="SKU-001",
            size_label="DN50",
            dn=50,
            actuation_code_id=None,
            order_index=0,
            created_at=datetime.now(tz=timezone.utc),
            cells=[
                DimensionCellResponse(
                    id=uuid4(),
                    row_id=row_id,
                    column_id=col.id,
                    value_number=Decimal("50"),
                    value_text=None,
                )
            ],
        )
        m = DimensionTableResponse(
            product_sku="SKU-001",
            family_id=fam,
            columns=[col],
            rows=[row],
        )
        assert len(m.columns) == 1
        assert len(m.rows) == 1
        assert m.rows[0].cells[0].value_number == Decimal("50")


class TestPressureTemperatureCurveResponse:
    def test_empty(self) -> None:
        m = PressureTemperatureCurveResponse(
            product_sku="SKU-001",
            series_variant_code=None,
            points=[],
        )
        assert m.points == []

    def test_with_points(self) -> None:
        from datetime import datetime, timezone

        p = PressureTemperaturePointResponse(
            id=uuid4(),
            product_sku="SKU-001",
            series_variant_code="PN16",
            temperature_c=Decimal("20"),
            pressure_max_bar=Decimal("16"),
            condition_en=None,
            order_index=0,
            created_at=datetime.now(tz=timezone.utc),
        )
        m = PressureTemperatureCurveResponse(
            product_sku="SKU-001",
            series_variant_code="PN16",
            points=[p],
        )
        assert len(m.points) == 1


# ===========================================================================
# ActuationCodeResponse (read-only)
# ===========================================================================
class TestActuationCodeResponse:
    def test_round_trip(self) -> None:
        from datetime import datetime, timezone

        m = ActuationCodeResponse(
            id=uuid4(),
            code="MR",
            name_en="Gearbox",
            type="gearbox",
            created_at=datetime.now(tz=timezone.utc),
        )
        assert m.type == "gearbox"

    def test_invalid_type(self) -> None:
        from datetime import datetime, timezone

        with pytest.raises(ValidationError):
            ActuationCodeResponse(
                id=uuid4(),
                code="X",
                name_en="X",
                type="bogus",  # type: ignore[arg-type]
                created_at=datetime.now(tz=timezone.utc),
            )
