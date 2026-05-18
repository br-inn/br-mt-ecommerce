"""vision_matcher.py — Comparador visual de imágenes de producto con Claude Haiku 4.5.

Usa Claude Vision (multimodal) para comparar dos imágenes de producto industrial
(válvulas, fittings) y determinar si son del mismo tipo.

Función exclusivamente como FILTRO NEGATIVO:
  - DIFFERENT_TYPE → descartar candidato (no usar como confirmación positiva)
  - SAME_TYPE / UNCERTAIN → continuar al siguiente paso del pipeline

Las imágenes se descargan como base64 con httpx async.
Errores de red (timeout, 404) → retornar UNCERTAIN sin propagar excepción.

Reutiliza el patrón de retry y fallback de vlm_judge.py del mismo módulo.
"""

from __future__ import annotations

import base64
import logging
import os
from enum import Enum

import httpx
import anthropic
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# Timeout para descarga de imágenes — ajustado para no bloquear el pipeline
_IMAGE_DOWNLOAD_TIMEOUT = 8.0  # segundos
# Timeout para la llamada a la API de Anthropic
_API_TIMEOUT = 30.0  # segundos
# Tamaño máximo de imagen antes de descartar (evitar tokens excesivos)
_MAX_IMAGE_BYTES = 4 * 1024 * 1024  # 4 MB


class VisualVerdict(str, Enum):
    """Veredicto del comparador visual."""

    SAME_TYPE = "same_type"
    DIFFERENT_TYPE = "different_type"
    UNCERTAIN = "uncertain"


_SYSTEM_PROMPT = (
    "Eres un auditor de catálogo de PVF (pipes, valves, fittings) industriales. "
    "Tu única tarea es comparar dos imágenes de producto y determinar si representan "
    "el mismo TIPO de producto (no necesariamente el mismo modelo o tamaño).\n\n"
    "Criterios clave para PVF:\n"
    "- Tipo de válvula: ball valve vs gate valve vs butterfly valve vs check valve → DIFERENTES\n"
    "- Conexión: flanged vs threaded vs wafer → puede indicar tipo diferente\n"
    "- Accesorios vs válvulas → DIFERENTES\n\n"
    "Si no puedes determinar claramente → UNCERTAIN.\n"
    "Responde SOLO con un JSON: {\"verdict\": \"same_type\"|\"different_type\"|\"uncertain\", \"reason\": \"<max 200 chars>\"}"
)


async def _download_image_as_base64(
    url: str, http_client: httpx.AsyncClient
) -> tuple[str, str] | None:
    """Descarga una imagen y la retorna como (base64_data, media_type).

    Retorna None si falla la descarga o la imagen supera el tamaño máximo.
    """
    try:
        response = await http_client.get(url, timeout=_IMAGE_DOWNLOAD_TIMEOUT, follow_redirects=True)
        response.raise_for_status()
        content = response.content
        if len(content) > _MAX_IMAGE_BYTES:
            logger.warning("vision_matcher: imagen demasiado grande (%d bytes): %s", len(content), url)
            return None
        content_type = response.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        # Normalizar a tipos soportados por Anthropic
        if content_type not in {"image/jpeg", "image/png", "image/gif", "image/webp"}:
            content_type = "image/jpeg"
        b64 = base64.standard_b64encode(content).decode("ascii")
        return b64, content_type
    except httpx.TimeoutException:
        logger.warning("vision_matcher: timeout descargando imagen: %s", url)
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning("vision_matcher: HTTP %d descargando imagen: %s", exc.response.status_code, url)
        return None
    except httpx.HTTPError as exc:
        logger.warning("vision_matcher: error HTTP descargando imagen: %s — %s", url, exc)
        return None


async def compare_product_images(
    mt_image_url: str,
    amazon_image_url: str,
) -> tuple[VisualVerdict, str]:
    """Compara dos imágenes de producto usando Claude Haiku 4.5 Vision.

    Args:
        mt_image_url: URL de la imagen del producto MT (Supabase Storage o CDN).
        amazon_image_url: URL de la imagen del candidato de Amazon.

    Returns:
        (VisualVerdict, reason_string)
        En caso de error → (VisualVerdict.UNCERTAIN, description_del_error)
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("vision_matcher: ANTHROPIC_API_KEY no configurado — retornando UNCERTAIN")
        return VisualVerdict.UNCERTAIN, "API key no configurada"

    # Verificar que tenemos URLs válidas
    if not mt_image_url or not amazon_image_url:
        return VisualVerdict.UNCERTAIN, "URL de imagen faltante"

    async with httpx.AsyncClient() as http_client:
        # Descargar ambas imágenes en paralelo (secuencial para simplicidad y trazabilidad)
        mt_img = await _download_image_as_base64(mt_image_url, http_client)
        if mt_img is None:
            return VisualVerdict.UNCERTAIN, f"No se pudo descargar imagen MT: {mt_image_url}"

        amz_img = await _download_image_as_base64(amazon_image_url, http_client)
        if amz_img is None:
            return VisualVerdict.UNCERTAIN, f"No se pudo descargar imagen Amazon: {amazon_image_url}"

    mt_b64, mt_mime = mt_img
    amz_b64, amz_mime = amz_img

    # Construir mensaje multimodal para Anthropic
    user_content = [
        {
            "type": "text",
            "text": (
                "Compara estas dos imágenes de producto industrial.\n"
                "Imagen 1 (producto MT/referencia):"
            ),
        },
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mt_mime,
                "data": mt_b64,
            },
        },
        {
            "type": "text",
            "text": "Imagen 2 (candidato Amazon):",
        },
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": amz_mime,
                "data": amz_b64,
            },
        },
        {
            "type": "text",
            "text": (
                "¿Son del mismo TIPO de producto (válvula/fitting)? "
                'Responde SOLO con JSON: {"verdict": "same_type"|"different_type"|"uncertain", "reason": "..."}'
            ),
        },
    ]

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)

        # Retry con backoff exponencial ante errores de red/API
        retryer = AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1.0, max=8.0),
            retry=retry_if_exception_type(anthropic.APIConnectionError),
            reraise=True,
        )

        raw_text = ""
        async for attempt in retryer:
            with attempt:
                response = await client.messages.create(
                    model="claude-haiku-4-5",
                    max_tokens=256,
                    temperature=0,
                    system=_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_content}],  # type: ignore[list-item]
                )
                for block in response.content:
                    if hasattr(block, "text"):
                        raw_text = block.text
                        break

        return _parse_vision_response(raw_text)

    except (RetryError, anthropic.APIError) as exc:
        logger.exception("vision_matcher: API error: %s", exc)
        return VisualVerdict.UNCERTAIN, f"Error API: {exc.__class__.__name__}"
    except Exception as exc:  # noqa: BLE001
        logger.exception("vision_matcher: error inesperado: %s", exc)
        return VisualVerdict.UNCERTAIN, f"Error inesperado: {exc.__class__.__name__}"


def _parse_vision_response(text: str) -> tuple[VisualVerdict, str]:
    """Parsea la respuesta JSON del modelo a (VisualVerdict, reason).

    Robusto: extrae el primer bloque JSON si hay texto extra.
    """
    import json

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return VisualVerdict.UNCERTAIN, text[:200] if text else "sin respuesta del modelo"

    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return VisualVerdict.UNCERTAIN, text[:200]

    verdict_raw = str(data.get("verdict", "uncertain")).lower()
    reason = str(data.get("reason") or data.get("reasoning") or "")[:200]

    verdict_map = {
        "same_type": VisualVerdict.SAME_TYPE,
        "different_type": VisualVerdict.DIFFERENT_TYPE,
        "uncertain": VisualVerdict.UNCERTAIN,
    }
    verdict = verdict_map.get(verdict_raw, VisualVerdict.UNCERTAIN)
    return verdict, reason


__all__ = ["VisualVerdict", "compare_product_images"]
