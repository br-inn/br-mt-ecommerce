"""ProductRepository — queries del catálogo."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import and_, exists, func, literal_column, or_, select
from sqlalchemy import update as sa_update
from sqlalchemy.orm import joinedload, noload, selectinload

from app.db.enums import DataQuality
from app.db.models.product import Product, ProductBoreDimension, ProductImage, ProductTranslation
from app.db.models.vocabularies import (
    Brand,
    Division,
    Family,
    Material,
    ProductDivision,
    Series,
    SeriesTier,
)
from app.repositories.base import BaseRepository


def _is_uuid(value: str) -> bool:
    """Heurística rápida: True si `value` parsea como UUID."""
    try:
        UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


class ProductRepository(BaseRepository[Product]):
    model = Product
    pk_field = "sku"
    soft_delete_field = "deleted_at"

    async def create(self, **kwargs: Any) -> Product:
        """Resolve brand/family text → FK UUIDs before INSERT.

        Migration 048 made brand_id + family_id NOT NULL. Callers such as the
        PIM importer pass `brand="MT"` (string) but not `brand_id` (UUID).
        This override looks up or creates the Brand/Family row so the INSERT
        never hits a NotNullViolationError.
        """
        if not kwargs.get("brand_id"):
            brand_name: str = kwargs.get("brand") or "MT"
            # Use .limit(1) + first() to avoid MultipleResultsFound when code
            # and name match different rows (e.g. code='MT' and code='mt' both
            # match lower=='mt').  Name match is preferred so order name-first.
            brand_row = (
                await self.session.execute(
                    select(Brand)
                    .where(
                        or_(
                            func.lower(Brand.name) == brand_name.lower(),
                            func.lower(Brand.code) == brand_name.lower(),
                        )
                    )
                    .order_by(
                        (func.lower(Brand.name) == brand_name.lower()).desc()
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if brand_row is not None:
                kwargs["brand_id"] = brand_row.id
            else:
                new_brand = Brand(code=brand_name.lower().replace(" ", "_"), name=brand_name)
                self.session.add(new_brand)
                await self.session.flush()
                kwargs["brand_id"] = new_brand.id

        if not kwargs.get("family_id"):
            family_name: str = kwargs.get("family") or "unclassified"
            family_row = (
                await self.session.execute(
                    select(Family)
                    .where(
                        or_(
                            func.lower(Family.name) == family_name.lower(),
                            func.lower(Family.code) == family_name.lower(),
                        )
                    )
                    .order_by(
                        (func.lower(Family.name) == family_name.lower()).desc()
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if family_row is not None:
                kwargs["family_id"] = family_row.id
            else:
                new_family = Family(code=family_name.lower().replace(" ", "_"), name=family_name)
                self.session.add(new_family)
                await self.session.flush()
                kwargs["family_id"] = new_family.id

        return await super().create(**kwargs)

    async def search_by_sku(self, sku: str) -> Product | None:
        return await self.get(sku)

    async def get_by_sku(self, sku: str) -> Product | None:
        """Alias canónico — devuelve producto por PK SKU."""
        return await self.get(sku)

    async def get_by_sku_for_matching(self, sku: str) -> Product | None:
        """Like get_by_sku but eager-loads product.model for matching pipeline."""
        from sqlalchemy import select

        stmt = select(Product).options(joinedload(Product.model)).where(Product.sku == sku)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

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
                selectinload(Product.product_divisions).selectinload(ProductDivision.division),
                joinedload(Product.model),
                joinedload(Product.series_rel),
                joinedload(Product.material_rel),
                joinedload(Product.display_pair_rel).selectinload(Product.translations),
            )
        )
        result = await self.session.execute(stmt, execution_options={"populate_existing": True})
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
        #
        # series_id / material_id aceptan **UUID o SLUG** (taxonomy registry mig 050+).
        # Si el caller pasa un UUID válido → comparación FK directa.
        # Si pasa un slug (lookup en tabla legacy por code) → se resuelve a UUID
        # vía JOIN con series.code / materials.code. Elección de implementación:
        # **lookup contra tabla legacy** (no contra taxonomy_nodes) por ser el path
        # más simple — un solo JOIN, sin atravesar el registry. El sync trigger
        # de mig 050 garantiza que slugs legacy === slugs del registry.
        division_code: str | None = None,
        series_id: UUID | str | None = None,
        material_id: UUID | str | None = None,
        tier_code: str | None = None,
        # Taxonomy lineage filters — pass through Product.subfamily / .type TEXT
        # (FKs subfamily_id/type_id se promoverán en Stage 4b).
        subfamily: str | None = None,
        type_: str | None = None,
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
        stmt = select(Product).options(
            selectinload(Product.translations),
            noload(Product.assets),
            noload(Product.product_certifications),
            noload(Product.product_applications),
            noload(Product.materials),
            noload(Product.connections),
            noload(Product.tech_tables),
            noload(Product.compatibilities_outgoing),
            noload(Product.compatibilities_incoming),
            noload(Product.product_divisions),
            noload(Product.bore_dimensions),
        )

        # Filtros principales
        clauses: list[Any] = []
        if family:
            clauses.append(Product.family == family)
        if subfamily:
            clauses.append(Product.subfamily == subfamily)
        if type_:
            clauses.append(Product.type == type_)
        if brand:
            clauses.append(Product.brand == brand)
        if data_quality:
            clauses.append(Product.data_quality == data_quality)
        if active is not None:
            # Fase B (mig 066): active deriva de lifecycle_status.
            if active:
                clauses.append(Product.lifecycle_status == "active")
            else:
                clauses.append(Product.lifecycle_status != "active")
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
            sub_div = (
                select(ProductDivision.product_sku)
                .join(Division, Division.id == ProductDivision.division_id)
                .where(
                    ProductDivision.product_sku == Product.sku,
                    Division.code == division_code,
                )
            )
            clauses.append(exists(sub_div))
        if series_id is not None:
            # Acepta UUID o SLUG (registry-aware). Si parsea como UUID se usa
            # directo contra la FK; de lo contrario se resuelve por `series.code`.
            if isinstance(series_id, UUID):
                clauses.append(Product.series_id == series_id)
            elif isinstance(series_id, str):
                if _is_uuid(series_id):
                    clauses.append(Product.series_id == UUID(series_id))
                else:
                    # Lookup contra tabla legacy `series.code` — mig 050 garantiza
                    # que el slug del registry === series.code (vía normalize_slug).
                    sub_series = select(Series.id).where(
                        Series.id == Product.series_id,
                        Series.code == series_id,
                    )
                    clauses.append(exists(sub_series))
        if material_id is not None:
            if isinstance(material_id, UUID):
                clauses.append(Product.material_id == material_id)
            elif isinstance(material_id, str):
                if _is_uuid(material_id):
                    clauses.append(Product.material_id == UUID(material_id))
                else:
                    sub_material = select(Material.id).where(
                        Material.id == Product.material_id,
                        Material.code == material_id,
                    )
                    clauses.append(exists(sub_material))
        if tier_code is not None:
            # JOIN series → series_tiers para filtrar por tier.code.
            sub_tier = (
                select(Series.id)
                .join(SeriesTier, SeriesTier.id == Series.tier_id)
                .where(
                    Series.id == Product.series_id,
                    SeriesTier.code == tier_code,
                )
            )
            clauses.append(exists(sub_tier))

        # Translation status: requiere subquery sobre product_translations.
        if translation_status:
            sub = select(ProductTranslation.sku).where(
                ProductTranslation.status == translation_status
            )
            if translation_lang:
                sub = sub.where(ProductTranslation.lang == translation_lang)
            clauses.append(Product.sku.in_(sub))

        # Búsqueda full-text — Fase B (mig 065): name_en ya no es columna;
        # ahora se hace LEFT JOIN a product_translations(lang='en') para
        # incluir el nombre canónico en el tsvector / ILIKE.
        if search:
            dialect = self.session.bind.dialect.name if self.session.bind else "postgresql"
            tr_alias = ProductTranslation.__table__.alias("pt_en_search")
            en_name_sql = (
                select(tr_alias.c.name)
                .where(
                    tr_alias.c.sku == Product.sku,
                    tr_alias.c.lang == "en",
                )
                .correlate(Product)
                .scalar_subquery()
            )
            if dialect == "postgresql":
                # Documento ponderado: sku 'A', name_en 'B', family 'C', brand 'D'.
                # literal_column evita que asyncpg envíe el peso como VARCHAR bind;
                # setweight requiere "char", no character varying.
                ts_doc = (
                    func.setweight(
                        func.to_tsvector("simple", func.coalesce(Product.sku, "")),
                        literal_column("'A'::\"char\""),
                    )
                    .op("||")(
                        func.setweight(
                            func.to_tsvector("simple", func.coalesce(en_name_sql, "")),
                            literal_column("'B'::\"char\""),
                        )
                    )
                    .op("||")(
                        func.setweight(
                            func.to_tsvector("simple", func.coalesce(Product.family, "")),
                            literal_column("'C'::\"char\""),
                        )
                    )
                    .op("||")(
                        func.setweight(
                            func.to_tsvector("simple", func.coalesce(Product.brand, "")),
                            literal_column("'D'::\"char\""),
                        )
                    )
                )
                ts_query = func.websearch_to_tsquery("simple", search)
                clauses.append(ts_doc.op("@@")(ts_query))
            else:
                term = f"%{search}%"
                clauses.append(or_(Product.sku.ilike(term), en_name_sql.ilike(term)))

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

    async def search_by_text(self, query: str, *, limit: int = 10) -> Sequence[Product]:
        """Full-text simple: pg_trgm sobre product_translations(lang='en').name + ILIKE sobre sku.

        Usa JOIN directo sobre product_translations para que el planner pueda
        usar idx_pt_name_en_trgm (GIN trgm index parcial WHERE lang='en').
        """
        term = query.strip()
        like_pattern = f"{term}%"
        pt = ProductTranslation.__table__.alias("pt_en_textsrch")
        stmt = (
            select(Product)
            .join(pt, (pt.c.sku == Product.sku) & (pt.c.lang == "en"), isouter=True)
            .where(
                Product.deleted_at.is_(None),
                or_(
                    Product.sku.ilike(like_pattern),
                    pt.c.name.op("%")(term),
                ),
            )
            .order_by(
                Product.sku.ilike(like_pattern).desc(),
                func.similarity(pt.c.name, term).desc(),
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
            # Fase B (mig 066): active → lifecycle_status='active'.
            stmt = stmt.where(
                Product.lifecycle_status == "active",
                Product.deleted_at.is_(None),
            )
        stmt = stmt.order_by(Product.sku.asc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def search_by_name(self, query: str, *, limit: int = 50) -> Sequence[Product]:
        """Búsqueda por similaridad pg_trgm sobre product_translations(lang='en').name.

        JOIN directo para usar idx_pt_name_en_trgm (GIN trgm index parcial).
        """
        pt = ProductTranslation.__table__.alias("pt_en_byname")
        stmt = (
            select(Product)
            .join(pt, (pt.c.sku == Product.sku) & (pt.c.lang == "en"))
            .where(
                pt.c.name.op("%")(query),
                Product.deleted_at.is_(None),
            )
            .order_by(func.similarity(pt.c.name, query).desc())
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


class ProductBoreDimensionRepository(BaseRepository[ProductBoreDimension]):
    model = ProductBoreDimension
    pk_field = "id"
    soft_delete_field = None

    async def list_for_sku(self, product_sku: str) -> Sequence[ProductBoreDimension]:
        stmt = (
            select(ProductBoreDimension)
            .where(ProductBoreDimension.product_sku == product_sku)
            .order_by(
                ProductBoreDimension.is_primary.desc(),
                ProductBoreDimension.standard_system.asc(),
                ProductBoreDimension.standard_code.asc(),
            )
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
        """Inserta o actualiza una traducción — operación atómica (INSERT ON CONFLICT).

        Elimina el doble roundtrip SELECT→INSERT/UPDATE que permite duplicados
        bajo concurrencia. Devuelve `(row, created)`.
        """
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        insert_values = {"sku": sku, "lang": lang, **fields}
        update_values = dict(fields)

        stmt = (
            pg_insert(ProductTranslation)
            .values(**insert_values)
            .on_conflict_do_update(
                index_elements=["sku", "lang"],
                set_={**update_values, "updated_at": func.now()},
            )
            .returning(ProductTranslation)
        )
        # populate_existing=True forces SQLAlchemy to update the identity-map entry
        # from the RETURNING result even when the object already exists in cache
        # (prevents stale values on second upsert within the same session).
        result = await self.session.execute(stmt, execution_options={"populate_existing": True})
        row = result.scalars().one()
        # Heurística: si created_at == updated_at la fila es nueva.
        created = row.created_at >= row.updated_at
        return row, created


class ProductImageRepository(BaseRepository[ProductImage]):
    model = ProductImage
    pk_field = "id"
    soft_delete_field = None

    async def list_for_sku(self, sku: str) -> Sequence[ProductImage]:
        # Tras drop de `role` (mig 053): ordenar por (is_primary, kind, position).
        stmt = (
            select(ProductImage)
            .where(ProductImage.sku == sku)
            .order_by(
                ProductImage.is_primary.desc(),
                ProductImage.kind.asc(),
                ProductImage.position.asc(),
            )
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
        """Marca una imagen como primaria en un solo UPDATE — desmarca el resto.

        Reemplaza el loop Python previo (list_for_sku + N writes individuales)
        con un único UPDATE que asigna is_primary = (id = :image_id) para todo
        el SKU, resultando en 1 roundtrip en lugar de 2+N.
        """
        target = await self.get_for_product(product_sku, image_id)
        if target is None:
            return None
        await self.session.execute(
            sa_update(ProductImage)
            .where(ProductImage.sku == product_sku)
            .values(is_primary=(ProductImage.id == image_id))
            .execution_options(synchronize_session="fetch")
        )
        await self.session.flush()
        await self.session.refresh(target)
        return target
