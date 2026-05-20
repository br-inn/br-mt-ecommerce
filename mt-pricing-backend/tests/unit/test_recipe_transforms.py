import pytest

from app.services.scraper.recipe_transforms import apply_transform


def test_none_transform_is_identity():
    assert apply_transform(None, "  hola ") == "  hola "


def test_regex_capture_returns_group_one():
    t = {"op": "regex_capture", "pattern": r"ASIN:\s*(\w+)"}
    assert apply_transform(t, "ASIN: B0CXYZ123 end") == "B0CXYZ123"


def test_regex_capture_no_match_returns_empty():
    t = {"op": "regex_capture", "pattern": r"(\d{4})"}
    assert apply_transform(t, "sin numeros") == ""


def test_strip_currency_keeps_digits():
    t = {"op": "strip_currency"}
    assert apply_transform(t, "AED 1,234.50") == "1234.50"


def test_replace():
    t = {"op": "replace", "find": " AED", "replace_with": ""}
    assert apply_transform(t, "99 AED") == "99"


def test_map_values():
    t = {"op": "map_values", "mapping": {"In Stock": "true", "Out": "false"}}
    assert apply_transform(t, "In Stock") == "true"
    assert apply_transform(t, "Desconocido") == "Desconocido"


def test_unit_factor_multiplies():
    t = {"op": "unit_factor", "factor": 0.0689476}
    assert float(apply_transform(t, "100 PSI")) == pytest.approx(6.89476)


def test_unknown_op_raises():
    with pytest.raises(ValueError, match="Unknown transform op"):
        apply_transform({"op": "nuke"}, "x")
