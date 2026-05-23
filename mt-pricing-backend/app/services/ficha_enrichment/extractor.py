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
    ExtractedCertificate,
    ExtractedDimensionRow,
    ExtractedFlowData,
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
        "Extract all product model fields from a PVF datasheet "
        "(valves, pipes, fittings). Omit fields not found in the PDF. "
        "ALL text output MUST be in English."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "family": {
                "type": "string",
                "description": "Product family in English matching the catalog (e.g. 'Ball Valve', 'Butterfly Valve', 'Gate Valve', 'Check Valve', 'Angle Valve'). English only.",
            },
            "subfamily": {
                "type": "string",
                "description": "Product subfamily in English (e.g. 'Threaded ball valve with ergonomic handle', 'Full bore butterfly valve').",
            },
            "type": {
                "type": "string",
                "description": "Specific product type in English (e.g. 'Threaded ball valve PN30', 'Wafer butterfly valve PN16').",
            },
            "material": {
                "type": "string",
                "description": "Canonical body material code in lowercase English (e.g. 'brass_cw617n', 'ss316', 'cast_iron').",
            },
            "dn": {
                "type": "string",
                "description": "Nominal diameter number only, no DN prefix (e.g. '50').",
            },
            "pn": {
                "type": "string",
                "description": "Nominal pressure number only, no PN prefix (e.g. '30').",
            },
            "connection": {
                "type": "string",
                "description": "Connection standard code only (e.g. 'bsp', 'npt', 'flanged', 'wafer'). Do NOT include gender here.",
            },
            "brand": {
                "type": "string",
                "description": "Brand using canonical catalog name: 'MT' or 'MT Middle East'. If PDF shows 'MT Business Key', 'MT BK', 'MTBK' or similar → use 'MT'.",
            },
            "temp_min_c": {"type": "integer", "description": "Minimum working temperature in °C."},
            "temp_max_c": {"type": "integer", "description": "Maximum working temperature in °C."},
            "pressure_max_bar": {
                "type": "number",
                "description": "Maximum working pressure in bar.",
            },
            "weight": {"type": "number"},
            "weight_unit": {"type": "string", "enum": ["kg", "g", "lb"]},
            "specs": {
                "type": "object",
                "properties": {
                    "seat_material": {
                        "type": "string",
                        "description": "Seat material in English (e.g. 'PTFE', 'EPDM').",
                    },
                    "seal_material": {
                        "type": "string",
                        "description": "Seal material in English (e.g. 'NBR', 'PTFE').",
                    },
                    "stem_material": {
                        "type": "string",
                        "description": "Stem material in English (e.g. 'Stainless steel', 'Brass CW617N').",
                    },
                    "standards": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Applicable standards (e.g. 'EN-ISO-228', 'EN-19').",
                    },
                    "certifications": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Certification codes (e.g. 'WRAS', 'ACS', 'PZH').",
                    },
                    "no_frost": {"type": "boolean"},
                    "actuation_type": {
                        "type": "string",
                        "description": "Actuation type in English (e.g. 'manual lever', 'pneumatic', 'electric').",
                    },
                    "bore_type": {
                        "type": "string",
                        "description": "Bore type in English (e.g. 'full bore', 'reduced bore').",
                    },
                    "end_connection_gender": {
                        "type": "string",
                        "enum": ["male-female", "female-female", "male-male"],
                        "description": "Gender configuration of threaded connections. 'male-female' = external thread on both ends (most common for inline valves). 'female-female' = internal thread on both ends. 'male-male' = both ends external. Only for threaded connections (bsp, npt, metric). Omit for flanged/wafer.",
                    },
                    "inlet_connection": {
                        "type": "string",
                        "description": "Inlet (entry) connection standard if different from outlet (e.g. 'bsp', 'flanged'). Omit if inlet equals outlet — use the top-level 'connection' field instead. Use only for asymmetric products (reducers, Y-strainers with blowdown, angle valves).",
                    },
                    "outlet_connection": {
                        "type": "string",
                        "description": "Outlet (exit) connection standard if different from inlet (e.g. 'bsp', 'flanged'). Omit if outlet equals inlet.",
                    },
                    "extra": {
                        "type": "object",
                        "description": (
                            "Additional fields without a dedicated slot. All values in English. "
                            "Use 'product_line' for product line names (e.g. 'Gold Series')."
                        ),
                    },
                },
            },
            "materials": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["component", "material"],
                    "properties": {
                        "component": {
                            "type": "string",
                            "enum": [
                                "body",
                                "closure",
                                "seat",
                                "gasket",
                                "screen",
                                "actuator_housing",
                                "stem",
                                "handle",
                                "other",
                            ],
                        },
                        "position": {"type": "integer", "default": 0},
                        "material": {"type": "string", "description": "Material name in English."},
                        "observations": {
                            "type": "string",
                            "description": "Additional observations in English.",
                        },
                        "material_grade": {
                            "type": "string",
                            "description": "Material grade per standard (e.g. EN-GJL-250, CW617N, AISI 304).",
                        },
                        "material_standard": {
                            "type": "string",
                            "description": "Material standard (e.g. UNE-EN-12165, ASTM A307).",
                        },
                        "surface_treatment": {
                            "type": "string",
                            "description": "Surface treatment in English (e.g. Nickel, Epoxy, Zinc, None).",
                        },
                    },
                },
            },
            "dimensions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["dn_label", "values"],
                    "properties": {
                        "dn_label": {
                            "type": "string",
                            "description": "DN label as it appears in the table (e.g. '1/2\"', 'DN15').",
                        },
                        "values": {"type": "object"},
                        "dn_secondary_label": {
                            "type": "string",
                            "description": "Outlet DN for reducers (e.g. '3/8\"' in a 1/2 x 3/8 reduction).",
                        },
                    },
                },
            },
            "translations": {
                "type": "array",
                "description": (
                    "Product name and description per language. "
                    "Extract ALWAYS if the PDF has bilingual text. "
                    "Include lang='es' for Spanish and lang='en' for English. "
                    "Each translation entry text must be in the language specified by lang."
                ),
                "items": {
                    "type": "object",
                    "required": ["lang"],
                    "properties": {
                        "lang": {"type": "string", "enum": ["es", "ar", "en"]},
                        "name": {
                            "type": "string",
                            "description": "Commercial product name in this language.",
                        },
                        "description": {
                            "type": "string",
                            "description": "Technical description in this language.",
                        },
                    },
                },
            },
            "model_gaps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Information found in the PDF with no corresponding model field (model validation). Write in English.",
            },
            "certificates": {
                "type": "array",
                "description": "Certifications detected in the PDF (ACS, WRAS, PZH, CE/PED, etc.).",
                "items": {
                    "type": "object",
                    "required": ["certification_code"],
                    "properties": {
                        "certification_code": {
                            "type": "string",
                            "description": "Code: ACS | WRAS | PZH | CE | FM | ISO9001.",
                        },
                        "cert_number": {"type": "string"},
                        "issuer": {
                            "type": "string",
                            "description": "Issuing body (e.g. Carso, BSI, TÜV).",
                        },
                        "issued_at": {
                            "type": "string",
                            "description": "Issue date ISO format (YYYY-MM-DD).",
                        },
                        "expires_at": {
                            "type": "string",
                            "description": "Expiry date ISO format (YYYY-MM-DD).",
                        },
                        "signatory_name": {"type": "string"},
                        "signatory_role": {"type": "string"},
                    },
                },
            },
            "flow_data": {
                "type": "array",
                "description": "Kv/Cv flow coefficients and filter mesh size per DN (strainers/filters).",
                "items": {
                    "type": "object",
                    "required": ["dn_label"],
                    "properties": {
                        "dn_label": {
                            "type": "string",
                            "description": "DN label as it appears in the table.",
                        },
                        "kv": {"type": "number", "description": "Flow coefficient Kv (m³/h)."},
                        "cv": {"type": "number", "description": "Flow coefficient Cv (US gpm)."},
                        "mesh_mm": {
                            "type": "number",
                            "description": "Mesh size in mm (e.g. 1.8, 1.0).",
                        },
                    },
                },
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
                "enum": [
                    "specs_text",
                    "dimension_drawing",
                    "section_drawing",
                    "pt_curve",
                    "certificate",
                    "exploded_view",
                    "materials_table",
                    "other",
                ],
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
    "You are a PVF product data specialist (valves, pipes, industrial fittings). "
    "Your task is to extract ALL product model fields from a technical datasheet. "
    "Be precise: if a value is not clearly visible in the PDF, do not include it. "
    "\n\nLANGUAGE RULE — CRITICAL: ALL output fields must be in English, "
    "regardless of the language of the PDF. This includes family, subfamily, type, "
    "material descriptions, observations, model_gaps, and any free-text fields. "
    "The ONLY exception is the 'translations' array, where each entry must be "
    "written in the language specified by its 'lang' field. "
    "\n\nMATERIALS: Use canonical lowercase English codes (brass_cw617n, ss316, ptfe, nbr, epdm). "
    "DN/PN: use the number only, no prefix (e.g. '30' not 'PN30'). "
    "\n\nTRANSLATIONS: If the PDF contains bilingual text (e.g. Spanish and English in parallel columns), "
    "extract the commercial name and description in both languages using lang='es' and lang='en'. "
    "Example: a PDF with 'Válvula de esfera / Ball valve' → extract both translations. "
    "\n\nPRODUCT LINE: If you find a product line or range name (e.g. 'GOLD SERIES', 'Premium Line'), "
    "store it in specs.extra.product_line. "
    "\n\nDN: The 'dn' field must be the main nominal size in mm (e.g. '15' for DN15). "
    "\n\nmodel_gaps is IMPORTANT: list in English everything found in the PDF that has no "
    "corresponding model field (e.g. 'torque table', 'Kv curve', 'CE certificate number X')."
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
                "extract_product_fields",
                "classify_pdf_page",
                "extract_pt_curve",
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
            component=m.get("component", "body"),
            position=m.get("position", 0),
            material=m.get("material", ""),
            observations=m.get("observations"),
            material_grade=m.get("material_grade"),
            material_standard=m.get("material_standard"),
            surface_treatment=m.get("surface_treatment"),
        )
        for m in (data.get("materials") or [])
        if m.get("component") and m.get("material")
    ]
    dimensions = [
        ExtractedDimensionRow(
            dn_label=d.get("dn_label", ""),
            values=d.get("values", {}),
            dn_secondary_label=d.get("dn_secondary_label"),
        )
        for d in (data.get("dimensions") or [])
        if d.get("dn_label")
    ]
    translations = [
        ExtractedTranslation(lang=t["lang"], name=t.get("name"), description=t.get("description"))
        for t in (data.get("translations") or [])
        if t.get("lang")
    ]
    certificates = [
        ExtractedCertificate(
            **{k: v for k, v in c.items() if k in ExtractedCertificate.model_fields}
        )
        for c in (data.get("certificates") or [])
        if c.get("certification_code")
    ]
    flow_data = [
        ExtractedFlowData(**{k: v for k, v in fd.items() if k in ExtractedFlowData.model_fields})
        for fd in (data.get("flow_data") or [])
        if fd.get("dn_label")
    ]
    return FichaExtractionResult(
        scalars=scalars,
        specs=specs,
        materials=materials,
        dimensions=dimensions,
        translations=translations,
        certificates=certificates,
        flow_data=flow_data,
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

    async def extract(
        self,
        *,
        pdf_bytes: bytes,
        filename: str = "ficha.pdf",
        classify_pages: bool = False,
    ) -> FichaExtractionResult:
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

        # Page classification es opcional — caro en tiempo (N llamadas visión en paralelo).
        # Los endpoints de preview la omiten; se puede activar explícitamente.
        if classify_pages and pdf_bytes:
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

    async def _classify_page(
        self,
        idx: int,
        png: bytes,
        client: Any,
    ) -> tuple[PageClassification | None, ExtractedAsset | None, list[dict[str, float]]]:
        """Clasifica una sola página — se llama en paralelo via asyncio.gather."""
        b64 = base64.b64encode(png).decode("ascii")
        try:
            resp = await client.messages.create(
                model=self._model,
                max_tokens=256,
                tools=[_PAGE_CLASSIFICATION_TOOL],
                tool_choice={"type": "tool", "name": "classify_pdf_page"},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": _PAGE_CLASSIFICATION_PROMPT},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": b64,
                                },
                            },
                        ],
                    }
                ],
            )
        except Exception as exc:
            logger.warning("page_classify failed idx=%d err=%s", idx, exc)
            return None, None, []

        tool_input = _parse_tool_response(resp)
        kind = tool_input.get("kind", "other")
        clf = PageClassification(
            page_index=idx,
            kind=kind,
            confidence=float(tool_input.get("confidence", 0.5)),
            description=tool_input.get("description", ""),
        )
        asset: ExtractedAsset | None = None
        if kind in _ASSET_KIND_MAP:
            asset = ExtractedAsset(
                page_index=idx,
                asset_kind=_ASSET_KIND_MAP[kind],
                description=clf.description,
                mime_type="image/png",
            )
        pt_points: list[dict[str, float]] = []
        if kind == "pt_curve":
            pt_points = await self._extract_pt_curve(png, client)
        return clf, asset, pt_points

    async def _classify_pages_and_extract(
        self,
        pdf_bytes: bytes,
        client: Any,
        max_pages: int = 9,
    ) -> tuple[list[PageClassification], list[ExtractedAsset], list[dict[str, float]]]:
        import asyncio
        from app.services.importer_datasheets.vision_extractor import _render_pdf_pages

        pngs = _render_pdf_pages(pdf_bytes, max_pages=max_pages, resolution=120)

        # Clasificar todas las páginas en paralelo — reduce N×15s a ~15s.
        page_results = await asyncio.gather(
            *[self._classify_page(idx, png, client) for idx, png in enumerate(pngs)],
            return_exceptions=True,
        )

        classifications: list[PageClassification] = []
        assets: list[ExtractedAsset] = []
        pt_points: list[dict[str, float]] = []

        for res in page_results:
            if isinstance(res, BaseException):
                logger.warning("page_classify task raised: %s", res)
                continue
            clf, asset, pts = res
            if clf:
                classifications.append(clf)
            if asset:
                assets.append(asset)
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
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": _PT_CURVE_PROMPT},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": b64,
                                },
                            },
                        ],
                    }
                ],
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
    "_TOOL_SCHEMA",
    "_PAGE_CLASSIFICATION_TOOL",
    "_PT_CURVE_TOOL",
]
