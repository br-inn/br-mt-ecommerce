"""DocumentService — Fase 4 versioned controlled documents.

CRUD básico para `documents`. Validación de unicidad (code, version, language)
y de la existencia del `asset_id` referenciado.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.documents import Document
from app.db.models.product import ProductAsset


class DocumentDomainError(Exception):
    """Errores de dominio del servicio de documents."""

    def __init__(self, message: str, code: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class DocumentService:
    """Servicio stateless para CRUD de `documents`."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------------------------------------------------------------- Reads
    async def list_documents(
        self, *, type_: str | None = None, language: str | None = None
    ) -> list[Document]:
        stmt = select(Document)
        if type_ is not None:
            stmt = stmt.where(Document.type == type_)
        if language is not None:
            stmt = stmt.where(Document.language == language.lower())
        stmt = stmt.order_by(Document.type, Document.code, Document.version)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_document(self, document_id: UUID) -> Document:
        result = await self.session.execute(
            select(Document).where(Document.id == document_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise DocumentDomainError(
                f"Document {document_id} no encontrado",
                code="document_not_found",
                status_code=404,
            )
        return row

    async def _get_optional(self, document_id: UUID) -> Document | None:
        result = await self.session.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def _assert_asset_exists(self, asset_id: UUID) -> None:
        result = await self.session.execute(
            select(ProductAsset.id).where(ProductAsset.id == asset_id)
        )
        if result.scalar_one_or_none() is None:
            raise DocumentDomainError(
                f"Asset {asset_id} no encontrado",
                code="asset_not_found",
                status_code=404,
            )

    async def _assert_unique(
        self,
        *,
        code: str,
        version: str,
        language: str,
        exclude_id: UUID | None = None,
    ) -> None:
        stmt = select(Document).where(
            Document.code == code,
            Document.version == version,
            Document.language == language,
        )
        if exclude_id is not None:
            stmt = stmt.where(Document.id != exclude_id)
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise DocumentDomainError(
                f"Documento ya existe para (code={code}, version={version}, "
                f"language={language})",
                code="document_conflict",
                status_code=409,
            )

    # ---------------------------------------------------------------- Create
    async def create(self, data: dict[str, Any]) -> Document:
        await self._assert_asset_exists(data["asset_id"])
        await self._assert_unique(
            code=data["code"],
            version=data["version"],
            language=data["language"],
        )
        doc = Document(**data)
        self.session.add(doc)
        await self.session.flush()
        return doc

    # ----------------------------------------------------------------- Patch
    async def patch(self, document_id: UUID, data: dict[str, Any]) -> Document:
        doc = await self.get_document(document_id)

        # Si cambia asset_id, validar existencia.
        new_asset_id = data.get("asset_id")
        if new_asset_id is not None and new_asset_id != doc.asset_id:
            await self._assert_asset_exists(new_asset_id)

        # Si cambia código/versión/idioma, validar unicidad.
        new_code = data.get("code", doc.code)
        new_version = data.get("version", doc.version)
        new_language = data.get("language", doc.language)
        if (new_code, new_version, new_language) != (doc.code, doc.version, doc.language):
            await self._assert_unique(
                code=new_code,
                version=new_version,
                language=new_language,
                exclude_id=document_id,
            )

        for k, v in data.items():
            setattr(doc, k, v)
        await self.session.flush()
        return doc

    # ---------------------------------------------------------------- Delete
    async def delete(self, document_id: UUID) -> None:
        doc = await self.get_document(document_id)
        await self.session.delete(doc)
        await self.session.flush()
