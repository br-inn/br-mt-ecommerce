"""Tests unitarios para ExportService — US-1B-04-02 / US-1B-04-03.

Cubre:
- ``generate_export``: retorna bytes CSV con filas aprobadas.
- Filtro runtime: filas ``pending_review`` no aparecen en el CSV.
- ``ADAPTER_REGISTRY``: tiene los canales AMAZON_UAE, NOON_UAE, SHOPIFY.
- US-1B-04-03: canal en estado no exportable → HTTPException 422.
- US-1B-04-03: solo precios approved/auto_approved se exportan.
- US-1B-04-03: canal en estado pilot exporta sin error.

asyncio_mode = "auto" (pyproject.toml), no se necesita @pytest.mark.asyncio.
"""

from __future__ import annotations

import io
import csv
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.services.pricing_export.export_service import ADAPTER_REGISTRY, ExportService
from app.services.pricing_export.publisher import ExportResult, PublishPayload

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CHANNEL_ID = uuid4()
_CHANNEL_CODE = "AMAZON_UAE"
_SCHEME_CODE = "FBA"


def _make_price(
    sku: str,
    status: str,
    amount: Decimal = Decimal("147.75"),
    channel_id: UUID = _CHANNEL_ID,
    scheme_code: str = _SCHEME_CODE,
    approved_at: datetime | None = None,
) -> MagicMock:
    price = MagicMock()
    price.product_sku = sku
    price.status = status
    price.amount = amount
    price.channel_id = channel_id
    price.scheme_code = scheme_code
    price.approved_at = approved_at or datetime(2026, 5, 12, 10, 0, 0, tzinfo=timezone.utc)
    price.fx_at = datetime(2026, 5, 12, 9, 0, 0, tzinfo=timezone.utc)
    return price


def _make_channel(
    channel_id: UUID = _CHANNEL_ID,
    code: str = _CHANNEL_CODE,
    state: str = "live",
    pilot_with_warnings: bool = False,
) -> MagicMock:
    channel = MagicMock()
    channel.id = channel_id
    channel.code = code
    channel.state = state
    channel.pilot_with_warnings = pilot_with_warnings
    return channel


def _make_csv_bytes(rows: list[dict]) -> bytes:
    """Genera CSV bytes mínimo para simular el adapter."""
    buf = io.StringIO()
    headers = ["sku", "price_aed", "status", "fx_rate", "approved_at"]
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore", lineterminator="\r\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def _make_export_result(rows_exported: int, rows_blocked: int = 0) -> ExportResult:
    return ExportResult(
        ok=True,
        channel_code=_CHANNEL_CODE,
        rows_exported=rows_exported,
        rows_blocked=rows_blocked,
        shadow_mode=False,
        exported_at=datetime.now(tz=timezone.utc),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_export_service_returns_csv_bytes():
    """ExportService retorna bytes CSV con las filas aprobadas."""
    approved_price = _make_price("MTV-1001", "approved")
    auto_price = _make_price("MTV-1002", "auto_approved")

    channel = _make_channel()

    # Mock session
    session = AsyncMock()

    # 1ª ejecución: canal query
    channel_scalars = MagicMock()
    channel_scalars.scalar_one_or_none.return_value = channel

    # 2ª ejecución: fn_channel_approved_prices — retorna filas tipo Row
    fn_row_1 = MagicMock()
    fn_row_1.sku = "MTV-1001"
    fn_row_1.amount = Decimal("147.75")
    fn_row_1.fx_at = datetime(2026, 5, 12, 9, 0, 0, tzinfo=timezone.utc)

    fn_row_2 = MagicMock()
    fn_row_2.sku = "MTV-1002"
    fn_row_2.amount = Decimal("147.75")
    fn_row_2.fx_at = datetime(2026, 5, 12, 9, 0, 0, tzinfo=timezone.utc)

    fn_result = MagicMock()
    fn_result.fetchall.return_value = [fn_row_1, fn_row_2]

    # 3ª ejecución: total prices query (para contar bloqueadas)
    total_scalars = MagicMock()
    total_scalars.scalars.return_value.all.return_value = [approved_price, auto_price]

    session.execute = AsyncMock(side_effect=[channel_scalars, fn_result, total_scalars])
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    # Mock adapter
    expected_csv = _make_csv_bytes(
        [
            {
                "sku": "MTV-1001",
                "price_aed": "147.75",
                "status": "approved",
                "fx_rate": "",
                "approved_at": "",
            },
            {
                "sku": "MTV-1002",
                "price_aed": "147.75",
                "status": "auto_approved",
                "fx_rate": "",
                "approved_at": "",
            },
        ]
    )
    result = _make_export_result(rows_exported=2)

    adapter = MagicMock()
    adapter.validate_payload.return_value = []
    adapter.export_csv = AsyncMock(return_value=(expected_csv, result))

    service = ExportService(session)
    with patch(
        "app.services.pricing_export.export_service.is_shadow_publish_amazon_enabled",
        new=AsyncMock(return_value=False),
    ):
        csv_bytes, manifest = await service.generate_export(
            channel_code=_CHANNEL_CODE,
            scheme_code=_SCHEME_CODE,
            generated_by_user_id=uuid4(),
            adapter=adapter,
        )

    assert isinstance(csv_bytes, bytes)
    assert len(csv_bytes) > 0
    # Verificar que validate_payload fue llamado con el payload correcto
    adapter.validate_payload.assert_called_once()
    payload_arg: PublishPayload = adapter.validate_payload.call_args[0][0]
    assert payload_arg.channel_code == _CHANNEL_CODE
    assert payload_arg.scheme_code == _SCHEME_CODE
    assert len(payload_arg.rows) == 2

    # Verificar que export_csv fue llamado
    adapter.export_csv.assert_called_once()

    # El manifest fue persistido
    session.add.assert_called_once()
    session.commit.assert_called_once()


async def test_export_service_filters_non_approved():
    """Filas con status pending_review no aparecen en el CSV (rows_blocked = 1)."""
    approved_price = _make_price("MTV-2001", "approved")
    blocked_price = _make_price("MTV-2002", "pending_review")

    channel = _make_channel()

    session = AsyncMock()

    # 1ª: canal query
    channel_scalars = MagicMock()
    channel_scalars.scalar_one_or_none.return_value = channel

    # 2ª: fn_channel_approved_prices — solo devuelve la fila aprobada
    fn_row = MagicMock()
    fn_row.sku = "MTV-2001"
    fn_row.amount = Decimal("147.75")
    fn_row.fx_at = datetime(2026, 5, 12, 9, 0, 0, tzinfo=timezone.utc)
    fn_result = MagicMock()
    fn_result.fetchall.return_value = [fn_row]

    # 3ª: total prices (approved + blocked)
    total_scalars = MagicMock()
    total_scalars.scalars.return_value.all.return_value = [approved_price, blocked_price]

    session.execute = AsyncMock(side_effect=[channel_scalars, fn_result, total_scalars])
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    # adapter retorna 1 fila exportada
    expected_csv = _make_csv_bytes(
        [
            {
                "sku": "MTV-2001",
                "price_aed": "147.75",
                "status": "approved",
                "fx_rate": "",
                "approved_at": "",
            },
        ]
    )
    result = _make_export_result(rows_exported=1, rows_blocked=0)

    adapter = MagicMock()
    adapter.validate_payload.return_value = []
    adapter.export_csv = AsyncMock(return_value=(expected_csv, result))

    service = ExportService(session)
    with patch(
        "app.services.pricing_export.export_service.is_shadow_publish_amazon_enabled",
        new=AsyncMock(return_value=False),
    ):
        csv_bytes, manifest = await service.generate_export(
            channel_code=_CHANNEL_CODE,
            scheme_code=_SCHEME_CODE,
            generated_by_user_id=None,
            adapter=adapter,
        )

    # Solo 1 fila approved pasó al payload
    payload_arg: PublishPayload = adapter.validate_payload.call_args[0][0]
    assert len(payload_arg.rows) == 1
    assert payload_arg.rows[0]["sku"] == "MTV-2001"

    # El servicio contabilizó 1 bloqueada (2 total − 1 aprobada)
    added_manifest = session.add.call_args[0][0]
    assert added_manifest.rows_blocked == 1


def test_adapter_registry_has_known_channels():
    """ADAPTER_REGISTRY tiene AMAZON_UAE, NOON_UAE, SHOPIFY."""
    assert "AMAZON_UAE" in ADAPTER_REGISTRY
    assert "NOON_UAE" in ADAPTER_REGISTRY
    assert "SHOPIFY" in ADAPTER_REGISTRY

    # Verificar que cada entry tiene los métodos requeridos del protocolo
    for code, adapter in ADAPTER_REGISTRY.items():
        assert hasattr(adapter, "validate_payload"), f"{code}: falta validate_payload"
        assert hasattr(adapter, "export_csv"), f"{code}: falta export_csv"
        assert hasattr(adapter, "shadow_publish"), f"{code}: falta shadow_publish"
        assert hasattr(adapter, "channel_code"), f"{code}: falta channel_code"


# ---------------------------------------------------------------------------
# US-1B-04-03: Constraint DB no-export sin aprobación
# ---------------------------------------------------------------------------


async def test_export_blocked_channel_raises():
    """Canal en estado 'inactive' → HTTPException 422 antes de consultar precios."""
    from fastapi import HTTPException

    channel = _make_channel(state="inactive")

    session = AsyncMock()
    channel_scalars = MagicMock()
    channel_scalars.scalar_one_or_none.return_value = channel
    session.execute = AsyncMock(return_value=channel_scalars)

    adapter = MagicMock()
    service = ExportService(session)

    with pytest.raises(HTTPException) as exc_info:
        await service.generate_export(
            channel_code=_CHANNEL_CODE,
            scheme_code=_SCHEME_CODE,
            generated_by_user_id=None,
            adapter=adapter,
        )

    assert exc_info.value.status_code == 422
    assert "live o pilot" in exc_info.value.detail
    # No debe haber llegado a consultar precios ni persistir nada
    adapter.export_csv.assert_not_called()
    session.add.assert_not_called()


async def test_export_only_approved_prices():
    """Solo se exportan precios approved/auto_approved; draft queda bloqueado."""
    draft_price = _make_price("MTV-3001", "draft")
    approved_price = _make_price("MTV-3002", "approved")
    auto_price = _make_price("MTV-3003", "auto_approved")

    channel = _make_channel(state="live")

    session = AsyncMock()

    # 1ª: canal query
    channel_scalars = MagicMock()
    channel_scalars.scalar_one_or_none.return_value = channel

    # 2ª: fn_channel_approved_prices — devuelve solo approved + auto_approved
    fn_row_1 = MagicMock()
    fn_row_1.sku = "MTV-3002"
    fn_row_1.amount = Decimal("147.75")
    fn_row_1.fx_at = None

    fn_row_2 = MagicMock()
    fn_row_2.sku = "MTV-3003"
    fn_row_2.amount = Decimal("200.00")
    fn_row_2.fx_at = None

    fn_result = MagicMock()
    fn_result.fetchall.return_value = [fn_row_1, fn_row_2]

    # 3ª: total prices (draft + approved + auto_approved = 3)
    total_scalars = MagicMock()
    total_scalars.scalars.return_value.all.return_value = [draft_price, approved_price, auto_price]

    session.execute = AsyncMock(side_effect=[channel_scalars, fn_result, total_scalars])
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    export_result = _make_export_result(rows_exported=2, rows_blocked=1)
    adapter = MagicMock()
    adapter.validate_payload.return_value = []
    adapter.export_csv = AsyncMock(
        return_value=(
            _make_csv_bytes(
                [
                    {
                        "sku": "MTV-3002",
                        "price_aed": "147.75",
                        "status": "approved",
                        "fx_rate": "",
                        "approved_at": "",
                    },
                    {
                        "sku": "MTV-3003",
                        "price_aed": "200.00",
                        "status": "auto_approved",
                        "fx_rate": "",
                        "approved_at": "",
                    },
                ]
            ),
            export_result,
        )
    )

    service = ExportService(session)
    with patch(
        "app.services.pricing_export.export_service.is_shadow_publish_amazon_enabled",
        new=AsyncMock(return_value=False),
    ):
        csv_bytes, manifest = await service.generate_export(
            channel_code=_CHANNEL_CODE,
            scheme_code=_SCHEME_CODE,
            generated_by_user_id=None,
            adapter=adapter,
        )

    payload_arg: PublishPayload = adapter.validate_payload.call_args[0][0]
    # Solo 2 filas aprobadas llegan al payload
    assert len(payload_arg.rows) == 2
    exported_skus = {r["sku"] for r in payload_arg.rows}
    assert "MTV-3002" in exported_skus
    assert "MTV-3003" in exported_skus
    assert "MTV-3001" not in exported_skus

    # El manifest registra 1 fila bloqueada (3 total − 2 aprobadas)
    added_manifest = session.add.call_args[0][0]
    assert added_manifest.rows_blocked == 1


async def test_export_pilot_channel_succeeds():
    """Canal en estado 'pilot' exporta sin error (incluye pilot_with_warnings=True)."""
    approved_price = _make_price("MTV-4001", "approved")

    channel = _make_channel(state="pilot", pilot_with_warnings=True)

    session = AsyncMock()

    # 1ª: canal query
    channel_scalars = MagicMock()
    channel_scalars.scalar_one_or_none.return_value = channel

    # 2ª: fn_channel_approved_prices
    fn_row = MagicMock()
    fn_row.sku = "MTV-4001"
    fn_row.amount = Decimal("99.00")
    fn_row.fx_at = datetime(2026, 5, 12, 9, 0, 0, tzinfo=timezone.utc)
    fn_result = MagicMock()
    fn_result.fetchall.return_value = [fn_row]

    # 3ª: total prices
    total_scalars = MagicMock()
    total_scalars.scalars.return_value.all.return_value = [approved_price]

    session.execute = AsyncMock(side_effect=[channel_scalars, fn_result, total_scalars])
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    export_result = _make_export_result(rows_exported=1)
    adapter = MagicMock()
    adapter.validate_payload.return_value = []
    adapter.export_csv = AsyncMock(
        return_value=(
            _make_csv_bytes(
                [
                    {
                        "sku": "MTV-4001",
                        "price_aed": "99.00",
                        "status": "approved",
                        "fx_rate": "",
                        "approved_at": "",
                    },
                ]
            ),
            export_result,
        )
    )

    service = ExportService(session)
    with patch(
        "app.services.pricing_export.export_service.is_shadow_publish_amazon_enabled",
        new=AsyncMock(return_value=False),
    ):
        csv_bytes, manifest = await service.generate_export(
            channel_code=_CHANNEL_CODE,
            scheme_code=_SCHEME_CODE,
            generated_by_user_id=None,
            adapter=adapter,
        )

    # Debe completar sin error y exportar la fila
    assert isinstance(csv_bytes, bytes)
    payload_arg: PublishPayload = adapter.validate_payload.call_args[0][0]
    assert len(payload_arg.rows) == 1
    assert payload_arg.rows[0]["sku"] == "MTV-4001"
    # El manifest fue persistido
    session.add.assert_called_once()
    session.commit.assert_called_once()
