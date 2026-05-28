"""Seed initial channel pricing parameters for Amazon UAE and Noon UAE.

Idempotent — uses INSERT … ON CONFLICT DO NOTHING for every row.

Usage (inside container):
    docker exec mt-backend python /app/app/scripts/seed_channel_pricing.py

Or directly:
    docker exec mt-backend python -c "
    import asyncio, sys; sys.path.insert(0, '/app')
    exec(open('/app/app/scripts/seed_channel_pricing.py').read())
    asyncio.run(main())
    "
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

from sqlalchemy import select, text

from app.db.engine import get_sessionmaker


# ---------------------------------------------------------------------------
# Pricing Desk family mapping (Spanish name → DB slug keywords for matching)
# ---------------------------------------------------------------------------
_FAMILY_DESK_MAP: list[tuple[str, list[str], Decimal]] = [
    # (pricing-desk name, slug keywords to try, margin_pct)
    ("VÁLVULAS INOX 3 PIEZAS (FONDO DE CUBA)", ["ball_valve"], Decimal("12")),
    ("VÁLVULAS DE LATÓN", ["ball_valve"], Decimal("12")),
    ("MANGUITOS ELÁSTICOS", ["coupling", "hose"], Decimal("0")),
    ("VÁLVULAS INOXIDABLES", ["valve"], Decimal("40")),
    ("VÁLVULAS DE FUNDICIÓN", ["gate_valve"], Decimal("25")),
]


async def main() -> None:  # noqa: C901  (complexity OK for seed script)
    Session = get_sessionmaker()

    async with Session() as session:
        # ------------------------------------------------------------------ #
        # 1. Trade route params — es_to_uae                                  #
        # ------------------------------------------------------------------ #
        await session.execute(
            text("""
                INSERT INTO trade_route_params
                    (id, route_code, description,
                     fx_rate, fx_buffer_pct,
                     freight_rate_per_kg, freight_min_aed,
                     import_tariff_pct, local_warehouse_pct, handling_pct,
                     updated_at)
                VALUES
                    (gen_random_uuid(), 'es_to_uae',
                     'Spain → UAE (EUR→AED) — initial Pricing Desk values',
                     4.28, 2,
                     0, 0,
                     4.14, 2, 1.5,
                     now())
                ON CONFLICT (route_code) DO NOTHING
            """)
        )
        print("[seed] trade_route_params: es_to_uae inserted (or already exists).")

        # Retrieve the route id
        route_row = (
            await session.execute(
                text("SELECT id FROM trade_route_params WHERE route_code = 'es_to_uae'")
            )
        ).fetchone()
        if route_row is None:
            raise RuntimeError("Route 'es_to_uae' not found after insert — cannot continue.")
        route_id = route_row[0]

        # ------------------------------------------------------------------ #
        # 2. Channel fee params                                               #
        # ------------------------------------------------------------------ #
        fee_specs = [
            {
                "channel_code": "amazon_uae",
                "mt_discount_pct": Decimal("15"),
                "commission_pct": Decimal("11"),
                "vat_pct": Decimal("5"),
                "advertising_pct": Decimal("8"),
                "returns_pct": Decimal("2"),
                "storage_multiplier": Decimal("1.0"),
            },
            {
                "channel_code": "noon_uae",
                "mt_discount_pct": Decimal("15"),
                "commission_pct": Decimal("10"),  # placeholder — confirm w/ Noon account
                "vat_pct": Decimal("5"),
                "advertising_pct": Decimal("5"),
                "returns_pct": Decimal("2"),
                "storage_multiplier": Decimal("1.0"),
            },
        ]

        for spec in fee_specs:
            ch_row = (
                await session.execute(
                    text("SELECT id FROM channels WHERE code = :code"),
                    {"code": spec["channel_code"]},
                )
            ).fetchone()
            if ch_row is None:
                print(f"[WARN] channel '{spec['channel_code']}' not found — skipping fee params.")
                continue
            ch_id = ch_row[0]

            await session.execute(
                text("""
                    INSERT INTO channel_fee_params
                        (id, channel_id, route_id,
                         mt_discount_pct, commission_pct, vat_pct,
                         advertising_pct, returns_pct, storage_multiplier,
                         updated_at)
                    VALUES
                        (gen_random_uuid(), :ch_id, :route_id,
                         :mt_discount_pct, :commission_pct, :vat_pct,
                         :advertising_pct, :returns_pct, :storage_multiplier,
                         now())
                    ON CONFLICT (channel_id) DO NOTHING
                """),
                {
                    "ch_id": ch_id,
                    "route_id": route_id,
                    "mt_discount_pct": spec["mt_discount_pct"],
                    "commission_pct": spec["commission_pct"],
                    "vat_pct": spec["vat_pct"],
                    "advertising_pct": spec["advertising_pct"],
                    "returns_pct": spec["returns_pct"],
                    "storage_multiplier": spec["storage_multiplier"],
                },
            )
            print(
                f"[seed] channel_fee_params: {spec['channel_code']} inserted (or already exists)."
            )

        # ------------------------------------------------------------------ #
        # 3. Channel scheme params                                            #
        # ------------------------------------------------------------------ #
        scheme_specs = [
            # amazon_uae
            {
                "channel_code": "amazon_uae",
                "fulfillment_scheme": "canal_full",
                "scheme_label": "FBA",
                "flat_supplement_aed": Decimal("0"),
                "pct_surcharge": Decimal("0"),
                "max_weight_kg": Decimal("25"),
            },
            {
                "channel_code": "amazon_uae",
                "fulfillment_scheme": "canal_lastmile",
                "scheme_label": "Easy Ship",
                "flat_supplement_aed": Decimal("6"),
                "pct_surcharge": Decimal("0"),
                "max_weight_kg": None,
            },
            {
                "channel_code": "amazon_uae",
                "fulfillment_scheme": "merchant_managed",
                "scheme_label": "Self-Ship",
                "flat_supplement_aed": Decimal("0"),
                "pct_surcharge": Decimal("15"),
                "max_weight_kg": None,
            },
            # noon_uae
            {
                "channel_code": "noon_uae",
                "fulfillment_scheme": "canal_full",
                "scheme_label": "FBN",
                "flat_supplement_aed": Decimal("0"),
                "pct_surcharge": Decimal("0"),
                "max_weight_kg": None,
            },
            {
                "channel_code": "noon_uae",
                "fulfillment_scheme": "merchant_managed",
                "scheme_label": "FBM",
                "flat_supplement_aed": Decimal("0"),
                "pct_surcharge": Decimal("0"),
                "max_weight_kg": None,
            },
        ]

        for spec in scheme_specs:
            ch_row = (
                await session.execute(
                    text("SELECT id FROM channels WHERE code = :code"),
                    {"code": spec["channel_code"]},
                )
            ).fetchone()
            if ch_row is None:
                print(
                    f"[WARN] channel '{spec['channel_code']}' not found — "
                    f"skipping scheme {spec['fulfillment_scheme']}."
                )
                continue
            ch_id = ch_row[0]

            await session.execute(
                text("""
                    INSERT INTO channel_scheme_params
                        (id, channel_id, fulfillment_scheme, scheme_label,
                         flat_supplement_aed, pct_surcharge, max_weight_kg)
                    VALUES
                        (gen_random_uuid(), :ch_id,
                         CAST(:fulfillment_scheme AS fulfillment_scheme),
                         :scheme_label, :flat_supplement_aed,
                         :pct_surcharge, :max_weight_kg)
                    ON CONFLICT (channel_id, fulfillment_scheme) DO NOTHING
                """),
                {
                    "ch_id": ch_id,
                    "fulfillment_scheme": spec["fulfillment_scheme"],
                    "scheme_label": spec["scheme_label"],
                    "flat_supplement_aed": spec["flat_supplement_aed"],
                    "pct_surcharge": spec["pct_surcharge"],
                    "max_weight_kg": spec["max_weight_kg"],
                },
            )
            print(
                f"[seed] channel_scheme_params: {spec['channel_code']} / "
                f"{spec['fulfillment_scheme']} ({spec['scheme_label']}) "
                f"inserted (or already exists)."
            )

        # ------------------------------------------------------------------ #
        # 4. Channel margin targets                                           #
        # ------------------------------------------------------------------ #
        # Families in DB use English names/codes (e.g. 'ball_valve', 'gate_valve').
        # The Pricing Desk provides Spanish names — we do best-effort slug matching.
        family_rows = (
            await session.execute(
                text("SELECT id, code, name FROM families ORDER BY code")
            )
        ).fetchall()
        family_by_slug: dict[str, tuple] = {row[1]: row for row in family_rows}

        channel_codes = ["amazon_uae", "noon_uae"]

        for desk_name, slug_candidates, margin_pct in _FAMILY_DESK_MAP:
            matched_family = None
            matched_slug = None
            for slug in slug_candidates:
                if slug in family_by_slug:
                    matched_family = family_by_slug[slug]
                    matched_slug = slug
                    break

            if matched_family is None:
                print(
                    f"[WARN] No DB family matched for pricing-desk entry '{desk_name}' "
                    f"(tried slugs: {slug_candidates}) — skipping margin target."
                )
                continue

            family_id = matched_family[0]
            family_display = f"{matched_family[2]} (code={matched_slug})"

            for ch_code in channel_codes:
                ch_row = (
                    await session.execute(
                        text("SELECT id FROM channels WHERE code = :code"),
                        {"code": ch_code},
                    )
                ).fetchone()
                if ch_row is None:
                    continue
                ch_id = ch_row[0]

                await session.execute(
                    text("""
                        INSERT INTO channel_margin_targets
                            (id, channel_id, family_id, selling_model,
                             margin_target_pct, updated_at)
                        VALUES
                            (gen_random_uuid(), :ch_id, :family_id,
                             CAST('b2c' AS selling_model), :margin_pct, now())
                        ON CONFLICT (channel_id, family_id, selling_model) DO NOTHING
                    """),
                    {
                        "ch_id": ch_id,
                        "family_id": family_id,
                        "margin_pct": margin_pct,
                    },
                )

            print(
                f"[seed] margin_targets: '{desk_name}' → {family_display} "
                f"@ {margin_pct}% (both channels)."
            )

        await session.commit()

    print("\n[seed] All done — commit successful.")


if __name__ == "__main__":
    asyncio.run(main())
