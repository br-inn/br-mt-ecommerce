"""Adapter Shopify — skeleton Sprint 8.

Sprint 8: implementación skeleton (stub). Shadow publish, export CSV y
export JSON-lines generan respuesta canned para desarrollo/testing.
Sprint 9+: integración real con Shopify Admin API / Hydrogen.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from uuid import uuid4

from app.services.pricing_export.publisher import ExportResult, PublishPayload

_CSV_HEADERS = ["sku", "price_aed", "status", "fx_rate", "approved_at"]


class ShopifyAdapter:
    """Shopify Plus / Hydrogen pricing export adapter — skeleton Sprint 8.

    Sprint 8: implementación skeleton (stub). Shadow publish, export CSV y
    export JSON-lines generan respuesta canned para desarrollo/testing.
    Sprint 9+: integración real con Shopify Admin API / Hydrogen storefront.

    Diferencia respecto a Amazon/Noon: ``export_csv`` también incluye una
    versión JSON-lines del payload (un objeto JSON por línea) adjunta en el
    campo ``raw`` del resultado, útil para ingestión directa vía Shopify
    Bulk Operations.
    """

    channel_code: str = "SHOPIFY"

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    def validate_payload(self, payload: PublishPayload) -> list[dict]:
        """Valida que todas las filas tengan ``sku`` y ``price_aed > 0``.

        Retorna lista de errores ``[{field, row, code, message}]``.
        Lista vacía = payload válido.
        """
        errors: list[dict] = []
        for idx, row in enumerate(payload.rows):
            sku = row.get("sku", "")
            if not sku:
                errors.append(
                    {
                        "field": "sku",
                        "row": idx,
                        "code": "MISSING_SKU",
                        "message": f"Fila {idx}: campo 'sku' ausente o vacío.",
                    }
                )
            price = row.get("price_aed", 0)
            try:
                price_val = float(price)
            except (TypeError, ValueError):
                price_val = 0.0
            if price_val <= 0:
                errors.append(
                    {
                        "field": "price_aed",
                        "row": idx,
                        "code": "INVALID_PRICE",
                        "message": f"Fila {idx}: 'price_aed' debe ser > 0 (recibido: {price!r}).",
                    }
                )
        return errors

    # ------------------------------------------------------------------
    # Shadow publish
    # ------------------------------------------------------------------

    async def shadow_publish(self, payload: PublishPayload) -> ExportResult:
        """Envía a sandbox de Shopify y captura respuesta.

        Sprint 8: stub — no hace HTTP real. ``shadow_mode=True``.
        """
        return ExportResult(
            ok=True,
            channel_code=self.channel_code,
            rows_exported=len(payload.rows),
            rows_blocked=0,
            submission_id=f"stub-shopify-{uuid4()}",
            shadow_mode=True,
            exported_at=datetime.now(tz=UTC),
            raw={"stub": True, "scheme_code": payload.scheme_code},
        )

    # ------------------------------------------------------------------
    # Export CSV (+ JSON-lines en raw)
    # ------------------------------------------------------------------

    async def export_csv(self, payload: PublishPayload) -> tuple[bytes, ExportResult]:
        """Genera CSV con precios aprobados listo para descarga.

        Columnas: sku, price_aed, status, fx_rate, approved_at.

        Adicionalmente, el campo ``raw`` del resultado incluye
        ``jsonl_content`` con las mismas filas en formato JSON-lines
        (un dict JSON por línea), útil para Shopify Bulk Operations.

        Retorna ``(csv_bytes, ExportResult)``.
        """
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=_CSV_HEADERS,
            extrasaction="ignore",
            lineterminator="\r\n",
        )
        writer.writeheader()

        rows_exported = 0
        rows_blocked = 0
        jsonl_lines: list[str] = []

        for row in payload.rows:
            status = row.get("status", "")
            if status != "approved":
                rows_blocked += 1
                continue
            filtered = {h: row.get(h, "") for h in _CSV_HEADERS}
            writer.writerow(filtered)
            jsonl_lines.append(json.dumps(filtered, ensure_ascii=False, default=str))
            rows_exported += 1

        csv_bytes = buf.getvalue().encode("utf-8")
        result = ExportResult(
            ok=True,
            channel_code=self.channel_code,
            rows_exported=rows_exported,
            rows_blocked=rows_blocked,
            shadow_mode=False,
            exported_at=datetime.now(tz=UTC),
            raw={
                "stub": True,
                "scheme_code": payload.scheme_code,
                "jsonl_content": "\n".join(jsonl_lines),
            },
        )
        return csv_bytes, result
