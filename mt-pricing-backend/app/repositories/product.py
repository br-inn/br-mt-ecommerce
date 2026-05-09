"""ProductRepository — queries del catálogo."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import selectinload

from app.db.enums import DataQuality
from app.db.models.product import Product, ProductImage, ProductTranslation
from app.db.models.vocabularies import (
    Division,
    ProductDivision,
    Series,
    SeriesTier,
)
from app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    model = Product
    pk_field = "sku"
    soft_delete_field = "deleted_at"

    async def search_by_sku(self, sku: str) -> Product | None:
        return await self.get(sku)

    async def get_by_sku(self, sku: str) -> Product | None:
        """Alias canónico — devuelve producto por PK SKU."""
        return await self.get(sku)

    async def get_full(self, sku: str) -> Product | None:
        """Carga producto + traducciones + imágenes (eager)."""
        return await self.get_with_translations_and_images(sku)

    async def get_with_translations_and_images(self, sku: str) -> Product | None:
        """Eager load translations + images + Stage 3 vocab. Usado en detail.

        Wave 11: añade ``product_divisions.division`` (M:N divisiones).
        Otros campos Stage 3 (``series``, ``material``, ``display_pair``) no
        son SA relationships en ``Product`` (los TEXT escalares ``series`` y
        ``material`` los shadow-arían) — la capa de routes los carga aparte.
        """
        stmt = (
            select(Product)
            .where(Product.sku == sku)
            .options(
                selectinload(Product.translations),
                selectinload(Product.assets),
                selectinload(Product.product_divisions).selectinload(
                    ProductDivision.division
                ),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_paginated_with_filters(
        self,
        *,
        family: str | None = None,
        brand: str | None = None,
        data_quality: str | None = None,
        translation_status: str | None = None,
        translation_lang: str | None = None,
        active: bool | None = None,
        dn: str | None = None,
        pn: str | None = None,
        material: str | None = None,
        created_after: Any | None = None,
        created_before: Any | None = None,
        search: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
        include_deleted: bool = False,
        include_total: bool = False,
        # Stage 3 filters (Wave 11) — divisions M:N + series rica + material vocab.
        division_code: str | None = None,
        series_id: UUID | None = None,
        material_id: UUID | None = None,
        tier_code: str | None = None,
    ) -> tuple[Sequence[Product], str | None, int | None]:
        """Cursor-based pagination con filtros + opcional total.

        Cursor es el `sku` del último elemento de la página anterior — orden
        natural por `sku ASC`.

        US-1A-02-09: nuevos filtros ``dn``, ``pn``, ``material``,
        ``created_after``, ``created_before``. Búsqueda full-text usa
        ``websearch_to_tsquery`` con peso por ``sku``/``name_en``/``family``/
        ``brand`` cuando Postgres soporta GIN sobre tsvector. Si el dialecto
        es SQLite (tests unit puros) hace fallback a ILIKE.

        Si ``include_total`` es True ejecuta un ``SELECT count(*)`` adicional
        sobre los mismos filtros (sin cursor) y lo devuelve como tercer
        elemento de la tupla.
        """
        stmt = select(Product)

        # Filtros principales
        clauses: list[Any] = []
        if family:
            clauses.append(Product.family == family)
        if brand:
            clauses.append(Product.brand == brand)
        if data_quality:
            clauses.append(Product.data_quality == data_quality)
        if active is not None:
            clauses.append(Product.active.is_(active))
        if dn is not None:
            clauses.append(Product.dn == dn)
        if pn is not None:
            clauses.append(Product.pn == pn)
        if material is not None:
            clauses.append(Product.material == material)
        if created_after is not None:
            clauses.append(Product.created_at >= created_after)
        if created_before is not None:
            clauses.append(Product.created_at <= created_before)
        if not include_deleted:
            clauses.append(Product.deleted_at.is_(None))

        # ---- Stage 3 filters (Wave 11) ---------------------------------------
        if division_code is not None:
            # EXISTS subquery sobre product_divisions JOIN divisions ON code.
            sub = (
                select(ProductDivision.product_sku)
                .join(Division, Division.id == ProductDivision.division_id)
                .where(
                    ProductDivision.product_sku == Product.sku,
                    Division.code == division_code,
                )
            )
            clauses.append(exists(sub))
        if series_id is not None:
            clauses.append(Product.series_id == series_id)
        if material_id is not None:
            clauses.append(Product.material_id == material_id)
        if tier_code is not None:
            # JOIN series → series_tiers para filtrar por tier.code.
            sub = (
                select(Series.id)
                .join(SeriesTier, SeriesTier.id == Series.tier_id)
                .where(
                    Series.id == Product.series_id,
                    SeriesTier.code == tier_code,
                )
            )
            clauses.append(exists(sub))

        # Translation status: requiere subquery sobre product_translations.
        if translation_status:
            sub = select(ProductTranslation.sku).where(
                ProductTranslation.status == translation_status
            )
            if translation_lang:
                sub = sub.where(ProductTranslation.lang == translation_lang)
            clauses.append(Product.sku.in_(sub))

        # Búsqueda full-text — usa websearch_to_tsquery sobre Postgres con
        # ranking por peso (sku>name>family>brand). En tests con SQLite cae
        # al fallback ILIKE.
        if search:
            dialect = self.session.bind.dialect.name if self.session.bind else "postgresql"
            if dialect == "postgresql":
                # Documento ponderado: sku 'A', name_en 'B', family 'C', brand 'D'.
                ts_doc = func.setweight(
                    func.to_tsvector(
                        "simple", func.coalesce(Product.sku, "")
                    ),
                    "A",
                ).op("||")(
                    func.setweight(
                        func.to_tsvector(
                            "simple", func.coalesce(Product.name_en, "")
                        ),
                        "B",
                    )
                ).op("||")(
                    func.setweight(
                        func.to_tsvector(
                            "simple", func.coalesce(Product.family, "")
                        ),
                        "C",
                    )
                ).op("||")(
                    func.setweight(
                        func.to_tsvector(
                            "simple", func.coalesce(Product.brand, "")
                        ),
                        "D",
                    )
                )
                ts_query = func.websearch_to_tsquery("simple", search)
                clauses.append(ts_doc.op("@@")(ts_query))
            else:
                term = f"%{search}%"
                clauses.append(
                    or_(Product.sku.ilike(term), Product.name_en.ilike(term))
                )

        if clauses:
            stmt = stmt.where(and_(*clauses))

        # Total count opcional — sobre los mismos filtros (sin cursor).
        total: int | None = None
        if include_total:
            count_stmt = select(func.count()).select_from(Product)
            if clauses:
                count_stmt = count_stmt.where(and_(*clauses))
            total_res = await self.session.execute(count_stmt)
            total = int(total_res.scalar_one() or 0)

        # Cursor — append AL FINAL para que no participe del count(*).
        if cursor:
            stmt = stmt.where(Product.sku > cursor)

        stmt = stmt.order_by(Product.sku.asc()).limit(limit + 1)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        next_cursor: str | None = None
        if len(rows) > limit:
            next_cursor = rows[limit - 1].sku
            rows = rows[:limit]
        return rows, next_cursor, total

    async def search_by_text(
        self, query: str, *, limit: int = 10
    ) -> Sequence[Product]:
        """Full-text simple: pg_trgm sobre name_en + ILIKE prefix sobre sku.

        Sprint 1 (sin pgvector): trigram similarity para name_en, ILIKE prefix
        para sku. Sprint 2+: hybrid (BM25 + embedding cosine) — TODO.
        """
        term = query.strip()
        like_pattern = f"{term}%"
        # similarity(name_en, query) — pg_trgm. Para SKU usamos ILIKE prefix
        # porque los códigos no se prestan a similarity.
        stmt = (
            select(Product)
            .where(
                Product.deleted_at.is_(None),
                or_(
                    Product.sku.ilike(like_pattern),
                    Product.name_en.op("%")(term),
                ),
            )
            .order_by(
                # ranking: prefix match SKU primero, luego similarity name_en.
                Product.sku.ilike(like_pattern).desc(),
                func.similarity(Product.name_en, term).desc(),
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_family(
        self, family: str, *, active_only: bool = True, limit: int = 100
    ) -> Sequence[Product]:
        stmt = select(Product).where(Product.family == family)
        if active_only:
            stmt = stmt.where(Product.active.is_(True), Product.deleted_at.is_(None))
        stmt = stmt.order_by(Product.sku.asc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def search_by_name(self, query: str, *, limit: int = 50) -> Sequence[Product]:
        """Búsqueda por similaridad pg_trgm sobre `name_en`."""
        stmt = (
            select(Product)
            .where(Product.name_en.op("%")(query))
            .where(Product.deleted_at.is_(None))
            .order_by(func.similarity(Product.name_en, query).desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_by_quality(self) -> dict[str, int]:
        stmt = (
            select(Product.data_quality, func.count())
            .where(Product.deleted_at.is_(None))
            .group_by(Product.data_quality)
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def list_blocked(self, *, limit: int = 50) -> Sequence[Product]:
        stmt = (
            select(Product)
            .where(
                Product.data_quality == DataQuality.BLOCKED.value,
                Product.deleted_at.is_(None),
            )
            .order_by(Product.sku.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class ProductTranslationRepository(BaseRepository[ProductTranslation]):
    model = ProductTranslation
    pk_field = "sku"
    soft_delete_field = None  # PK compuesto, hard-delete only

    async def get_for_sku(
        self, sku: str, *, lang: str | None = None
    ) -> Sequence[ProductTranslation]:
        stmt = select(ProductTranslation).where(ProductTranslation.sku == sku)
        if lang:
            stmt = stmt.where(ProductTranslation.lang == lang)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_one(self, sku: str, lang: str) -> ProductTranslation | None:
        stmt = select(ProductTranslation).where(
            ProductTranslation.sku == sku,
            ProductTranslation.lang == lang,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        sku: str,
        lang: str,
        **fields: Any,
    ) -> tuple[ProductTranslation, bool]:
        """Inserta o actualiza una traducción. Devuelve `(row, created)`."""
        existing = await self.get_one(sku, lang)
        if existing is None:
            row = ProductTranslation(sku=sku, lang=lang, **fields)
            self.session.add(row)
            await self.session.flush()
            return row, True
        for k, v in fields.items():
            setattr(existing, k, v)
        await self.session.flush()
        return existing, False


class ProductImageRepository(BaseRepository[ProductImage]):
    model = ProductImage
    pk_field = "id"
    soft_delete_field = None

    async def list_for_sku(self, sku: str) -> Sequence[ProductImage]:
        stmt = (
            select(ProductImage)
            .where(ProductImage.sku == sku)
            .order_by(ProductImage.is_primary.desc(), ProductImage.role.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_for_product(self, product_sku: str, image_id: Any) -> ProductImage | None:
        stmt = select(ProductImage).where(
            ProductImage.id == image_id, ProductImage.sku == product_sku
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def set_primary(self, product_sku: str, image_id: Any) -> ProductImage | None:
        """Marca una imagen como primaria — al resto las pone is_primary=False.

        Idempotente: si la imagen ya es primaria, no falla.
        """
        target = await self.get_for_product(product_sku, image_id)
        if target is None:
            return None
        # Demote others (mismo sku) — flush antes de promote para respetar
        # cualquier unique partial index futuro sobre (sku, is_primary=true).
        for img in await self.list_for_sku(product_sku):
            if img.id != image_id and img.is_primary:
                img.is_primary = False
        target.is_primary = True
        await self.session.flush()
        return target
