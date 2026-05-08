"""Wave 5 — unit tests for ParentResolver (validation + fallback resolution)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.products.parent_resolver import (
    CycleError,
    DepthExceededError,
    ParentNotFoundError,
    ParentResolver,
)


def _session_with_first(row: object | None) -> AsyncMock:
    """Build an AsyncMock session whose `execute().first()` returns `row`."""
    session = AsyncMock()
    result = MagicMock()
    result.first.return_value = row
    session.execute = AsyncMock(return_value=result)
    return session


def _session_with_scalar(value: object | None) -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    session.execute = AsyncMock(return_value=result)
    return session


# ---- validate_parent_link ----------------------------------------------------

@pytest.mark.asyncio
async def test_parent_link_none_is_noop() -> None:
    resolver = ParentResolver(AsyncMock())
    await resolver.validate_parent_link("MTV-100-DN15", None)


@pytest.mark.asyncio
async def test_parent_link_self_cycle_rejected() -> None:
    resolver = ParentResolver(AsyncMock())
    with pytest.raises(CycleError):
        await resolver.validate_parent_link("MTV-100", "MTV-100")


@pytest.mark.asyncio
async def test_parent_link_parent_not_found() -> None:
    session = _session_with_first(None)
    resolver = ParentResolver(session)
    with pytest.raises(ParentNotFoundError):
        await resolver.validate_parent_link("MTV-100-DN15", "MTV-NOPE")


@pytest.mark.asyncio
async def test_parent_link_depth_exceeded_when_parent_is_variant() -> None:
    parent_row = SimpleNamespace(sku="MTV-MID", parent_sku="MTV-ROOT", is_variant=True)
    session = _session_with_first(parent_row)
    resolver = ParentResolver(session)
    with pytest.raises(DepthExceededError):
        await resolver.validate_parent_link("MTV-CHILD", "MTV-MID")


@pytest.mark.asyncio
async def test_parent_link_valid_parent_passes() -> None:
    parent_row = SimpleNamespace(sku="MTV-100", parent_sku=None, is_variant=False)
    session = _session_with_first(parent_row)
    resolver = ParentResolver(session)
    await resolver.validate_parent_link("MTV-100-DN15", "MTV-100")


# ---- resolve_assets ----------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_assets_uses_own_when_present() -> None:
    session = AsyncMock()
    own = [SimpleNamespace(sku="MTV-100-DN15", kind="photo")]
    own_result = MagicMock()
    own_result.scalars.return_value.all.return_value = own
    session.execute = AsyncMock(return_value=own_result)

    resolver = ParentResolver(session)
    assets, inherited = await resolver.resolve_assets("MTV-100-DN15", kind="photo")
    assert list(assets) == own
    assert inherited is None


@pytest.mark.asyncio
async def test_resolve_assets_falls_back_to_parent() -> None:
    session = AsyncMock()
    parent_assets = [SimpleNamespace(sku="MTV-100", kind="photo")]

    own_result = MagicMock()
    own_result.scalars.return_value.all.return_value = []
    parent_lookup_result = MagicMock()
    parent_lookup_result.scalar_one_or_none.return_value = "MTV-100"
    parent_assets_result = MagicMock()
    parent_assets_result.scalars.return_value.all.return_value = parent_assets

    session.execute = AsyncMock(
        side_effect=[own_result, parent_lookup_result, parent_assets_result]
    )

    resolver = ParentResolver(session)
    assets, inherited = await resolver.resolve_assets("MTV-100-DN15", kind="photo")
    assert list(assets) == parent_assets
    assert inherited == "MTV-100"


@pytest.mark.asyncio
async def test_resolve_assets_no_parent_returns_empty() -> None:
    session = AsyncMock()
    own_result = MagicMock()
    own_result.scalars.return_value.all.return_value = []
    parent_lookup_result = MagicMock()
    parent_lookup_result.scalar_one_or_none.return_value = None

    session.execute = AsyncMock(side_effect=[own_result, parent_lookup_result])

    resolver = ParentResolver(session)
    assets, inherited = await resolver.resolve_assets("MTV-STANDALONE")
    assert list(assets) == []
    assert inherited is None


# ---- resolve_translations ----------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_translations_inherits_from_parent_when_empty() -> None:
    session = AsyncMock()
    parent_translations = [SimpleNamespace(sku="MTV-100", lang="es")]

    own_result = MagicMock()
    own_result.scalars.return_value.all.return_value = []
    parent_lookup_result = MagicMock()
    parent_lookup_result.scalar_one_or_none.return_value = "MTV-100"
    parent_tr_result = MagicMock()
    parent_tr_result.scalars.return_value.all.return_value = parent_translations

    session.execute = AsyncMock(
        side_effect=[own_result, parent_lookup_result, parent_tr_result]
    )

    resolver = ParentResolver(session)
    translations, inherited = await resolver.resolve_translations("MTV-100-DN15")
    assert list(translations) == parent_translations
    assert inherited == "MTV-100"


# ---- resolve_specs -----------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_specs_merges_parent_under_own() -> None:
    session = AsyncMock()
    own_row = SimpleNamespace(specs={"a": 1, "b": 2}, parent_sku="MTV-100")
    parent_specs = {"b": 99, "c": 3}

    own_result = MagicMock()
    own_result.first.return_value = own_row
    parent_result = MagicMock()
    parent_result.scalar_one_or_none.return_value = parent_specs

    session.execute = AsyncMock(side_effect=[own_result, parent_result])

    resolver = ParentResolver(session)
    merged, inherited = await resolver.resolve_specs("MTV-100-DN15")
    # Own value 'b': 2 wins over parent 'b': 99; inherited 'c' from parent.
    assert merged == {"a": 1, "b": 2, "c": 3}
    assert inherited == "MTV-100"


@pytest.mark.asyncio
async def test_resolve_specs_no_parent_returns_own_only() -> None:
    session = AsyncMock()
    own_row = SimpleNamespace(specs={"x": 1}, parent_sku=None)
    own_result = MagicMock()
    own_result.first.return_value = own_row
    session.execute = AsyncMock(return_value=own_result)

    resolver = ParentResolver(session)
    merged, inherited = await resolver.resolve_specs("MTV-STANDALONE")
    assert merged == {"x": 1}
    assert inherited is None


@pytest.mark.asyncio
async def test_resolve_specs_unknown_sku_returns_empty() -> None:
    session = _session_with_first(None)
    resolver = ParentResolver(session)
    merged, inherited = await resolver.resolve_specs("UNKNOWN")
    assert merged == {}
    assert inherited is None


# ---- recompute_parent_flags --------------------------------------------------

@pytest.mark.asyncio
async def test_recompute_flags_marks_self_variant_when_parent_set() -> None:
    session = AsyncMock()
    sku_lookup = MagicMock()
    sku_lookup.scalar_one_or_none.return_value = "MTV-100"
    update_self = MagicMock()
    update_parent = MagicMock()
    session.execute = AsyncMock(side_effect=[sku_lookup, update_self, update_parent])

    resolver = ParentResolver(session)
    await resolver.recompute_parent_flags("MTV-100-DN15")

    # 3 calls: read parent_sku, update self, update parent.
    assert session.execute.await_count == 3


@pytest.mark.asyncio
async def test_recompute_flags_clears_variant_when_parent_null() -> None:
    session = AsyncMock()
    sku_lookup = MagicMock()
    sku_lookup.scalar_one_or_none.return_value = None
    update_self = MagicMock()
    session.execute = AsyncMock(side_effect=[sku_lookup, update_self])

    resolver = ParentResolver(session)
    await resolver.recompute_parent_flags("MTV-STANDALONE")

    # Only 2 calls (no parent update).
    assert session.execute.await_count == 2
