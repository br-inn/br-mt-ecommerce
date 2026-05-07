"""FastAPI dependency `get_db_session` + helpers de session.

Uso:

    from fastapi import Depends
    from app.db import get_db_session

    @router.get("/products/{sku}")
    async def get_product(sku: str, session: AsyncSession = Depends(get_db_session)):
        ...

Política transaccional:
- Una request HTTP = una session.
- Si la handler lanza, hacemos rollback explícito.
- Si todo va bien, commit al final.
- `expire_on_commit=False` para que los objetos sigan accesibles tras commit
  (devolverlos en el response sin lazy-loads inesperados).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_sessionmaker


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields una AsyncSession con commit/rollback automáticos."""
    async with get_sessionmaker()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
