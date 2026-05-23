"""Dimension services — Fase 3 tablas técnicas granulares.

Servicios:

- ``DimensionService``: CRUD de columnas por familia + filas por producto +
  celdas. Compone ``get_table_for_product`` para devolver la matriz
  completa (columnas + filas con celdas) para render del frontend.

- ``PressureTemperatureService``: CRUD de puntos de la curva P-T por
  producto + composición de curva (agrupada por ``series_variant_code``).

- ``ActuationCodeService`` y ``StandardService``: catálogos (list + admin
  CRUD para standards; actuation_codes son seed-only).

- ``DimensionDomainError``: error de dominio normalizado, alineado con
  ``AttributeDomainError`` para mapping HTTP uniforme.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.dimensions import (
    ActuationCode,
    DimensionCell,
    DimensionColumn,
    DimensionRow,
    PressureTemperaturePoint,
    Standard,
)
from app.db.models.product import Product


class DimensionDomainError(Exception):
    """Domain error for dimension operations — maps to HTTP via API layer."""

    def __init__(self, message: str, code: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


# ===========================================================================
# ActuationCodeService — read-only catálogo
# ===========================================================================
class ActuationCodeService:
    """List actuation codes (seed-only, no CRUD)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> Sequence[ActuationCode]:
        stmt = select(ActuationCode).order_by(ActuationCode.code)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get(self, actuation_id: UUID) -> ActuationCode:
        row = await self.session.get(ActuationCode, actuation_id)
        if row is None:
            raise DimensionDomainError(
                f"ActuationCode {actuation_id} not found",
                code="actuation_code_not_found",
                status_code=404,
            )
        return row


# ===========================================================================
# StandardService — list + admin CRUD
# ===========================================================================
class StandardService:
    """CRUD for standards catalog."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> Sequence[Standard]:
        stmt = select(Standard).order_by(Standard.code, Standard.edition)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get(self, std_id: UUID) -> Standard:
        row = await self.session.get(Standard, std_id)
        if row is None:
            raise DimensionDomainError(
                f"Standard {std_id} not found",
                code="standard_not_found",
                status_code=404,
            )
        return row

    async def create(self, data: dict[str, Any]) -> Standard:
        row = Standard(**data)
        self.session.add(row)
        try:
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            raise DimensionDomainError(
                f"Standard creation failed: {e.orig}",
                code="standard_conflict",
                status_code=409,
            ) from e
        await self.session.refresh(row)
        return row

    async def patch(self, std_id: UUID, data: dict[str, Any]) -> Standard:
        row = await self.get(std_id)
        for k, v in data.items():
            setattr(row, k, v)
        try:
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            raise DimensionDomainError(
                f"Standard patch failed: {e.orig}",
                code="standard_conflict",
                status_code=409,
            ) from e
        await self.session.refresh(row)
        return row

    async def delete(self, std_id: UUID) -> None:
        row = await self.get(std_id)
        await self.session.delete(row)
        await self.session.commit()


# ===========================================================================
# DimensionService — columns + rows + cells
# ===========================================================================
class DimensionService:
    """Manage dimension table columns (family-level), rows + cells (per product)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Columns (family-level)
    # ------------------------------------------------------------------
    async def list_columns_for_family(self, family_id: UUID) -> Sequence[DimensionColumn]:
        stmt = (
            select(DimensionColumn)
            .where(DimensionColumn.family_id == family_id)
            .order_by(DimensionColumn.order_index, DimensionColumn.code)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_column(self, column_id: UUID) -> DimensionColumn:
        row = await self.session.get(DimensionColumn, column_id)
        if row is None:
            raise DimensionDomainError(
                f"DimensionColumn {column_id} not found",
                code="dimension_column_not_found",
                status_code=404,
            )
        return row

    async def create_column(
        self,
        family_id: UUID,
        code: str,
        label_en: str,
        unit: str | None = None,
        order_index: int = 0,
    ) -> DimensionColumn:
        row = DimensionColumn(
            family_id=family_id,
            code=code,
            label_en=label_en,
            unit=unit,
            order_index=order_index,
        )
        self.session.add(row)
        try:
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            raise DimensionDomainError(
                f"Column (family={family_id}, code={code}) already exists",
                code="dimension_column_conflict",
                status_code=409,
            ) from e
        await self.session.refresh(row)
        return row

    async def patch_column(self, column_id: UUID, data: dict[str, Any]) -> DimensionColumn:
        row = await self.get_column(column_id)
        for k, v in data.items():
            setattr(row, k, v)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def delete_column(self, column_id: UUID) -> None:
        row = await self.get_column(column_id)
        # FK on dimension_cells is RESTRICT — surface a domain error if used.
        in_use_stmt = select(DimensionCell.id).where(DimensionCell.column_id == column_id).limit(1)
        in_use = await self.session.execute(in_use_stmt)
        if in_use.scalar_one_or_none() is not None:
            raise DimensionDomainError(
                f"Cannot delete column {column_id}: in use by dimension_cells",
                code="dimension_column_in_use",
                status_code=409,
            )
        await self.session.delete(row)
        await self.session.commit()

    # ------------------------------------------------------------------
    # Rows (per product)
    # ------------------------------------------------------------------
    async def list_rows_for_product(self, product_sku: str) -> Sequence[DimensionRow]:
        stmt = (
            select(DimensionRow)
            .where(DimensionRow.product_sku == product_sku)
            .options(selectinload(DimensionRow.cells))
            .order_by(DimensionRow.order_index, DimensionRow.created_at)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_row(self, row_id: UUID) -> DimensionRow:
        row = await self.session.get(DimensionRow, row_id)
        if row is None:
            raise DimensionDomainError(
                f"DimensionRow {row_id} not found",
                code="dimension_row_not_found",
                status_code=404,
            )
        return row

    async def upsert_row(
        self,
        product_sku: str,
        size_label: str | None = None,
        dn: int | None = None,
        actuation_code_id: UUID | None = None,
        order_index: int = 0,
    ) -> DimensionRow:
        """Upsert by (product_sku, size_label, actuation_code_id).

        If a row with the same triple exists, patch its order_index + dn;
        otherwise insert a new row.
        """
        product = await self.session.get(Product, product_sku)
        if product is None:
            raise DimensionDomainError(
                f"Product {product_sku} not found",
                code="product_not_found",
                status_code=404,
            )

        stmt = select(DimensionRow).where(
            DimensionRow.product_sku == product_sku,
            DimensionRow.size_label.is_(None)
            if size_label is None
            else DimensionRow.size_label == size_label,
            DimensionRow.actuation_code_id.is_(None)
            if actuation_code_id is None
            else DimensionRow.actuation_code_id == actuation_code_id,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.dn = dn
            existing.order_index = order_index
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        row = DimensionRow(
            product_sku=product_sku,
            size_label=size_label,
            dn=dn,
            actuation_code_id=actuation_code_id,
            order_index=order_index,
        )
        self.session.add(row)
        try:
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            raise DimensionDomainError(
                f"Row creation failed: {e.orig}",
                code="dimension_row_conflict",
                status_code=409,
            ) from e
        await self.session.refresh(row)
        return row

    async def patch_row(self, row_id: UUID, data: dict[str, Any]) -> DimensionRow:
        row = await self.get_row(row_id)
        for k, v in data.items():
            setattr(row, k, v)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def delete_row(self, row_id: UUID) -> None:
        row = await self.get_row(row_id)
        await self.session.delete(row)
        await self.session.commit()

    # ------------------------------------------------------------------
    # Cells (intersección row × column)
    # ------------------------------------------------------------------
    async def set_cell(
        self,
        row_id: UUID,
        column_id: UUID,
        *,
        value_number: Decimal | None = None,
        value_text: str | None = None,
    ) -> DimensionCell:
        """Upsert cell value.

        Exactly one of ``value_number`` / ``value_text`` must be provided
        (others are rejected by CHECK constraint in DB; we raise earlier
        with a clean domain error).
        """
        if value_number is None and (value_text is None or value_text == ""):
            raise DimensionDomainError(
                "Either value_number or value_text must be provided.",
                code="dimension_cell_value_missing",
                status_code=400,
            )

        # Verify row + column existence + family coherence.
        row = await self.get_row(row_id)
        column = await self.get_column(column_id)
        product = await self.session.get(Product, row.product_sku)
        if product is not None and product.family_id != column.family_id:
            raise DimensionDomainError(
                (
                    f"Column {column_id} belongs to family {column.family_id}, "
                    f"but product {row.product_sku} is in family {product.family_id}."
                ),
                code="dimension_cell_family_mismatch",
                status_code=409,
            )

        existing_stmt = select(DimensionCell).where(
            DimensionCell.row_id == row_id,
            DimensionCell.column_id == column_id,
        )
        result = await self.session.execute(existing_stmt)
        cell = result.scalar_one_or_none()
        if cell is None:
            cell = DimensionCell(
                row_id=row_id,
                column_id=column_id,
                value_number=value_number,
                value_text=value_text,
            )
            self.session.add(cell)
        else:
            cell.value_number = value_number
            cell.value_text = value_text

        try:
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            raise DimensionDomainError(
                f"Cell upsert failed: {e.orig}",
                code="dimension_cell_conflict",
                status_code=409,
            ) from e
        await self.session.refresh(cell)
        return cell

    async def delete_cell(self, cell_id: UUID) -> None:
        cell = await self.session.get(DimensionCell, cell_id)
        if cell is None:
            raise DimensionDomainError(
                f"DimensionCell {cell_id} not found",
                code="dimension_cell_not_found",
                status_code=404,
            )
        await self.session.delete(cell)
        await self.session.commit()

    # ------------------------------------------------------------------
    # Composite — full table for a product
    # ------------------------------------------------------------------
    async def get_table_for_product(self, product_sku: str) -> dict[str, Any]:
        """Return composite dict {product_sku, family_id, columns, rows}.

        - columns: ordered by order_index.
        - rows: ordered by order_index, each with cells eager-loaded.
        """
        product = await self.session.get(Product, product_sku)
        if product is None:
            raise DimensionDomainError(
                f"Product {product_sku} not found",
                code="product_not_found",
                status_code=404,
            )
        columns = await self.list_columns_for_family(product.family_id)
        rows = await self.list_rows_for_product(product_sku)
        return {
            "product_sku": product_sku,
            "family_id": product.family_id,
            "columns": list(columns),
            "rows": list(rows),
        }


# ===========================================================================
# PressureTemperatureService
# ===========================================================================
class PressureTemperatureService:
    """Manage pressure-temperature points for a product."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_product(
        self,
        product_sku: str,
        series_variant_code: str | None = None,
    ) -> Sequence[PressureTemperaturePoint]:
        stmt = select(PressureTemperaturePoint).where(
            PressureTemperaturePoint.product_sku == product_sku
        )
        if series_variant_code is not None:
            stmt = stmt.where(PressureTemperaturePoint.series_variant_code == series_variant_code)
        stmt = stmt.order_by(
            PressureTemperaturePoint.series_variant_code,
            PressureTemperaturePoint.order_index,
            PressureTemperaturePoint.temperature_c,
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_curve_for_product(
        self,
        product_sku: str,
        series_variant_code: str | None = None,
    ) -> dict[str, Any]:
        """Return composite dict {product_sku, series_variant_code, points}."""
        product = await self.session.get(Product, product_sku)
        if product is None:
            raise DimensionDomainError(
                f"Product {product_sku} not found",
                code="product_not_found",
                status_code=404,
            )
        points = await self.list_for_product(product_sku, series_variant_code)
        return {
            "product_sku": product_sku,
            "series_variant_code": series_variant_code,
            "points": list(points),
        }

    async def get_point(self, point_id: UUID) -> PressureTemperaturePoint:
        row = await self.session.get(PressureTemperaturePoint, point_id)
        if row is None:
            raise DimensionDomainError(
                f"PressureTemperaturePoint {point_id} not found",
                code="ptp_not_found",
                status_code=404,
            )
        return row

    async def add_point(
        self,
        product_sku: str,
        *,
        temperature_c: Decimal,
        pressure_max_bar: Decimal,
        series_variant_code: str | None = None,
        condition_en: str | None = None,
        order_index: int = 0,
    ) -> PressureTemperaturePoint:
        product = await self.session.get(Product, product_sku)
        if product is None:
            raise DimensionDomainError(
                f"Product {product_sku} not found",
                code="product_not_found",
                status_code=404,
            )
        if pressure_max_bar < Decimal("0"):
            raise DimensionDomainError(
                "pressure_max_bar must be non-negative.",
                code="ptp_invalid_pressure",
                status_code=400,
            )
        row = PressureTemperaturePoint(
            product_sku=product_sku,
            series_variant_code=series_variant_code,
            temperature_c=temperature_c,
            pressure_max_bar=pressure_max_bar,
            condition_en=condition_en,
            order_index=order_index,
        )
        self.session.add(row)
        try:
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            raise DimensionDomainError(
                f"Point creation failed: {e.orig}",
                code="ptp_create_failed",
                status_code=400,
            ) from e
        await self.session.refresh(row)
        return row

    async def patch_point(self, point_id: UUID, data: dict[str, Any]) -> PressureTemperaturePoint:
        row = await self.get_point(point_id)
        for k, v in data.items():
            setattr(row, k, v)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def delete_point(self, point_id: UUID) -> None:
        row = await self.get_point(point_id)
        await self.session.delete(row)
        await self.session.commit()

    async def delete_all_for_product(self, product_sku: str) -> int:
        """Bulk delete all points for a product. Returns number deleted."""
        stmt = delete(PressureTemperaturePoint).where(
            PressureTemperaturePoint.product_sku == product_sku
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount or 0
