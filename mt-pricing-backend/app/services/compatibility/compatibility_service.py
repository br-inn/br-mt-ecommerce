"""CompatibilityService — orquesta CompatibilityRepo + validaciones + auditoría.

Responsabilidades:
- Validar que ambos SKUs existen antes de enlazar.
- Delegar la lógica de persistencia (incluyendo sync bidireccional) al repo.
- Emitir eventos de auditoría en cada add/remove a través de AuditRepository.
- Exponer excepciones de dominio claras para la capa de routes.

Bidireccionalidad ``replaces``/``replaced_by``:
    El repo gestiona la inserción/eliminación automática del inverso. El
    servicio simplemente asegura que ambos SKUs existen y delega.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.audit import AuditRepository
from app.repositories.compatibility import CompatibilityRepo
from app.repositories.product import ProductRepository
from app.db.models.compatibility import ProductCompatibility


# ---------------------------------------------------------------------------
# Excepciones de dominio
# ---------------------------------------------------------------------------
class CompatibilityDomainError(Exception):
    """Base para errores recuperables de compatibilidad."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class CompatibilitySkuNotFoundError(CompatibilityDomainError):
    def __init__(self, sku: str) -> None:
        super().__init__(
            code="compatibility_sku_not_found",
            message=f"Producto '{sku}' no encontrado.",
            status_code=404,
        )


class CompatibilitySelfLoopError(CompatibilityDomainError):
    def __init__(self) -> None:
        super().__init__(
            code="compatibility_self_loop",
            message="Un producto no puede ser compatible con sí mismo.",
            status_code=422,
        )


class CompatibilityDuplicateError(CompatibilityDomainError):
    def __init__(self, product_sku: str, compatible_with_sku: str, kind: str) -> None:
        super().__init__(
            code="compatibility_duplicate",
            message=(f"Ya existe un enlace ({product_sku} → {kind} → {compatible_with_sku})."),
            status_code=409,
        )


class CompatibilityNotFoundError(CompatibilityDomainError):
    def __init__(self, product_sku: str, compatible_with_sku: str, kind: str) -> None:
        super().__init__(
            code="compatibility_not_found",
            message=(f"Enlace ({product_sku} → {kind} → {compatible_with_sku}) no encontrado."),
            status_code=404,
        )


# ---------------------------------------------------------------------------
# Servicio
# ---------------------------------------------------------------------------
class CompatibilityService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = CompatibilityRepo(session)
        self._product_repo = ProductRepository(session)
        self._audit = AuditRepository(session)

    # --- helpers -----------------------------------------------------------

    async def _assert_sku_exists(self, sku: str) -> None:
        prod = await self._product_repo.get_by_sku(sku)
        if prod is None:
            raise CompatibilitySkuNotFoundError(sku)

    # --- reads -------------------------------------------------------------

    async def list_for_product(
        self,
        sku: str,
        *,
        kind: str | None = None,
    ) -> Sequence[ProductCompatibility]:
        await self._assert_sku_exists(sku)
        return await self._repo.list_for_product(sku, kind=kind)

    async def list_inverse(
        self,
        sku: str,
        *,
        kind: str | None = None,
    ) -> Sequence[ProductCompatibility]:
        await self._assert_sku_exists(sku)
        return await self._repo.list_inverse(sku, kind=kind)

    # --- mutations ---------------------------------------------------------

    async def add_link(
        self,
        product_sku: str,
        compatible_with_sku: str,
        kind: str,
        *,
        notes: str | None = None,
        position: int = 0,
        actor_id: UUID | None = None,
        actor_email: str | None = None,
        owner_type: str = "product",
        dn_min: int | None = None,
        dn_max: int | None = None,
    ) -> ProductCompatibility:
        """Añade un enlace de compatibilidad.

        Validaciones:
        - Ambos SKUs deben existir.
        - product_sku != compatible_with_sku (no self-loop).
        - No puede existir ya el mismo (product_sku, compatible_with_sku, kind).
        - dn_min/dn_max coherentes (validado por CHECK en DB + schema).

        Para ``replaces``/``replaced_by``, el repo crea también el inverso.
        """
        if product_sku == compatible_with_sku:
            raise CompatibilitySelfLoopError()

        await self._assert_sku_exists(product_sku)
        await self._assert_sku_exists(compatible_with_sku)

        if dn_min is not None and dn_max is not None and dn_max < dn_min:
            raise CompatibilityDomainError(
                code="compatibility_dn_range_invalid",
                message="dn_max debe ser >= dn_min",
                status_code=422,
            )

        try:
            link = await self._repo.add_link(
                product_sku,
                compatible_with_sku,
                kind,
                notes=notes,
                position=position,
                created_by=actor_id,
                owner_type=owner_type,
                dn_min=dn_min,
                dn_max=dn_max,
            )
        except IntegrityError as exc:
            raise CompatibilityDuplicateError(product_sku, compatible_with_sku, kind) from exc

        await self._audit.record(
            entity_type="product_compatibility",
            entity_id=f"{product_sku}:{compatible_with_sku}:{kind}",
            action="compatibility.add",
            actor_id=actor_id,
            actor_email=actor_email,
            after={
                "product_sku": product_sku,
                "compatible_with_sku": compatible_with_sku,
                "kind": kind,
                "notes": notes,
                "position": position,
                "owner_type": owner_type,
                "dn_min": dn_min,
                "dn_max": dn_max,
            },
        )
        return link

    async def remove_link(
        self,
        product_sku: str,
        compatible_with_sku: str,
        kind: str,
        *,
        actor_id: UUID | None = None,
        actor_email: str | None = None,
    ) -> None:
        """Elimina un enlace de compatibilidad.

        Para ``replaces``/``replaced_by``, el repo elimina también el inverso.
        """
        deleted = await self._repo.remove_link(product_sku, compatible_with_sku, kind)
        if not deleted:
            raise CompatibilityNotFoundError(product_sku, compatible_with_sku, kind)

        await self._audit.record(
            entity_type="product_compatibility",
            entity_id=f"{product_sku}:{compatible_with_sku}:{kind}",
            action="compatibility.remove",
            actor_id=actor_id,
            actor_email=actor_email,
            before={
                "product_sku": product_sku,
                "compatible_with_sku": compatible_with_sku,
                "kind": kind,
            },
        )

    async def replace_all_for_product(
        self,
        sku: str,
        links: list[dict],
        *,
        actor_id: UUID | None = None,
        actor_email: str | None = None,
    ) -> list[ProductCompatibility]:
        """Reemplaza todos los enlaces OUTGOING de ``sku`` con la lista dada.

        Valida que todos los ``compatible_with_sku`` existen antes de ejecutar
        la operación. Acepta opcionalmente ``owner_type``, ``dn_min``, ``dn_max``
        por item (Fase 5).
        """
        await self._assert_sku_exists(sku)

        # Validar todos los destinos antes de mutar.
        for item in links:
            csku = item["compatible_with_sku"]
            if csku == sku:
                raise CompatibilitySelfLoopError()
            await self._assert_sku_exists(csku)
            # Validar rango DN si ambos provistos.
            dmn = item.get("dn_min")
            dmx = item.get("dn_max")
            if dmn is not None and dmx is not None and dmx < dmn:
                raise CompatibilityDomainError(
                    code="compatibility_dn_range_invalid",
                    message="dn_max debe ser >= dn_min",
                    status_code=422,
                )

        try:
            created = await self._repo.replace_all_for_product(sku, links, created_by=actor_id)
        except IntegrityError as exc:
            raise CompatibilityDomainError(
                code="compatibility_replace_conflict",
                message="Conflicto de integridad durante el reemplazo bulk.",
                status_code=409,
            ) from exc

        await self._audit.record(
            entity_type="product_compatibility",
            entity_id=sku,
            action="compatibility.replace_all",
            actor_id=actor_id,
            actor_email=actor_email,
            after={"sku": sku, "count": len(created)},
        )
        return created

    # ------------------------------------------------------------------
    # Fase 5 — polymorphic / DN-aware queries
    # ------------------------------------------------------------------

    async def list_for_owner(
        self,
        owner_type: str,
        owner_id: str,
        *,
        kind: str | None = None,
        dn: int | None = None,
    ) -> Sequence[ProductCompatibility]:
        """Lista compatibilidades por owner polymorphic con filtro DN opcional.

        Para ``owner_type='product'`` valida que el SKU exista (legacy). Para
        ``owner_type='series'`` no valida (owner_id es un series code o id).
        """
        if owner_type not in ("product", "variant", "series"):
            raise CompatibilityDomainError(
                code="compatibility_owner_type_invalid",
                message=f"owner_type inválido: {owner_type!r}",
                status_code=422,
            )
        if owner_type == "product":
            await self._assert_sku_exists(owner_id)
        return await self._repo.list_for_owner(owner_type, owner_id, kind=kind, dn=dn)

    async def list_spare_parts_for_series(
        self,
        series_id: str,
        *,
        dn: int | None = None,
    ) -> Sequence[ProductCompatibility]:
        """Resuelve recambios aplicables a una serie en un DN concreto.

        Shortcut sobre ``list_for_owner(owner_type='series', kind='spare_part')``.
        """
        return await self._repo.list_for_owner("series", series_id, kind="spare_part", dn=dn)
