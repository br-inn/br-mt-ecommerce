"""Storage helper para Supabase Storage `product-images` (US-1A-02-06).

API pública:
- `build_product_image_path(sku, role, ext, image_id=None)` — construye path
  determinístico siguiendo convención `master/{sku}/{uuid}.{ext}` o
  `thumbnails/{sku}/{size}/primary.webp`.
- `create_signed_url(storage_path, ttl_seconds=None)` — emite signed URL via
  `service_role` bypass de RLS. Default TTL 1h, configurable hasta 24h
  (ADR-033 dice 24h max).
- `upload_bytes(storage_path, data, content_type)` — uploads via service_role.

⚠ NUNCA expongas estas funciones directamente a routers públicos. El service
debe ser invocado desde un endpoint con `require_role_claim('comercial', ...)`
o equivalente para garantizar que la URL signed sólo se emita para usuarios
autorizados (RLS de Storage no se aplica con service_role — el control de acceso
se hace en API gating).

Tests: `tests/db/test_storage_helper.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from app.core.config import settings
from app.core.supabase import get_supabase_admin

if TYPE_CHECKING:
    from supabase import Client

# --------------------------------------------------------------------------
# Constantes
# --------------------------------------------------------------------------
#: TTL default para signed URLs — 1h, configurable via env var.
DEFAULT_SIGNED_URL_TTL_SECONDS: int = 3600

#: TTL máximo permitido — 24h (ADR-033). Cualquier llamada con TTL superior
#: se trunca a este valor con warning.
MAX_SIGNED_URL_TTL_SECONDS: int = 86400

#: Roles válidos para path semántico — espejo de `ProductImage.role`.
_VALID_ROLES = frozenset({"primary", "gallery", "thumbnail", "external_mirror"})

#: Mapeo role → prefijo de path en bucket.
_ROLE_PATH_PREFIX = {
    "primary": "master",
    "gallery": "master",
    "external_mirror": "external_mirror",
    "thumbnail": "thumbnails",
}


# --------------------------------------------------------------------------
# Path builder
# --------------------------------------------------------------------------
def build_product_image_path(
    sku: str,
    role: str,
    ext: str,
    *,
    image_id: str | None = None,
    thumbnail_size: int | None = None,
) -> str:
    """Construye path canónico dentro del bucket `product-images`.

    Convenciones:
    - `role='primary'` o `role='gallery'`  → `master/{sku}/{image_id|uuid}.{ext}`
    - `role='external_mirror'`             → `external_mirror/{sku}/{image_id|uuid}.{ext}`
    - `role='thumbnail'`                   → `thumbnails/{sku}/{size}/primary.webp`
                                             (en este caso `ext` se ignora,
                                             siempre webp; `thumbnail_size` requerido)

    Args:
        sku: SKU del producto (e.g. "MT-V-038").
        role: tipo de imagen (`primary` | `gallery` | `external_mirror` | `thumbnail`).
        ext: extensión sin punto (`png` | `jpg` | `jpeg` | `webp` | `avif`).
        image_id: opcional, UUID estable; si no se provee, se genera uno.
        thumbnail_size: requerido si `role='thumbnail'` (256 | 512 | 1024).

    Raises:
        ValueError: role inválido o thumbnail sin size.
    """
    if role not in _VALID_ROLES:
        raise ValueError(
            f"role inválido: {role!r}. Válidos: {sorted(_VALID_ROLES)}"
        )

    if role == "thumbnail":
        if thumbnail_size not in (256, 512, 1024):
            raise ValueError(
                f"thumbnail_size requerido y debe ser 256/512/1024 (got {thumbnail_size!r})"
            )
        return f"thumbnails/{sku}/{thumbnail_size}/primary.webp"

    prefix = _ROLE_PATH_PREFIX[role]
    fname_id = image_id or str(uuid4())
    ext_clean = ext.lstrip(".").lower()
    return f"{prefix}/{sku}/{fname_id}.{ext_clean}"


# --------------------------------------------------------------------------
# Signed URL emission
# --------------------------------------------------------------------------
def _clamp_ttl(ttl_seconds: int | None) -> int:
    """Aplica defaults + límites al TTL solicitado."""
    if ttl_seconds is None:
        return DEFAULT_SIGNED_URL_TTL_SECONDS
    if ttl_seconds <= 0:
        raise ValueError(f"ttl_seconds debe ser > 0 (got {ttl_seconds!r})")
    if ttl_seconds > MAX_SIGNED_URL_TTL_SECONDS:
        return MAX_SIGNED_URL_TTL_SECONDS
    return ttl_seconds


def create_signed_url(
    storage_path: str,
    *,
    ttl_seconds: int | None = None,
    bucket: str | None = None,
    client: Client | None = None,
) -> dict[str, Any]:
    """Emite signed URL para un objeto del bucket privado `product-images`.

    Usa `service_role` (bypass RLS) — el caller debe haber validado autorización
    a nivel API antes de invocar.

    Args:
        storage_path: path dentro del bucket (sin slash inicial).
        ttl_seconds: TTL en segundos. Default 1h, max 24h.
        bucket: override opcional del bucket (default `product-images` desde settings).
        client: opcional override del cliente Supabase (testing).

    Returns:
        dict con `signed_url` (str) y `expires_in` (int seconds).

    Raises:
        ValueError: ttl inválido.
        RuntimeError: error de Supabase (re-raised).
    """
    bucket = bucket or settings.SUPABASE_STORAGE_BUCKET_IMAGES
    ttl = _clamp_ttl(ttl_seconds)
    sb = client or get_supabase_admin()

    response = sb.storage.from_(bucket).create_signed_url(
        path=storage_path,
        expires_in=ttl,
    )
    # supabase-py v2 retorna dict con clave 'signedURL' (camelCase) o 'signed_url'.
    signed = response.get("signedURL") or response.get("signed_url") or response.get("signedUrl")
    if not signed:
        raise RuntimeError(
            f"Supabase no retornó signed URL para {storage_path!r}: {response!r}"
        )

    return {
        "signed_url": signed,
        "expires_in": ttl,
        "storage_path": storage_path,
        "bucket": bucket,
    }


# --------------------------------------------------------------------------
# Upload helper
# --------------------------------------------------------------------------
def upload_bytes(
    storage_path: str,
    data: bytes,
    *,
    content_type: str,
    bucket: str | None = None,
    upsert: bool = False,
    client: Client | None = None,
) -> dict[str, Any]:
    """Sube `data` al bucket via `service_role` (bypass RLS).

    El caller se responsabiliza de validar MIME, size y permisos antes de invocar.

    Returns:
        dict con `storage_path`, `bucket`, `bytes` (size).
    """
    bucket = bucket or settings.SUPABASE_STORAGE_BUCKET_IMAGES
    sb = client or get_supabase_admin()

    sb.storage.from_(bucket).upload(
        path=storage_path,
        file=data,
        file_options={
            "content-type": content_type,
            "upsert": "true" if upsert else "false",
        },
    )

    return {
        "storage_path": storage_path,
        "bucket": bucket,
        "bytes": len(data),
        "content_type": content_type,
    }
