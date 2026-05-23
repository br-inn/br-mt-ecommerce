"""Unit tests for ProductModel ORM — pure Python (no DB)."""

import uuid
from app.db.models.product_models import (
    ProductModel,
    ModelDimensionRow,
    ModelFlowData,
    ModelTechTable,
)


def test_product_model_instantiation():
    m = ProductModel(
        id=uuid.uuid4(),
        series_id=uuid.uuid4(),
        code="4295",
        color_label="red",
    )
    assert m.code == "4295"
    assert m.color_label == "red"
    assert m.variant_of_id is None


def test_model_dimension_row_jsonb_default():
    row = ModelDimensionRow(
        model_id=uuid.uuid4(),
        dn_mm=15,
        dimensions={},
    )
    assert row.dimensions == {}
    assert row.dn_secondary_mm is None


def test_model_flow_data_defaults():
    fd = ModelFlowData(
        model_id=uuid.uuid4(),
        dn_mm=25,
    )
    assert fd.kv is None
    assert fd.mesh_mm is None


def test_model_tech_table_kind():
    tt = ModelTechTable(
        model_id=uuid.uuid4(),
        kind="pt_curve",
        data={},
    )
    assert tt.kind == "pt_curve"
    assert tt.gasket_material is None
