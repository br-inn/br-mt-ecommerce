"""Unit tests for SpecsRegistry — loader and fallback chain.

All tests are pure unit — no IO beyond the bundled schemas/ directory.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.specs.specs_registry import SpecsRegistry

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry(tmp_path: Path, schemas: dict[str, dict]) -> SpecsRegistry:
    """Write *schemas* as JSON files into *tmp_path* and return a fresh registry."""
    for key, schema in schemas.items():
        (tmp_path / f"{key}.json").write_text(json.dumps(schema), encoding="utf-8")
    return SpecsRegistry(schemas_dir=tmp_path)


# ---------------------------------------------------------------------------
# Tests — loader
# ---------------------------------------------------------------------------


def test_registry_loads_bundled_schemas() -> None:
    """The shipped schemas dir must contain _default, valve_ball, and filter."""
    reg = SpecsRegistry()  # uses real schemas dir
    keys = reg.list_keys()
    assert "_default" in keys
    assert "valve_ball" in keys
    assert "filter" in keys


def test_registry_loads_json_content(tmp_path: Path) -> None:
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}
    reg = _make_registry(tmp_path, {"my_family": schema})
    result = reg.get_schema_by_key("my_family")
    assert result is not None
    assert result["type"] == "object"


def test_registry_skips_invalid_json(tmp_path: Path) -> None:
    (tmp_path / "bad.json").write_text("{not valid json", encoding="utf-8")
    (tmp_path / "_default.json").write_text('{"type":"object"}', encoding="utf-8")
    reg = SpecsRegistry(schemas_dir=tmp_path)
    # bad.json skipped; _default still loads
    assert reg.get_schema_by_key("bad") is None
    assert reg.get_schema_by_key("_default") is not None


def test_registry_returns_empty_for_missing_dir(tmp_path: Path) -> None:
    missing = tmp_path / "nonexistent"
    reg = SpecsRegistry(schemas_dir=missing)
    schema = reg.get_schema("anything")
    assert schema == {}


def test_list_keys_is_sorted(tmp_path: Path) -> None:
    reg = _make_registry(tmp_path, {"z_fam": {}, "a_fam": {}, "_default": {}})
    keys = reg.list_keys()
    assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# Tests — fallback chain
# ---------------------------------------------------------------------------


def test_fallback_family_subfamily_exact_match(tmp_path: Path) -> None:
    reg = _make_registry(
        tmp_path,
        {
            "valve_ball": {"type": "object", "title": "BallValve"},
            "valve": {"type": "object", "title": "GenericValve"},
            "_default": {"type": "object", "title": "Default"},
        },
    )
    schema = reg.get_schema("valve", "ball")
    assert schema["title"] == "BallValve"


def test_fallback_family_level_when_no_subfamily_schema(tmp_path: Path) -> None:
    reg = _make_registry(
        tmp_path,
        {
            "valve": {"type": "object", "title": "GenericValve"},
            "_default": {"type": "object", "title": "Default"},
        },
    )
    schema = reg.get_schema("valve", "gate")
    assert schema["title"] == "GenericValve"


def test_fallback_default_when_no_family_schema(tmp_path: Path) -> None:
    reg = _make_registry(
        tmp_path,
        {
            "_default": {"type": "object", "title": "Default"},
        },
    )
    schema = reg.get_schema("unknown_family", "unknown_sub")
    assert schema["title"] == "Default"


def test_fallback_default_when_no_subfamily_given(tmp_path: Path) -> None:
    reg = _make_registry(
        tmp_path,
        {
            "_default": {"type": "object", "title": "Default"},
        },
    )
    schema = reg.get_schema("filter")
    assert schema["title"] == "Default"


def test_exact_key_lookup_returns_none_for_missing(tmp_path: Path) -> None:
    reg = _make_registry(tmp_path, {"_default": {}})
    assert reg.get_schema_by_key("nonexistent") is None


def test_singleton_reset(tmp_path: Path) -> None:
    SpecsRegistry.reset_instance()
    inst1 = SpecsRegistry.get_instance(schemas_dir=tmp_path)
    inst2 = SpecsRegistry.get_instance()  # should return same instance
    assert inst1 is inst2
    SpecsRegistry.reset_instance()  # cleanup for other tests
