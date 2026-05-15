"""MatchService — orquestador del matching pipeline foundation.

Combina las piezas de Sprint 3:
1. :class:`QueryBuilder` produce queries multi-canal para el SKU.
2. Para cada fetcher registrado, ejecuta ``fetch`` con la primera query del
   canal correspondiente (los stubs ignoran la query → devuelven canned).
3. Cada candidato se puntúa con :func:`compute_scoring` (0-100).
4. Cada candidato se clasifica como ``peer`` (score ≥ 70) o ``drop`` /
   ``unknown`` según reglas heurísticas — el threshold es provisional para
   Sprint 3 y vivirá en ``comparator_config`` cuando exista.
5. Persistencia upsert vía :class:`MatchCandidateRepository`.

Errores de dominio se modelan como :class:`MatchDomainError` para que la capa
de routes los traduzca a HTTP 4xx (mismo patrón que ``ProductDomainError``).
"""

from __future__ import annotations

import re as _re
from collections.abc import Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from app.services.matching.enhanced_match_service import EnhancedMatchResult

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.inventory import CostLot
from app.db.models.match_candidate import MatchCandidate
from app.repositories.matches import MatchCandidateRepository
from app.repositories.product import ProductRepository
from app.services.matching.adapters import (
    AmazonUaeStubFetcher,
    NoonUaeStubFetcher,
)
from app.services.matching.delivery_classifier import classify_delivery
from app.services.matching.ports import CandidateRaw, FetcherPort, Query
from app.services.matching.search_query_cache import get_or_generate_query
from app.services.matching.query_builder import QueryBuilder
from app.services.matching.material_normalizer import MaterialNormalizer
from app.services.matching.scoring import compute_scoring

# Threshold provisional Sprint 3 — peer cuando score ≥ 70.
# TODO(ADR-MATCH-THRESHOLDS): externalizar a comparator_config.
PEER_SCORE_THRESHOLD = 70
DROP_SCORE_THRESHOLD = 40

# PSI→PN conversion: Amazon UAE listings express pressure in PSI/WOG.
_PSI_PER_BAR = 14.5038
_PN_GRADES = [6, 10, 16, 25, 40, 63, 100, 160]
_MAX_PRESSURE_RE = _re.compile(
    r'PN\s*(\d+)'                                          # "PN30", "PN 40"
    r'|(\d+(?:[.,]\d+)?)\s*(?:psi|wog|wsp|lb(?:/in)?²?)'  # "1000 PSI", "1000 WOG"
    r'|(\d+(?:[.,]\d+)?)\s*bar',                           # "40 bar"
    _re.I,
)


def _pdp_pn_parse(maximum_pressure: str | None) -> int | None:
    """Convierte el campo maximum_pressure de Amazon a un grado PN estándar."""
    if not maximum_pressure:
        return None
    m = _MAX_PRESSURE_RE.search(maximum_pressure)
    if not m:
        return None
    if m.group(1):
        return int(m.group(1))
    if m.group(2):
        psi = float(m.group(2).replace(",", ""))
        bar = psi / _PSI_PER_BAR
    else:
        bar = float(m.group(3).replace(",", ""))
    for grade in _PN_GRADES:
        if bar <= grade * 1.15:
            return grade
    return 160


class MatchDomainError(Exception):
    """Errores de negocio del matching service — mapean a 4xx en routes."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class MatchSkuNotFoundError(MatchDomainError):
    def __init__(self, sku: str) -> None:
        super().__init__(
            code="match_sku_not_found",
            message=f"SKU {sku!r} no existe — no se pueden traer candidatos.",
            status_code=404,
        )


class MatchCandidateNotFoundError(MatchDomainError):
    def __init__(self, candidate_id: UUID | str) -> None:
        super().__init__(
            code="match_candidate_not_found",
            message=f"Match candidate {candidate_id!s} no existe.",
            status_code=404,
        )


class MatchInvalidTransitionError(MatchDomainError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            code="match_invalid_transition",
            message=f"Transición {current!r} → {target!r} no permitida.",
            status_code=409,
        )


def _classify_candidate(
    score: int,
    scoring_notes: list[str],
    family: str | None = None,
) -> str:
    """Clasifica el candidato como peer / drop / unknown.

    Heurística Sprint 3:
    - score ≥ 70 → ``peer`` (peer-group para G1).
    - 40 ≤ score < 70 → ``drop`` (no es el mismo producto, pero compite).
    - score < 40 o note bloqueante según taxonomía → ``unknown``.

    Los blockers dependen de la familia del SKU (p.ej. ball_valve bloquea
    dn_mismatch, mini_mismatch, thread_standard_mismatch; manómetros no
    bloquean por DN). Ver taxonomy_rules.TAXONOMY_PROFILES.
    """
    from app.services.matching.taxonomy_rules import get_profile

    profile = get_profile(family)
    if profile.hard_blockers.intersection(scoring_notes):
        return "unknown"
    if score >= PEER_SCORE_THRESHOLD:
        return "peer"
    if score >= DROP_SCORE_THRESHOLD:
        return "drop"
    return "unknown"


class MatchService:
    """Orquesta query → fetch → score → upsert.

    El servicio recibe la sesión async y opcionalmente fetchers custom (para
    tests). Por defecto usa los stubs de Amazon UAE + Noon UAE.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        fetchers: Sequence[FetcherPort] | None = None,
        query_builder: QueryBuilder | None = None,
        material_normalizer: MaterialNormalizer | None = None,
    ) -> None:
        self.session = session
        self.fetchers: list[FetcherPort] = list(
            fetchers
            if fetchers is not None
            else (AmazonUaeStubFetcher(), NoonUaeStubFetcher())
        )
        self.query_builder = query_builder or QueryBuilder()
        self._matches_repo = MatchCandidateRepository(session)
        self._products_repo = ProductRepository(session)
        # Normalizer se carga lazy desde DB la primera vez que se necesita.
        self._material_normalizer: MaterialNormalizer | None = material_normalizer

    # ----------------------------------------------------------------------
    # Refresh
    # ----------------------------------------------------------------------
    async def refresh_candidates(self, sku: str) -> list[MatchCandidate]:
        """Etapa 1+2 stub + scoring + persistencia.

        Devuelve los candidatos ya persistidos (orden por score DESC).
        """
        product = await self._products_repo.get_by_sku_for_matching(sku)
        if product is None:
            raise MatchSkuNotFoundError(sku)

        sku_dict = self._product_to_dict(product)
        queries = self.query_builder.build_for_sku(sku_dict)

        # LLM-generated query (Claude Haiku) — prepended as priority 0 for
        # Amazon UAE. Cached in DB by (sku, channel); regenerated only when the
        # product changes or the user forces it. Falls back silently when
        # ANTHROPIC_API_KEY is not configured.
        llm_query_text = await get_or_generate_query(self.session, sku_dict, "amazon_uae")
        if llm_query_text:
            queries.insert(0, Query(
                text=llm_query_text,
                source="amazon_uae",
                lang="en",
                type="llm",
            ))

        # Commit aquí para liberar el row lock de product_search_queries
        # (UPDATE last_used_at) antes de los HTTP requests (60-90s).
        # Sin esto, el lock se mantiene durante todo el scraping y Supabase
        # cancela la sesión por statement_timeout en concurrent tasks.
        await self.session.commit()

        # Hard cap to protect against runaway scraping. The actual number of
        # persisted candidates is driven by score: anything below DROP_SCORE_THRESHOLD
        # is discarded, so the data itself determines how many are kept.
        _MAX_TOTAL_PER_CHANNEL = 30

        persisted: list[MatchCandidate] = []
        for fetcher in self.fetchers:
            channel_queries = [q for q in queries if q.source == fetcher.channel]
            if not channel_queries:
                continue

            # Run all queries in priority order. Stop only when the safety cap
            # is reached — score filtering below determines what actually gets kept.
            seen_external_ids: set[str] = set()
            total_fetched = 0
            for query in channel_queries:
                if total_fetched >= _MAX_TOTAL_PER_CHANNEL:
                    break
                candidates_raw = await fetcher.fetch(query, sku=sku)
                for raw in candidates_raw:
                    if raw.external_id in seen_external_ids:
                        continue
                    seen_external_ids.add(raw.external_id)
                    total_fetched += 1
                    row = await self._score_and_upsert(sku_dict, raw)
                    # Discard candidates below score floor OR blocked by a hard
                    # taxonomy rule (kind="unknown" = product type mismatch, PN
                    # below requirement, etc.). Taxonomy blockers supersede score.
                    if row.score < DROP_SCORE_THRESHOLD or row.kind == "unknown":
                        await self.session.delete(row)
                        await self.session.flush()
                        continue
                    persisted.append(row)

            # Limpiar candidatos `pending` del canal que no pertenecen a los
            # resultados actuales. Solo si el fetcher devolvió algo — si el
            # scraper fue bloqueado o falló, conservamos los existentes.
            if seen_external_ids:
                await self._purge_stale_pending(sku, fetcher.channel, seen_external_ids)

        # Sort por score DESC (best first), estable.
        persisted.sort(key=lambda r: r.score, reverse=True)
        return persisted

    async def _purge_stale_pending(
        self, sku: str, channel: str, keep_external_ids: set[str]
    ) -> None:
        """Elimina candidatos `pending` del canal cuyo external_id no está en keep_external_ids.

        Mantiene intactos los candidatos `validated` y `discarded` (decisiones humanas).
        """
        stmt = (
            delete(MatchCandidate)
            .where(
                MatchCandidate.product_sku == sku,
                MatchCandidate.channel == channel,
                MatchCandidate.status == "pending",
                MatchCandidate.external_id.notin_(keep_external_ids),
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def _score_and_upsert(
        self, sku_dict: dict[str, Any], raw: CandidateRaw
    ) -> MatchCandidate:
        raw_s = raw.specs or {}
        cand_dict: dict[str, Any] = {
            "title": raw.title,   # necesario para mini qualifier y product_type
            "brand": raw.brand,
            "price_aed": raw.price_aed,
            "delivery_text": raw.delivery_text,
            "specs": dict(raw_s),
        }
        # Aplastamos specs al top-level para que `compute_scoring` los lea.
        for k, v in raw_s.items():
            cand_dict.setdefault(k, v)

        # Normalizar nombres de campos PDP → nombres que espera compute_scoring.
        # Amazon PDP usa "material_type", "thread_type", "maximum_pressure";
        # el scoring lee "material", "thread", "pn" respectivamente.
        if raw_s.get("material_type") and not cand_dict.get("material"):
            cand_dict["material"] = raw_s["material_type"]
        if raw_s.get("thread_type") and not cand_dict.get("thread"):
            cand_dict["thread"] = raw_s["thread_type"]
        if raw_s.get("thread_size") and not cand_dict.get("size"):
            cand_dict["size"] = raw_s["thread_size"]
        _pn = _pdp_pn_parse(raw_s.get("maximum_pressure"))
        if _pn and not cand_dict.get("pn"):
            cand_dict["pn"] = _pn
        if raw_s.get("number_of_ports") and not cand_dict.get("ways"):
            try:
                cand_dict["ways"] = int(str(raw_s["number_of_ports"]).split()[0])
            except (ValueError, TypeError):
                pass

        # Fallback: extraer tamaño del título cuando specs no lo tiene.
        # curl_cffi no puede acceder al PDP, pero el título suele tener el tamaño.
        # _normalize_dn reconoce '1/2"', '1/2 inch', '1/2in', 'DN15', etc.
        if not cand_dict.get("dn") and not cand_dict.get("size"):
            from app.services.matching.scoring import _normalize_dn  # noqa: PLC0415
            title_dn = _normalize_dn(raw.title or "")
            if title_dn:
                cand_dict["size"] = title_dn

        # Fallback: detectar material desde el título cuando SERP-only (sin PDP).
        # curl_cffi no renderiza JS y no accede al PDP; el título suele mencionar
        # el material. Necesario para que material_mismatch dispare como blocker.
        if not cand_dict.get("material"):
            _title_lower = (raw.title or "").lower()
            _TITLE_MATERIALS = [
                (["stainless steel", "stainless-steel", "ss304", "ss316",
                  "304 stainless", "316 stainless", "inox"], "stainless_steel"),
                (["cast iron", "cast_iron", "hierro fundido"], "cast_iron"),
                (["carbon steel", "carbon-steel"], "carbon_steel"),
                (["polypropylene", " pp "], "polypropylene"),
                (["cpvc"], "cpvc"),
                (["bronze", "bronce"], "bronze"),
                (["pvc"], "pvc"),
                (["brass", "laiton", "latón", "latone"], "brass"),
            ]
            for _keywords, _mat in _TITLE_MATERIALS:
                if any(kw in _title_lower for kw in _keywords):
                    cand_dict["material"] = _mat
                    break

        if self._material_normalizer is None:
            self._material_normalizer = await MaterialNormalizer.from_db(self.session)
        breakdown = compute_scoring(sku_dict, cand_dict, material_normalizer=self._material_normalizer)
        kind = _classify_candidate(breakdown.score, breakdown.notes, family=sku_dict.get("family"))

        # Persistir el breakdown completo como parte del JSONB para auditoría.
        specs_to_persist = dict(raw_s)
        specs_to_persist["_scoring"] = breakdown.as_dict()

        # Aliases normalizados — frontend busca "material", "thread", "pn", "size"
        for _alias, _src in (
            ("material", cand_dict.get("material")),
            ("thread", cand_dict.get("thread")),
            ("size", cand_dict.get("size")),
            ("pn", cand_dict.get("pn")),
            ("ways", cand_dict.get("ways")),
        ):
            if _src is not None:
                specs_to_persist.setdefault(_alias, _src)

        # Preservar description_text e image_url en JSONB para que
        # refresh_candidates_enhanced pueda pasarlos a la Capa 1 (LLM) y Capa 2 (visión).
        raw_payload = raw.raw_payload or {}
        if raw_payload.get("description_text"):
            specs_to_persist["_description_text"] = raw_payload["description_text"]
        if raw_payload.get("image_url"):
            specs_to_persist["_amazon_image_url"] = raw_payload["image_url"]

        image_url = raw_payload.get("image_url") or None
        source_url = raw_payload.get("url") or None

        delivery = classify_delivery(raw.delivery_text)
        specs_to_persist["_delivery"] = {
            "category": delivery.category,
            "estimated_days": delivery.estimated_days,
            "price_confidence_score": delivery.price_confidence_score,
            "note": delivery.note,
        }

        from app.services.matching.extractors.pdp_extractor import parse_pack_units  # noqa: PLC0415
        pack_units = parse_pack_units(raw.title, raw.specs or {})

        return await self._matches_repo.upsert_candidate(
            product_sku=str(sku_dict.get("sku")),
            channel=raw.source,
            external_id=raw.external_id,
            title=raw.title,
            brand=raw.brand,
            price_aed=raw.price_aed,
            delivery_text=raw.delivery_text,
            specs_jsonb=specs_to_persist,
            kind=kind,
            score=breakdown.score,
            image_url=image_url,
            source_url=source_url,
            delivery_category=delivery.category,
            price_confidence_score=delivery.price_confidence_score,
            pack_units=pack_units,
        )

    # ----------------------------------------------------------------------
    # Listing / detail
    # ----------------------------------------------------------------------
    async def list_candidates(
        self,
        *,
        sku: str | None = None,
        status: str | None = None,
        channel: str | None = None,
        cursor: UUID | None = None,
        limit: int = 50,
    ) -> tuple[Sequence[MatchCandidate], UUID | None]:
        return await self._matches_repo.list_with_filters(
            sku=sku, status=status, channel=channel, cursor=cursor, limit=limit
        )

    async def get_candidate(self, candidate_id: UUID) -> MatchCandidate:
        obj = await self._matches_repo.get(candidate_id)
        if obj is None:
            raise MatchCandidateNotFoundError(candidate_id)
        return obj

    # ----------------------------------------------------------------------
    # State transitions
    # ----------------------------------------------------------------------
    async def validate_candidate(
        self, candidate_id: UUID, *, user_id: UUID | None
    ) -> MatchCandidate:
        obj = await self.get_candidate(candidate_id)
        if obj.status == "discarded":
            raise MatchInvalidTransitionError(obj.status, "validated")
        updated = await self._matches_repo.mark_validated(
            candidate_id, user_id=user_id
        )
        assert updated is not None  # acabamos de leer el row
        return updated

    async def discard_candidate(
        self, candidate_id: UUID, *, reason: str | None = None
    ) -> MatchCandidate:
        obj = await self.get_candidate(candidate_id)
        if obj.status == "validated":
            raise MatchInvalidTransitionError(obj.status, "discarded")
        updated = await self._matches_repo.mark_discarded(candidate_id, reason=reason)
        assert updated is not None
        return updated

    # ----------------------------------------------------------------------
    # Three-way summary (pricing)
    # ----------------------------------------------------------------------
    async def get_three_way_summary(self, sku: str) -> dict[str, Any]:
        """Combina los tres legs de pricing para un SKU.

        Leg 1 — producto MT: verifica que el SKU existe en el catálogo.
        Leg 2 — mejor candidato validado del scraper: el MatchCandidate con
                 status='validated' y score más alto que tenga price_aed.
        Leg 3 — costo de compra real: último CostLot activo (mayor
                 effective_at) con qty_remaining > 0 para el SKU.

        Returns:
            dict compatible con ThreeWaySummaryResponse schema.

        Raises:
            MatchSkuNotFoundError: si el SKU no existe en el catálogo.
        """
        # --- Leg 1: verificar que el SKU existe ---
        product = await self._products_repo.get_by_sku_for_matching(sku)
        if product is None:
            raise MatchSkuNotFoundError(sku)

        missing_legs: list[str] = []

        # --- Leg 2: mejor candidato validado con precio de mercado ---
        stmt_candidate = (
            select(MatchCandidate)
            .where(
                MatchCandidate.product_sku == sku,
                MatchCandidate.status == "validated",
                MatchCandidate.price_aed.is_not(None),
            )
            .order_by(MatchCandidate.score.desc(), MatchCandidate.updated_at.desc())
            .limit(1)
        )
        result_candidate = await self.session.execute(stmt_candidate)
        best_candidate: MatchCandidate | None = result_candidate.scalar_one_or_none()

        if best_candidate is None:
            missing_legs.append("market_candidate")

        # --- Leg 3: último lote de costo real con stock disponible ---
        stmt_cost = (
            select(CostLot)
            .where(
                CostLot.sku == sku,
                CostLot.qty_remaining > 0,
            )
            .order_by(CostLot.effective_at.desc())
            .limit(1)
        )
        result_cost = await self.session.execute(stmt_cost)
        last_lot: CostLot | None = result_cost.scalar_one_or_none()

        if last_lot is None:
            missing_legs.append("purchase_cost")

        # --- Margen estimado ---
        precio_mercado: Decimal | None = (
            best_candidate.price_aed if best_candidate else None
        )
        costo_compra: Decimal | None = (
            last_lot.unit_cost_aed if last_lot else None
        )

        margen_aed: Decimal | None = None
        margen_pct: Decimal | None = None
        if precio_mercado is not None and costo_compra is not None:
            margen_aed = (precio_mercado - costo_compra).quantize(Decimal("0.0001"))
            if precio_mercado != 0:
                margen_pct = (margen_aed / precio_mercado * 100).quantize(
                    Decimal("0.0001")
                )

        return {
            "sku": sku,
            # Leg 2
            "best_candidate_id": best_candidate.id if best_candidate else None,
            "best_candidate_title": best_candidate.title if best_candidate else None,
            "best_candidate_channel": best_candidate.channel if best_candidate else None,
            "precio_mercado_aed": precio_mercado,
            "candidate_score": best_candidate.score if best_candidate else None,
            # Leg 3
            "costo_compra_aed": costo_compra,
            "costo_lot_id": last_lot.id if last_lot else None,
            "costo_supplier": last_lot.supplier_code if last_lot else None,
            # Margen
            "margen_estimado_pct": margen_pct,
            "margen_estimado_aed": margen_aed,
            # Completitud
            "is_three_way_complete": len(missing_legs) == 0,
            "missing_legs": missing_legs,
        }

    # ----------------------------------------------------------------------
    # Enhanced matching (Capa 0+1+2 con LLM y visión)
    # ----------------------------------------------------------------------

    async def _get_mt_image_url(self, sku: str) -> str | None:
        """Devuelve la URL pública de la foto principal del producto MT en Supabase Storage."""
        from sqlalchemy import select as sa_select

        from app.core.config import settings
        from app.db.models.product import ProductAsset

        stmt = (
            sa_select(ProductAsset)
            .where(ProductAsset.sku == sku, ProductAsset.kind == "photo")
            .order_by(ProductAsset.is_primary.desc(), ProductAsset.position)
            .limit(1)
        )
        asset = (await self.session.execute(stmt)).scalar_one_or_none()
        if asset is None:
            return None
        supabase_base = str(settings.SUPABASE_URL).rstrip("/")
        return f"{supabase_base}/storage/v1/object/public/{asset.bucket}/{asset.storage_path}"

    async def refresh_candidates_enhanced(
        self,
        sku: str,
        *,
        mt_image_url: str | None = None,
    ) -> list[tuple[MatchCandidate, EnhancedMatchResult]]:
        """Pipeline mejorado: fetch determinista + enriquecimiento LLM + visión.

        Llama a ``refresh_candidates()`` para poblar/actualizar los candidatos
        en DB, luego aplica ``enhanced_score()`` sobre cada uno y actualiza
        ``specs_jsonb._enhanced`` con el método y resultado.

        NO rompe el flujo existente — es un método adicional que enriquece los
        candidatos ya persistidos.

        Args:
            sku: SKU del producto MT a procesar.
            mt_image_url: URL de imagen del producto MT para comparación visual.
                          Puede ser None — en ese caso la Capa 2 se omite.

        Returns:
            Lista de (MatchCandidate actualizado, EnhancedMatchResult) ordenada
            por score DESC.
        """
        from app.services.matching.enhanced_match_service import (  # lazy — anthropic only in scraper-worker
            EnhancedMatchResult,
            enhanced_score,
        )

        # Etapa base: fetch + score determinista + upsert (flujo existente)
        candidates = await self.refresh_candidates(sku)

        product = await self._products_repo.get_by_sku_for_matching(sku)
        if product is None:
            raise MatchSkuNotFoundError(sku)
        product_data = self._product_to_dict(product)

        # Obtener imagen MT si no se pasó externamente
        effective_mt_image_url = mt_image_url or await self._get_mt_image_url(sku)

        # Leer la query LLM cacheada para incluirla en el panel de análisis.
        from app.db.models.search_query import ProductSearchQuery as _PSQ
        _psq_stmt = select(_PSQ).where(_PSQ.sku == sku, _PSQ.channel == "amazon_uae")
        _psq_row = (await self.session.execute(_psq_stmt)).scalar_one_or_none()
        cached_llm_query: str | None = _psq_row.query_text if _psq_row else None

        results: list[tuple[MatchCandidate, EnhancedMatchResult]] = []

        for candidate in candidates:
            jsonb = dict(candidate.specs_jsonb or {})

            # Reconstruir CandidateRaw desde el MatchCandidate persistido.
            # raw_payload debe reconstruir description_text e image_url que
            # _score_and_upsert() guardó en specs_jsonb con prefijo "_".
            raw = CandidateRaw(
                source=candidate.channel,
                external_id=candidate.external_id,
                title=candidate.title,
                brand=candidate.brand,
                price_aed=candidate.price_aed,
                delivery_text=candidate.delivery_text,
                specs=jsonb,
                raw_payload={
                    "image_url": candidate.image_url or jsonb.get("_amazon_image_url", ""),
                    "url": candidate.source_url or "",
                    "description_text": jsonb.get("_description_text", ""),
                },
            )

            # Aplicar pipeline mejorado
            result = await enhanced_score(product_data, raw, mt_image_url=effective_mt_image_url)

            # Actualizar specs_jsonb con metadata del pipeline mejorado
            current_specs = dict(candidate.specs_jsonb or {})
            current_specs["_enhanced"] = {
                "score": result.score,
                "method": result.method,
                "auto_validate": result.auto_validate,
                "llm_confidence": result.llm_confidence,
                "visual_verdict": result.visual_verdict,
                "llm_specs": result.llm_specs,
                "breakdown": result.breakdown,
                "llm_query": cached_llm_query,
                # Incluir info de entrega desde _delivery (ya calculado en _score_and_upsert)
                "delivery": current_specs.get("_delivery"),
            }

            # Fusionar specs LLM al top-level de specs_jsonb para que la UI
            # las lea directamente sin tener que navegar el dict anidado.
            # Mapeamos los nombres del extractor a las claves que espera el frontend.
            if result.llm_specs:
                llm = result.llm_specs
                if llm.get("material"):
                    current_specs["material"] = llm["material"]
                if llm.get("valve_type"):
                    current_specs["valve_type"] = llm["valve_type"]
                if llm.get("size_inches"):
                    current_specs["size"] = llm["size_inches"]
                if llm.get("pressure_pn") is not None:
                    current_specs["pn"] = llm["pressure_pn"]
                if llm.get("end_connection"):
                    current_specs["thread"] = llm["end_connection"]
                if llm.get("alloy_code"):
                    current_specs["alloy"] = llm["alloy_code"]

            # Actualizar score si el pipeline lo mejoró
            if result.score != candidate.score:
                candidate.score = result.score

            candidate.specs_jsonb = current_specs
            await self.session.flush()
            await self.session.refresh(candidate)

            results.append((candidate, result))

        # Ordenar por score DESC
        results.sort(key=lambda pair: pair[0].score, reverse=True)
        return results

    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------
    @staticmethod
    def _product_to_dict(product: Any) -> dict[str, Any]:
        """Extrae los campos relevantes para el matching de un Product ORM o dict."""
        if isinstance(product, dict):
            base = dict(product)
        else:
            specs = dict(getattr(product, "specs", {}) or {})
            # Flatten nested specs lists to scalars for QueryBuilder consumption.
            alloy_list = specs.get("alloy") or []
            standards_list = specs.get("standards") or []

            # `type` (e.g. "Ball Valve M-F PN30") is the best English descriptor;
            # fall back to erp_name which also contains English text.
            product_type = getattr(product, "type", None)
            erp_name = getattr(product, "erp_name", None)

            # product_materials — componentes body/ball/seat/stem (Wave 3).
            # Si la relación está cargada (selectinload en el caller), se usa;
            # de lo contrario queda vacío y el scoring cae al campo plano.
            pm_rel = getattr(product, "materials", None) or []
            product_materials = [
                {"component": pm.component, "material": pm.material, "position": pm.position}
                for pm in pm_rel
            ]

            base = {
                "sku": getattr(product, "sku", None),
                # name_en → product type takes priority over erp_name; both are
                # English and much more useful than the Spanish family field.
                "name_en": product_type or erp_name,
                "product_type": product_type,
                "erp_name": erp_name,
                "family": getattr(product, "family", None),
                "subfamily": getattr(product, "subfamily", None),
                "material": getattr(product, "material", None),
                "dn": getattr(product, "dn", None),
                "pn": getattr(product, "pn", None),
                "connection": getattr(product, "connection", None),
                "brand": getattr(product, "brand", None),
                "specs": specs,
                # Flatten key specs so QueryBuilder can read them directly.
                "alloy": alloy_list[0] if alloy_list else None,
                "norma": standards_list[0] if standards_list else None,
                # Componentes de material para scoring compuesto body/ball/seat.
                "product_materials": product_materials,
            }
        # Alias `thread` ⇄ `connection` para que scoring lea ambos.
        if base.get("thread") is None and base.get("connection") is not None:
            base["thread"] = base["connection"]
        return base
