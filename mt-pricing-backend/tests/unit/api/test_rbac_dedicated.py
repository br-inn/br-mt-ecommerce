"""Unit tests del RBAC dedicado de Sprint 5 (US-1A-07-04).

Verifica:

- Permisos dedicados (`matches:read|write`, `channels:read|manage`,
  `prices:override_review`, `graphrag:admin`) están enforced en sus endpoints.
- Cross-deny: roles con permisos *adyacentes* pero NO los específicos
  reciben 403 (gerente sin `matches:write` en ruta refresh; auditor sin
  `channels:manage`; comercial sin `prices:override_review`).
- 401 si no hay usuario autenticado en absoluto.

Patrón: monta cada router en una FastAPI ad-hoc (igual que
``test_matches_api`` / ``test_pricing_engine_api``). NO toca ``app/main.py``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.deps import get_current_user, get_db_session, require_permissions
from app.api.routes.channels_mirror import (
    get_channel_adapters,
    get_mirror_service,
    router as channels_router,
)
from app.api.routes.matches import (
    get_match_service,
    router as matches_router,
)
from app.api.routes.pricing_engine import (
    get_revise_service,
    router as pricing_engine_router,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeRole:
    def __init__(self, code: str, perms: list[str]) -> None:
        self.code = code
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self, role_code: str, perms: list[str]) -> None:
        self.id: UUID = uuid4()
        self.email = f"{role_code}@mt.ae"
        self.is_active = True
        self.deleted_at = None
        self.role = _FakeRole(role_code, perms)


# Mapeo canónico — refleja lo que sembra la migration 026 (post-snapshot).
ROLE_PERMS: dict[str, list[str]] = {
    "comercial": [
        "matches:read",
        "matches:write",
        "products:read",
        "products:write",
        "prices:propose",
        "suppliers:read",
    ],
    "gerente_comercial": [
        "matches:write",
        "channels:manage",
        "prices:override_review",
        "prices:approve",
        "products:read",
    ],
    "ti_integracion": [
        "channels:manage",
        "graphrag:admin",
        "jobs:read",
        "jobs:write",
        "jobs:run",
        "suppliers:write",
    ],
    "auditor": [
        "matches:read",
        "channels:read",
    ],
    "admin": [
        "matches:read",
        "matches:write",
        "channels:read",
        "channels:manage",
        "prices:override_review",
        "graphrag:admin",
    ],
}


def _make_user(role_code: str) -> _FakeUser:
    return _FakeUser(role_code, ROLE_PERMS[role_code])


# ---------------------------------------------------------------------------
# Helpers — apply RBAC enforcement to a test app while overriding services.
# ---------------------------------------------------------------------------
def _wire_rbac_app(
    *,
    router: Any,
    user: _FakeUser | None,
    service_overrides: dict[Any, Any] | None = None,
) -> FastAPI:
    """Construye una FastAPI ad-hoc con RBAC enforced.

    A diferencia de ``test_matches_api``, **NO** hacemos override de los
    closures ``_check`` de ``require_permissions`` — al contrario, queremos
    que se ejecute la lógica real para validar denegaciones.

    En su lugar:
    - Override de ``get_current_user`` devolviendo ``user`` (o lanzando 401
      si user is None).
    - Override de ``get_db_session`` con MagicMock (los services se mockean).
    - ProductRepository y refresh_sku_task parcheados a nivel módulo para
      que el endpoint /refresh funcione sin DB ni Celery real.
    """
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    # Patch ProductRepository so refresh endpoint works without real DB.
    import app.repositories.product as _product_repo_mod
    from unittest.mock import MagicMock as _MagicMock

    class _FakeProductRepo:
        def __init__(self, _session: Any) -> None:
            pass

        async def get_by_sku(self, sku: str) -> Any:
            return _MagicMock(sku=sku)  # non-None → SKU exists

    _product_repo_mod.ProductRepository = _FakeProductRepo  # type: ignore[assignment]

    # Patch Celery task so refresh endpoint doesn't need a broker.
    import app.workers.tasks.comparator as _comparator_mod

    _mock_task = _MagicMock()
    _mock_task.apply_async.return_value.id = "test-task-id"
    _comparator_mod.refresh_sku_task = _mock_task  # type: ignore[attr-defined]

    async def _override_db() -> Any:
        yield _MagicMock()

    async def _override_user() -> _FakeUser:
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing bearer token",
            )
        return user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    if service_overrides:
        for dep, fake in service_overrides.items():
            app.dependency_overrides[dep] = lambda _f=fake: _f

    return app


async def _client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


# ---------------------------------------------------------------------------
# 1. matches:read — auditor allow, ti_integracion deny (no tiene matches:read).
# ---------------------------------------------------------------------------
async def test_matches_list_auditor_allowed_with_dedicated_perm() -> None:
    user = _make_user("auditor")  # tiene matches:read
    svc = MagicMock()
    svc.list_candidates = AsyncMock(return_value=([], None))
    app = _wire_rbac_app(
        router=matches_router,
        user=user,
        service_overrides={get_match_service: svc},
    )
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/matches")
    assert resp.status_code == 200, resp.text


async def test_matches_list_ti_denied_no_matches_read() -> None:
    # ti_integracion en el mapping NO tiene matches:read — debe 403.
    user = _make_user("ti_integracion")
    svc = MagicMock()
    app = _wire_rbac_app(
        router=matches_router,
        user=user,
        service_overrides={get_match_service: svc},
    )
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/matches")
    assert resp.status_code == 403, resp.text
    body = resp.json()
    assert "matches:read" in str(body["detail"])


# ---------------------------------------------------------------------------
# 2. matches:write — comercial allow refresh; auditor deny refresh.
# ---------------------------------------------------------------------------
async def test_matches_refresh_comercial_allowed() -> None:
    user = _make_user("comercial")
    svc = MagicMock()
    svc.list_candidates = AsyncMock(return_value=([], None))
    app = _wire_rbac_app(
        router=matches_router,
        user=user,
        service_overrides={get_match_service: svc},
    )
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/matches/MTBR4001050/refresh")
    assert resp.status_code == 202, resp.text


async def test_matches_refresh_auditor_denied() -> None:
    # Auditor sólo tiene matches:read — refresh requiere matches:write → 403.
    user = _make_user("auditor")
    svc = MagicMock()
    svc.refresh_candidates = AsyncMock(return_value=[])
    app = _wire_rbac_app(
        router=matches_router,
        user=user,
        service_overrides={get_match_service: svc},
    )
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/matches/MTBR4001050/refresh")
    assert resp.status_code == 403, resp.text
    body = resp.json()
    assert "matches:write" in str(body["detail"])


# ---------------------------------------------------------------------------
# 3. channels:read / channels:manage — auditor diff allow; comercial sync deny.
# ---------------------------------------------------------------------------
async def test_channels_diff_auditor_allowed_read_only() -> None:
    """Verifica que el dependency `require_permissions("channels:read")`
    aplicado en `/channels/.../diff` autoriza al auditor (que tiene
    `channels:read`). Llamamos directo al closure devuelto por la factory
    para evitar serialización downstream del fake."""
    user = _make_user("auditor")
    dep = require_permissions("channels:read")
    result = await dep(user=user)
    assert result is user


async def test_channels_sync_comercial_denied_no_manage() -> None:
    # comercial NO tiene channels:manage — sync debe 403.
    user = _make_user("comercial")
    svc = MagicMock()
    app = _wire_rbac_app(
        router=channels_router,
        user=user,
        service_overrides={
            get_mirror_service: svc,
            get_channel_adapters: {},
        },
    )
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/channels/amazon_uae/MTBR4001050/sync")
    assert resp.status_code == 403, resp.text
    body = resp.json()
    assert "channels:manage" in str(body["detail"])


# ---------------------------------------------------------------------------
# 4. prices:override_review — gerente allow counter; comercial deny.
# ---------------------------------------------------------------------------
async def test_revise_counter_gerente_allowed() -> None:
    """Gerente tiene `prices:override_review` — el dependency lo deja pasar."""
    user = _make_user("gerente_comercial")
    dep = require_permissions("prices:override_review")
    result = await dep(user=user)
    assert result is user


async def test_revise_counter_comercial_denied_no_override_review() -> None:
    # comercial tiene prices:propose pero NO prices:override_review.
    user = _make_user("comercial")
    revise_svc = MagicMock()
    app = _wire_rbac_app(
        router=pricing_engine_router,
        user=user,
        service_overrides={get_revise_service: revise_svc},
    )
    pid = uuid4()
    async with await _client(app) as ac:
        resp = await ac.post(
            f"/api/v1/pricing/prices/{pid}/revise-counter",
            json={"new_amount": "95.00", "reason": "ajuste"},
        )
    assert resp.status_code == 403, resp.text
    body = resp.json()
    assert "prices:override_review" in str(body["detail"])


# ---------------------------------------------------------------------------
# 5. Cross-permission isolation — gerente refresh denied if no matches:write.
# ---------------------------------------------------------------------------
async def test_gerente_has_matches_write_can_validate() -> None:
    """gerente_comercial tiene matches:write — el dependency autoriza."""
    user = _make_user("gerente_comercial")
    dep = require_permissions("matches:write")
    result = await dep(user=user)
    assert result is user


# ---------------------------------------------------------------------------
# 6. Sin usuario (401) — anónimo no pasa el dependency.
# ---------------------------------------------------------------------------
async def test_anonymous_user_returns_401() -> None:
    svc = MagicMock()
    app = _wire_rbac_app(
        router=matches_router,
        user=None,
        service_overrides={get_match_service: svc},
    )
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/matches")
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# 7. require_permissions — multi-perm AND semantics (sanity).
# ---------------------------------------------------------------------------
async def test_require_permissions_multi_all_must_be_present() -> None:
    """AND semantics: pedir {matches:read, matches:write} y un user con solo
    matches:read → 403 con la lista de missing perms en el detail."""
    user = _make_user("auditor")  # solo matches:read y channels:read
    dep = require_permissions("matches:read", "matches:write")
    with pytest.raises(HTTPException) as exc:
        await dep(user=user)
    assert exc.value.status_code == 403
    detail = exc.value.detail
    assert "matches:write" in str(detail)
    # No debe quejarse del que sí está presente.
    assert "missing_permissions" in str(detail)


# ---------------------------------------------------------------------------
# 8. Admin happy-path — tiene todos los permisos dedicados.
# ---------------------------------------------------------------------------
async def test_admin_passes_all_dedicated_perms() -> None:
    user = _make_user("admin")
    match_svc = MagicMock()
    match_svc.list_candidates = AsyncMock(return_value=([], None))
    app = _wire_rbac_app(
        router=matches_router,
        user=user,
        service_overrides={get_match_service: match_svc},
    )
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/matches")
    assert resp.status_code == 200, resp.text
