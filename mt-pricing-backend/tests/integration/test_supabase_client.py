"""US-1A-01-09-S1 — DoD: smoke test del cliente supabase-py dual.

AC del backlog (líneas 473-477):
- `get_supabase_admin()` retorna un cliente inicializado con SERVICE_ROLE_KEY.
- `get_supabase_client()` retorna un cliente inicializado con ANON_KEY.
- Smoke test contra Supabase real (`auth.admin.list_users`) — SKIPPED si las
  credenciales reales no están disponibles (CI sin Doppler).

El test "real" se marca skip por defecto en local — sólo corre cuando se
exporta `SUPABASE_INTEGRATION_TEST=1` y hay un `SUPABASE_URL` distinto del
placeholder de `.env.example`.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.integration]


def test_get_supabase_client_returns_client_with_anon_key() -> None:
    """`get_supabase_client()` instancia con la anon key; cacheado por lru."""
    # Resetea el lru_cache del módulo para que use los settings de test.
    from app.core.supabase import get_supabase_client

    get_supabase_client.cache_clear()

    with patch("app.core.supabase.create_client") as mocked:
        mocked.return_value = MagicMock(name="anon_client")
        client = get_supabase_client()

    assert client is not None
    mocked.assert_called_once()
    args, kwargs = mocked.call_args
    # Posicional: (URL, KEY)
    assert args[0].startswith("https://")
    # La anon key real es secret — el mock recibe el plaintext expuesto
    # por SecretStr.get_secret_value(). Verificamos que NO sea el SERVICE_ROLE.
    from app.core.config import settings

    assert args[1] == settings.SUPABASE_ANON_KEY.get_secret_value()


def test_get_supabase_admin_returns_client_with_service_role_key() -> None:
    """`get_supabase_admin()` usa SERVICE_ROLE_KEY (bypass RLS)."""
    from app.core.supabase import get_supabase_admin

    get_supabase_admin.cache_clear()

    with patch("app.core.supabase.create_client") as mocked:
        mocked.return_value = MagicMock(name="admin_client")
        client = get_supabase_admin()

    assert client is not None
    mocked.assert_called_once()
    args, _ = mocked.call_args

    from app.core.config import settings

    assert args[1] == settings.SUPABASE_SERVICE_ROLE_KEY.get_secret_value()


def test_supabase_clients_are_distinct_singletons() -> None:
    """Anon y admin son clientes distintos pero cada uno cachea su propia instancia."""
    from app.core.supabase import get_supabase_admin, get_supabase_client

    get_supabase_client.cache_clear()
    get_supabase_admin.cache_clear()

    with patch("app.core.supabase.create_client") as mocked:
        mocked.side_effect = [MagicMock(name="anon"), MagicMock(name="admin")]
        anon1 = get_supabase_client()
        admin1 = get_supabase_admin()
        anon2 = get_supabase_client()
        admin2 = get_supabase_admin()

    # lru_cache → segunda llamada devuelve la misma instancia
    assert anon1 is anon2
    assert admin1 is admin2
    # pero anon != admin
    assert anon1 is not admin1
    # create_client se llamó exactamente 2 veces (uno por cliente)
    assert mocked.call_count == 2


@pytest.mark.skipif(
    os.environ.get("SUPABASE_INTEGRATION_TEST") != "1"
    or "your-project" in os.environ.get("SUPABASE_URL", ""),
    reason="Requiere SUPABASE_INTEGRATION_TEST=1 + SUPABASE_URL real (Doppler).",
)
def test_supabase_admin_smoke_list_users_real() -> None:
    """Smoke real contra Supabase: `auth.admin.list_users(per_page=1)` retorna 200.

    Sólo se ejecuta cuando hay credenciales reales disponibles. Útil en CI
    nocturno tras `doppler run --command="pytest -k smoke_real"`.
    """
    from app.core.supabase import get_supabase_admin

    get_supabase_admin.cache_clear()
    admin = get_supabase_admin()

    # supabase-py >= 2.x: `list_users` retorna list o objeto con `users`.
    response = admin.auth.admin.list_users(per_page=1)
    # Aceptamos cualquiera de las dos formas — depende de la versión exacta.
    assert response is not None
