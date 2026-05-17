"""Rule Engine REST API.

Endpoints para gestionar taxonomía de perfiles, transformaciones de unidades,
equivalencias de normas, configuración del comparador y sugerencias de reglas.

GET/PUT /rule-engine/taxonomy-profiles
GET/POST/DELETE /rule-engine/unit-transforms
GET/POST /rule-engine/norm-equivalences
GET/PUT /rule-engine/comparator-config
GET /rule-engine/rule-suggestions  POST .../apply  POST .../dismiss
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_role
from app.db.models.comparator_config import ComparatorConfig
from app.db.models.rule_suggestion import RuleSuggestion
from app.repositories.comparator_config import ComparatorConfigRepository
from app.repositories.match_rule_stat import MatchRuleStatRepository
from app.repositories.norm_equivalence import NormEquivalenceRepository
from app.repositories.rule_suggestion import RuleSuggestionRepository
from app.repositories.taxonomy_profile import TaxonomyProfileRepository
from app.repositories.unit_transform import UnitTransformRepository
from app.schemas.rule_engine import (
    ComparatorConfigEntry,
    ComparatorConfigUpdate,
    NormEquivalenceCreate,
    NormEquivalenceResponse,
    ProfileMetrics,
    RuleSuggestionResponse,
    TaxonomyProfileResponse,
    TaxonomyProfileUpdate,
    UnitTransformCreate,
    UnitTransformResponse,
)
from app.services.matching.rule_engine_cache import get_rule_engine_cache

router = APIRouter(
    prefix="/rule-engine",
    tags=["rule-engine"],
    dependencies=[Depends(require_role("admin"))],
)


# ── Taxonomy Profiles ────────────────────────────────────────────────────────

@router.get("/taxonomy-profiles", response_model=list[TaxonomyProfileResponse])
async def list_taxonomy_profiles(session: AsyncSession = Depends(get_db_session)):
    repo = TaxonomyProfileRepository(session)
    return await repo.list_all()


@router.get("/taxonomy-profiles/{family}", response_model=TaxonomyProfileResponse)
async def get_taxonomy_profile(family: str, session: AsyncSession = Depends(get_db_session)):
    repo = TaxonomyProfileRepository(session)
    profile = await repo.get_by_family(family)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Familia '{family}' no encontrada")
    return profile


@router.put("/taxonomy-profiles/{family}", response_model=TaxonomyProfileResponse)
async def update_taxonomy_profile(
    family: str,
    body: TaxonomyProfileUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    repo = TaxonomyProfileRepository(session)
    profile = await repo.upsert_by_family(
        family=family,
        weights=body.weights,
        hard_blockers=body.hard_blockers,
        description=body.description,
    )
    await session.commit()
    get_rule_engine_cache()._loaded_at = 0.0
    return profile


@router.get("/taxonomy-profiles/{family}/stats", response_model=ProfileMetrics)
async def get_taxonomy_profile_stats(
    family: str,
    days: int = 30,
    session: AsyncSession = Depends(get_db_session),
):
    tp_repo = TaxonomyProfileRepository(session)
    profile = await tp_repo.get_by_family(family)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Familia '{family}' no encontrada")
    stat_repo = MatchRuleStatRepository(session)
    metrics = await stat_repo.get_profile_metrics(profile.id, days=days)
    return metrics


# ── Unit Transforms ──────────────────────────────────────────────────────────

@router.get("/unit-transforms", response_model=list[UnitTransformResponse])
async def list_unit_transforms(session: AsyncSession = Depends(get_db_session)):
    repo = UnitTransformRepository(session)
    return await repo.list_all()


@router.post("/unit-transforms", response_model=UnitTransformResponse, status_code=201)
async def create_unit_transform(
    body: UnitTransformCreate,
    session: AsyncSession = Depends(get_db_session),
):
    repo = UnitTransformRepository(session)
    obj = await repo.create(**body.model_dump())
    await session.commit()
    await session.refresh(obj)
    return obj


@router.delete("/unit-transforms/{transform_id}", status_code=204)
async def delete_unit_transform(
    transform_id: UUID,
    session: AsyncSession = Depends(get_db_session),
):
    repo = UnitTransformRepository(session)
    obj = await repo.get(transform_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Transformación no encontrada")
    await session.delete(obj)
    await session.commit()


# ── Norm Equivalences ────────────────────────────────────────────────────────

@router.get("/norm-equivalences", response_model=list[NormEquivalenceResponse])
async def list_norm_equivalences(session: AsyncSession = Depends(get_db_session)):
    repo = NormEquivalenceRepository(session)
    return await repo.list_all()


@router.post("/norm-equivalences", response_model=NormEquivalenceResponse, status_code=201)
async def create_norm_equivalence(
    body: NormEquivalenceCreate,
    session: AsyncSession = Depends(get_db_session),
):
    repo = NormEquivalenceRepository(session)
    obj = await repo.create(**body.model_dump())
    await session.commit()
    await session.refresh(obj)
    return obj


# ── Comparator Config ────────────────────────────────────────────────────────

@router.get("/comparator-config", response_model=list[ComparatorConfigEntry])
async def list_comparator_config(session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(select(ComparatorConfig).order_by(ComparatorConfig.key))
    return list(result.scalars().all())


@router.put("/comparator-config/{key}")
async def update_comparator_config(
    key: str,
    body: ComparatorConfigUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    repo = ComparatorConfigRepository(session)
    obj = await repo.set_value(key, body.value)
    await session.commit()
    get_rule_engine_cache()._loaded_at = 0.0
    return {"key": obj.key, "value": obj.value}


# ── Rule Suggestions ─────────────────────────────────────────────────────────

@router.get("/rule-suggestions", response_model=list[RuleSuggestionResponse])
async def list_rule_suggestions(
    status: str = "pending",
    session: AsyncSession = Depends(get_db_session),
):
    stmt = (
        select(RuleSuggestion)
        .where(RuleSuggestion.status == status)
        .order_by(RuleSuggestion.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("/rule-suggestions/{suggestion_id}/apply", status_code=200)
async def apply_rule_suggestion(
    suggestion_id: UUID,
    session: AsyncSession = Depends(get_db_session),
):
    repo = RuleSuggestionRepository(session)
    suggestion = await repo.get(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Sugerencia no encontrada")
    if suggestion.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Sugerencia ya está en estado '{suggestion.status}'",
        )
    if suggestion.taxonomy_profile_id and suggestion.proposed_change.get("weights"):
        tp_repo = TaxonomyProfileRepository(session)
        profile = await tp_repo.get(suggestion.taxonomy_profile_id)
        if profile:
            profile.weights = suggestion.proposed_change["weights"]
            get_rule_engine_cache()._loaded_at = 0.0
    suggestion.status = "applied"
    await session.commit()
    return {"status": "applied"}


@router.post("/rule-suggestions/{suggestion_id}/dismiss", status_code=200)
async def dismiss_rule_suggestion(
    suggestion_id: UUID,
    session: AsyncSession = Depends(get_db_session),
):
    repo = RuleSuggestionRepository(session)
    suggestion = await repo.get(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Sugerencia no encontrada")
    suggestion.status = "dismissed"
    await session.commit()
    return {"status": "dismissed"}
