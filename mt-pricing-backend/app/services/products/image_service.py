"""ImageService — mirror externo + signed upload URL + validación.

Sprint 1: implementación mínima.
- mirror_external_image: stub determinista que devuelve el path remoto que el
  worker real generará (FR-IMG-02). Sprint 2 lo reemplaza por la lógica de
  descarga + reupload a Supabase Storage.
- generate_signed_upload_url: usa supabase admin client (Storage API). Si el
  cliente no está configurado en el entorno (tests), devuelve un fake URL
  determinista.
- validate_image: magic bytes + tamaño (no decodifica imagen completa).
"""

from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from app.core.config import settings

# Magic bytes — primeros bytes de cada formato soportado.
_MAGIC_PREFIXES: dict[str, list[bytes]] = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/webp": [b"RIFF"],  # luego WEBP en bytes 8-12
    "image/avif": [b"\x00\x00\x00 ftypavif", b"\x00\x00\x00\x1cftypavif"],
}


class ImageValidationError(ValueError):
    """Validación de imagen falló — magic bytes, tamaño, MIME."""


class ImageService:
    """Servicio sin estado — todas las dependencias por argumento o settings."""

    BUCKET = "product-images"
    MAX_BYTES = 10 * 1024 * 1024  # 10 MB

    def _safe_filename(self, filename: str) -> str:
        # Defensa-en-profundidad — los schemas ya validan, pero no confiar.
        if not re.match(r"^[A-Za-z0-9._\-]{1,256}$", filename):
            raise ImageValidationError("filename inválido")
        return filename

    def _build_storage_path(self, sku: str, filename: str) -> str:
        """Construye el path canónico en Supabase Storage."""
        clean = self._safe_filename(filename)
        prefix = sku[:2].upper() if len(sku) >= 2 else "_"
        return f"{prefix}/{sku}/{uuid4().hex}_{clean}"

    # ------------------------------------------------------------------- Mirror
    async def mirror_external_image(self, url: str, sku: str) -> str:
        """FR-IMG-02 — calcula el storage_path donde estará la imagen mirrored.

        Sprint 1: stub. No descarga nada — devuelve la ruta canónica que el
        worker real (Sprint 2) usará. El llamador puede luego encolar una task
        Celery para hacer el mirror real.
        """
        if not url:
            raise ImageValidationError("URL externa vacía")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ImageValidationError(f"esquema no soportado: {parsed.scheme}")
        # Stable hash → idempotente
        digest = hashlib.sha256(f"{sku}|{url}".encode()).hexdigest()[:16]
        # Heurística: extensión a partir del path; default jpg.
        ext = "jpg"
        m = re.search(r"\.([a-zA-Z0-9]{2,5})($|\?)", parsed.path)
        if m:
            ext = m.group(1).lower()
        prefix = sku[:2].upper() if len(sku) >= 2 else "_"
        return f"{prefix}/{sku}/mirror_{digest}.{ext}"

    # ----------------------------------------------------------- Signed upload
    def generate_signed_upload_url(
        self,
        sku: str,
        filename: str,
        content_type: str,
        expires_in: int = 600,
    ) -> dict[str, Any]:
        """Genera una signed URL para upload directo desde el frontend.

        Sprint 2 — integración real con `supabase.storage.create_signed_upload_url()`.
        Devuelve `{ storage_path, upload_url, token, expires_in, bucket }`.

        El frontend hace `supabase.storage.from(bucket).uploadToSignedUrl(path, token, file)`
        — el `token` viene del SDK Supabase y es self-contained (no header bearer).

        En entornos sin SUPABASE configurado (placeholder default), devuelve un
        payload fake determinista para testing.
        """
        storage_path = self._build_storage_path(sku, filename)
        admin_url = getattr(settings, "SUPABASE_URL", None)
        admin_key_obj = getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)
        admin_key = (
            admin_key_obj.get_secret_value()
            if admin_key_obj is not None and hasattr(admin_key_obj, "get_secret_value")
            else admin_key_obj
        )
        # Detección entorno fake (default settings de placeholder).
        is_placeholder = (
            not admin_url
            or "your-project" in str(admin_url)
            or not admin_key
            or "your-service-role-key" in str(admin_key)
        )
        if is_placeholder:
            return {
                "storage_path": storage_path,
                "upload_url": f"https://fake-storage.local/{self.BUCKET}/{storage_path}",
                "token": "fake-token",
                "method": "PUT",
                "headers": {"Content-Type": content_type},
                "expires_in": expires_in,
                "bucket": self.BUCKET,
            }
        try:
            from app.core.supabase import get_supabase_admin

            client = get_supabase_admin()
            signed = client.storage.from_(self.BUCKET).create_signed_upload_url(storage_path)
        except Exception:
            # Fallback determinista — endpoint sin token, frontend mostrará error
            # de upload pero no rompemos el contrato del API.
            return {
                "storage_path": storage_path,
                "upload_url": (
                    f"{admin_url}/storage/v1/object/upload/sign/{self.BUCKET}/{storage_path}"
                ),
                "token": "",
                "method": "PUT",
                "headers": {"Content-Type": content_type},
                "expires_in": expires_in,
                "bucket": self.BUCKET,
            }

        # supabase-py 2.x devuelve dict con keys variables según versión:
        # `{"signed_url": ..., "token": ..., "path": ...}` (snake) o
        # `{"signedURL": ..., "token": ...}` (camel). Normalizamos.
        upload_url = (
            signed.get("signed_url") or signed.get("signedURL") or signed.get("signedUrl") or ""
        )
        token = signed.get("token", "")
        return {
            "storage_path": storage_path,
            "upload_url": upload_url,
            "token": token,
            "method": "PUT",
            "headers": {"Content-Type": content_type},
            "expires_in": expires_in,
            "bucket": self.BUCKET,
        }

    # ------------------------------------------------------------- Validation
    def validate_image(
        self,
        data: bytes,
        *,
        max_size_mb: int = 10,
        declared_mime: str | None = None,
    ) -> str:
        """Valida tamaño + magic bytes. Devuelve el MIME detectado.

        Si `declared_mime` se pasa, exige que coincida con el detectado.
        """
        max_bytes = max_size_mb * 1024 * 1024
        if len(data) == 0:
            raise ImageValidationError("payload vacío")
        if len(data) > max_bytes:
            raise ImageValidationError(
                f"imagen excede el límite de {max_size_mb} MB ({len(data)} bytes)"
            )

        detected: str | None = None
        for mime, prefixes in _MAGIC_PREFIXES.items():
            for prefix in prefixes:
                if data.startswith(prefix):
                    detected = mime
                    break
                # Caso especial WEBP: "RIFF....WEBP"
                if (
                    mime == "image/webp"
                    and len(data) >= 12
                    and data[:4] == b"RIFF"
                    and data[8:12] == b"WEBP"
                ):
                    detected = mime
                    break
            if detected:
                break

        if detected is None:
            raise ImageValidationError(
                "magic bytes no reconocidos — formatos soportados: jpeg/png/webp/avif"
            )
        if declared_mime and declared_mime != detected:
            raise ImageValidationError(
                f"MIME declarado {declared_mime!r} no coincide con detectado {detected!r}"
            )
        return detected
