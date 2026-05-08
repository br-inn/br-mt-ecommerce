"""Assets domain services — Wave 1 asset unification.

- asset_service.AssetService — CRUD + upload URLs + archive/restore/mirror.
"""

from __future__ import annotations

from app.services.assets.asset_service import AssetService

__all__ = ["AssetService"]
