"""Pydantic API schemas — request/response models.

Convención:
- Un módulo por dominio (`products.py`, `prices.py`, etc. — Agente F/G).
- `common.py` mantiene tipos compartidos: ProblemDetails, Pagination, Cursor.
"""

from app.schemas.common import Cursor, Pagination, ProblemDetails

__all__ = ["Cursor", "Pagination", "ProblemDetails"]
