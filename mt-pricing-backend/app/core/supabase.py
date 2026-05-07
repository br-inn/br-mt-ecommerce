"""Supabase client factories — diferenciadas por privilegio (ADR-031, §8.0.2).

Patrón de dos clientes:
- `get_supabase_client()` — anon key, para flows público / cliente final.
- `get_supabase_admin()` — service_role key, SOLO para `auth.admin.*` y
  operaciones administrativas (invite, force-logout, signed URLs Storage).
  Nunca exponer a routers públicos: gating por `require_permissions(["users:manage"])`.

Ambos clientes son singletons cacheados — `supabase-py` mantiene su propio pool
HTTP internamente.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from app.core.config import settings


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Cliente con `anon` key — respeta RLS como cualquier usuario público."""
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_ANON_KEY.get_secret_value(),
    )


@lru_cache(maxsize=1)
def get_supabase_admin() -> Client:
    """Cliente con `service_role` key — bypass RLS. Uso restringido."""
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY.get_secret_value(),
    )
