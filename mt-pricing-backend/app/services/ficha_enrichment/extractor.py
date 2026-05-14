"""Extrae campos del modelo de producto desde texto+tablas de una ficha técnica.

Usa Claude claude-sonnet-4-6 via anthropic SDK con tool_use para output estructurado.
Si no hay API key o MT_LIVE_NETWORK != 'true', devuelve resultado vacío sin lanzar.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

from app.schemas.ficha_enrich import (
    ExtractedAsset,
    ExtractedDimensionRow,
    ExtractedMaterial,
    ExtractedScalars,
    ExtractedSpecs,
    ExtractedTranslation,
    FichaExtractionResult,
    PageClassification,
)
from app.services.importer_datasheets.pdf_extractor import extract_pdf_metadata

logger = logging.getLogger(__name__)

_TOOL_SCHEMA: dict[str, Any] = {
    "name": "extract_product_fields",
    "description": (
        "Extrae todos los campos del modelo de producto de una ficha técnica PVF "
        "(válvulas, tuberías, accesorios). Omite los campos que no aparecen en el PDF."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "family": {"type": "string", "description": "Familia del producto (ej. 'válvulas de esfera')"},
            "subfamily": {"type": "string"},
            "type": {"type": "string", "description": "Tipo específico (ej. 'esfera roscada PN30')"},
            "material": {"type": "string", "description": "Material cuerpo canónico (ej. 'brass_cw617n', 'ss316')"},
            "dn": {"type": "string", "description": "Solo número sin prefijo DN (ej. '50')"},
            "pn": {"type": "string", "description": "Solo número sin prefijo PN (ej. '30')"},
            "connection": {"type": "string", "description": "Tipo de conexión (ej. 'bsp', 'npt', 'flanged')"},
            "brand": {"type": "string"},
            "temp_min_c": {"type": "integer", "description": "Temperatura mínima de trabajo en °C"},
            "temp_max_c": {"type": "integer", "description": "Temperatura máxima de trabajo en °C"},
            "pressure_max_bar": {"type": "number", "description": "Presión máxima en bar"},
            "weight": {"type": "number"},
            "weight_unit": {"type": "string", "enum": ["kg", "g", "lb"]},
            "size": {"type": "string", "description": "Rango de tamaños (ej. '1/4\" a 2\"')"},
            "specs": {
                "type": "object",
                "properties": {
                    "seat_material": {"type": "string"},
                    "seal_material": {"type": "string"},
                    "stem_material": {"type": "string"},
                    "standards": {"type": "array", "items": {"type": "string"}},
                    "certifications": {"type": "array", "items": {"type": "string"}},
                    "no_frost": {"type": "boolean"},
                    "actuation_type": {"type": "string"},
                    "bore_type": {"type": "string"},
                    "extra": {"type": "object"},
                },
            },
            "materials": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["component", "material"],
                    "properties": {
                        "component": {"type": "string", "enum": ["body", "seat", "stem", "seal", "disc", "nut", "handle"]},
                        "position": {"type": "integer", "default": 0},
                        "material": {"type": "string"},
                        "observations": {"type": "string"},
                    },
                },
            },
            "dimensions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["dn_label", "values"],
                    "properties": {
                        "dn_label": {"type": "string"},
                        "values": {"type": "object"},
                    },
                },
            },
            "translations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["lang"],
                    "properties": {
                        "lang": {"type": "string", "enum": ["es", "ar", "en"]},
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                    },
                },
            },
            "model_gaps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Información en PDF sin campo en el modelo (validación del modelo).",
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
            },
        },
        "required": ["confidence"],
    },
}

_PAGE_CLASSIFICATION_TOOL: dict[str, Any] = {
    "name": "classify_pdf_page",
    "description": "Clasifica una página de ficha técnica PVF.",
    "input_schema": {
        "type": "object",
        "required": ["kind", "confidence"],
        "properties": {
            "kind": {
                "type": "string",
                "enum": ["specs_text", "dimension_drawing", "section_drawing",
                         "pt_curve", "certificate", "exploded_view", "materials_table", "other"],
            },
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "description": {"type": "string"},
        },
    },
}

_PT_CURVE_TOOL: dict[str, Any] = {
    "name": "extract_pt_curve",
    "description": "Extrae puntos de la curva Presión-Temperatura de un gráfico.",
    "input_schema": {
        "type": "object",
        "required": ["points"],
        "properties": {
            "points": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["temperature_c", "pressure_max_bar"],
                    "properties": {
                        "temperature_c": {"type": "number"},
                        "pressure_max_bar": {"type": "number"},
                    },
                },
            },
        },
    },
}

_SYSTEM_PROMPT = (
    "Eres un especialista en datos de productos PVF (válvulas, tuberías, accesorios industriales). "
    "Tu tarea es extraer TODOS los campos del modelo de producto de una ficha técnica. "
    "Sé preciso: si no ves el dato claramente, no lo incluyas. "
    "Para materiales, usa nombres canónicos en inglés lowercase (brass_cw617n, ss316, ptfe, nbr, epdm). "
    "Para dn/pn, usa solo el número sin prefijo (ej. '30' no 'PN30'). "
    "El campo model_gaps es IMPORTANTE: lista todo lo que encuentres en el PDF que no tenga campo "
    "correspondiente en el modelo (ej. 'tabla de par de apriete', 'curva Kv', 'certificado CE número X')."
)

_PAGE_CLASSIFICATION_PROMPT = (
    "You are a PVF datasheet page classifier.\n"
    "Classify this PDF page into exactly one category:\n"
    "- specs_text: text with technical specs (temp, pressure, materials, standards)\n"
    "- dimension_drawing: dimensional drawing with measurements\n"
    "- section_drawing: cross-section view showing internal components\n"
    "- pt_curve: pressure-temperature curve or chart\n"
    "- certificate: certification page (CE, WRAS, ACS, etc.)\n"
    "- exploded_view: exploded/assembly view showing parts\n"
    "- materials_table: table listing materials by component\n"
    "- other: cover page, legal text, contact info\n"
    "Respond using the classify_pdf_page tool."
)

_PT_CURVE_PROMPT = (
    "This is a pressure-temperature (P/T) rating curve from a PVF datasheet. "
    "Extract all visible data points from the curve. "
    "Each point has a temperature in °C (x-axis) and maximum pressure in bar (y-axis). "
    "Use the extract_pt_curve tool to return the points array."
)

_ASSET_KIND_MAP = {
    "dimension_drawing": "dimension_drawing",
    "section_drawing": "section_drawing",
    "exploded_view": "exploded_3d",
    "certificate": "certificate_pdf",
}


def _live_enabled() -> bool:
    return os.environ.get("MT_LIVE_NETWORK", "").lower() == "true"


def _format_tables(tables: list[dict]) -> str:
    if not tables:
        return "(sin tablas detectadas)"
    lines: list[str] = []
    for t in tables:
        lines.append(f"[Página {t.get('page', '?')}]")
        headers = t.get("headers", [])
        rows = t.get("rows", [])
        if headers:
            lines.append(" | ".join(str(h) for h in headers))
        for row in rows[:20]:
            lines.append(" | ".join(str(c) for c in row))
        lines.append("")
    return "\n".join(lines)


def _parse_tool_response(response: Any) -> dict[str, Any]:
    for block in response.content:
        if hasattr(block, "type") and block.type == "tool_use":
            if hasattr(block, "name") and block.name in (
                "extract_product_fields", "classify_pdf_page", "extract_pt_curve"
            ):
                inp = block.input
                if isinstance(inp, str):
                    return json.loads(inp)
                return inp  # type: ignore[return-value]
    return {}


def _build_result(data: dict[str, Any], raw_text: str) -> FichaExtractionResult:
    specs_data = data.get("specs") or {}
    scalars = ExtractedScalars(
        family=data.get("family"),
        subfamily=data.get("subfamily"),
        type=data.get("type"),
        material=data.get("material"),
        dn=data.get("dn"),
        pn=data.get("pn"),
        connection=data.get("connection"),
        brand=data.get("brand"),
        weight=data.get("weight"),
        weight_unit=data.get("weight_unit"),
        temp_min_c=data.get("temp_min_c"),
        temp_max_c=data.get("temp_max_c"),
        pressure_max_bar=data.get("pressure_max_bar"),
        size=data.get("size"),
    )
    specs = ExtractedSpecs(
        seat_material=specs_data.get("seat_material"),
        seal_material=specs_data.get("seal_material"),
        stem_material=specs_data.get("stem_material"),
        standards=specs_data.get("standards") or [],
        certifications=specs_data.get("certifications") or [],
        no_frost=specs_data.get("no_frost"),
        actuation_type=specs_data.get("actuation_type"),
        bore_type=specs_data.get("bore_type"),
        extra=specs_data.get("extra") or {},
    )
    materials = [
        ExtractedMaterial(
            component=m["component"],
            position=m.get("position", 0),
            material=m["material"],
            observations=m.get("observations"),
        )
        for m in (data.get("materials") or [])
        if m.get("component") and m.get("material")
    ]
    dimensions = [
        ExtractedDimensionRow(dn_label=d["dn_label"], values=d.get("values", {}))
        for d in (data.get("dimensions") or [])
        if d.get("dn_label")
    ]
    translations = [
        ExtractedTranslation(lang=t["lang"], name=t.get("name"), description=t.get("description"))
        for t in (data.get("translations") or [])
        if t.get("lang")
    ]
    return FichaExtractionResult(
        scalars=scalars,
        specs=specs,
        materials=materials,
        dimensions=dimensions,
        translations=translations,
        model_gaps=data.get("model_gaps") or [],
        confidence=float(data.get("confidence") or 0.0),
        raw_text_preview=raw_text[:500],
    )


class FichaEnrichmentExtractor:
    """Extrae campos estructurados de un PDF ficha técnica usando Claude."""

    def __init__(self, *, api_key: str | None = None, model: str = "claude-sonnet-4-6") -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._model = model

    def _is_enabled(self) -> bool:
        return bool(self._api_key) and _live_enabled()

    async def extract(self, *, pdf_bytes: bytes, filename: str = "ficha.pdf") -> FichaExtractionResult:
        meta = extract_pdf_metadata(pdf_bytes)
        text: str = meta.get("text", "") or ""
        tables: list[dict] = meta.get("tables", []) or []

        if not self._is_enabled():
            logger.info("ficha_enrichment: extractor disabled (no API key or live network off)")
            return FichaExtractionResult(
                scalars=ExtractedScalars(),
                specs=ExtractedSpecs(),
                model_gaps=["extractor_disabled_no_api_key"],
                confidence=0.0,
                raw_text_preview=text[:500],
            )

        tables_str = _format_tables(tables)
        user_message = (
            f"Filename: {filename}\n\n"
            f"=== TEXTO EXTRAÍDO ===\n{text[:8000]}\n\n"
            f"=== TABLAS DETECTADAS ===\n{tables_str[:4000]}"
        )

        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=self._api_key)
            response = await client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=_SYSTEM_PROMPT,
                tools=[_TOOL_SCHEMA],
                tool_choice={"type": "tool", "name": "extract_product_fields"},
                messages=[{"role": "user", "content": user_message}],
            )
        except Exception as exc:
            logger.exception("ficha_enrichment: Claude call failed")
            return FichaExtractionResult(
                scalars=ExtractedScalars(),
                specs=ExtractedSpecs(),
                model_gaps=[f"claude_error: {type(exc).__name__}"],
                confidence=0.0,
                raw_text_preview=text[:500],
            )

        tool_input = _parse_tool_response(response)
        result = _build_result(tool_input, raw_text=text)

        # Page classification (only if enabled and PDF has content)
        if self._is_enabled() and pdf_bytes:
            try:
                import anthropic as _anthropic
                client2 = _anthropic.AsyncAnthropic(api_key=self._api_key)
                page_clfs, page_assets, pt_points = await self._classify_pages_and_extract(
                    pdf_bytes, client2
                )
                result.page_classifications = page_clfs
                result.extracted_assets = page_assets
                result.pt_curve_points = pt_points
            except Exception as exc:
                logger.warning("page_classify failed: %s", exc)

        return result

    async def _classify_pages_and_extract(
        self,
        pdf_bytes: bytes,
        client: Any,
        max_pages: int = 9,
    ) -> tuple[list[PageClassification], list[ExtractedAsset], list[dict[str, float]]]:
        from app.services.importer_datasheets.vision_extractor import _render_pdf_pages

        pngs = _render_pdf_pages(pdf_bytes, max_pages=max_pages, resolution=120)
        classifications: list[PageClassification] = []
        assets: list[ExtractedAsset] = []
        pt_points: list[dict[str, float]] = []

        for idx, png in enumerate(pngs):
            b64 = base64.b64encode(png).decode("ascii")
            try:
                resp = await client.messages.create(
                    model=self._model,
                    max_tokens=256,
                    tools=[_PAGE_CLASSIFICATION_TOOL],
                    tool_choice={"type": "tool", "name": "classify_pdf_page"},
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": _PAGE_CLASSIFICATION_PROMPT},
                            {"type": "image", "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": b64,
                            }},
                        ],
                    }],
                )
            except Exception as exc:
                logger.warning("page_classify failed idx=%d err=%s", idx, exc)
                continue

            tool_input = _parse_tool_response(resp)
            kind = tool_input.get("kind", "other")
            clf = PageClassification(
                page_index=idx,
                kind=kind,
                confidence=float(tool_input.get("confidence", 0.5)),
                description=tool_input.get("description", ""),
            )
            classifications.append(clf)

            if kind in _ASSET_KIND_MAP:
                assets.append(ExtractedAsset(
                    page_index=idx,
                    asset_kind=_ASSET_KIND_MAP[kind],
                    description=clf.description,
                    mime_type="image/png",
                ))

            if kind == "pt_curve":
                pts = await self._extract_pt_curve(png, client)
                pt_points.extend(pts)

        return classifications, assets, pt_points

    async def _extract_pt_curve(self, png_bytes: bytes, client: Any) -> list[dict[str, float]]:
        b64 = base64.b64encode(png_bytes).decode("ascii")
        try:
            resp = await client.messages.create(
                model=self._model,
                max_tokens=512,
                tools=[_PT_CURVE_TOOL],
                tool_choice={"type": "tool", "name": "extract_pt_curve"},
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _PT_CURVE_PROMPT},
                        {"type": "image", "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64,
                        }},
                    ],
                }],
            )
        except Exception as exc:
            logger.warning("pt_curve_extract failed: %s", exc)
            return []
        tool_input = _parse_tool_response(resp)
        return [
            {
                "temperature_c": float(p["temperature_c"]),
                "pressure_max_bar": float(p["pressure_max_bar"]),
            }
            for p in (tool_input.get("points") or [])
            if "temperature_c" in p and "pressure_max_bar" in p
        ]


__all__ = [
    "FichaEnrichmentExtractor",
    "_build_result",
    "_format_tables",
    "_parse_tool_response",
    "_PAGE_CLASSIFICATION_TOOL",
    "_PT_CURVE_TOOL",
]
