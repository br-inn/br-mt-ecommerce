"""Wave 11 — DisplayPairService unit tests.

Cubre:
- set_pair simétrico (UPDATEs en ambas direcciones)
- self-pair rejection (400)
- prior-pair takeover (limpia partner anterior)
- clear_pair simétrico
- clear_pair idempotente cuando no hay pareja
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.products.display_pair_service import DisplayPairService
from app.services.vocabularies.vocabulary_service import VocabularyDomainError


def _scalar_one_or_none(value: object | None) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _empty_result() -> MagicMock:
    return MagicMock()


# ---- self-pair rejection -----------------------------------------------------


@pytest.mark.asyncio
async def test_set_pair_self_rejected_400() -> None:
    session = AsyncMock()
    svc = DisplayPairService(session)
    with pytest.raises(VocabularyDomainError) as exc:
        await svc.set_pair("MTV-100", "MTV-100")
    assert exc.value.status_code == 400
    assert exc.value.code == "display_pair_self"


# ---- missing sku 404 ---------------------------------------------------------


@pytest.mark.asyncio
async def test_set_pair_missing_sku_a_404() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[_scalar_one_or_none(None)])
    svc = DisplayPairService(session)
    with pytest.raises(VocabularyDomainError) as exc:
        await svc.set_pair("MISSING", "MTV-200")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_set_pair_missing_sku_b_404() -> None:
    prod_a = SimpleNamespace(sku="MTV-100", display_pair_sku=None)
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalar_one_or_none(prod_a),
            _scalar_one_or_none(None),
        ]
    )
    svc = DisplayPairService(session)
    with pytest.raises(VocabularyDomainError) as exc:
        await svc.set_pair("MTV-100", "MISSING")
    assert exc.value.status_code == 404


# ---- symmetric set without prior pairs ---------------------------------------


@pytest.mark.asyncio
async def test_set_pair_symmetric_no_prior() -> None:
    prod_a = SimpleNamespace(sku="4295", display_pair_sku=None)
    prod_b = SimpleNamespace(sku="42952", display_pair_sku=None)
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalar_one_or_none(prod_a),
            _scalar_one_or_none(prod_b),
            _empty_result(),  # update sku_a
            _empty_result(),  # update sku_b
        ]
    )
    session.commit = AsyncMock()

    svc = DisplayPairService(session)
    await svc.set_pair("4295", "42952")

    # 2 reads + 2 updates = 4 executes (no prior cleanups)
    assert session.execute.await_count == 4
    session.commit.assert_awaited_once()


# ---- idempotent: same pair already set ---------------------------------------


@pytest.mark.asyncio
async def test_set_pair_already_paired_no_prior_cleanup() -> None:
    prod_a = SimpleNamespace(sku="4295", display_pair_sku="42952")
    prod_b = SimpleNamespace(sku="42952", display_pair_sku="4295")
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalar_one_or_none(prod_a),
            _scalar_one_or_none(prod_b),
            _empty_result(),  # update sku_a
            _empty_result(),  # update sku_b
        ]
    )
    session.commit = AsyncMock()
    svc = DisplayPairService(session)
    await svc.set_pair("4295", "42952")
    # No prior-cleanup updates because prior == new partner.
    assert session.execute.await_count == 4


# ---- prior-pair takeover -----------------------------------------------------


@pytest.mark.asyncio
async def test_set_pair_prior_takeover_clears_old_partner() -> None:
    # 4295 was paired with 4295-OLD, now repair with 42952.
    prod_a = SimpleNamespace(sku="4295", display_pair_sku="4295-OLD")
    prod_b = SimpleNamespace(sku="42952", display_pair_sku=None)
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalar_one_or_none(prod_a),
            _scalar_one_or_none(prod_b),
            _empty_result(),  # clear prior partner of A (4295-OLD)
            _empty_result(),  # update sku_a
            _empty_result(),  # update sku_b
        ]
    )
    session.commit = AsyncMock()

    svc = DisplayPairService(session)
    await svc.set_pair("4295", "42952")

    # 2 reads + 1 prior cleanup + 2 updates = 5
    assert session.execute.await_count == 5
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_pair_prior_takeover_both_sides() -> None:
    # Both A and B had different prior partners.
    prod_a = SimpleNamespace(sku="4295", display_pair_sku="4295-OLD")
    prod_b = SimpleNamespace(sku="42952", display_pair_sku="42952-OLD")
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalar_one_or_none(prod_a),
            _scalar_one_or_none(prod_b),
            _empty_result(),  # clear prior partner of A
            _empty_result(),  # clear prior partner of B
            _empty_result(),  # update sku_a
            _empty_result(),  # update sku_b
        ]
    )
    session.commit = AsyncMock()

    svc = DisplayPairService(session)
    await svc.set_pair("4295", "42952")
    assert session.execute.await_count == 6


# ---- clear_pair --------------------------------------------------------------


@pytest.mark.asyncio
async def test_clear_pair_symmetric() -> None:
    prod = SimpleNamespace(sku="4295", display_pair_sku="42952")
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalar_one_or_none(prod),
            _empty_result(),  # null self
            _empty_result(),  # null partner
        ]
    )
    session.commit = AsyncMock()
    svc = DisplayPairService(session)
    await svc.clear_pair("4295")
    assert session.execute.await_count == 3
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_clear_pair_idempotent_no_pair() -> None:
    prod = SimpleNamespace(sku="4295", display_pair_sku=None)
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[_scalar_one_or_none(prod)]
    )
    session.commit = AsyncMock()
    svc = DisplayPairService(session)
    await svc.clear_pair("4295")
    # Only the read; no updates, no commit.
    assert session.execute.await_count == 1
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_clear_pair_missing_sku_404() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[_scalar_one_or_none(None)])
    svc = DisplayPairService(session)
    with pytest.raises(VocabularyDomainError) as exc:
        await svc.clear_pair("MISSING")
    assert exc.value.status_code == 404
