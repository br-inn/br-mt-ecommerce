"""One-shot seed: parse the standalone Pricing Desk HTML and populate the DB.

Reads `Documentos referencia de articulos/Herramientas Manuales/
MT_Amazon_UAE_App_Pricing_Desk_260526_1947.html` and inserts/updates:
  - products.pe_eur, catalog_pvp_eur, weight
  - channel_product_logistics (inbound, storage, fulfillment, default_scheme)

Run once:
    docker exec mt-backend python /app/app/scripts/seed_amazon_uae_from_html.py

Idempotent. Products NOT in the products table are reported as 'skipped'
(this script does NOT create products -- only updates existing ones).
"""
from __future__ import annotations

import asyncio
import json
import re
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_sessionmaker

DATA_RE = re.compile(r"const\s+DATA\s*=\s*(\[.*?\]);", re.DOTALL)
HTML_DEFAULT_PATH = Path(
    "/app/Documentos referencia de articulos/Herramientas Manuales/"
    "MT_Amazon_UAE_App_Pricing_Desk_260526_1947.html"
)

SCHEME_MAP = {"fba": "canal_full", "easyship": "canal_lastmile"}


def extract_data_array(html: str) -> list[dict]:
    """Extract and parse the const DATA = [...] JavaScript array."""
    match = DATA_RE.search(html)
    if not match:
        raise ValueError("Could not find 'const DATA = [...]' in HTML")
    raw = match.group(1)
    return json.loads(raw)


async def seed(session: AsyncSession, html_path: Path = HTML_DEFAULT_PATH) -> dict:
    """Insert/update products + channel_product_logistics from HTML data."""
    html = html_path.read_text(encoding="utf-8")
    rows = extract_data_array(html)

    channel_id = (
        await session.execute(text("SELECT id FROM channels WHERE code = 'amazon_uae'"))
    ).scalar_one()

    fx_rate = (
        await session.execute(
            text("SELECT fx_rate FROM trade_route_params WHERE route_code = 'es_to_uae'")
        )
    ).scalar_one()
    fx_rate = Decimal(str(fx_rate))

    upserted_products = 0
    upserted_logistics = 0
    skipped: list[dict] = []

    for row in rows:
        sku = row["s"]
        pe_eur = Decimal(str(row["pe"]))
        techo_aed = Decimal(str(row["v"]))
        catalog_pvp_eur = (techo_aed / fx_rate).quantize(Decimal("0.0001"))
        weight = Decimal(str(row["peso"]))
        default_scheme = SCHEME_MAP.get(row.get("rec", "fba"), "canal_full")

        result = await session.execute(
            text("""
                UPDATE products
                SET pe_eur = :pe_eur,
                    catalog_pvp_eur = :catalog_pvp_eur,
                    weight = :weight
                WHERE sku = :sku
            """),
            {
                "pe_eur": pe_eur,
                "catalog_pvp_eur": catalog_pvp_eur,
                "weight": weight,
                "sku": sku,
            },
        )
        if result.rowcount == 0:
            skipped.append({"sku": sku, "reason": "not in products table"})
            continue
        upserted_products += 1

        await session.execute(
            text("""
                INSERT INTO channel_product_logistics
                    (product_sku, channel_id, inbound_fee_aed, storage_fee_aed,
                     fulfillment_fee_aed, default_scheme)
                VALUES
                    (:sku, :channel_id, :inbound, :storage, :fulfillment, :scheme)
                ON CONFLICT (product_sku, channel_id) DO UPDATE SET
                    inbound_fee_aed = EXCLUDED.inbound_fee_aed,
                    storage_fee_aed = EXCLUDED.storage_fee_aed,
                    fulfillment_fee_aed = EXCLUDED.fulfillment_fee_aed,
                    default_scheme = EXCLUDED.default_scheme,
                    updated_at = now()
            """),
            {
                "sku": sku,
                "channel_id": channel_id,
                "inbound": Decimal(str(row["fba_env"])),
                "storage": Decimal(str(row["fba_alm"])),
                "fulfillment": Decimal(str(row["fba_fee"])),
                "scheme": default_scheme,
            },
        )
        upserted_logistics += 1

    await session.commit()
    return {
        "total_rows": len(rows),
        "products_updated": upserted_products,
        "logistics_upserted": upserted_logistics,
        "skipped": skipped,
    }


async def main() -> None:
    Session = get_sessionmaker()
    async with Session() as session:
        report = await seed(session)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
