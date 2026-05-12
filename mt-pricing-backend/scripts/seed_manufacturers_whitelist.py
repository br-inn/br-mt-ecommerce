"""Seed script — manufacturers_whitelist (US-F15-02-03).

Ejecutar:
    python -m scripts.seed_manufacturers_whitelist

Idempotente: usa INSERT ... ON CONFLICT (manufacturer_name) DO UPDATE para
actualizar canonical_domains, brand_aliases y confidence sin crear duplicados.
Exit code 0 si OK, 1 si error.
"""

from __future__ import annotations

import sys

from sqlalchemy import text
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Seed data — fabricantes industriales de válvulas/fittings
# ---------------------------------------------------------------------------
SEED_DATA: list[dict] = [
    {
        "manufacturer_name": "Pegler Yorkshire",
        "canonical_domains": ["pegler.com", "pegler.co.uk", "yorkshire-fittings.co.uk"],
        "brand_aliases": ["Pegler", "Yorkshire"],
        "confidence": 1.0,
    },
    {
        "manufacturer_name": "Giacomini",
        "canonical_domains": ["giacomini.com"],
        "brand_aliases": ["Giacomini"],
        "confidence": 1.0,
    },
    {
        "manufacturer_name": "Apollo Valves",
        "canonical_domains": ["apollovalves.com", "apolloflow.com"],
        "brand_aliases": ["Apollo"],
        "confidence": 1.0,
    },
    {
        "manufacturer_name": "Nibco",
        "canonical_domains": ["nibco.com"],
        "brand_aliases": ["NIBCO"],
        "confidence": 1.0,
    },
    {
        "manufacturer_name": "Honeywell Building Technologies",
        "canonical_domains": ["honeywellprocess.com", "buildingcontrols.honeywell.com"],
        "brand_aliases": ["Honeywell", "Resideo"],
        "confidence": 1.0,
    },
    {
        "manufacturer_name": "Danfoss",
        "canonical_domains": ["danfoss.com"],
        "brand_aliases": ["Danfoss"],
        "confidence": 1.0,
    },
    {
        "manufacturer_name": "Arco Valves",
        "canonical_domains": ["arcovalves.com"],
        "brand_aliases": ["Arco"],
        "confidence": 1.0,
    },
    {
        "manufacturer_name": "Watts Water Technologies",
        "canonical_domains": ["watts.com", "wattswater.com"],
        "brand_aliases": ["Watts", "Watts Water"],
        "confidence": 1.0,
    },
    {
        "manufacturer_name": "Aalberts Industries",
        "canonical_domains": ["aalberts-integrated-piping.com", "aalberts.com"],
        "brand_aliases": ["Aalberts", "VSH", "Conex"],
        "confidence": 1.0,
    },
    {
        "manufacturer_name": "IMI Hydronic Engineering",
        "canonical_domains": ["imi-hydronic.com"],
        "brand_aliases": ["IMI", "Heimeier", "TA Hydronics"],
        "confidence": 1.0,
    },
    {
        "manufacturer_name": "Caleffi",
        "canonical_domains": ["caleffi.com"],
        "brand_aliases": ["Caleffi"],
        "confidence": 1.0,
    },
    {
        "manufacturer_name": "Grundfos",
        "canonical_domains": ["grundfos.com"],
        "brand_aliases": ["Grundfos"],
        "confidence": 1.0,
    },
    {
        "manufacturer_name": "Flamco",
        "canonical_domains": ["flamco.com"],
        "brand_aliases": ["Flamco"],
        "confidence": 1.0,
    },
    {
        "manufacturer_name": "Oventrop",
        "canonical_domains": ["oventrop.com"],
        "brand_aliases": ["Oventrop"],
        "confidence": 1.0,
    },
    {
        "manufacturer_name": "Afriso",
        "canonical_domains": ["afriso.com", "afriso.de"],
        "brand_aliases": ["Afriso"],
        "confidence": 1.0,
    },
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main() -> None:
    from app.core.config import settings

    engine = create_engine(str(settings.ALEMBIC_DATABASE_URL), echo=False)

    upsert_sql = text("""
        INSERT INTO manufacturers_whitelist
            (manufacturer_name, canonical_domains, brand_aliases, confidence, active)
        VALUES
            (:manufacturer_name, :canonical_domains, :brand_aliases, :confidence, true)
        ON CONFLICT (manufacturer_name) DO UPDATE SET
            canonical_domains = EXCLUDED.canonical_domains,
            brand_aliases     = EXCLUDED.brand_aliases,
            confidence        = EXCLUDED.confidence
    """)

    inserted = 0
    updated = 0

    with Session(engine) as session:
        for row in SEED_DATA:
            # Determinar si ya existe para reportar inserted vs updated
            exists = session.execute(
                text("SELECT 1 FROM manufacturers_whitelist WHERE manufacturer_name = :n"),
                {"n": row["manufacturer_name"]},
            ).scalar_one_or_none()

            session.execute(
                upsert_sql,
                {
                    "manufacturer_name": row["manufacturer_name"],
                    "canonical_domains": row["canonical_domains"],
                    "brand_aliases": row["brand_aliases"],
                    "confidence": row["confidence"],
                },
            )

            if exists:
                updated += 1
            else:
                inserted += 1

        session.commit()

    total = len(SEED_DATA)
    print(f"manufacturers_whitelist seed OK — {total} rows procesados: {inserted} inserted, {updated} updated")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
