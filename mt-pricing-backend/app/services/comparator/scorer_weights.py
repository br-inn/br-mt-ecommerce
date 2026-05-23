"""scorer_weights.py — Carga de pesos de scoring por familia de producto.

Integración:
    Conectar con el scorer/matching service cuando se implemente ScoringService.
    Mientras tanto, expone `load_weights(family)` como utilidad standalone.

Configuración:
    SCORER_WEIGHTS_PATH en `app/core/config.py` (default: config/scorer_weights_by_family.yaml)
    Si el archivo no existe → logger.warning + pesos hardcoded.

Nota de integración (Completion Notes):
    No existe ScoringService centralizado en app/services/comparator/ ni
    app/services/matching/ — el scoring multi-dimensional vive en el pipeline
    de investigación (research workstream, US-F15 sprint). Esta función provee
    la capa de configuración lista para conectar cuando el scorer se implemente.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Pesos hardcoded — fallback si el YAML no está disponible.
_DEFAULT_WEIGHTS: dict[str, dict[str, float]] = {
    "default": {
        "material": 0.30,
        "pn": 0.25,
        "thread": 0.20,
        "norma": 0.15,
        "brand_tier": 0.05,
        "delivery": 0.05,
    },
    "valve_family": {
        "material": 0.35,
        "pn": 0.30,
        "thread": 0.15,
        "norma": 0.10,
        "brand_tier": 0.05,
        "delivery": 0.05,
    },
    "fitting_family": {
        "material": 0.25,
        "pn": 0.20,
        "thread": 0.25,
        "norma": 0.15,
        "brand_tier": 0.10,
        "delivery": 0.05,
    },
}

_SUPPORTED_FAMILIES = frozenset(["valve_family", "fitting_family"])

# Cache de perfiles cargados (reset via _clear_cache() en tests)
_cached_profiles: dict[str, dict[str, float]] | None = None


def _load_yaml_profiles(path: Path) -> dict[str, dict[str, float]] | None:
    """Carga perfiles desde YAML. Retorna None si no disponible."""
    try:
        import yaml  # PyYAML — disponible en el proyecto
    except ImportError:
        logger.warning("scorer_weights: PyYAML no disponible — usando pesos hardcoded")
        return None

    if not path.exists():
        logger.warning("scorer_weights: archivo %s no encontrado — usando pesos hardcoded", path)
        return None

    try:
        with open(path, encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f)
        profiles: dict[str, dict[str, float]] = data.get("profiles", {})
        if not profiles:
            logger.warning(
                "scorer_weights: YAML %s sin clave 'profiles' — usando pesos hardcoded", path
            )
            return None
        return profiles
    except Exception as exc:  # noqa: BLE001
        logger.warning("scorer_weights: error leyendo %s: %s — usando pesos hardcoded", path, exc)
        return None


def _get_weights_path() -> Path:
    """Retorna el path configurado via SCORER_WEIGHTS_PATH o el default."""
    try:
        from app.core.config import settings  # evitar import circular en tests

        raw = getattr(settings, "SCORER_WEIGHTS_PATH", "config/scorer_weights_by_family.yaml")
    except Exception:  # noqa: BLE001
        raw = "config/scorer_weights_by_family.yaml"
    return Path(raw)


def _get_profiles() -> dict[str, dict[str, float]]:
    """Retorna perfiles (lazy-load con cache en proceso)."""
    global _cached_profiles  # noqa: PLW0603
    if _cached_profiles is None:
        path = _get_weights_path()
        loaded = _load_yaml_profiles(path)
        _cached_profiles = loaded if loaded is not None else _DEFAULT_WEIGHTS
    return _cached_profiles


def _clear_cache() -> None:
    """Limpia el cache de perfiles (útil en tests)."""
    global _cached_profiles  # noqa: PLW0603
    _cached_profiles = None


def load_weights(family: str | None = None) -> dict[str, float]:
    """Carga pesos desde YAML según familia de producto.

    Args:
        family: Familia del SKU (e.g. "valve_family", "fitting_family").
                None o desconocida → perfil "default".

    Returns:
        Diccionario {dimensión: peso} que suma 1.0.

    Uso en ScoringService::

        weights = load_weights(sku_dict.get("family"))
        score = sum(weights[dim] * scores[dim] for dim in weights)
    """
    profiles = _get_profiles()

    if family in _SUPPORTED_FAMILIES and family in profiles:
        profile_name = family
    else:
        profile_name = "default"

    weights = profiles.get(profile_name, _DEFAULT_WEIGHTS["default"])
    logger.debug("scorer_weights: usando perfil '%s' (family=%s)", profile_name, family)
    return dict(weights)


def get_weights_profile_name(family: str | None = None) -> str:
    """Retorna el nombre del perfil que se usaría para `family`.

    Útil para incluir en metadata.weights_profile del resultado de scoring.
    """
    if family in _SUPPORTED_FAMILIES:
        return family
    return "default"


__all__ = [
    "load_weights",
    "get_weights_profile_name",
]
