"""Servicios de imports batch (Celery) — US-1A-06-01.

Diferencia clave vs ``app.services.importer.*`` (wizard sincrono Pantalla 10):
- Aquí persistimos ``ImportRun`` en BD y corremos en Celery worker.
- El wizard sincrono usa parse → diff → apply con preview-ready en memoria.
- Este pipeline usa upsert directo por SKU sin diff visual previo. Pensado
  para primer load del PIM en dev y para imports recurrentes futuros (cron).
"""

from __future__ import annotations

from app.services.imports.pim_importer import PimImporter
from app.services.imports.pim_row_mapper import map_pim_row_to_product

__all__ = ["PimImporter", "map_pim_row_to_product"]
