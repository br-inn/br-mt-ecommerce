"""Test that Product has model_id attribute (pure Python, no DB)."""

from sqlalchemy import inspect as sa_inspect

from app.db.models.product import Product


def test_product_has_model_id():
    mapper = sa_inspect(Product)
    col_names = {c.key for c in mapper.mapper.column_attrs}
    assert "model_id" in col_names, "model_id column not found on Product mapper"
