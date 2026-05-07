"""ProductService — orquesta repositorios + audit emission.

Ningún acceso directo a `session` desde aquí salvo a través de los repos.
Las excepciones de dominio se traducen a HTTPException en la capa de routes.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product, ProductImage, ProductTranslation
from app.db.models.user import User
from app.repositories.audit import AuditRepository
from app.repositories.product import (
    ProductImageRepository,
    ProductRepository,
    ProductTranslationRepository,
)


class ProductDomainError(Exception):
    """Errores de negocio recoverables — mapeo a 4xx en routes."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ProductNotFoundError(ProductDomainError):
    def __init__(self, sku: str) -> None:
        super().__init__(
            code="product_not_found",
            message=f"Producto {sku!r} no existe.",
            status_code=404,
        )


class ProductAlreadyExistsError(ProductDomainError):
    def __init__(self, sku: str) -> None:
        super().__init__(
            code="product_duplicate_sku",
            message=f"Producto con SKU {sku!r} ya existe.",
            status_code=409,
        )


class ProductLockedFieldError(ProductDomainError):
    def __init__(self, fields: list[str]) -> None:
        super().__init__(
            code="product_locked_field",
            message=f"Intento de modificar campos bloqueados manualmente: {fields}",
            status_code=409,
        )


class ProductPreconditionFailedError(ProductDomainError):
    """Optimistic-lock conflict — el `If-Match` ETag no coincide con `updated_at` actual."""

    def __init__(self, sku: str) -> None:
        super().__init__(
            code="product_precondition_failed",
            message=(
                f"ETag enviado no coincide con la versión actual de {sku!r}. "
                f"Refresca la ficha y reintenta."
            ),
            status_code=412,
        )


class ProductImmutableFieldError(ProductDomainError):
    """Intento de cambiar un campo identificador inmutable (ej. SKU)."""

    def __init__(self, field: str) -> None:
        super().__init__(
            code="product_immutable_field",
            message=f"Campo {field!r} es inmutable (BR-1a-01).",
            status_code=422,
        )


class ProductDataQualityTransitionError(ProductDomainError):
    """Transición de `data_quality` inválida o sin completitud requerida."""

    def __init__(self, message: str, missing: list[str] | None = None) -> None:
        super().__init__(
            code="product_data_quality_invalid_transition",
            message=message,
            status_code=422,
        )
        self.missing = missing or []


# Snapshot helper — convierte modelo SQLAlchemy a dict serializable para audit.
_AUDIT_FIELDS = (
    "sku",
    "name_en",
    "description_en",
    "marketing_copy_en",
    "family",
    "subfamily",
    "type",
    "material",
    "dn",
    "pn",
    "connection",
    "brand",
    "specs",
    "dimensions",
    "weight",
    "weight_unit",
    "packaging",
    "intrastat_code",
    "erp_name",
    "image_url",
    "data_quality",
    "manual_locked_fields",
    "active",
)


def _snapshot(obj: Product) -> dict[str, Any]:
    """Serializa un producto a dict JSON-friendly para audit `before/after`."""
    out: dict[str, Any] = {}
    for f in _AUDIT_FIELDS:
        v = getattr(obj, f, None)
        if v is None:
            out[f] = None
        elif hasattr(v, "isoformat"):
            out[f] = v.isoformat()
        else:
            out[f] = str(v) if not isinstance(v, (dict, list, bool, int, float)) else v
    return out


def _diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return {
        k: {"from": before.get(k), "to": after[k]}
        for k in after
        if before.get(k) != after[k]
    }


class ProductService:
    """Orquesta CRUD + búsqueda + traducciones + imágenes (set_primary)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.products = ProductRepository(session)
        self.translations = ProductTranslationRepository(session)
        self.images = ProductImageRepository(session)
        self.audit = AuditRepository(session)

    # ------------------------------------------------------------------ Lookup
    async def get_product_by_id(self, sku: str) -> Product:
        prod = await self.products.get_with_translations_and_images(sku)
        if prod is None or prod.deleted_at is not None:
            raise ProductNotFoundError(sku)
        return prod

    async def get_product_by_sku(self, sku: str) -> Product:
        return await self.get_product_by_id(sku)

    async def list_products(
        self,
        *,
        family: str | None = None,
        brand: str | None = None,
        translation_status: str | None = None,
        translation_lang: str | None = None,
        data_quality: str | None = None,
        active: bool | None = None,
        dn: str | None = None,
        pn: str | None = None,
        material: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        search: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
        include_total: bool = False,
    ) -> tuple[Sequence[Product], str | None, int | None]:
        return await self.products.list_paginated_with_filters(
            family=family,
            brand=brand,
            translation_status=translation_status,
            translation_lang=translation_lang,
            data_quality=data_quality,
            active=active,
            dn=dn,
            pn=pn,
            material=material,
            created_after=created_after,
            created_before=created_before,
            search=search,
            cursor=cursor,
            limit=limit,
            include_total=include_total,
        )

    async def search_products(self, query: str, *, limit: int = 10) -> Sequence[Product]:
        """Cmd-K — Sprint 1 trigram. Sprint 2+ híbrido con embeddings."""
        return await self.products.search_by_text(query, limit=limit)

    # --------------------------------------------------------------- Mutations
    async def create_product(self, data: dict[str, Any], actor: User) -> Product:
        sku = data["sku"]
        existing = await self.products.get_by_sku(sku)
        if existing is not None:
            raise ProductAlreadyExistsError(sku)
        prod = await self.products.create(
            **data,
            created_by=actor.id,
            updated_by=actor.id,
        )
        await self.audit.record(
            entity_type="product",
            entity_id=prod.sku,
            action="product.created",
            actor_id=actor.id,
            actor_email=actor.email,
            after=_snapshot(prod),
        )
        return prod

    async def update_product(
        self, sku: str, data: dict[str, Any], actor: User
    ) -> Product:
        prod = await self.products.get_by_sku(sku)
        if prod is None or prod.deleted_at is not None:
            raise ProductNotFoundError(sku)

        # Respeta manual_locked_fields — sólo bloquea si el caller intenta
        # cambiar valor (no si manda el mismo).
        locked = list(prod.manual_locked_fields or [])
        violated: list[str] = []
        # `manual_locked_fields` se permite reasignar siempre desde el patch.
        for f, v in data.items():
            if f == "manual_locked_fields":
                continue
            if f in locked and getattr(prod, f, None) != v:
                violated.append(f)
        if violated:
            raise ProductLockedFieldError(violated)

        before = _snapshot(prod)
        for k, v in data.items():
            setattr(prod, k, v)
        prod.updated_by = actor.id
        await self.session.flush()
        after = _snapshot(prod)
        await self.audit.record(
            entity_type="product",
            entity_id=prod.sku,
            action="product.updated",
            actor_id=actor.id,
            actor_email=actor.email,
            before=before,
            after=after,
            payload_diff=_diff(before, after),
        )
        return prod

    # ------------------------------------------------------------------ PUT
    # Campos NUNCA editables por PUT (identidad / managed by sistema).
    _IMMUTABLE_FIELDS: frozenset[str] = frozenset(
        {
            "sku",
            "internal_id",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "deleted_at",
            "embedding_text",
            "embedding_image",
            "embedding_model",
            "embedding_at",
        }
    )
    # Campos que el PUT puede setear (whitelist explícita — nada de getattr loose).
    _PUT_FIELDS: tuple[str, ...] = (
        "name_en",
        "description_en",
        "marketing_copy_en",
        "family",
        "subfamily",
        "type",
        "material",
        "dn",
        "pn",
        "connection",
        "brand",
        "specs",
        "dimensions",
        "weight",
        "weight_unit",
        "packaging",
        "intrastat_code",
        "erp_name",
        "image_url",
        "data_quality",
        "manual_locked_fields",
        "active",
    )

    @staticmethod
    def etag_for(prod: Product) -> str:
        """Construye un ETag débil basado en `updated_at` ISO-8601.

        Convención: ``W/"<iso8601>"``. La capa router lo serializa al header
        `ETag` y verifica `If-Match` contra esta cadena.
        """
        ts = prod.updated_at
        if ts is None:
            ts = datetime.now(tz=timezone.utc)
        # Normaliza a UTC ISO con sufijo Z para evitar offsets ambiguos.
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return f'W/"{ts.astimezone(timezone.utc).isoformat()}"'

    async def replace_product(
        self,
        sku: str,
        data: dict[str, Any],
        actor: User,
        *,
        if_match: str | None = None,
    ) -> Product:
        """PUT /products/{sku} — full update con optimistic locking.

        - `data` debe contener TODOS los campos editables (PUT, no PATCH).
        - `if_match` opcional: si está, debe igualar el ETag actual o lanza 412.
        - Respeta `manual_locked_fields` excepto cuando el caller reasigna el
          set de locks explícitamente.
        - SKU es inmutable (BR-1a-01).
        """
        prod = await self.products.get_by_sku(sku)
        if prod is None or prod.deleted_at is not None:
            raise ProductNotFoundError(sku)

        # Optimistic locking — chequeo ETag. Si el cliente no envía If-Match,
        # last-write-wins (S2 acepta este modo).
        if if_match is not None:
            current_etag = self.etag_for(prod)
            if if_match.strip() != current_etag:
                raise ProductPreconditionFailedError(sku)

        # Bloqueo por SKU explícito en payload (no permitimos rename).
        if "sku" in data and data["sku"] != sku:
            raise ProductImmutableFieldError("sku")

        # Construye payload limpio — descarta sku si vino igual.
        payload = {k: v for k, v in data.items() if k in self._PUT_FIELDS}

        # Locks: bloquear escrituras sobre campos en manual_locked_fields
        # cuyo nuevo valor difiera. El propio set `manual_locked_fields` se
        # puede reescribir libremente por PUT.
        locked = list(prod.manual_locked_fields or [])
        violated: list[str] = []
        for f, v in payload.items():
            if f == "manual_locked_fields":
                continue
            if f in locked and getattr(prod, f, None) != v:
                violated.append(f)
        if violated:
            raise ProductLockedFieldError(violated)

        before = _snapshot(prod)
        for k, v in payload.items():
            setattr(prod, k, v)
        prod.updated_by = actor.id
        # Forzamos updated_at a now() — algunos test backends no triggerean
        # `onupdate` cuando se persiste sin valor explícito.
        prod.updated_at = datetime.now(tz=timezone.utc)
        await self.session.flush()
        after = _snapshot(prod)
        diff = _diff(before, after)
        # Si nada cambió, igual emitimos audit (PUT semánticamente reemplaza
        # la representación; útil en pista de auditoría) — pero con `payload_diff={}`.
        await self.audit.record(
            entity_type="product",
            entity_id=prod.sku,
            action="product.replaced",
            actor_id=actor.id,
            actor_email=actor.email,
            before=before,
            after=after,
            payload_diff=diff,
        )
        return prod

    # --------------------------------------------------------- data_quality
    # Campos que deben estar poblados para promover a `complete`.
    _DATA_QUALITY_REQUIRED_FIELDS: tuple[str, ...] = (
        "name_en",
        "family",
        "material",
        "dn",
        "pn",
    )

    # Transiciones permitidas (S2 = todas las directas; en S3 puede agregarse
    # workflow de aprobación). Ver BR-1a-DQ-01.
    _DATA_QUALITY_VALID: frozenset[str] = frozenset(
        {"complete", "partial", "blocked", "migrated_demo"}
    )

    async def patch_data_quality(
        self, sku: str, new_value: str, actor: User, *, reason: str | None = None
    ) -> Product:
        """PATCH /products/{sku}/data-quality — toggle con validación.

        Reglas:
        - `new_value` debe ser uno de los enums permitidos.
        - Para promover a `complete`, los campos `_DATA_QUALITY_REQUIRED_FIELDS`
          deben estar todos no-nulos (BR-1a-DQ-01).
        - `blocked` / `partial` / `migrated_demo` son toggles libres.
        - Audit registra `data_quality.transition` con `from`/`to`.
        """
        if new_value not in self._DATA_QUALITY_VALID:
            raise ProductDataQualityTransitionError(
                f"data_quality {new_value!r} no permitido. "
                f"Permitidos: {sorted(self._DATA_QUALITY_VALID)}"
            )
        prod = await self.products.get_by_sku(sku)
        if prod is None or prod.deleted_at is not None:
            raise ProductNotFoundError(sku)

        prev = prod.data_quality
        if prev == new_value:
            # Idempotente — no emitimos audit ni cambiamos nada.
            return prod

        if new_value == "complete":
            missing = [
                f for f in self._DATA_QUALITY_REQUIRED_FIELDS
                if getattr(prod, f, None) in (None, "")
            ]
            if missing:
                raise ProductDataQualityTransitionError(
                    (
                        f"No se puede marcar {sku!r} como `complete`: faltan campos "
                        f"obligatorios {missing}."
                    ),
                    missing=missing,
                )

        prod.data_quality = new_value
        prod.updated_by = actor.id
        prod.updated_at = datetime.now(tz=timezone.utc)
        await self.session.flush()
        await self.audit.record(
            entity_type="product",
            entity_id=prod.sku,
            action="product.data_quality.transition",
            actor_id=actor.id,
            actor_email=actor.email,
            before={"data_quality": prev},
            after={"data_quality": new_value},
            payload_diff={"data_quality": {"from": prev, "to": new_value}},
            reason=reason,
        )
        return prod

    async def soft_delete_product(self, sku: str, actor: User) -> None:
        prod = await self.products.get_by_sku(sku)
        if prod is None or prod.deleted_at is not None:
            raise ProductNotFoundError(sku)
        before = _snapshot(prod)
        prod.deleted_at = datetime.now(tz=timezone.utc)
        prod.active = False
        prod.updated_by = actor.id
        await self.session.flush()
        await self.audit.record(
            entity_type="product",
            entity_id=prod.sku,
            action="product.deleted",
            actor_id=actor.id,
            actor_email=actor.email,
            before=before,
            after=_snapshot(prod),
        )

    # --------------------------------------------------------------- Images
    async def confirm_image_upload(
        self,
        product_sku: str,
        *,
        storage_path: str,
        mime_type: str,
        bytes_size: int | None,
        width: int | None,
        height: int | None,
        alt_text: str | None,
        is_primary: bool,
        role: str,
        actor: User,
    ) -> ProductImage:
        """Crea row en `product_images` tras upload exitoso a Supabase Storage.

        Llamado por POST /products/{sku}/images/confirm — el frontend hace
        primero PUT a la signed URL y luego este endpoint para que el backend
        persista metadata + dispare el pipeline async (thumbnails).
        """
        prod = await self.products.get_by_sku(product_sku)
        if prod is None or prod.deleted_at is not None:
            raise ProductNotFoundError(product_sku)

        img = ProductImage(
            sku=product_sku,
            role=role,
            storage_path=storage_path,
            mime_type=mime_type,
            bytes_size=bytes_size,
            width=width,
            height=height,
            alt_text=alt_text,
            is_primary=is_primary,
            status="active",
            image_status="mirrored",  # Subida directa al bucket — ya está allá.
            created_by=actor.id,
        )
        self.session.add(img)
        await self.session.flush()

        # Si el caller pidió is_primary=true, demote al resto (idempotente).
        if is_primary:
            await self.images.set_primary(product_sku, img.id)

        await self.audit.record(
            entity_type="product_image",
            entity_id=str(img.id),
            action="product.image.uploaded",
            actor_id=actor.id,
            actor_email=actor.email,
            after={
                "sku": product_sku,
                "image_id": str(img.id),
                "storage_path": storage_path,
                "mime_type": mime_type,
                "bytes_size": bytes_size,
                "is_primary": is_primary,
            },
        )

        # Dispatch generación de thumbnails async (FR-IMG-04). Best-effort —
        # si Celery está caído, el row ya está y se puede reintentar manual.
        try:
            from app.workers.thumbnails import generate_thumbnails

            generate_thumbnails.delay(product_sku, storage_path)
        except Exception:  # noqa: BLE001
            # No romper el upload por fallo de enqueue.
            pass

        return img

    async def set_primary_image(
        self, product_sku: str, image_id: UUID, actor: User
    ) -> ProductImage:
        prod = await self.products.get_by_sku(product_sku)
        if prod is None or prod.deleted_at is not None:
            raise ProductNotFoundError(product_sku)
        img = await self.images.set_primary(product_sku, image_id)
        if img is None:
            raise ProductDomainError(
                code="image_not_found",
                message=f"Imagen {image_id} no existe para producto {product_sku}.",
                status_code=404,
            )
        await self.audit.record(
            entity_type="product_image",
            entity_id=str(image_id),
            action="product.image.set_primary",
            actor_id=actor.id,
            actor_email=actor.email,
            after={"sku": product_sku, "image_id": str(image_id)},
        )
        return img

    async def delete_image(
        self, product_sku: str, image_id: UUID, actor: User
    ) -> None:
        img = await self.images.get_for_product(product_sku, image_id)
        if img is None:
            raise ProductDomainError(
                code="image_not_found",
                message=f"Imagen {image_id} no existe para producto {product_sku}.",
                status_code=404,
            )
        before = {
            "sku": img.sku,
            "id": str(img.id),
            "storage_path": img.storage_path,
            "is_primary": img.is_primary,
        }
        await self.session.delete(img)
        await self.session.flush()
        await self.audit.record(
            entity_type="product_image",
            entity_id=str(image_id),
            action="product.image.deleted",
            actor_id=actor.id,
            actor_email=actor.email,
            before=before,
        )

    # --------------------------------------------------------------- Translations
    async def list_translations(self, product_sku: str) -> Sequence[ProductTranslation]:
        prod = await self.products.get_by_sku(product_sku)
        if prod is None or prod.deleted_at is not None:
            raise ProductNotFoundError(product_sku)
        return await self.translations.get_for_sku(product_sku)

    async def upsert_translation(
        self,
        product_sku: str,
        lang: str,
        data: dict[str, Any],
        actor: User,
    ) -> tuple[ProductTranslation, bool]:
        prod = await self.products.get_by_sku(product_sku)
        if prod is None or prod.deleted_at is not None:
            raise ProductNotFoundError(product_sku)
        # Si el caller especifica draft/approved, registramos translated_by/at.
        fields = dict(data)
        fields.setdefault("translated_by", actor.id)
        fields.setdefault("translated_at", datetime.now(tz=timezone.utc))
        row, created = await self.translations.upsert(
            sku=product_sku, lang=lang, **fields
        )
        await self.audit.record(
            entity_type="product_translation",
            entity_id=f"{product_sku}:{lang}",
            action="product.translation.upserted" if not created else "product.translation.created",
            actor_id=actor.id,
            actor_email=actor.email,
            after={
                "sku": row.sku,
                "lang": row.lang,
                "name": row.name,
                "status": row.status,
            },
        )
        return row, created

    async def add_translation(
        self,
        product_sku: str,
        lang: str,
        data: dict[str, Any],
        actor: User,
    ) -> ProductTranslation:
        row, _created = await self.upsert_translation(product_sku, lang, data, actor)
        return row

    async def update_translation(
        self,
        product_sku: str,
        lang: str,
        data: dict[str, Any],
        actor: User,
    ) -> ProductTranslation:
        existing = await self.translations.get_one(product_sku, lang)
        if existing is None:
            raise ProductDomainError(
                code="translation_not_found",
                message=f"Traducción {lang!r} no existe para {product_sku}.",
                status_code=404,
            )
        row, _ = await self.upsert_translation(product_sku, lang, data, actor)
        return row

    async def approve_translation(
        self, product_sku: str, lang: str, actor: User
    ) -> ProductTranslation:
        existing = await self.translations.get_one(product_sku, lang)
        if existing is None:
            raise ProductDomainError(
                code="translation_not_found",
                message=f"Traducción {lang!r} no existe para {product_sku}.",
                status_code=404,
            )
        existing.status = "approved"
        existing.reviewed_by = actor.id
        existing.reviewed_at = datetime.now(tz=timezone.utc)
        await self.session.flush()
        await self.audit.record(
            entity_type="product_translation",
            entity_id=f"{product_sku}:{lang}",
            action="product.translation.approved",
            actor_id=actor.id,
            actor_email=actor.email,
            after={"sku": product_sku, "lang": lang, "status": "approved"},
        )
        return existing

    # ----------------------------------------------------------- Datasheets
    async def attach_datasheet(
        self,
        *,
        product_sku: str,
        kind: str,
        storage_path: str,
        original_filename: str,
        specs: dict[str, Any],
        actor: User,
        _import_run_id: str | None = None,
    ) -> Any:
        """Asocia un PDF (ya subido a Storage) a un SKU en `product_datasheets`.

        Idempotente por ``storage_path``: si la fila ya existe, agrega el SKU
        al ``sku_list`` JSONB (sin duplicar). Audit emitido en cada creación
        o append.
        """
        from sqlalchemy import select

        from app.db.models.datasheet_import_run import ProductDatasheet

        prod = await self.products.get_by_sku(product_sku)
        if prod is None or prod.deleted_at is not None:
            raise ProductNotFoundError(product_sku)

        stmt = select(ProductDatasheet).where(
            ProductDatasheet.storage_path == storage_path
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()

        run_uuid: UUID | None = None
        if _import_run_id:
            try:
                candidate = UUID(_import_run_id)
            except (ValueError, TypeError):
                candidate = None
            # FK a import_runs.id — solo lo asignamos si la fila existe; la
            # pipeline in-memory de ImporterDatasheetsService genera UUIDs sin
            # registrar import_runs (out of scope Sprint 4).
            if candidate is not None:
                exists = await self.session.execute(
                    text("SELECT 1 FROM public.import_runs WHERE id = :rid"),
                    {"rid": candidate},
                )
                if exists.scalar() is not None:
                    run_uuid = candidate

        if existing is None:
            ds = ProductDatasheet(
                kind=kind,
                storage_path=storage_path,
                original_filename=original_filename,
                file_size_bytes=specs.get("file_size_bytes", 0) if isinstance(specs, dict) else 0,
                sku_list=[product_sku],
                specs_extracted=specs or {},
                import_run_id=run_uuid,
                uploaded_by=actor.id,
            )
            self.session.add(ds)
            await self.session.flush()
            await self.audit.record(
                entity_type="product_datasheet",
                entity_id=str(ds.id),
                action="product.datasheet.attached",
                actor_id=actor.id,
                actor_email=actor.email,
                after={
                    "sku": product_sku,
                    "kind": kind,
                    "storage_path": storage_path,
                    "original_filename": original_filename,
                },
            )
            return ds

        # Idempotente: solo append si el SKU no estaba ya en sku_list.
        skus = list(existing.sku_list or [])
        if product_sku in skus:
            return existing
        skus.append(product_sku)
        existing.sku_list = skus
        await self.session.flush()
        await self.audit.record(
            entity_type="product_datasheet",
            entity_id=str(existing.id),
            action="product.datasheet.sku_appended",
            actor_id=actor.id,
            actor_email=actor.email,
            after={
                "sku": product_sku,
                "storage_path": storage_path,
                "sku_list_size": len(skus),
            },
        )
        return existing
