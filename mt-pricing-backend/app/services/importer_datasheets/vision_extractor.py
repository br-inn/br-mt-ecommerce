"""Vision-based datasheet extractor (US-1A-06-04-V2 stretch).

Convierte un PDF a imágenes página-por-página (vía ``pdfplumber.to_image()``)
y delega a un cliente Vision (OpenAI / Anthropic) para extraer specs
estructuradas (DN, PN, material, seal, plus extras) en formato JSON.

Diseño:
- Reutiliza la abstracción :class:`app.services.matching.vlm_judge.VLMClient`
  Protocol — aunque ese contrato es para "judge dos imágenes", acá usamos un
  *adapter* propio (``VisionExtractorClient`` Protocol) que recibe data-URLs
  png + un prompt y devuelve JSON. Los adapters concretos (OpenAI/Anthropic)
  se cablean encima de los mismos endpoints HTTP que vlm_judge — pero como
  el contrato de respuesta es distinto (specs vs verdict) mantenemos un
  Protocol específico aquí.
- ``MT_LIVE_NETWORK != true`` → no se llama proveedor (devuelve resultado
  vacío con razón). Mismo gate que el VLM judge.
- pdfplumber.to_image() puede fallar si el PDF está corrupto / no nativo →
  capturamos y devolvemos ``error`` sin lanzar.

Los tests inyectan un VisionExtractorClient mock para evitar HTTP y
Pillow/pdfplumber en CI.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class VisionPageResult:
    """Salida bruta del Vision API por página."""

    page_index: int
    raw_text: str
    parsed: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VisionExtractionResult:
    """Salida agregada multi-página."""

    pages: list[VisionPageResult] = field(default_factory=list)
    specs: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    error: str | None = None
    skipped: bool = False
    skip_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pages": [
                {
                    "page_index": p.page_index,
                    "raw_text": p.raw_text,
                    "parsed": dict(p.parsed),
                }
                for p in self.pages
            ],
            "specs": dict(self.specs),
            "confidence": round(self.confidence, 4),
            "error": self.error,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
        }


# ---------------------------------------------------------------------------
# Client Protocol
# ---------------------------------------------------------------------------
class VisionExtractorClient(Protocol):
    """Cliente Vision para extraer specs de una imagen-página.

    Contrato testeable: recibe PNG bytes + prompt, devuelve respuesta cruda
    (texto). El parseo a JSON lo hace el extractor (función
    :func:`_parse_vision_response`).
    """

    async def extract(self, *, png_bytes: bytes, prompt: str) -> str: ...


_PROMPT_TEMPLATE = (
    "You are an industrial PVF (pipes/valves/fittings) catalog auditor.\n"
    "Given the following datasheet page, extract any of these specs you can\n"
    "identify: DN (nominal diameter), PN (pressure rating), material,\n"
    "seal/sealing material. Respond ONLY with a JSON object with these\n"
    "fields (omit unknowns):\n"
    '  "dn": string (e.g. "DN50"),\n'
    '  "pn": string (e.g. "PN16"),\n'
    '  "material": string (e.g. "brass" / "ss316" / "ductile_iron"),\n'
    '  "seal": string (e.g. "epdm" / "nbr"),\n'
    '  "extra": object (any other relevant key/value)\n'
    'Filename: {filename}\n'
)


# ---------------------------------------------------------------------------
# Default client adapters
# ---------------------------------------------------------------------------
class OpenAIVisionExtractor:
    """Adapter Vision OpenAI — gpt-4o / gpt-4o-mini.

    Reusa el mismo HTTP shape que :class:`OpenAIVisionJudge` (vlm_judge) pero
    con prompt + parsing específico de specs.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        http_client: Any = None,
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._model = model
        self._http_client = http_client
        self._owns_client = http_client is None
        self._base_url = base_url

    async def _http(self) -> Any:
        if self._http_client is None:
            import httpx  # local import — opcional para tests

            self._http_client = httpx.AsyncClient(timeout=60.0)
        return self._http_client

    async def aclose(self) -> None:
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def extract(self, *, png_bytes: bytes, prompt: str) -> str:
        client = await self._http()
        b64 = base64.b64encode(png_bytes).decode("ascii")
        body = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64}"
                            },
                        },
                    ],
                }
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
        }
        resp = await client.post(
            f"{self._base_url}/chat/completions",
            json=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return str(data["choices"][0]["message"]["content"])


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------
def _parse_vision_response(text: str) -> dict[str, Any]:
    """Parsea respuesta cruda del Vision client → dict de specs.

    Robusto: si hay texto extra antes/después del JSON, busca el primer ``{``
    y último ``}``. Si no hay JSON parseable devuelve ``{}``.
    """
    if not text:
        return {}
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {}
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, Any] = {}
    for k in ("dn", "pn", "material", "seal"):
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            out[k] = v.strip()
    extra = data.get("extra")
    if isinstance(extra, dict):
        out["extra"] = {
            k: v for k, v in extra.items() if isinstance(k, str)
        }
    return out


def _live_enabled() -> bool:
    """Mismo gate que :class:`VLMJudge`. Off → no llamamos al proveedor."""
    val = os.environ.get("MT_LIVE_NETWORK", "false").strip().lower()
    return val in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Page rendering
# ---------------------------------------------------------------------------
def _render_pdf_pages(
    payload: bytes, *, max_pages: int = 4, resolution: int = 150
) -> list[bytes]:
    """Convierte un PDF en PNG bytes por página vía ``pdfplumber.to_image()``.

    Si pdfplumber no está disponible o el PDF no se puede abrir, devuelve
    ``[]``. ``max_pages`` cap defensivo para datasheets de 50+ páginas.
    """
    try:
        import pdfplumber  # type: ignore
    except Exception:  # noqa: BLE001
        logger.warning("vision_extractor: pdfplumber no instalado")
        return []

    pngs: list[bytes] = []
    try:
        with pdfplumber.open(io.BytesIO(payload)) as pdf:  # pragma: no cover
            for idx, page in enumerate(pdf.pages):
                if idx >= max_pages:
                    break
                try:
                    img = page.to_image(resolution=resolution)
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    pngs.append(buf.getvalue())
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "vision_extractor: page render failed idx=%d err=%s",
                        idx,
                        exc,
                    )
                    continue
    except Exception as exc:  # noqa: BLE001
        logger.warning("vision_extractor: pdf open failed err=%s", exc)
        return []
    return pngs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
class VisionExtractor:
    """Servicio público — combina render + Vision client + parser.

    Tests inyectan ``client`` mock + ``page_renderer`` mock para evitar
    pdfplumber / Pillow / HTTP.
    """

    def __init__(
        self,
        *,
        client: VisionExtractorClient | None = None,
        page_renderer: Any = None,
        max_pages: int = 4,
    ) -> None:
        self._client = client
        self._page_renderer = page_renderer or _render_pdf_pages
        self._max_pages = max_pages

    def _resolve_client(self) -> VisionExtractorClient | None:
        if self._client is not None:
            return self._client
        provider = os.environ.get("VLM_JUDGE_PROVIDER", "openai").lower()
        if provider == "openai" and os.environ.get("OPENAI_API_KEY"):
            return OpenAIVisionExtractor()
        return None

    async def extract(
        self,
        *,
        pdf_bytes: bytes,
        filename: str = "datasheet.pdf",
    ) -> VisionExtractionResult:
        if not _live_enabled():
            return VisionExtractionResult(
                skipped=True,
                skip_reason="vision_disabled_live_network_off",
            )

        client = self._resolve_client()
        if client is None:
            return VisionExtractionResult(
                skipped=True,
                skip_reason="vision_provider_not_configured",
            )

        try:
            pngs = self._page_renderer(pdf_bytes, max_pages=self._max_pages)
        except Exception as exc:  # noqa: BLE001
            logger.exception("vision_extractor: render failed")
            return VisionExtractionResult(
                error=f"pdf_render_failed: {type(exc).__name__}",
            )

        if not pngs:
            return VisionExtractionResult(
                error="pdf_render_empty",
            )

        prompt = _PROMPT_TEMPLATE.format(filename=filename)
        agg_specs: dict[str, Any] = {}
        confidences: list[float] = []
        pages_out: list[VisionPageResult] = []
        for idx, png in enumerate(pngs):
            try:
                raw = await client.extract(png_bytes=png, prompt=prompt)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "vision_extractor: client.extract failed idx=%d err=%s",
                    idx,
                    exc,
                )
                pages_out.append(
                    VisionPageResult(page_index=idx, raw_text="", parsed={})
                )
                continue
            parsed = _parse_vision_response(raw)
            pages_out.append(
                VisionPageResult(page_index=idx, raw_text=raw, parsed=parsed)
            )
            # Merge: la primera página que reporta cada spec gana (datasheets
            # tienen el header en pág 1 — buena heurística para PVF).
            for k in ("dn", "pn", "material", "seal"):
                if k in parsed and k not in agg_specs:
                    agg_specs[k] = parsed[k]
            extra_in = parsed.get("extra")
            if isinstance(extra_in, dict) and extra_in:
                merged_extra = dict(agg_specs.get("extra") or {})
                for ek, ev in extra_in.items():
                    if ek not in merged_extra:
                        merged_extra[ek] = ev
                agg_specs["extra"] = merged_extra
            # Confidence heurístico: count specs / 4 (max DN/PN/material/seal).
            recognized = sum(
                1 for k in ("dn", "pn", "material", "seal") if k in parsed
            )
            confidences.append(recognized / 4.0)

        confidence = (
            sum(confidences) / len(confidences) if confidences else 0.0
        )

        return VisionExtractionResult(
            pages=pages_out,
            specs=agg_specs,
            confidence=round(confidence, 4),
        )


__all__ = [
    "OpenAIVisionExtractor",
    "VisionExtractionResult",
    "VisionExtractor",
    "VisionExtractorClient",
    "VisionPageResult",
    "_parse_vision_response",
    "_render_pdf_pages",
]
