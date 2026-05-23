"""brand_extractor_poc.py — POC del patrón generate de llm-scraper en Python.

Demuestra US-SCR-05-01: Claude genera el JSON mapping de atributos UNA VEZ
por marca, y ese mapping se aplica sin LLM en scrapes posteriores.

Uso::

    # Generar mapping para una marca con raw_pairs de ejemplo (sin scraper real):
    python scripts/poc/brand_extractor_poc.py --brand "Grundfos" --dry-run

    # Con datos reales de DB (requiere marca registrada):
    python scripts/poc/brand_extractor_poc.py --brand-id <uuid> --marketplace amazon_uae

Salida:
    Imprime el JSON mapping generado y un ejemplo de aplicación.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("brand_extractor_poc")


# ---------------------------------------------------------------------------
# Sample data: typical raw_pairs for industrial valve brands on Amazon UAE
# ---------------------------------------------------------------------------

SAMPLE_RAW_PAIRS_BY_BRAND: dict[str, list[dict]] = {
    "Grundfos": [
        {"label": "Brand", "value": "Grundfos"},
        {"label": "Model Number", "value": "CM5-5 A-R-G-E-AQQE"},
        {"label": "Material", "value": "Cast Iron"},
        {"label": "Head (m)", "value": "44"},
        {"label": "Flow Rate (m³/h)", "value": "5"},
        {"label": "Inlet diameter", "value": "1 inch"},
        {"label": "Outlet diameter", "value": "1 inch"},
        {"label": "Operating temperature (°C)", "value": "-10 to 90"},
        {"label": "Max. liquid temperature (°C)", "value": "90"},
        {"label": "Rated power input (kW)", "value": "0.55"},
    ],
    "Emerson": [
        {"label": "Manufacturer", "value": "Emerson"},
        {"label": "Part Number", "value": "KVS-15"},
        {"label": "Valve Body Material", "value": "Brass"},
        {"label": "Nominal Size (DN)", "value": "DN15"},
        {"label": "Pressure Rating (bar)", "value": "16"},
        {"label": "End Connection", "value": "Threaded NPT"},
        {"label": "Fluid Temperature Range (°C)", "value": "-20 to 120"},
        {"label": "Kvs value (m³/h)", "value": "6.3"},
        {"label": "Standard", "value": "EN 13709"},
    ],
    "Parker": [
        {"label": "Brand Name", "value": "Parker"},
        {"label": "Product Number", "value": "B3PK-SS"},
        {"label": "Body Material", "value": "316 Stainless Steel"},
        {"label": "Port Size", "value": '3/4"'},
        {"label": "Cv Flow Coefficient", "value": "24"},
        {"label": "Pressure Rating (PSI)", "value": "1000"},
        {"label": "Temperature Range (°F)", "value": "-65 to 400"},
        {"label": "End Connections", "value": "FNPT"},
        {"label": "Valve Type", "value": "Ball Valve"},
    ],
}


async def run_dry(brand_name: str) -> None:
    """Generate and apply mapping using sample data (no DB, no real scraper)."""
    from app.services.scraper.brand_extractor_service import (
        apply_mapping,
        generate_mapping_via_claude,
    )

    raw_pairs = SAMPLE_RAW_PAIRS_BY_BRAND.get(brand_name)
    if not raw_pairs:
        available = ", ".join(SAMPLE_RAW_PAIRS_BY_BRAND.keys())
        logger.error("Brand '%s' not in sample data. Available: %s", brand_name, available)
        sys.exit(1)

    logger.info("=== Bootstrap: generating mapping for %s via Claude ===", brand_name)
    attribute_map = await generate_mapping_via_claude(
        brand_name=brand_name,
        marketplace="amazon_uae",
        sample_raw_pairs=raw_pairs,
    )

    if not attribute_map:
        logger.error("Empty mapping generated — check ANTHROPIC_API_KEY")
        sys.exit(1)

    print("\n📋 Generated attribute_map:")
    print(json.dumps(attribute_map, indent=2, ensure_ascii=False))

    logger.info("\n=== Monitoring: applying mapping without LLM ===")
    result = apply_mapping(attribute_map, raw_pairs)

    print("\n✅ Canonical specs extracted (no LLM call):")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    covered = len(result)
    total = len(raw_pairs)
    print(f"\n📊 Coverage: {covered}/{total} attributes mapped ({covered / total * 100:.0f}%)")


async def run_with_db(brand_id: str, marketplace: str) -> None:
    """Run bootstrap against a real brand in DB."""
    import uuid as _uuid

    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select

    from app.db.models.comparator import CompetitorBrand
    from app.services.matching.adapter_registry import get_fetcher
    from app.services.matching.ports import Query
    from app.services.scraper.brand_extractor_service import BrandExtractorService

    brand_uuid = _uuid.UUID(brand_id)

    async with AsyncSessionLocal() as session:
        r = await session.execute(select(CompetitorBrand).where(CompetitorBrand.id == brand_uuid))
        brand = r.scalar_one_or_none()
        if not brand:
            logger.error("Brand %s not found in DB", brand_id)
            sys.exit(1)

        logger.info("Brand: %s (search term: %s)", brand.name, brand.effective_search_term)

        # Check if mapping already exists
        svc = BrandExtractorService(session)
        existing = await svc.get_mapping(brand_uuid, marketplace)
        if existing:
            logger.info(
                "Existing mapping found (%d entries). Use --force to regenerate.", len(existing)
            )
            print(json.dumps(existing, indent=2))
            return

        # Fetch sample products
        logger.info("Fetching sample products from %s...", marketplace)
        fetcher = get_fetcher(marketplace)
        query = Query(
            text=brand.effective_search_term,
            source=marketplace,
            type="brand",
            dept=brand.amazon_dept,
            category_node=brand.amazon_category_node,
        )
        candidates = await fetcher.fetch(query)
        logger.info("Fetched %d candidates", len(candidates))

        # Collect raw_pairs
        sample_raw_pairs: list[dict] = []
        sample_asins: list[str] = []
        for cand in candidates[:3]:
            asin = cand.raw_payload.get("asin", "")
            if asin:
                sample_asins.append(asin)
            for k, v in cand.specs.items():
                sample_raw_pairs.append({"label": k, "value": str(v)})

        if not sample_raw_pairs:
            logger.error("No specs collected. Cannot generate extractor.")
            sys.exit(1)

        attribute_map = await svc.bootstrap(
            brand_id=brand_uuid,
            brand_name=brand.name,
            marketplace=marketplace,
            sample_raw_pairs=sample_raw_pairs,
            sample_asins=sample_asins,
        )

        print("\n✅ Generated and saved attribute_map:")
        print(json.dumps(attribute_map, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Brand Extractor POC — US-SCR-05-01")
    parser.add_argument("--brand", help="Brand name (uses sample data, no DB needed)")
    parser.add_argument("--brand-id", help="Brand UUID from DB (runs real scraper)")
    parser.add_argument("--marketplace", default="amazon_uae", choices=["amazon_uae", "noon_uae"])
    args = parser.parse_args()

    if args.brand:
        asyncio.run(run_dry(args.brand))
    elif args.brand_id:
        asyncio.run(run_with_db(args.brand_id, args.marketplace))
    else:
        parser.print_help()
        print("\nSample brands for --dry-run:", ", ".join(SAMPLE_RAW_PAIRS_BY_BRAND.keys()))
        sys.exit(1)


if __name__ == "__main__":
    main()
