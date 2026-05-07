"""Audit hooks específicos del workflow de traducciones.

Encapsula el shape canónico del payload `before/after/payload_diff` de los
audit events emitidos por :class:`TranslationWorkflowService`. Centralizar
aquí evita drift en los tests downstream que filtran por `action`.

Acciones esperadas (alineadas con tab Auditoría — Pantalla 6 UX):

- ``product.translation.review_requested``  — autor pide review.
- ``product.translation.approved``          — aprobador valida.
- ``product.translation.rejected``          — aprobador rechaza con reason.
- ``product.translation.marked_stale``      — master EN cambió.

Cada evento usa ``entity_type='product_translation'`` y
``entity_id=f'{sku}:{lang}'`` para que las queries del tab Auditoría
agrupen por traducción.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.db.models.user import User
from app.repositories.audit import AuditRepository

# Set canonical de acciones que la UI del tab Auditoría reconoce.
TRANSLATION_AUDIT_ACTIONS: frozenset[str] = frozenset(
    {
        "product.translation.review_requested",
        "product.translation.approved",
        "product.translation.rejected",
        "product.translation.marked_stale",
    }
)


def build_transition_payload(
    *,
    sku: str,
    lang: str,
    previous: str,
    new: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Construye el payload `after` canónico de una transición."""
    payload: dict[str, Any] = {
        "sku": sku,
        "lang": lang,
        "from": previous,
        "to": new,
    }
    if reason is not None:
        payload["reason"] = reason
    return payload


def build_transition_diff(previous: str, new: str) -> dict[str, Any]:
    return {"status": {"from": previous, "to": new}}


class TranslationAuditEmitter:
    """Wrapper sobre :class:`AuditRepository` con el shape correcto.

    Mantiene el contrato `before/after/payload_diff/reason` requerido por
    el tab Auditoría — los handlers del workflow llaman SIEMPRE a través de
    esta clase para que los tests de integración del tab Auditoría
    encuentren los eventos por `action`.
    """

    def __init__(self, repo: AuditRepository) -> None:
        self.repo = repo

    async def record_transition(
        self,
        *,
        sku: str,
        lang: str,
        previous: str,
        new: str,
        action: str,
        actor: User,
        reason: str | None = None,
    ) -> Any:
        if action not in TRANSLATION_AUDIT_ACTIONS:
            # Defensa: blindamos contra typos en callers — falla pronto.
            raise ValueError(f"Acción de audit inesperada: {action!r}")
        payload = build_transition_payload(
            sku=sku, lang=lang, previous=previous, new=new, reason=reason
        )
        diff = build_transition_diff(previous, new)
        return await self.repo.record(
            entity_type="product_translation",
            entity_id=f"{sku}:{lang}",
            action=action,
            actor_id=actor.id,
            actor_email=getattr(actor, "email", None),
            actor_role=_role_code(actor),
            before={"status": previous},
            after=payload,
            payload_diff=diff,
            reason=reason,
        )


def _role_code(actor: User) -> str | None:
    role = getattr(actor, "role", None)
    if role is None:
        return None
    return getattr(role, "code", None)


__all__ = [
    "TRANSLATION_AUDIT_ACTIONS",
    "TranslationAuditEmitter",
    "build_transition_diff",
    "build_transition_payload",
]
