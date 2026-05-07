"""Dev helper — limpia productos + import_runs colgados por la primera
ejecución fallida del PIM importer (bug Decimal serialization).

Uso: docker exec mt-backend python /app/scripts/reset_pim_state.py
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.db.engine import get_sessionmaker


async def main() -> None:
    sm = get_sessionmaker()
    async with sm() as s:
        await s.execute(text("UPDATE import_runs SET status = 'failed' WHERE status = 'running'"))
        await s.execute(text("ALTER TABLE products DISABLE TRIGGER trg_products_no_hard_delete"))
        await s.execute(text("DELETE FROM product_translations"))
        await s.execute(text("DELETE FROM product_images"))
        await s.execute(text("DELETE FROM products"))
        await s.execute(text("ALTER TABLE products ENABLE TRIGGER trg_products_no_hard_delete"))
        await s.execute(
            text("DELETE FROM audit_events WHERE reason LIKE 'PIM batch import run%'")
        )
        await s.commit()
    print("reset done")


if __name__ == "__main__":
    asyncio.run(main())
