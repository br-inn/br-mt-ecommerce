"""Cursor pagination helpers — base64-encoded JSON contracts.

Convención (US-1A-02-02-S1, arquitectura §11.1):
- El cursor opaco que recibe/devuelve la API es ``base64url(json({"sku": "<last_sku>"}))``.
- El repositorio (Agente 1) trabaja con el `sku` en plano. Esta capa sólo
  encodea/decodea el wrapper, manteniendo el contrato público estable
  independientemente de cómo el repo paginate internamente.
- Si el cliente manda un cursor inválido (base64 o JSON malformado, o falta la
  clave esperada), devolvemos `400 Bad Request` con un `ProblemDetails`.

Uso típico::

    raw_sku_cursor = decode_sku_cursor(cursor)               # str | None
    rows, next_sku = await service.list_products(cursor=raw_sku_cursor, ...)
    next_cursor = encode_sku_cursor(next_sku)                # str | None
"""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any

from fastapi import HTTPException, status

__all__ = [
    "decode_cursor",
    "decode_sku_cursor",
    "encode_cursor",
    "encode_sku_cursor",
]


def _b64url_encode(data: bytes) -> str:
    # base64url sin padding — más amigable para query strings.
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(token: str) -> bytes:
    # Re-añade padding antes de decodificar (urlsafe_b64decode lo exige).
    padding = "=" * (-len(token) % 4)
    return base64.urlsafe_b64decode(token + padding)


def encode_cursor(payload: dict[str, Any]) -> str:
    """Serializa un dict pequeño como cursor opaco base64url-JSON."""
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _b64url_encode(raw)


def decode_cursor(cursor: str) -> dict[str, Any]:
    """Decodifica un cursor opaco; lanza 400 si está corrupto."""
    try:
        raw = _b64url_decode(cursor)
        payload = json.loads(raw)
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "type": "https://mtme-api/errors/invalid-cursor",
                "title": "Invalid cursor",
                "status": 400,
                "code": "invalid_cursor",
                "detail": "Cursor opaco corrupto o no decodificable.",
            },
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "type": "https://mtme-api/errors/invalid-cursor",
                "title": "Invalid cursor",
                "status": 400,
                "code": "invalid_cursor",
                "detail": "Cursor payload debe ser objeto JSON.",
            },
        )
    return payload


def encode_sku_cursor(sku: str | None) -> str | None:
    """Wrapper específico para el cursor `{"sku": "..."}`."""
    if sku is None:
        return None
    return encode_cursor({"sku": sku})


def decode_sku_cursor(cursor: str | None) -> str | None:
    """Devuelve el `sku` interno o lanza 400 si el cursor no contiene `sku`."""
    if cursor is None:
        return None
    payload = decode_cursor(cursor)
    sku = payload.get("sku")
    if not isinstance(sku, str) or not sku:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "type": "https://mtme-api/errors/invalid-cursor",
                "title": "Invalid cursor",
                "status": 400,
                "code": "invalid_cursor",
                "detail": "Cursor falta clave 'sku' o es vacío.",
            },
        )
    return sku
