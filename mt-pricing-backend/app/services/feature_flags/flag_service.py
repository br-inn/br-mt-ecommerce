"""FlagService — lookup/update de ``feature_flags`` con cache Redis 60s TTL.

US-1A-09-08 (Sprint 5).

Patrón:
- Cache key namespace: ``mt:feature_flags:<KEY>`` (TTL 60s).
- Cache miss → fallback DB → SETEX con TTL 60s.
- Cache value es ``"1"`` / ``"0"`` (más liviano que JSON; sólo bool en S5).
- Update vía :meth:`set_flag` invalida el cache + commit DB en una transacción.

Cross-worker: 60s TTL es el SLA de propagación tras un toggle (acceptable
en S5 — un kill-switch global rompe el ciclo via :class:`KillSwitch` sin
esperar al TTL).

Hot-path lookup (``is_enabled``) NO toca DB cuando el cache está caliente —
costo: 1 ``GET`` Redis (~0.5ms p99). Si Redis está caído cae al DB read.

Tests:
- Backed por un fake redis (in-process dict) + fake repo.
- Sin DB real — tests usan inyección de ``flag_repo`` y ``redis``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


CACHE_NS = "mt:feature_flags"
CACHE_TTL_SECONDS = 60


# ---------------------------------------------------------------------------
# Flag keys canónicos — todos boolean en S5
# ---------------------------------------------------------------------------
FLAG_LIVE_NETWORK_AMAZON_UAE = "MT_LIVE_NETWORK_AMAZON_UAE"
FLAG_LIVE_NETWORK_NOON_UAE = "MT_LIVE_NETWORK_NOON_UAE"
FLAG_LIVE_NETWORK_SP_API = "MT_LIVE_NETWORK_SP_API"
FLAG_LIVE_NETWORK_NOON_API = "MT_LIVE_NETWORK_NOON_API"
FLAG_VLM_JUDGE = "MT_LIVE_NETWORK_VLM_JUDGE"
FLAG_KILL_SWITCH = "KILL_SWITCH"
# Comparator research workstream (ADR-012) — seed en mig. 069.
FLAG_COMPARATOR_ENABLED = "COMPARATOR_ENABLED"

KNOWN_FLAGS: tuple[str, ...] = (
    FLAG_LIVE_NETWORK_AMAZON_UAE,
    FLAG_LIVE_NETWORK_NOON_UAE,
    FLAG_LIVE_NETWORK_SP_API,
    FLAG_LIVE_NETWORK_NOON_API,
    FLAG_VLM_JUDGE,
    FLAG_KILL_SWITCH,
    FLAG_COMPARATOR_ENABLED,
)


# ---------------------------------------------------------------------------
# Redis protocol — duck-typed para que tests inyecten un fake
# ---------------------------------------------------------------------------
class _RedisLike(Protocol):
    async def get(self, key: str) -> str | bytes | None: ...
    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = ...,
    ) -> bool: ...
    async def delete(self, *keys: str) -> int: ...


# ---------------------------------------------------------------------------
# FlagService — instancia con DI explícita en tests, get_default() en prod
# ---------------------------------------------------------------------------
class FlagService:
    """Backend de feature flags con cache Redis 60s.

    Args:
        flag_repo: repositorio que expone ``get_value(key)`` y
            ``upsert(key, value, updated_by)`` async.
        redis: cliente compatible con :class:`_RedisLike` (``redis.asyncio.Redis``
            en prod).
    """

    def __init__(self, flag_repo: object, redis: _RedisLike | None) -> None:
        self.flag_repo = flag_repo
        self.redis = redis

    # ------------------------------------------------------------------ #
    # Hot-path lookup
    # ------------------------------------------------------------------ #
    async def is_enabled(self, key: str) -> bool:
        """Devuelve True si el flag ``key`` está activo.

        Orden de resolución:
            1. Cache Redis (key ``mt:feature_flags:<KEY>``).
            2. DB (``feature_flags`` table) → set cache con TTL 60s.
            3. Default seguro: ``False``.
        """
        cached = await self._cache_get(key)
        if cached is not None:
            return cached

        value = await self._db_get(key)
        await self._cache_set(key, value)
        return value

    async def get_all(self) -> dict[str, bool]:
        """Snapshot actual de TODOS los flags conocidos. NO usa cache (admin)."""
        out: dict[str, bool] = {}
        for k in KNOWN_FLAGS:
            out[k] = await self._db_get(k)
        return out

    # ------------------------------------------------------------------ #
    # Mutación — invalidación de cache obligatoria
    # ------------------------------------------------------------------ #
    async def set_flag(
        self,
        key: str,
        value: bool,
        *,
        updated_by: UUID | None = None,
    ) -> bool:
        """Persiste flag y purga cache. Devuelve el valor seteado."""
        if key not in KNOWN_FLAGS:
            raise ValueError(
                f"Flag desconocido: {key!r}. Permitidos: {KNOWN_FLAGS}"
            )
        await self.flag_repo.upsert(key=key, value=value, updated_by=updated_by)  # type: ignore[attr-defined]
        await self._cache_invalidate(key)
        logger.info(
            "feature_flag.toggled",
            extra={"key": key, "value": value, "updated_by": str(updated_by)},
        )
        return value

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    async def _db_get(self, key: str) -> bool:
        try:
            value = await self.flag_repo.get_value(key)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "feature_flag.db_lookup_failed",
                extra={"key": key, "error": str(exc)},
            )
            return False
        return bool(value)

    async def _cache_get(self, key: str) -> bool | None:
        if self.redis is None:
            return None
        try:
            raw = await self.redis.get(f"{CACHE_NS}:{key}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "feature_flag.cache_get_failed",
                extra={"key": key, "error": str(exc)},
            )
            return None
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return raw == "1"

    async def _cache_set(self, key: str, value: bool) -> None:
        if self.redis is None:
            return
        try:
            await self.redis.set(
                f"{CACHE_NS}:{key}",
                "1" if value else "0",
                ex=CACHE_TTL_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "feature_flag.cache_set_failed",
                extra={"key": key, "error": str(exc)},
            )

    async def _cache_invalidate(self, key: str) -> None:
        if self.redis is None:
            return
        try:
            await self.redis.delete(f"{CACHE_NS}:{key}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "feature_flag.cache_invalidate_failed",
                extra={"key": key, "error": str(exc)},
            )


# ---------------------------------------------------------------------------
# Singleton helpers — usados por adapter registries
# ---------------------------------------------------------------------------
_default_service: FlagService | None = None


def set_default_service(service: FlagService | None) -> None:
    """Inyecta (o resetea) la instancia singleton — sólo tests/bootstrap."""
    global _default_service
    _default_service = service


def get_default_service() -> FlagService | None:
    """Devuelve singleton activo o ``None`` si no se ha bootstrappeado."""
    return _default_service


# ---------------------------------------------------------------------------
# Sync helpers — adapter registries son síncronos (factory pattern)
# ---------------------------------------------------------------------------
def is_enabled(key: str) -> bool:
    """Lookup síncrono — devuelve False si no hay servicio bootstrappeado.

    Adapter registries usan este helper para decidir stub vs real. El caller
    debe haber bootstrappeado el servicio en lifespan startup. Si no hay
    servicio activo (e.g. test puro sin DI), devuelve False (modo seguro).
    """
    service = _default_service
    if service is None:
        return False
    # Atajo: usamos un cache-only lookup para no bloquear el factory
    # síncronamente. En prod el cache estará caliente; en cold-start se
    # devuelve False (modo seguro) y el siguiente request ya tendrá el
    # valor cacheado.
    return _sync_lookup_via_service(service, key)


def is_live_network_enabled(channel: str) -> bool:
    """Atajo: ``MT_LIVE_NETWORK_<CHANNEL>``. Considera kill-switch global.

    Args:
        channel: identifier compatible con ``flag_service.FLAG_*``
            (e.g. ``"AMAZON_UAE"``, ``"NOON_UAE"``, ``"SP_API"``,
            ``"NOON_API"``, ``"VLM_JUDGE"``).
    """
    from app.services.feature_flags.kill_switch import is_kill_switch_engaged

    if is_kill_switch_engaged():
        return False
    return is_enabled(f"MT_LIVE_NETWORK_{channel.upper()}")


# Lookup síncrono internal: si el servicio expone un cache local en memoria
# lo lee; sino devuelve False. La idea es no bloquear hilos sync esperando
# Redis — en prod el cache local se rellena con primer touch async via
# ``warmup``. En tests, se inyecta el valor directo.
_local_cache: dict[str, bool] = {}


def _sync_lookup_via_service(service: FlagService, key: str) -> bool:
    return _local_cache.get(key, False)


def warmup_local_cache(values: dict[str, bool]) -> None:
    """Rellena el cache local in-process desde un snapshot.

    Llamado al arrancar lifespan tras un :meth:`FlagService.get_all`. Tests
    también lo usan para forzar un valor sin pasar por Redis/DB.
    """
    _local_cache.clear()
    _local_cache.update(values)


def clear_local_cache() -> None:
    """Limpia el cache in-process. Tests usan este helper en teardown."""
    _local_cache.clear()


def set_local_flag(key: str, value: bool) -> None:
    """Override directo del cache local. Sólo tests / hot-toggle admin."""
    _local_cache[key] = value


__all__ = [
    "CACHE_NS",
    "CACHE_TTL_SECONDS",
    "FLAG_COMPARATOR_ENABLED",
    "FLAG_KILL_SWITCH",
    "FLAG_LIVE_NETWORK_AMAZON_UAE",
    "FLAG_LIVE_NETWORK_NOON_API",
    "FLAG_LIVE_NETWORK_NOON_UAE",
    "FLAG_LIVE_NETWORK_SP_API",
    "FLAG_VLM_JUDGE",
    "FlagService",
    "KNOWN_FLAGS",
    "clear_local_cache",
    "get_default_service",
    "is_enabled",
    "is_live_network_enabled",
    "set_default_service",
    "set_local_flag",
    "warmup_local_cache",
]
