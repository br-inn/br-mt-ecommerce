"""Adapter Amazon UAE — US-1B-04-04 shadow publish.

Sprint 8: export CSV canned para desarrollo/testing.
US-1B-04-04: shadow_publish escribe CSV real en /tmp sin llamar SP-API.
Sprint 9+: integración real con SP-API Listings/Pricing endpoint.
"""

from __future__ import annotations

import csv
import io
import logging
import os
import tempfile
from datetime import datetime, timezone
from uuid import uuid4

from app.services.pricing_export.publisher import ExportResult, PublishPayload

logger = logging.getLogger(__name__)

# Columnas exportadas en CSV hacia Amazon UAE
_CSV_HEADERS = ["sku", "price_aed", "status", "fx_rate", "approved_at"]


class AmazonUAEAdapter:
    """Amazon UAE SP-API pricing export adapter — skeleton Sprint 8.

    Sprint 8: implementación skeleton (stub). Shadow publish y export CSV
    generan respuesta canned para desarrollo/testing.
    Sprint 9+: integración real con SP-API Listings/Pricing endpoint.
    """

    channel_code: str = "AMAZON_UAE"

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
        """Shadow mode: valida el payload, genera el feed CSV y lo escribe en /tmp.

        En lugar de enviar a Amazon real, escribe en
        ``/tmp/shadow_amazon_uae_<timestamp>.csv`` y retorna
        ``ExportResult`` con ``shadow_mode=True``.

        Sprint 9+: reemplazar escritura en /tmp por llamada real al sandbox SP-API.
        """
        errors = self.validate_payload(payload)
        if errors:
            return ExportResult(
                ok=False,
                channel_code=self.channel_code,
                rows_exported=0,
                rows_blocked=len(errors),
                errors=errors,
                shadow_mode=True,
                exported_at=datetime.now(tz=timezone.utc),
            )

        # Generar CSV con misma lógica que export_csv
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
        for row in payload.rows:
            status = row.get("status", "")
            if status != "approved":
                rows_blocked += 1
                continue
            writer.writerow({h: row.get(h, "") for h in _CSV_HEADERS})
            rows_exported += 1

        csv_content = buf.getvalue()

        # Escribir en /tmp sin retornar bytes al cliente
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        shadow_filename = f"shadow_amazon_uae_{timestamp}.csv"
        shadow_path = os.path.join(tempfile.gettempdir(), shadow_filename)
        with open(shadow_path, "w", encoding="utf-8", newline="") as fh:
            fh.write(csv_content)

        logger.info(
            "SHADOW PUBLISH: %d rows written to %s",
            rows_exported,
            shadow_path,
        )

        return ExportResult(
            ok=True,
            channel_code=self.channel_code,
            rows_exported=rows_exported,
            rows_blocked=rows_blocked,
            submission_id=f"shadow-amz-{uuid4()}",
            shadow_mode=True,
            exported_at=datetime.now(tz=timezone.utc),
            raw={"shadow_path": shadow_path, "scheme_code": payload.scheme_code},
        )

    # ------------------------------------------------------------------
    # Export CSV
    # ------------------------------------------------------------------

    async def export_csv(self, payload: PublishPayload) -> tuple[bytes, ExportResult]:
        """Genera CSV con precios aprobados listo para descarga.

        Columnas: sku, price_aed, status, fx_rate, approved_at.
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
        for row in payload.rows:
            status = row.get("status", "")
            if status != "approved":
                rows_blocked += 1
                continue
            writer.writerow({h: row.get(h, "") for h in _CSV_HEADERS})
            rows_exported += 1

        csv_bytes = buf.getvalue().encode("utf-8")
        result = ExportResult(
            ok=True,
            channel_code=self.channel_code,
            rows_exported=rows_exported,
            rows_blocked=rows_blocked,
            shadow_mode=False,
            exported_at=datetime.now(tz=timezone.utc),
            raw={"stub": True, "scheme_code": payload.scheme_code},
        )
        return csv_bytes, result
