"""llm_spec_extractor.py — Extractor de specs técnicas de texto Amazon via Claude Haiku 4.5.

Usa tool_use de Anthropic SDK para extraer specs estructuradas de texto libre
del PDP de Amazon. Temperature=0 para determinismo máximo.

Resultado: AmazonSpecsExtracted (Pydantic) con campos opcionales.
Si falla → retorna AmazonSpecsExtracted vacío (todos None, confidence=0.0).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import anthropic
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema de salida
# ---------------------------------------------------------------------------


class AmazonSpecsExtracted(BaseModel):
    """Specs técnicas extraídas del PDP de Amazon por Claude Haiku."""

    material: str | None = Field(
        None,
        description='Material canónico: "brass", "ss316", "cast_iron", "carbon_steel", etc.',
    )
    valve_type: str | None = Field(
        None,
        description='Tipo de válvula: "ball_valve", "gate_valve", "butterfly_valve", "check_valve", etc.',
    )
    size_inches: str | None = Field(
        None,
        description='Tamaño en pulgadas como string: "1/2", "3/4", "1", "1 1/2", "2"',
    )
    size_dn: int | None = Field(
        None, description="Tamaño en DN (diámetro nominal): 15, 20, 25, 32, 40, 50, 80, 100"
    )
    pressure_pn: int | None = Field(
        None, description="Presión nominal PN: 6, 10, 16, 25, 40"
    )
    end_connection: str | None = Field(
        None,
        description='Tipo de conexión: "BSP", "NPT", "FLANGED", "WAFER", "WELD", "PRESS_FIT"',
    )
    end_connection_gender: str | None = Field(
        None,
        description='Género de las conexiones roscadas: "male-female", "female-female", "male-male". null si no se especifica.',
    )
    bore_type: str | None = Field(
        None,
        description='Tipo de paso: "full_bore" (paso total) o "reduced_bore" (paso reducido). null si no se especifica.',
    )
    seat_material: str | None = Field(
        None,
        description='Material del asiento: "PTFE", "RPTFE", "EPDM", "NBR", "FKM", "metal". null si no se menciona.',
    )
    seal_material: str | None = Field(
        None,
        description='Material del sello/O-ring: "NBR", "EPDM", "FKM", "PTFE". null si no se menciona.',
    )
    alloy_code: str | None = Field(
        None,
        description='Código de aleación exacto si está presente: "CW617N", "AISI316", "A105", "CF8M"',
    )
    confidence: float = Field(
        0.0,
        description="Confianza global de la extracción en [0.0, 1.0]",
    )


# ---------------------------------------------------------------------------
# Tool schema para Anthropic tool_use
# ---------------------------------------------------------------------------

_EXTRACT_TOOL: dict[str, Any] = {
    "name": "extract_amazon_specs",
    "description": (
        "Extrae specs técnicas estructuradas de un producto industrial (válvulas, fittings, tuberías) "
        "a partir del título y descripción del listing de Amazon. "
        "Si un campo no está claramente indicado en el texto, déjalo null. "
        "NO inventes specs. Prefiere null a una respuesta incierta."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "material": {
                "type": ["string", "null"],
                "description": 'Material canónico: "brass", "ss316", "ss304", "cast_iron", "carbon_steel", "bronze", "pvc". null si no está claro.',
            },
            "valve_type": {
                "type": ["string", "null"],
                "description": 'Tipo: "ball_valve", "gate_valve", "butterfly_valve", "check_valve", "globe_valve", "strainer", "angle_valve". null si no es una válvula o no está claro.',
            },
            "size_inches": {
                "type": ["string", "null"],
                "description": 'Tamaño en pulgadas como string exacto del texto: "1/2", "3/4", "1", "1 1/2", "2". null si no aparece.',
            },
            "size_dn": {
                "type": ["integer", "null"],
                "description": "Diámetro nominal DN como entero: 15, 20, 25, 32, 40, 50. null si no aparece.",
            },
            "pressure_pn": {
                "type": ["integer", "null"],
                "description": "Presión PN como entero: 6, 10, 16, 25, 40. null si no aparece.",
            },
            "end_connection": {
                "type": ["string", "null"],
                "description": 'Tipo de conexión en mayúsculas: "BSP", "NPT", "FLANGED", "WAFER", "WELD", "PRESS_FIT", "COMPRESSION". Solo el estándar, sin género. null si no está claro.',
            },
            "end_connection_gender": {
                "type": ["string", "null"],
                "enum": ["male-female", "female-female", "male-male", None],
                "description": 'Género de las conexiones roscadas si se especifica explícitamente en el texto: "male-female" (roscas externas en ambos extremos), "female-female" (internas en ambos), "male-male" (ambas externas). null si no se menciona.',
            },
            "bore_type": {
                "type": ["string", "null"],
                "enum": ["full_bore", "reduced_bore", None],
                "description": '"full_bore" si el texto menciona "full bore", "full port", "full flow", paso total. "reduced_bore" si menciona "reduced bore", "standard bore". null si no está claro.',
            },
            "seat_material": {
                "type": ["string", "null"],
                "description": 'Material del asiento si se menciona explícitamente: "PTFE", "RPTFE", "EPDM", "NBR", "FKM", "metal". null si no aparece.',
            },
            "seal_material": {
                "type": ["string", "null"],
                "description": 'Material del sello/O-ring si se menciona explícitamente: "NBR", "EPDM", "FKM", "PTFE". null si no aparece.',
            },
            "alloy_code": {
                "type": ["string", "null"],
                "description": 'Código de aleación exacto si aparece en el texto: "CW617N", "CW602N", "AISI316", "A105", "CF8M". null si no aparece.',
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Confianza global: 1.0 si todos los campos encontrados son explícitos; 0.5 si algunos son inferidos; 0.2 si el producto no parece PVF industrial.",
            },
        },
        "required": ["confidence"],
    },
}

_SYSTEM_PROMPT = (
    "Eres un experto en catálogos técnicos de PVF (pipes, valves, fittings) industriales. "
    "Tu tarea es extraer specs estructuradas de listings de Amazon. "
    "Reglas estrictas:\n"
    "1. NO inventes specs. Si un campo no aparece explícitamente en el texto, devuelve null.\n"
    "2. Prefiere null a una respuesta incierta.\n"
    "3. Los códigos de aleación (CW617N, AISI316) deben estar textualmente en el título/descripción.\n"
    "4. El campo confidence refleja qué tan confiado estás de la extracción completa (no de un campo solo)."
)


# ---------------------------------------------------------------------------
# Función pública
# ---------------------------------------------------------------------------


async def extract_specs_from_amazon_text(
    amazon_title: str,
    amazon_description: str = "",
    amazon_specs_raw: dict[str, Any] | None = None,
) -> AmazonSpecsExtracted:
    """Extrae specs técnicas de texto libre de Amazon usando Claude Haiku 4.5.

    Args:
        amazon_title: Título del listing de Amazon.
        amazon_description: Descripción o bullet points del PDP.
        amazon_specs_raw: Dict con specs crudas del PDP (thread_size, material_type, etc.).

    Returns:
        AmazonSpecsExtracted con los campos encontrados. Si falla → todos None, confidence=0.0.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("llm_spec_extractor: ANTHROPIC_API_KEY no configurado — retornando vacío")
        return AmazonSpecsExtracted()

    # Construir texto de entrada
    parts: list[str] = []
    if amazon_title:
        parts.append(f"Title: {amazon_title}")
    if amazon_description:
        parts.append(f"Description: {amazon_description[:2000]}")  # cap para no inflar tokens
    if amazon_specs_raw:
        specs_lines = [f"  {k}: {v}" for k, v in amazon_specs_raw.items() if v]
        if specs_lines:
            parts.append("Technical specs from PDP:\n" + "\n".join(specs_lines))

    if not parts:
        return AmazonSpecsExtracted()

    user_message = "\n\n".join(parts)

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        # Anthropic prompt caching (US-SCR-04-08a): el system prompt es largo y
        # repetitivo entre llamadas → cache_control ephemeral ahorra tokens de entrada.
        # Requiere modelo compatible con prompt caching (claude-haiku-4-5+).
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            temperature=0,  # determinismo crítico
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=[_EXTRACT_TOOL],  # type: ignore[list-item]
            tool_choice={"type": "tool", "name": "extract_amazon_specs"},
            messages=[{"role": "user", "content": user_message}],
        )

        # Extraer el tool_use block
        tool_input: dict[str, Any] | None = None
        for block in response.content:
            if block.type == "tool_use" and block.name == "extract_amazon_specs":
                tool_input = block.input  # type: ignore[assignment]
                break

        if tool_input is None:
            logger.warning("llm_spec_extractor: modelo no llamó la tool — retornando vacío")
            return AmazonSpecsExtracted()

        return AmazonSpecsExtracted(
            material=tool_input.get("material"),
            valve_type=tool_input.get("valve_type"),
            size_inches=tool_input.get("size_inches"),
            size_dn=tool_input.get("size_dn"),
            pressure_pn=tool_input.get("pressure_pn"),
            end_connection=tool_input.get("end_connection"),
            end_connection_gender=tool_input.get("end_connection_gender"),
            bore_type=tool_input.get("bore_type"),
            seat_material=tool_input.get("seat_material"),
            seal_material=tool_input.get("seal_material"),
            alloy_code=tool_input.get("alloy_code"),
            confidence=float(tool_input.get("confidence") or 0.0),
        )

    except anthropic.APIError as exc:
        logger.exception("llm_spec_extractor: Anthropic API error: %s", exc)
        return AmazonSpecsExtracted()
    except Exception as exc:  # noqa: BLE001
        logger.exception("llm_spec_extractor: error inesperado: %s", exc)
        return AmazonSpecsExtracted()


__all__ = ["AmazonSpecsExtracted", "extract_specs_from_amazon_text"]
