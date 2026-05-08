"""SpecsRegistry — loads and caches family/subfamily JSON Schemas from disk.

Schema file naming convention:
- ``{family}_{subfamily}.json`` — e.g. ``valve_ball.json``
- ``{family}.json`` — e.g. ``filter.json``
- ``_default.json`` — catch-all for unknown families

Fallback chain (first match wins):
    ``{family}_{subfamily}`` → ``{family}`` → ``_default``
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import ClassVar

logger = logging.getLogger(__name__)

# Canonical path to schemas directory relative to this file.
_SCHEMAS_DIR = Path(__file__).parent.parent.parent / "schemas" / "specs"

_DEFAULT_KEY = "_default"


class SpecsRegistry:
    """In-memory registry of specs JSON Schemas, loaded once at startup.

    Usage (singleton pattern — call ``SpecsRegistry.get_instance()``):

        registry = SpecsRegistry.get_instance()
        schema = registry.get_schema("valve", "ball")
    """

    _instance: ClassVar[SpecsRegistry | None] = None

    def __init__(self, schemas_dir: Path | None = None) -> None:
        self._dir = schemas_dir or _SCHEMAS_DIR
        self._schemas: dict[str, dict] = {}
        self._load()

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------
    @classmethod
    def get_instance(cls, *, schemas_dir: Path | None = None) -> SpecsRegistry:
        """Return (or create) the module-level singleton instance."""
        if cls._instance is None:
            cls._instance = cls(schemas_dir=schemas_dir)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton — used in tests that need a fresh registry."""
        cls._instance = None

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------
    def _load(self) -> None:
        """Load all ``.json`` files from the schemas directory into memory."""
        if not self._dir.is_dir():
            logger.warning("specs schemas dir not found: %s", self._dir)
            return

        loaded = 0
        for path in sorted(self._dir.glob("*.json")):
            key = path.stem  # filename without extension, e.g. "valve_ball"
            try:
                with path.open(encoding="utf-8") as fh:
                    schema = json.load(fh)
                self._schemas[key] = schema
                loaded += 1
                logger.debug("loaded specs schema: %s -> %s", key, path)
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("failed to load specs schema %s: %s", path, exc)

        logger.info("SpecsRegistry loaded %d schemas from %s", loaded, self._dir)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------
    def get_schema(self, family: str, subfamily: str | None = None) -> dict:
        """Return the best-matching schema dict for the given family/subfamily.

        Fallback chain:
        1. ``{family}_{subfamily}`` (exact match)
        2. ``{family}`` (family-level)
        3. ``_default`` (catch-all)

        Always returns a dict (empty dict if even _default is missing, which
        should not happen in a correctly deployed service).
        """
        candidates: list[str] = []
        if subfamily:
            candidates.append(f"{family}_{subfamily}")
        candidates.append(family)
        candidates.append(_DEFAULT_KEY)

        for key in candidates:
            schema = self._schemas.get(key)
            if schema is not None:
                return schema

        logger.warning(
            "no specs schema found for family=%r subfamily=%r, returning empty",
            family,
            subfamily,
        )
        return {}

    def list_keys(self) -> list[str]:
        """Return all loaded schema keys (for debugging / admin)."""
        return sorted(self._schemas.keys())

    def get_schema_by_key(self, key: str) -> dict | None:
        """Return schema by exact key (filename stem). Returns None if not found."""
        return self._schemas.get(key)
