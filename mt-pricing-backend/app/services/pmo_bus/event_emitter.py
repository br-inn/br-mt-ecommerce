"""Event emitter — captura eventos audit clave hacia el bus PMO (US-RND-01-12).

Whitelist explícita (mantener corta — eventos Fase 2 sólo). Eventos fuera de
whitelist se rechazan con `ValueError`. Esto previene leaks de PII y mantiene
el contrato estable hacia BR PMO Fase 2.

Eventos whitelisted:
- price.approved      — precio canal aprobado por gerente
- price.rejected      — precio canal rechazado en revisión
- cost.upserted       — coste material/proveedor actualizado (drift > umbral)
- translation.approved — traducción aprobada por translation owner

Cada evento normaliza payload mínimo: sin PII, sólo IDs + métricas + decision.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.services.pmo_bus.ports import PmoEvent, PmoEventPublisherPort

logger = structlog.get_logger(__name__)

# Whitelist canónica — incrementar SOLO con review explícito (PR ADR-082).
PMO_EVENT_WHITELIST: frozenset[str] = frozenset(
    {
        "price.approved",
        "price.rejected",
        "cost.upserted",
        "translation.approved",
    }
)

# Claves PII que NUNCA viajan al bus PMO — defensa segunda línea
# (la primera es no incluirlas en el caller, esta es backstop).
_PII_KEYS_BLOCKLIST: frozenset[str] = frozenset(
    {
        "email",
        "phone",
        "password",
        "token",
        "secret",
        "jwt",
        "api_key",
        "authorization",
    }
)


class PmoEventEmitter:
    """Wrapper que valida nombre + payload antes de delegar al publisher."""

    def __init__(self, publisher: PmoEventPublisherPort) -> None:
        self._publisher = publisher

    def emit(
        self,
        event_name: str,
        payload: dict[str, Any],
        *,
        correlation_id: str | None = None,
    ) -> None:
        """Valida y publica un evento.

        Raises:
            ValueError: si `event_name` no está en `PMO_EVENT_WHITELIST`.
        """
        if event_name not in PMO_EVENT_WHITELIST:
            raise ValueError(
                f"Event '{event_name}' not in PMO whitelist. Allowed: {sorted(PMO_EVENT_WHITELIST)}"
            )

        sanitized = self._sanitize(payload)
        event = PmoEvent(
            event_name=event_name,
            payload=sanitized,
            correlation_id=correlation_id,
        )
        self._publisher.publish(event)
        logger.info(
            "pmo_bus.emitted",
            event_name=event_name,
            correlation_id=correlation_id,
        )

    @staticmethod
    def _sanitize(payload: dict[str, Any]) -> dict[str, Any]:
        """Elimina claves PII detectadas (defensa en profundidad)."""
        clean: dict[str, Any] = {}
        for key, value in payload.items():
            if key.lower() in _PII_KEYS_BLOCKLIST:
                continue
            clean[key] = value
        return clean

    # -------------------------------------------------------------------------
    # Helpers de conveniencia para los call-sites más comunes
    # -------------------------------------------------------------------------
    def emit_price_approved(
        self,
        *,
        sku: str,
        channel: str,
        scheme: str,
        price_aed: float,
        approver_id: str,
        correlation_id: str | None = None,
    ) -> None:
        self.emit(
            "price.approved",
            {
                "sku": sku,
                "channel": channel,
                "scheme": scheme,
                "price_aed": price_aed,
                "approver_id": approver_id,
            },
            correlation_id=correlation_id,
        )

    def emit_price_rejected(
        self,
        *,
        sku: str,
        channel: str,
        scheme: str,
        reason: str,
        rejecter_id: str,
        correlation_id: str | None = None,
    ) -> None:
        self.emit(
            "price.rejected",
            {
                "sku": sku,
                "channel": channel,
                "scheme": scheme,
                "reason": reason,
                "rejecter_id": rejecter_id,
            },
            correlation_id=correlation_id,
        )

    def emit_cost_upserted(
        self,
        *,
        material_code: str,
        supplier_id: str,
        cost_eur: float,
        delta_pct: float | None = None,
        correlation_id: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "material_code": material_code,
            "supplier_id": supplier_id,
            "cost_eur": cost_eur,
        }
        if delta_pct is not None:
            payload["delta_pct"] = delta_pct
        self.emit("cost.upserted", payload, correlation_id=correlation_id)

    def emit_translation_approved(
        self,
        *,
        entity_type: str,
        entity_id: str,
        locale: str,
        approver_id: str,
        correlation_id: str | None = None,
    ) -> None:
        self.emit(
            "translation.approved",
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "locale": locale,
                "approver_id": approver_id,
            },
            correlation_id=correlation_id,
        )
