"""Unit tests para CompatibilityService — sin DB.

Cobertura:
1.  Happy path: add_link simple (spare_part).
2.  Happy path: remove_link.
3.  Bidireccional: add replaces crea replaced_by.
4.  Bidireccional: add replaced_by crea replaces.
5.  Bidireccional: remove replaces elimina replaced_by.
6.  Rechazo de self-loop.
7.  Rechazo de duplicate (IntegrityError del repo).
8.  Rechazo de compatible_with_sku inexistente.
9.  Rechazo de product_sku inexistente.
10. list_for_product con SKU que no existe → CompatibilitySkuNotFoundError.
11. list_inverse con SKU válido retorna lista.
12. replace_all_for_product bulk.
13. replace_all_for_product con self-loop en lista.
14. remove_link con enlace inexistente → CompatibilityNotFoundError.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.services.compatibility.compatibility_service import (
    CompatibilityDomainError,
    CompatibilityDuplicateError,
    CompatibilityNotFoundError,
    CompatibilitySelfLoopError,
    CompatibilityService,
    CompatibilitySkuNotFoundError,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeProduct:
    def __init__(self, sku: str) -> None:
        self.sku = sku
        self.name_en = f"Product {sku}"
        self.family = "valves"
        self.images = []


class _FakeLink:
    def __init__(
        self,
        product_sku: str,
        compatible_with_sku: str,
        kind: str,
        notes: str | None = None,
        position: int = 0,
    ) -> None:
        self.id = uuid4()
        self.product_sku = product_sku
        self.compatible_with_sku = compatible_with_sku
        self.kind = kind
        self.notes = notes
        self.position = position
        self.created_at = None
        self.created_by = None
        self.compatible_with = _FakeProduct(compatible_with_sku)


def _make_service(
    *,
    products: dict[str, _FakeProduct] | None = None,
    existing_links: list[_FakeLink] | None = None,
) -> tuple[CompatibilityService, Any, Any, Any]:
    """Construye servicio con repos mockeados.

    Retorna (service, compat_repo_mock, product_repo_mock, audit_mock).
    """
    products = products or {}
    existing_links = existing_links or []

    session = MagicMock()

    compat_repo = MagicMock()
    product_repo = MagicMock()
    audit_repo = MagicMock()

    # product_repo.get_by_sku
    async def _get_by_sku(sku: str):
        return products.get(sku)

    product_repo.get_by_sku = AsyncMock(side_effect=_get_by_sku)

    # audit.record
    audit_repo.record = AsyncMock()

    svc = CompatibilityService(session)
    svc._repo = compat_repo
    svc._product_repo = product_repo
    svc._audit = audit_repo

    return svc, compat_repo, product_repo, audit_repo


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_link_simple_spare_part() -> None:
    """Happy path: add_link spare_part retorna el enlace."""
    p_a = _FakeProduct("MT-A-001")
    p_b = _FakeProduct("MT-B-002")
    svc, repo, _, audit = _make_service(products={"MT-A-001": p_a, "MT-B-002": p_b})

    fake_link = _FakeLink("MT-A-001", "MT-B-002", "spare_part")
    repo.add_link = AsyncMock(return_value=fake_link)

    link = await svc.add_link("MT-A-001", "MT-B-002", "spare_part")

    repo.add_link.assert_awaited_once()
    audit.record.assert_awaited_once()
    assert link.kind == "spare_part"


@pytest.mark.asyncio
async def test_remove_link_happy_path() -> None:
    """Happy path: remove_link devuelve sin excepción."""
    p_a = _FakeProduct("MT-A-001")
    p_b = _FakeProduct("MT-B-002")
    svc, repo, _, audit = _make_service(products={"MT-A-001": p_a, "MT-B-002": p_b})
    repo.remove_link = AsyncMock(return_value=True)

    await svc.remove_link("MT-A-001", "MT-B-002", "spare_part")

    repo.remove_link.assert_awaited_once()
    audit.record.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_replaces_creates_inverse() -> None:
    """add_link replaces delega al repo que crea el inverso replaced_by."""
    p_a = _FakeProduct("MT-A-001")
    p_b = _FakeProduct("MT-B-002")
    svc, repo, _, _ = _make_service(products={"MT-A-001": p_a, "MT-B-002": p_b})

    fake_link = _FakeLink("MT-A-001", "MT-B-002", "replaces")
    repo.add_link = AsyncMock(return_value=fake_link)

    await svc.add_link("MT-A-001", "MT-B-002", "replaces")

    # El servicio llama a repo.add_link con kind="replaces";
    # el repo es responsable del inverso.
    call_args = repo.add_link.call_args
    assert call_args.args[2] == "replaces"


@pytest.mark.asyncio
async def test_add_replaced_by_delegates_to_repo() -> None:
    """add_link replaced_by funciona simétrico."""
    p_a = _FakeProduct("MT-A-001")
    p_b = _FakeProduct("MT-B-002")
    svc, repo, _, _ = _make_service(products={"MT-A-001": p_a, "MT-B-002": p_b})

    fake_link = _FakeLink("MT-A-001", "MT-B-002", "replaced_by")
    repo.add_link = AsyncMock(return_value=fake_link)

    link = await svc.add_link("MT-A-001", "MT-B-002", "replaced_by")
    assert link.kind == "replaced_by"


@pytest.mark.asyncio
async def test_remove_replaces_delegates_bidirectional() -> None:
    """remove_link replaces — delega al repo con kind='replaces'."""
    p_a = _FakeProduct("MT-A-001")
    p_b = _FakeProduct("MT-B-002")
    svc, repo, _, _ = _make_service(products={"MT-A-001": p_a, "MT-B-002": p_b})
    repo.remove_link = AsyncMock(return_value=True)

    await svc.remove_link("MT-A-001", "MT-B-002", "replaces")

    call_args = repo.remove_link.call_args
    assert call_args.args[2] == "replaces"


@pytest.mark.asyncio
async def test_self_loop_rejected() -> None:
    """add_link con product_sku == compatible_with_sku lanza CompatibilitySelfLoopError."""
    p_a = _FakeProduct("MT-A-001")
    svc, _, _, _ = _make_service(products={"MT-A-001": p_a})

    with pytest.raises(CompatibilitySelfLoopError):
        await svc.add_link("MT-A-001", "MT-A-001", "spare_part")


@pytest.mark.asyncio
async def test_duplicate_raises_duplicate_error() -> None:
    """Cuando el repo lanza IntegrityError, el servicio lo traduce a CompatibilityDuplicateError."""
    p_a = _FakeProduct("MT-A-001")
    p_b = _FakeProduct("MT-B-002")
    svc, repo, _, _ = _make_service(products={"MT-A-001": p_a, "MT-B-002": p_b})
    repo.add_link = AsyncMock(side_effect=IntegrityError(None, None, Exception("unique")))

    with pytest.raises(CompatibilityDuplicateError):
        await svc.add_link("MT-A-001", "MT-B-002", "spare_part")


@pytest.mark.asyncio
async def test_compatible_with_sku_not_found() -> None:
    """compatible_with_sku inexistente lanza CompatibilitySkuNotFoundError."""
    p_a = _FakeProduct("MT-A-001")
    svc, _, _, _ = _make_service(products={"MT-A-001": p_a})
    # MT-B-999 no está en products dict.

    with pytest.raises(CompatibilitySkuNotFoundError) as exc_info:
        await svc.add_link("MT-A-001", "MT-B-999", "accessory")

    assert "MT-B-999" in exc_info.value.message


@pytest.mark.asyncio
async def test_product_sku_not_found() -> None:
    """product_sku inexistente lanza CompatibilitySkuNotFoundError."""
    p_b = _FakeProduct("MT-B-002")
    svc, _, _, _ = _make_service(products={"MT-B-002": p_b})

    with pytest.raises(CompatibilitySkuNotFoundError) as exc_info:
        await svc.add_link("MT-X-999", "MT-B-002", "spare_part")

    assert "MT-X-999" in exc_info.value.message


@pytest.mark.asyncio
async def test_list_for_product_sku_not_found() -> None:
    """list_for_product con SKU inexistente lanza CompatibilitySkuNotFoundError."""
    svc, _, _, _ = _make_service(products={})

    with pytest.raises(CompatibilitySkuNotFoundError):
        await svc.list_for_product("MT-NONEXIST")


@pytest.mark.asyncio
async def test_list_inverse_returns_list() -> None:
    """list_inverse devuelve la lista del repo."""
    p_a = _FakeProduct("MT-A-001")
    svc, repo, _, _ = _make_service(products={"MT-A-001": p_a})
    fake_links = [_FakeLink("MT-B-002", "MT-A-001", "spare_part")]
    repo.list_inverse = AsyncMock(return_value=fake_links)

    result = await svc.list_inverse("MT-A-001")

    assert len(result) == 1
    assert result[0].compatible_with_sku == "MT-A-001"


@pytest.mark.asyncio
async def test_replace_all_bulk() -> None:
    """replace_all_for_product crea múltiples enlaces."""
    p_a = _FakeProduct("MT-A-001")
    p_b = _FakeProduct("MT-B-002")
    p_c = _FakeProduct("MT-C-003")
    svc, repo, _, audit = _make_service(
        products={"MT-A-001": p_a, "MT-B-002": p_b, "MT-C-003": p_c}
    )

    fake_created = [
        _FakeLink("MT-A-001", "MT-B-002", "spare_part"),
        _FakeLink("MT-A-001", "MT-C-003", "accessory"),
    ]
    repo.replace_all_for_product = AsyncMock(return_value=fake_created)

    links = [
        {"compatible_with_sku": "MT-B-002", "kind": "spare_part", "notes": None, "position": 0},
        {"compatible_with_sku": "MT-C-003", "kind": "accessory", "notes": None, "position": 1},
    ]
    result = await svc.replace_all_for_product("MT-A-001", links)

    assert len(result) == 2
    audit.record.assert_awaited_once()


@pytest.mark.asyncio
async def test_replace_all_self_loop_in_list() -> None:
    """replace_all_for_product rechaza self-loop en cualquier item de la lista."""
    p_a = _FakeProduct("MT-A-001")
    svc, _, _, _ = _make_service(products={"MT-A-001": p_a})

    links = [
        {"compatible_with_sku": "MT-A-001", "kind": "spare_part", "notes": None, "position": 0},
    ]
    with pytest.raises(CompatibilitySelfLoopError):
        await svc.replace_all_for_product("MT-A-001", links)


@pytest.mark.asyncio
async def test_remove_link_not_found() -> None:
    """remove_link con enlace inexistente lanza CompatibilityNotFoundError."""
    p_a = _FakeProduct("MT-A-001")
    p_b = _FakeProduct("MT-B-002")
    svc, repo, _, _ = _make_service(products={"MT-A-001": p_a, "MT-B-002": p_b})
    repo.remove_link = AsyncMock(return_value=False)  # no rows deleted

    with pytest.raises(CompatibilityNotFoundError):
        await svc.remove_link("MT-A-001", "MT-B-002", "spare_part")


# ---------------------------------------------------------------------------
# Fase 5 — list_for_owner + DN range + list_spare_parts_for_series
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_link_propagates_owner_type_and_dn() -> None:
    """add_link Fase 5 propaga owner_type + dn_min/dn_max al repo."""
    p_a = _FakeProduct("MT-A-001")
    p_b = _FakeProduct("MT-KIT-001")
    svc, repo, _, _ = _make_service(products={"MT-A-001": p_a, "MT-KIT-001": p_b})
    fake_link = _FakeLink("MT-A-001", "MT-KIT-001", "spare_part")
    repo.add_link = AsyncMock(return_value=fake_link)

    await svc.add_link(
        "MT-A-001",
        "MT-KIT-001",
        "spare_part",
        owner_type="series",
        dn_min=15,
        dn_max=50,
    )

    kwargs = repo.add_link.call_args.kwargs
    assert kwargs["owner_type"] == "series"
    assert kwargs["dn_min"] == 15
    assert kwargs["dn_max"] == 50


@pytest.mark.asyncio
async def test_add_link_rejects_dn_max_less_than_min() -> None:
    """add_link con dn_max < dn_min → CompatibilityDomainError 422."""
    p_a = _FakeProduct("MT-A-001")
    p_b = _FakeProduct("MT-KIT-002")
    svc, _, _, _ = _make_service(products={"MT-A-001": p_a, "MT-KIT-002": p_b})

    with pytest.raises(CompatibilityDomainError) as exc:
        await svc.add_link(
            "MT-A-001",
            "MT-KIT-002",
            "spare_part",
            dn_min=50,
            dn_max=15,
        )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_list_for_owner_product_validates_sku() -> None:
    """list_for_owner con owner_type='product' valida SKU existente."""
    svc, _, _, _ = _make_service(products={})  # no products

    with pytest.raises(CompatibilitySkuNotFoundError):
        await svc.list_for_owner("product", "MT-NOPE")


@pytest.mark.asyncio
async def test_list_for_owner_series_no_sku_check() -> None:
    """list_for_owner con owner_type='series' NO valida existencia en products."""
    svc, repo, _, _ = _make_service(products={})
    fake_links = [
        _FakeLink("series-pn40", "MT-KIT-A", "spare_part"),
    ]
    repo.list_for_owner = AsyncMock(return_value=fake_links)

    rows = await svc.list_for_owner("series", "series-pn40")
    assert len(rows) == 1
    repo.list_for_owner.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_for_owner_invalid_type_rejected() -> None:
    """owner_type fuera del set permitido → 422."""
    svc, _, _, _ = _make_service(products={})

    with pytest.raises(CompatibilityDomainError) as exc:
        await svc.list_for_owner("invalid_kind", "x")
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_list_for_owner_passes_dn_filter_to_repo() -> None:
    """list_for_owner propaga dn al repo (filtro de rango)."""
    svc, repo, _, _ = _make_service(products={})
    repo.list_for_owner = AsyncMock(return_value=[])

    await svc.list_for_owner("series", "series-pn40", dn=32)

    kwargs = repo.list_for_owner.call_args.kwargs
    assert kwargs["dn"] == 32


@pytest.mark.asyncio
async def test_list_spare_parts_for_series_shortcut() -> None:
    """list_spare_parts_for_series llama al repo con kind='spare_part'."""
    svc, repo, _, _ = _make_service(products={})
    repo.list_for_owner = AsyncMock(return_value=[])

    await svc.list_spare_parts_for_series("series-pn40", dn=25)

    call_args = repo.list_for_owner.call_args
    assert call_args.args[0] == "series"
    assert call_args.args[1] == "series-pn40"
    assert call_args.kwargs["kind"] == "spare_part"
    assert call_args.kwargs["dn"] == 25
