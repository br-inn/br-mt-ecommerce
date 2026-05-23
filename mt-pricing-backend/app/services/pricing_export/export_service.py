"""Export Service — US-1B-04-02 / US-1B-04-03.

Orquesta la generación de CSV de precios aprobados para un canal dado.
Solo incluye filas con status ``approved`` o ``auto_approved``; el resto
se contabiliza en ``rows_blocked`` del manifest.

US-1B-04-03 añade:
- Validación de estado del canal: solo ``live`` o ``pilot`` pueden exportar.
- Uso de ``fn_channel_approved_prices`` (mig 082) para filtrar a nivel DB.

Arquitectura hexagonal: el adapter (``ChannelPublisher``) es inyectado por
el caller (route o test), el servicio no instancia adapters directamente.
``ADAPTER_REGISTRY`` es un helper de conveniencia para el endpoint REST.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.channels import Channel
from app.db.models.exports import ExportManifest
from app.db.models.pricing import Price
from app.services.feature_flags.flag_service import is_shadow_publish_amazon_enabled
from app.services.pricing_export.adapters.amazon_uae import AmazonUAEAdapter
from app.services.pricing_export.adapters.noon_uae import NoonUAEAdapter
from app.services.pricing_export.adapters.shopify import ShopifyAdapter
from app.services.pricing_export.publisher import ChannelPublisher, PublishPayload

# ---------------------------------------------------------------------------
# Adapter registry — DI por clave de canal
# ---------------------------------------------------------------------------

ADAPTER_REGISTRY: dict[str, ChannelPublisher] = {
    "AMAZON_UAE": AmazonUAEAdapter(),
    "NOON_UAE": NoonUAEAdapter(),
    "SHOPIFY": ShopifyAdapter(),
}

# Statuses que califican como "aprobados" y pueden exportarse
_APPROVED_STATUSES = {"approved", "auto_approved"}


_EXPORTABLE_STATES = {"live", "pilot"}


class ExportService:
    """Servicio de exportación de precios aprobados hacia canales externos.

    Pasos (US-1B-04-03):
    1. Verifica que el canal existe y está en estado ``live`` o ``pilot``.
    2. Usa ``fn_channel_approved_prices`` (DB function, mig 082) para obtener
       solo precios aprobados — garantía a nivel DB de no-export sin aprobación.
    3. Cuenta filas bloqueadas (total canal×scheme menos aprobadas).
    4. Construye ``PublishPayload`` y delega CSV al adapter.
    5. Persiste ``ExportManifest`` y retorna ``(csv_bytes, manifest)``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def generate_export(
        self,
        channel_code: str,
        scheme_code: str,
        generated_by_user_id: UUID | None,
        adapter: ChannelPublisher,
    ) -> tuple[bytes, ExportManifest]:
        """Genera CSV de precios aprobados y archiva el manifest.

        Returns:
            Tupla ``(csv_bytes, ExportManifest)`` ya persistida en DB.

        Raises:
            HTTPException(422): si el canal no está en estado ``live`` o ``pilot``.
            LookupError: si el ``channel_code`` no existe en la tabla ``channels``.
            ValueError: si ``validate_payload`` retorna errores.
        """
        # ------------------------------------------------------------------
        # 1. Verificar que el canal existe y está en estado exportable
        # ------------------------------------------------------------------
        channel_result = await self.session.execute(
            select(Channel).where(Channel.code == channel_code)
        )
        channel = channel_result.scalar_one_or_none()
        if channel is None:
            raise LookupError(f"Canal '{channel_code}' no encontrado en la base de datos.")

        if channel.state not in _EXPORTABLE_STATES:
            raise HTTPException(
                status_code=422,
                detail="Canal no está en estado exportable (live o pilot)",
            )

        # ------------------------------------------------------------------
        # 2. Obtener precios aprobados vía fn_channel_approved_prices (mig 082)
        #    La función garantiza a nivel DB que solo salen approved/auto_approved.
        # ------------------------------------------------------------------
        fn_result = await self.session.execute(
            text(
                "SELECT price_id, sku, amount, fx_at"
                " FROM fn_channel_approved_prices(:channel_id, :scheme_code)"
            ),
            {"channel_id": channel.id, "scheme_code": scheme_code},
        )
        fn_rows = fn_result.fetchall()

        # ------------------------------------------------------------------
        # 3. Contar filas bloqueadas (total − aprobadas)
        # ------------------------------------------------------------------
        total_result = await self.session.execute(
            select(Price).where(
                Price.channel_id == channel.id,
                Price.scheme_code == scheme_code,
            )
        )
        all_prices: list[Price] = list(total_result.scalars().all())
        blocked_count = len(all_prices) - len(fn_rows)
        if blocked_count < 0:
            blocked_count = 0

        approved_rows: list[dict] = []
        fx_as_of: datetime | None = None

        for row in fn_rows:
            approved_rows.append(
                {
                    "sku": row.sku,
                    "price_aed": str(row.amount),
                    "status": "approved",  # solo approved/auto_approved salen de la función
                    "fx_rate": "",  # resolved in adapter / future sprint
                    "approved_at": "",
                }
            )
            if row.fx_at is not None:
                if fx_as_of is None or row.fx_at > fx_as_of:
                    fx_as_of = row.fx_at

        # ------------------------------------------------------------------
        # 4. Construir payload y validar
        # ------------------------------------------------------------------
        now = datetime.now(tz=UTC)
        payload = PublishPayload(
            channel_code=channel_code,
            scheme_code=scheme_code,
            rows=approved_rows,
            generated_at=now,
            fx_as_of=fx_as_of,
        )

        errors = adapter.validate_payload(payload)
        if errors:
            raise ValueError(f"Payload inválido para canal '{channel_code}': {errors!r}")

        # ------------------------------------------------------------------
        # 4. Shadow publish o CSV normal según feature flag
        # ------------------------------------------------------------------
        use_shadow = channel_code == "AMAZON_UAE" and await is_shadow_publish_amazon_enabled(
            self.session
        )

        if use_shadow:
            result = await adapter.shadow_publish(payload)
            csv_bytes = b""  # no se retorna contenido en shadow mode
            shadow_path = result.raw.get("shadow_path", "") if result.raw else ""
            file_ref = f"shadow://{shadow_path}" if shadow_path else "shadow://"
            manifest_status = "completed"
        else:
            csv_bytes, result = await adapter.export_csv(payload)
            file_ref = ""  # Sprint 9+: ruta/URL en Storage
            manifest_status = "completed"

        # ------------------------------------------------------------------
        # 5. Persistir manifest
        # ------------------------------------------------------------------
        manifest = ExportManifest(
            channel_code=channel_code,
            scheme_code=scheme_code,
            status=manifest_status,
            rows_exported=result.rows_exported,
            rows_blocked=blocked_count,
            file_ref=file_ref,
            fx_as_of=fx_as_of,
            generated_by=generated_by_user_id,
        )
        self.session.add(manifest)
        await self.session.commit()
        await self.session.refresh(manifest)

        return csv_bytes, manifest


__all__ = ["ADAPTER_REGISTRY", "ExportService"]
