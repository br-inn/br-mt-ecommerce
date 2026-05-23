from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_FALLBACK_WEIGHTS: dict[str, dict[str, Decimal]] = {
    "_default": {
        "material": Decimal("0.18"),
        "pn": Decimal("0.14"),
        "dn": Decimal("0.00"),
        "product_type": Decimal("0.00"),
        "thread_standard": Decimal("0.14"),
        "ways": Decimal("0.00"),
        "norma": Decimal("0.14"),
        "brand_tier": Decimal("0.18"),
        "delivery": Decimal("0.14"),
        "data_completeness": Decimal("0.08"),
    },
}
_FALLBACK_CONFIG: dict[str, Any] = {
    "peer_threshold": 70,
    "drop_threshold": 40,
    "g1_median_multiplier": 1.10,
    "g2_multipliers": {"default": 2.5, "stainless": 3.0, "cast_iron": 2.0},
    "hitl_value_threshold_aed": 1000,
}


@dataclass
class CachedProfile:
    family: str
    weights: dict[str, Decimal]
    hard_blockers: frozenset[str]


class RuleEngineCache:
    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl_seconds = ttl_seconds
        self._profiles: dict[str, CachedProfile] = {}
        self._config: dict[str, Any] = {}
        self._loaded_at: float = 0.0

    def _is_expired(self) -> bool:
        return (time.monotonic() - self._loaded_at) > self.ttl_seconds

    async def ensure_loaded(self, session: AsyncSession) -> None:
        if not self._is_expired() and self._profiles:
            return
        try:
            await self._reload(session)
        except Exception as exc:
            logger.warning(
                "rule_engine_cache.reload_failed — using fallback", extra={"error": str(exc)[:120]}
            )
            if self._profiles:
                # Already have cached data — degrade gracefully, keep stale profiles
                return
            # No profiles at all — load hardcoded fallback but still propagate the error
            self._load_fallback()
            raise

    async def _reload(self, session: AsyncSession) -> None:
        from app.repositories.comparator_config import ComparatorConfigRepository
        from app.repositories.taxonomy_profile import TaxonomyProfileRepository

        profile_repo = TaxonomyProfileRepository(session)
        config_repo = ComparatorConfigRepository(session)

        profiles = await profile_repo.list_all()
        config = await config_repo.get_all()

        self._profiles = {
            p.family: CachedProfile(
                family=p.family,
                weights={k: Decimal(str(v)) for k, v in p.weights.items()},
                hard_blockers=frozenset(p.hard_blockers),
            )
            for p in profiles
        }
        self._config = config
        self._loaded_at = time.monotonic()
        logger.info("rule_engine_cache.reloaded", extra={"profiles": len(self._profiles)})

    def _load_fallback(self) -> None:
        self._profiles = {
            k: CachedProfile(family=k, weights=v, hard_blockers=frozenset())
            for k, v in _FALLBACK_WEIGHTS.items()
        }
        self._config = dict(_FALLBACK_CONFIG)
        self._loaded_at = time.monotonic()

    def get_profile(self, family: str) -> CachedProfile | None:
        profile = self._profiles.get(family)
        if profile:
            return profile
        slug = (family or "").strip().lower().replace(" ", "_")
        profile = self._profiles.get(slug)
        if profile:
            return profile
        profile = self._profiles.get((family or "").upper())
        if profile:
            return profile
        return self._profiles.get("_default")

    def get_config_value(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)


_GLOBAL_CACHE = RuleEngineCache(ttl_seconds=300)


def get_rule_engine_cache() -> RuleEngineCache:
    return _GLOBAL_CACHE
