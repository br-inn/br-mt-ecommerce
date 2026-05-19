import asyncio, json, sys

SKU = sys.argv[1] if len(sys.argv) > 1 else "4097015"

async def run():
    from app.db.session import get_sessionmaker
    from sqlalchemy import text

    sm = get_sessionmaker()
    async with sm() as s:
        r = await s.execute(text("""
            SELECT mc.title, mc.score, mc.kind, mc.price_aed,
                   mc.price_confidence_score,
                   mc.specs_jsonb->'_scoring' as scoring,
                   mc.channel, mc.external_id
            FROM match_candidates mc
            WHERE mc.product_sku = :sku
            ORDER BY mc.score DESC
        """), {"sku": SKU})
        rows = r.fetchall()
        print(f"\n=== Candidatos para SKU {SKU} ({len(rows)} total) ===\n")
        for row in rows:
            scoring = row[5] or {}
            if isinstance(scoring, str):
                scoring = json.loads(scoring)
            notes = scoring.get("notes", [])
            breakdown = scoring.get("breakdown", {})
            print(f"  score={row[1]:>3}  kind={row[2]:<8}  pcs={row[4] or '?':>3}  price={row[3] or '?'}  [{row[6]}]")
            print(f"    title: {(row[0] or '')[:75]}")
            if notes:
                print(f"    notes: {notes}")
            # Mostrar dimensiones clave
            dims = ["material","dn","pn","thread_standard","product_type","ways","brand_tier"]
            dim_str = "  ".join(f"{k}={v:.2f}" for k,v in breakdown.items() if k in dims and v is not None)
            if dim_str:
                print(f"    dims: {dim_str}")
            print()

asyncio.run(run())
