"""Exception Rules CRUD API — US-1B-02-02.

Endpoints:
- POST   /exception-rules               — crear nueva regla
- PATCH  /exception-rules/{id}/activate — activar regla + cierra anterior
- GET    /exception-rules/history       — historial completo paginado
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.repositories.audit import AuditRepository
from app.repositories.pricing import ExceptionRuleRepository
from app.schemas.pricing import (
    ExceptionRuleActivateResponse,
    ExceptionRuleCreate,
    ExceptionRuleResponse,
)

router = APIRouter(prefix="/exception-rules", tags=["exception-rules"])


# ---------------------------------------------------------------------------
# POST /exception-rules — crear nueva regla (inactiva por defecto)
# ---------------------------------------------------------------------------
@router.post(
    "",
    response_model=ExceptionRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nueva exception rule (inactiva hasta activar explícitamente)",
    responses={409: {"description": "Código de regla ya existe"}},
)
async def create_exception_rule(
    data: ExceptionRuleCreate,
    user: Annotated[User, Depends(require_permissions("prices:approve"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ExceptionRuleResponse:
    repo = ExceptionRuleRepository(session)

    # Verificar unicidad del código.
    existing = await repo.get_by_code(data.code)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "exception_rule_code_conflict",
                "title": f"Ya existe una regla con código '{data.code}'",
            },
        )

    rule_data = data.model_dump()
    rule_data["active"] = False
    rule_data["created_by"] = user.id

    rule = await repo.create(rule_data)

    audit = AuditRepository(session)
    await audit.record(
        entity_type="exception_rule",
        entity_id=str(rule.id),
        action="exception_rule.created",
        actor_id=user.id,
        actor_email=user.email,
        after={
            "code": rule.code,
            "active": rule.active,
            "version": rule.version,
        },
    )
    return ExceptionRuleResponse.model_validate(rule)


# ---------------------------------------------------------------------------
# PATCH /exception-rules/{rule_id}/activate
# ---------------------------------------------------------------------------
@router.patch(
    "/{rule_id}/activate",
    response_model=ExceptionRuleActivateResponse,
    summary="Activa una exception rule y cierra la versión anterior del mismo scope",
    responses={
        404: {"description": "Regla no encontrada"},
    },
)
async def activate_exception_rule(
    rule_id: UUID,
    user: Annotated[User, Depends(require_permissions("prices:approve"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ExceptionRuleActivateResponse:
    repo = ExceptionRuleRepository(session)
    try:
        rule = await repo.activate(rule_id, actor_id=user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "exception_rule_not_found",
                "title": str(exc),
            },
        ) from exc

    audit = AuditRepository(session)
    await audit.record(
        entity_type="exception_rule",
        entity_id=str(rule.id),
        action="exception_rule.activated",
        actor_id=user.id,
        actor_email=user.email,
        after={
            "code": rule.code,
            "active": rule.active,
            "effective_from": rule.effective_from.isoformat() if rule.effective_from else None,
        },
    )
    return ExceptionRuleActivateResponse.model_validate(rule)


# ---------------------------------------------------------------------------
# GET /exception-rules/history — historial completo
# ---------------------------------------------------------------------------
@router.get(
    "/history",
    response_model=list[ExceptionRuleResponse],
    summary="Historial completo de exception rules (activas + cerradas), orden created_at desc",
)
async def list_exception_rules_history(
    _user: Annotated[User, Depends(require_permissions("prices:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ExceptionRuleResponse]:
    repo = ExceptionRuleRepository(session)
    rows = await repo.list_history(limit=limit)
    return [ExceptionRuleResponse.model_validate(r) for r in rows]
