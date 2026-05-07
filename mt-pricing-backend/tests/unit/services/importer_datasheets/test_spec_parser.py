"""Unit tests para `app.services.importer_datasheets.spec_parser`."""

from __future__ import annotations

import pytest

from app.services.importer_datasheets.spec_parser import (
    parse_datasheet_filename,
    parse_specs_from_text,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Filename
# ---------------------------------------------------------------------------
def test_filename_mtft_single_suffix() -> None:
    res = parse_datasheet_filename("MTFT_5114.pdf")
    assert res.ok
    assert res.kind == "ficha_tecnica"
    assert res.sku_suffixes == ["5114"]


def test_filename_mtce_compliance() -> None:
    res = parse_datasheet_filename("MTCE_001.pdf")
    assert res.ok
    assert res.kind == "compliance"


def test_filename_mtman_manual() -> None:
    res = parse_datasheet_filename("MTMAN_2024.pdf")
    assert res.ok
    assert res.kind == "manual"


def test_filename_multi_sku() -> None:
    res = parse_datasheet_filename("MTFT_5114-5115-5116.pdf")
    assert res.ok
    assert res.sku_suffixes == ["5114", "5115", "5116"]


def test_filename_invalid_no_prefix() -> None:
    res = parse_datasheet_filename("random.pdf")
    assert not res.ok
    assert res.error and "MT(FT|CE|MAN)" in res.error


def test_filename_case_insensitive_prefix() -> None:
    res = parse_datasheet_filename("mtft_500.pdf")
    assert res.ok
    assert res.kind == "ficha_tecnica"


def test_filename_with_path() -> None:
    res = parse_datasheet_filename("/uploads/MTFT_500.pdf")
    assert res.ok


# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------
def test_specs_dn_pn_extracted() -> None:
    specs = parse_specs_from_text("Body: brass DN 50 PN16")
    assert specs.dn == "DN50"
    assert specs.pn == "PN16"


def test_specs_material_canonical() -> None:
    specs = parse_specs_from_text("Material body: Brass CW617N")
    # Con "cw617n" canonicalizamos a brass_cw617n (más específico que brass).
    assert specs.material == "brass_cw617n"


def test_specs_seal_canonical() -> None:
    specs = parse_specs_from_text("Sealing: EPDM rubber")
    assert specs.seal == "epdm"


def test_specs_empty_text_returns_empty() -> None:
    specs = parse_specs_from_text("")
    assert specs.is_empty


def test_specs_pn_without_digit_ignored() -> None:
    specs = parse_specs_from_text("PNFOO is not a real spec")
    assert specs.pn is None


def test_specs_to_dict_skips_none() -> None:
    specs = parse_specs_from_text("DN25")
    d = specs.to_dict()
    assert d == {"dn": "DN25"}


def test_specs_extracts_seal_viton_as_fkm_alternative() -> None:
    specs = parse_specs_from_text("Sealing material: Viton")
    assert specs.seal == "viton"
