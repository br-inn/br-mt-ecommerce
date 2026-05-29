"""SupplierService — orquesta CRUD + audit (US-1A-03-02).

Contrato:
- ``create`` falla con 409 si el ``code`` ya existe.
- ``update`` (PUT) replace de los campos editables; ``code`` inmutable.
- ``soft_delete`` setea ``active=false`` y registra audit; el endpoint DELETE
  HTTP retorna 405 vía router (BR-VAT compliance).
- Cada mutación emite ``audit_events`` con before/after/diff.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.supplier import Supplier
from app.db.models.user import User
from app.repositories.audit import AuditRepository
from app.repositories.supplier import SupplierRepository


class SupplierDomainError(Exception):
    """Errores de negocio recoverables — 4xx en routes."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class SupplierNotFoundError(SupplierDomainError):
    def __init__(self, code: str) -> None:
        super().__init__(
            code="supplier_not_found",
            message=f"Proveedor {code!r} no existe.",
            status_code=404,
        )


class SupplierAlreadyExistsError(SupplierDomainError):
    def __init__(self, code: str) -> None:
        super().__init__(
            code="supplier_duplicate_code",
            message=f"Proveedor con code {code!r} ya existe.",
            status_code=409,
        )


class SupplierInvalidCurrencyError(SupplierDomainError):
    def __init__(self, currency: str) -> None:
        super().__init__(
            code="supplier_invalid_currency",
            message=f"Currency {currency!r} no existe en `currencies`.",
            status_code=422,
        )


_AUDIT_FIELDS = (
    "code",
    "name",
    "contact_email",
    "contact_phone",
    "contract_currency",
    "lead_time_days",
    "payment_terms",
    "notes",
    "active",
)


def _snapshot(s: Supplier) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in _AUDIT_FIELDS:
        v = getattr(s, f, None)
        if v is None:
            out[f] = None
        elif hasattr(v, "isoformat"):
            out[f] = v.isoformat()
        elif isinstance(v, (dict, list, bool, int, float)):
            out[f] = v
        else:
            out[f] = str(v)
    return out


def _diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return {k: {"from": before.get(k), "to": after[k]} for k in after if before.get(k) != after[k]}


class SupplierService:
    """CRUD + audit. Stateless por request (DI factory en deps)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.suppliers = SupplierRepository(session)
        self.audit = AuditRepository(session)

    # ---------------------------------------------------------------- queries
    async def get_by_code(self, code: str) -> Supplier:
        s = await self.suppliers.get_by_code(code)
        if s is None:
            raise SupplierNotFoundError(code)
        return s

    async def list_suppliers(
        self,
        *,
        active: bool | None = None,
        contract_currency: str | None = None,
        search: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
        include_total: bool = False,
    ) -> tuple[Sequence[Supplier], str | None, int | None]:
        return await self.suppliers.list_paginated(
            active=active,
            contract_currency=contract_currency,
            search=search,
            cursor=cursor,
            limit=limit,
            include_total=include_total,
        )

    # -------------------------------------------------------------- mutations
    async def create_supplier(self, data: dict[str, Any], actor: User) -> Supplier:
        existing = await self.suppliers.get_by_code(data["code"])
        if existing is not None:
            raise SupplierAlreadyExistsError(data["code"])
        try:
            sup = await self.suppliers.create(**data)
        except IntegrityError as exc:
            # Detección típica de FK violation a currencies — UX-friendly.
            await self.session.rollback()
            msg = str(exc.orig) if exc.orig else str(exc)
            if "currencies" in msg.lower() or "contract_currency" in msg.lower():
                raise SupplierInvalidCurrencyError(data.get("contract_currency", "")) from exc
            raise
        await self.audit.record(
            entity_type="supplier",
            entity_id=sup.code,
            action="supplier.created",
            actor_id=actor.id,
            actor_email=actor.email,
            after=_snapshot(sup),
        )
        return sup

    async def replace_supplier(self, code: str, data: dict[str, Any], actor: User) -> Supplier:
        sup = await self.suppliers.get_by_code(code)
        if sup is None:
            raise SupplierNotFoundError(code)
        before = _snapshot(sup)
        for k, v in data.items():
            if k == "code":
                continue  # inmutable
            setattr(sup, k, v)
        sup.updated_at = datetime.now(tz=UTC)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            msg = str(exc.orig) if exc.orig else str(exc)
            if "currencies" in msg.lower() or "contract_currency" in msg.lower():
                raise SupplierInvalidCurrencyError(data.get("contract_currency", "")) from exc
            raise
        after = _snapshot(sup)
        await self.audit.record(
            entity_type="supplier",
            entity_id=sup.code,
            action="supplier.replaced",
            actor_id=actor.id,
            actor_email=actor.email,
            before=before,
            after=after,
            payload_diff=_diff(before, after),
        )
        return sup

    async def patch_supplier(self, code: str, data: dict[str, Any], actor: User) -> Supplier:
        sup = await self.suppliers.get_by_code(code)
        if sup is None:
            raise SupplierNotFoundError(code)
        if not data:
            return sup
        before = _snapshot(sup)
        for k, v in data.items():
            if k == "code":
                continue
            setattr(sup, k, v)
        sup.updated_at = datetime.now(tz=UTC)
        await self.session.flush()
        after = _snapshot(sup)
        diff = _diff(before, after)
        if diff:
            await self.audit.record(
                entity_type="supplier",
                entity_id=sup.code,
                action="supplier.patched",
                actor_id=actor.id,
                actor_email=actor.email,
                before=before,
                after=after,
                payload_diff=diff,
            )
        return sup
