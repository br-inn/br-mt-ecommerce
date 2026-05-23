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

import logging
import re as _re
from collections.abc import Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.services.matching.enhanced_match_service import EnhancedMatchResult
    from app.repositories.unmatched_offers import UnmatchedOfferRepository

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.inventory import CostLot
from app.db.models.match_candidate import MatchCandidate
from app.repositories.matches import MatchCandidateRepository
from app.repositories.product import ProductRepository
from app.services.matching.adapters import (
    AmazonUaeStubFetcher,
)
from app.services.matching.delivery_classifier import classify_delivery
from app.services.matching.ports import CandidateRaw, FetcherPort, Query
from app.services.matching.search_query_cache import get_or_generate_query
from app.services.matching.query_builder import QueryBuilder
from app.core.config import settings
from app.services.matching.material_normalizer import MaterialNormalizer
from app.services.matching.scoring import compute_scoring

# Threshold provisional Sprint 3 — peer cuando score ≥ 70.
# TODO(ADR-MATCH-THRESHOLDS): externalizar a comparator_config.
PEER_SCORE_THRESHOLD = 70
DROP_SCORE_THRESHOLD = 40


def _get_thresholds(cache=None) -> tuple[int, int]:
    """Retorna (peer_threshold, drop_threshold) desde cache o fallback."""
    if cache is not None:
        peer = int(cache.get_config_value("peer_threshold", 70))
        drop = int(cache.get_config_value("drop_threshold", 40))
        return peer, drop
    return 70, 40


def populate_conformal_fields(candidate: Any, calibrator: Any | None) -> None:
    """Puebla calibrated_confidence/conf_lower/conf_upper/review_priority.

    Si calibrator es None, no hace nada.
    """
    if calibrator is None:
        return
    from decimal import Decimal as _D  # noqa: PLC0415

    raw = candidate.score / 100.0
    pred = calibrator.predict_with_interval(raw)
    candidate.calibrated_confidence = _D(str(round(pred.point_estimate, 4)))
    candidate.conf_lower = _D(str(round(pred.lower_bound, 4)))
    candidate.conf_upper = _D(str(round(pred.upper_bound, 4)))
    candidate.review_priority = pred.review_priority


# PSI→PN conversion: Amazon UAE listings express pressure in PSI/WOG.
_PSI_PER_BAR = 14.5038
_PN_GRADES = [6, 10, 16, 25, 40, 63, 100, 160]
_MAX_PRESSURE_RE = _re.compile(
    r"PN\s*(\d+)"  # "PN30", "PN 40"
    r"|(\d+(?:[.,]\d+)?)\s*(?:psi|wog|wsp|lb(?:/in)?²?)"  # "1000 PSI", "1000 WOG"
    r"|(\d+(?:[.,]\d+)?)\s*bar",  # "40 bar"
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
    peer_threshold: int = 70,
    drop_threshold: int = 40,
) -> str:
    """Clasifica el candidato como peer / drop / unknown.

    Heurística Sprint 3:
    - score ≥ peer_threshold → ``peer`` (peer-group para G1).
    - drop_threshold ≤ score < peer_threshold → ``drop`` (no es el mismo producto, pero compite).
    - score < drop_threshold o note bloqueante según taxonomía → ``unknown``.

    Los blockers dependen de la familia del SKU (p.ej. ball_valve bloquea
    dn_mismatch, mini_mismatch, thread_standard_mismatch; manómetros no
    bloquean por DN). Ver taxonomy_rules.TAXONOMY_PROFILES.
    """
    from app.services.matching.taxonomy_rules import get_profile

    profile = get_profile(family)
    if profile.hard_blockers.intersection(scoring_notes):
        return "unknown"
    if score >= peer_threshold:
        return "peer"
    if score >= drop_threshold:
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
        unmatched_repo: "UnmatchedOfferRepository | None" = None,
    ) -> None:
        self.session = session
        self.fetchers: list[FetcherPort] = list(
            fetchers
            if fetchers is not None
            else (AmazonUaeStubFetcher(),)  # Noon UAE no implementado aún
        )
        self.query_builder = query_builder or QueryBuilder()
        self._matches_repo = MatchCandidateRepository(session)
        self._products_repo = ProductRepository(session)
        # Normalizer se carga lazy desde DB la primera vez que se necesita.
        self._material_normalizer: MaterialNormalizer | None = material_normalizer
        self._unmatched_repo = unmatched_repo

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
            queries.insert(
                0,
                Query(
                    text=llm_query_text,
                    source="amazon_uae",
                    lang="en",
                    type="llm",
                ),
            )

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
                        if self._unmatched_repo is not None:
                            try:
                                await self._unmatched_repo.upsert_from_raw(raw, source_sku=sku)
                            except Exception:
                                logger.warning(
                                    "unmatched_offer.upsert_failed",
                                    extra={"external_id": raw.external_id, "channel": raw.source},
                                    exc_info=True,
                                )
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

        # ── Cross-encoder re-ranking (US-SCR-04-08a) ──────────────────────────
        # Aplica ms-marco-MiniLM-L-6-v2 si está disponible. Degradación
        # graceful: si sentence-transformers no está instalado o Redis no
        # disponible, se mantiene el orden por score determinista.
        # Feature flag: CROSS_ENCODER_ENABLED=true (default: false).
        _cross_encoder_enabled = settings.ENABLE_CROSS_ENCODER_RERANKER
        _rerank_query = sku_dict.get("name_en") or sku_dict.get("name") or ""
        if _cross_encoder_enabled and persisted and _rerank_query:
            try:
                from app.services.matching.cross_encoder_reranker import rerank_candidates  # noqa: PLC0415

                # Convertir a dicts para el reranker
                cand_dicts = [
                    {
                        "id": str(c.id),
                        "title": c.title or "",
                        "_idx": i,
                    }
                    for i, c in enumerate(persisted)
                ]
                from app.core.redis import get_redis  # noqa: PLC0415

                reranked_dicts = await rerank_candidates(
                    query=_rerank_query,
                    candidates=cand_dicts,
                    text_field="title",
                    redis_client=get_redis(),
                )
                # Reordenar persisted según nuevo ranking del cross-encoder
                idx_order = [d["_idx"] for d in reranked_dicts]
                persisted = [persisted[i] for i in idx_order]

                # Escribir calibrated_confidence = sigmoid(rerank_score) → [0, 1]
                import math as _math  # noqa: PLC0415

                for _rd, _row in zip(reranked_dicts, persisted, strict=False):
                    _rs = _rd.get("rerank_score")
                    if _rs is not None:
                        _row.calibrated_confidence = Decimal(
                            str(round(1.0 / (1.0 + _math.exp(-_rs)), 4))
                        )

                logger.debug(
                    "cross_encoder.reranked",
                    extra={"sku": sku, "n": len(persisted)},
                )
            except Exception as _ce_exc:
                logger.debug(
                    "cross_encoder.skipped",
                    extra={"reason": str(_ce_exc)[:120]},
                )

        # ── Pool-relativa: maneta (handle) ────────────────────────────────────
        # Regla: candidatos con handle_mismatch solo se listan si NO hay ningún
        # candidato sin mismatch en el pool. Si hay alternativas sin mismatch,
        # los candidatos con mismatch se eliminan completamente.
        # Si TODOS tienen mismatch → se muestran pero con confidence -15.
        # No necesita check previo de sku_has_handle: si _handle_score no detectó
        # datos de maneta en el SKU, ningún candidato tendrá la nota y
        # mismatch_rows quedará vacío.
        if persisted:
            mismatch_rows: list[MatchCandidate] = []
            ok_count = 0
            for row in persisted:
                _notes = (row.specs_jsonb or {}).get("_scoring", {}).get("notes", [])
                if "handle_mismatch" in _notes:
                    mismatch_rows.append(row)
                else:
                    ok_count += 1

            if ok_count > 0 and mismatch_rows:
                # Hay mejores alternativas → excluir los de handle distinto
                for row in mismatch_rows:
                    persisted.remove(row)
                    await self.session.delete(row)
                await self.session.flush()
            elif mismatch_rows and ok_count == 0:
                # Sin alternativas → mantenerlos pero bajar confianza
                for row in mismatch_rows:
                    row.price_confidence_score = max(0, (row.price_confidence_score or 0) - 15)
                await self.session.flush()

        # Helper reutilizable para lógica pool-relativa por nota de mismatch.
        async def _apply_pool_relative_note(note: str) -> None:
            mismatch: list[MatchCandidate] = []
            ok = 0
            for row in persisted:
                _ns = (row.specs_jsonb or {}).get("_scoring", {}).get("notes", [])
                if note in _ns:
                    mismatch.append(row)
                else:
                    ok += 1
            if ok > 0 and mismatch:
                for row in mismatch:
                    persisted.remove(row)
                    await self.session.delete(row)
                await self.session.flush()
            elif mismatch and ok == 0:
                for row in mismatch:
                    row.price_confidence_score = max(0, (row.price_confidence_score or 0) - 15)
                await self.session.flush()

        # Helper para comparación directa de specs_jsonb (sin depender de _scoring.notes).
        async def _apply_pool_relative_spec(
            sku_value: str | None,
            spec_key: str,
            normalize_fn: Any,
        ) -> None:
            if not sku_value:
                return
            sku_norm = normalize_fn(sku_value)
            if not sku_norm:
                return
            mismatch: list[MatchCandidate] = []
            ok = 0
            for row in persisted:
                cand_val = (row.specs_jsonb or {}).get(spec_key)
                cand_norm = normalize_fn(cand_val)
                if cand_norm and cand_norm != sku_norm:
                    mismatch.append(row)
                else:
                    ok += 1
            if ok > 0 and mismatch:
                for row in mismatch:
                    persisted.remove(row)
                    await self.session.delete(row)
                await self.session.flush()
            elif mismatch and ok == 0:
                for row in mismatch:
                    row.price_confidence_score = max(0, (row.price_confidence_score or 0) - 15)
                await self.session.flush()

        # ── Pool-relativa: género de conexión ──────────────────────────────────
        from app.services.matching.scoring import (  # noqa: PLC0415
            _normalize_gender,
            _normalize_bore,
            _normalize_seat_mat,
        )

        _sku_specs = sku_dict.get("specs") or {}

        await _apply_pool_relative_spec(
            _sku_specs.get("end_connection_gender"), "connection_gender", _normalize_gender
        )

        # ── Pool-relativa: bore type (full bore / reduced bore) ────────────────
        await _apply_pool_relative_spec(_sku_specs.get("bore_type"), "bore_type", _normalize_bore)

        # ── Pool-relativa: material asiento (seat_material) ────────────────────
        await _apply_pool_relative_spec(
            _sku_specs.get("seat_material"), "seat_material", _normalize_seat_mat
        )

        # ── Pool-relativa: material sello (seal_material) ──────────────────────
        await _apply_pool_relative_spec(
            _sku_specs.get("seal_material"), "seal_material", _normalize_seat_mat
        )

        # ── Pool-relativa: inlet/outlet asimétrico ─────────────────────────────
        # Solo aplica si el SKU tiene conexiones distintas en inlet y outlet
        # (producto asimétrico, p.ej. reductor, válvula de ángulo).
        _sku_inlet = _sku_specs.get("inlet_connection")
        _sku_outlet = _sku_specs.get("outlet_connection")
        if persisted and _sku_inlet and _sku_outlet and _sku_inlet != _sku_outlet:
            _io_mismatch: list[MatchCandidate] = []
            _io_ok = 0
            for row in persisted:
                _rs = row.specs_jsonb or {}
                _c_inlet = _rs.get("inlet_connection")
                _c_outlet = _rs.get("outlet_connection")
                if (_c_inlet and _c_inlet != _sku_inlet) or (
                    _c_outlet and _c_outlet != _sku_outlet
                ):
                    _io_mismatch.append(row)
                else:
                    _io_ok += 1
            if _io_ok > 0 and _io_mismatch:
                for row in _io_mismatch:
                    persisted.remove(row)
                    await self.session.delete(row)
                await self.session.flush()
            elif _io_mismatch and _io_ok == 0:
                for row in _io_mismatch:
                    row.price_confidence_score = max(0, (row.price_confidence_score or 0) - 15)
                await self.session.flush()

        return persisted

    async def _purge_stale_pending(
        self, sku: str, channel: str, keep_external_ids: set[str]
    ) -> None:
        """Elimina candidatos `pending` del canal cuyo external_id no está en keep_external_ids.

        Mantiene intactos los candidatos `validated` y `discarded` (decisiones humanas).
        """
        stmt = delete(MatchCandidate).where(
            MatchCandidate.product_sku == sku,
            MatchCandidate.channel == channel,
            MatchCandidate.status == "pending",
            MatchCandidate.external_id.notin_(keep_external_ids),
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def _score_and_upsert(
        self, sku_dict: dict[str, Any], raw: CandidateRaw
    ) -> MatchCandidate:
        from app.services.matching.rule_engine_cache import get_rule_engine_cache  # noqa: PLC0415

        _cache = get_rule_engine_cache()
        peer_threshold, drop_threshold = _get_thresholds(_cache)

        raw_s = raw.specs or {}
        cand_dict: dict[str, Any] = {
            "title": raw.title,  # necesario para mini qualifier y product_type
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

        # Fallback: extraer PN del título / description_text cuando el PDP no lo tiene.
        # Muchos listings de Amazon no incluyen maximum_pressure en specs estructuradas
        # pero sí en el título ("PN30") o en la descripción ("Full Flow PN30").
        if not cand_dict.get("pn"):
            _pn_text = (raw.title or "") + " " + (raw.raw_payload or {}).get("description_text", "")
            _pn_from_text = _pdp_pn_parse(_pn_text)
            if _pn_from_text:
                cand_dict["pn"] = _pn_from_text

        # Fallback: extraer rosca/thread del título cuando specs no lo tiene.
        # El título suele incluir "BSP", "NPT", "BSPP", etc.
        if not cand_dict.get("thread"):
            _thread_src = (
                (raw.title or "") + " " + (raw.raw_payload or {}).get("description_text", "")
            )
            _thread_src_upper = _thread_src.upper()
            for _std in ("BSPT", "BSPP", "BSP", "NPTF", "NPT"):
                if _std in _thread_src_upper:
                    cand_dict["thread"] = _std
                    break

        # Fallback: detectar material desde el título cuando SERP-only (sin PDP).
        # curl_cffi no renderiza JS y no accede al PDP; el título suele mencionar
        # el material. Necesario para que material_mismatch dispare como blocker.
        if not cand_dict.get("material"):
            _title_lower = (raw.title or "").lower()
            _TITLE_MATERIALS = [
                (
                    [
                        "stainless steel",
                        "stainless-steel",
                        "ss304",
                        "ss316",
                        "304 stainless",
                        "316 stainless",
                        "inox",
                    ],
                    "stainless_steel",
                ),
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

        # Pasar description_text al candidato para que _handle_score pueda extraer
        # color/tipo de maneta desde texto cuando no está en specs estructurados.
        if not cand_dict.get("description_text"):
            cand_dict["description_text"] = (raw.raw_payload or {}).get("description_text", "")

        if self._material_normalizer is None:
            self._material_normalizer = await MaterialNormalizer.from_db(self.session)
        breakdown = compute_scoring(
            sku_dict, cand_dict, material_normalizer=self._material_normalizer
        )
        kind = _classify_candidate(
            breakdown.score,
            breakdown.notes,
            family=sku_dict.get("family"),
            peer_threshold=peer_threshold,
            drop_threshold=drop_threshold,
        )

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

        candidate = await self._matches_repo.upsert_candidate(
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

        # ── Auto-enqueue HITL: confidence < 0.6 AND price > 1000 AED ──────
        await self._maybe_enqueue_hitl(candidate, raw)

        # ── Instrumentación match_rule_stats (best-effort) ────────────────
        try:
            from app.repositories.match_rule_stat import MatchRuleStatRepository  # noqa: PLC0415
            from app.repositories.taxonomy_profile import TaxonomyProfileRepository  # noqa: PLC0415

            stat_repo = MatchRuleStatRepository(self.session)
            tp_repo = TaxonomyProfileRepository(self.session)
            family = sku_dict.get("family") or "_default"
            tp = await tp_repo.get_by_family(family)
            await stat_repo.create(
                match_candidate_id=candidate.id,
                taxonomy_profile_id=tp.id if tp else None,
                score_breakdown=breakdown.as_dict(),
                dimensions_fired=breakdown.notes,
            )
        except Exception as _stat_exc:
            logger.warning("match_rule_stat.insert_failed", extra={"error": str(_stat_exc)[:80]})

        return candidate

    async def _maybe_enqueue_hitl(self, candidate: MatchCandidate, raw: "CandidateRaw") -> None:
        """Inserta en hitl_queue si confidence < 0.6 Y product_value > 1000 AED.

        Idempotente: no inserta si ya existe un item ``pending`` para ese match_id
        (índice parcial único en la migración). No propaga excepciones — el
        encolado HITL es best-effort y no debe romper el pipeline de matching.
        """
        try:
            await self.__maybe_enqueue_hitl_impl(candidate, raw)
        except Exception as _hitl_exc:
            logger.warning(
                "hitl_queue.enqueue_failed",
                extra={"error": str(_hitl_exc)[:120]},
            )

    async def __maybe_enqueue_hitl_impl(
        self, candidate: MatchCandidate, raw: "CandidateRaw"
    ) -> None:
        """Implementación interna — ver _maybe_enqueue_hitl.

        Lógica ampliada (mig 142 / US-SCR-04-08b):
        - ``high_value_review``: true cuando VLM grade A/B Y price > 1000 AED.
        - ``is_first_appearance``: true cuando el SKU nunca había aparecido en
          match_candidates antes de este candidato.
        - ``priority_score`` = (1 - confidence) × economic_value × (2.0 si is_first_appearance else 1.0).
        """
        from decimal import Decimal

        from app.db.models.hitl_queue import (
            HitlQueue,
            HITL_CONFIDENCE_THRESHOLD,
            HITL_VALUE_THRESHOLD_AED,
        )
        from sqlalchemy import select as _select, func as _func

        # Determinar uncertainty_score (defensivo: FakeMatchRow en tests puede no tener el atributo)
        conf = getattr(candidate, "calibrated_confidence", None)
        if conf is not None:
            uncertainty = Decimal("1") - conf
        else:
            uncertainty = Decimal("1")  # confianza desconocida → máxima incertidumbre

        if float(uncertainty) > (1.0 - HITL_CONFIDENCE_THRESHOLD):
            # Solo encolar si hay precio suficientemente alto
            price_val = raw.price_aed
            if price_val is not None and float(price_val) > HITL_VALUE_THRESHOLD_AED:
                # Comprobar si ya está en cola
                existing_stmt = _select(HitlQueue.id).where(
                    HitlQueue.match_id == candidate.id,
                    HitlQueue.status == "pending",
                )
                existing = await self.session.execute(existing_stmt)
                if existing.first() is not None:
                    return  # ya en cola

                # ── high_value_review: VLM grade A/B + price > 1000 AED ──────
                vlm_grade = (candidate.specs_jsonb or {}).get("_enhanced", {}).get("visual_verdict")
                high_value_review = (
                    vlm_grade in ("A", "B") and float(price_val) > HITL_VALUE_THRESHOLD_AED
                )

                # ── is_first_appearance: SKU nunca visto en match_candidates ──
                prior_count_stmt = _select(_func.count(MatchCandidate.id)).where(
                    MatchCandidate.product_sku == candidate.product_sku,
                    MatchCandidate.id != candidate.id,
                )
                prior_count_result = await self.session.execute(prior_count_stmt)
                prior_count = prior_count_result.scalar_one()
                is_first_appearance = prior_count == 0

                # ── priority_score con multiplicador de primera aparición ─────
                economic_value = Decimal(str(price_val))
                first_appearance_multiplier = (
                    Decimal("2.0") if is_first_appearance else Decimal("1.0")
                )
                priority = uncertainty * economic_value * first_appearance_multiplier

                hitl_item = HitlQueue(
                    match_id=candidate.id,
                    uncertainty_score=uncertainty,
                    product_value_aed=economic_value,
                    priority_score=priority,
                    status="pending",
                    high_value_review=high_value_review,
                    is_first_appearance=is_first_appearance,
                )
                self.session.add(hitl_item)
                await self.session.flush()
                logger.info(
                    "hitl_queue.auto_enqueued",
                    extra={
                        "match_id": str(candidate.id),
                        "sku": candidate.product_sku,
                        "uncertainty": float(uncertainty),
                        "price_aed": float(price_val),
                        "priority_score": float(priority),
                        "high_value_review": high_value_review,
                        "is_first_appearance": is_first_appearance,
                    },
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
        updated = await self._matches_repo.mark_validated(candidate_id, user_id=user_id)
        assert updated is not None  # acabamos de leer el row
        updated.label = "accept"
        await self._record_human_feedback(updated, label=1, user_id=user_id)
        return updated

    async def discard_candidate(
        self, candidate_id: UUID, *, reason: str | None = None
    ) -> MatchCandidate:
        obj = await self.get_candidate(candidate_id)
        if obj.status == "validated":
            raise MatchInvalidTransitionError(obj.status, "discarded")
        updated = await self._matches_repo.mark_discarded(candidate_id, reason=reason)
        assert updated is not None
        updated.label = "reject"
        await self._record_human_feedback(updated, label=0, user_id=None)
        return updated

    async def _record_human_feedback(
        self, candidate: MatchCandidate, *, label: int, user_id: UUID | None
    ) -> None:
        """Cierra el lazo de feedback: golden_labels + human_outcome del agente."""
        from app.repositories.golden_labels import GoldenLabelRepository  # noqa: PLC0415
        from app.repositories.match_agent import MatchAgentDecisionRepository  # noqa: PLC0415

        try:
            await GoldenLabelRepository(self.session).upsert(
                sku=candidate.product_sku,
                candidate_id=candidate.id,
                label=label,
                score=candidate.score / 100.0,
                judged_by=user_id,
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "match_service._record_human_feedback.golden_labels_failed", exc_info=True
            )

        try:
            outcome = "validated" if label == 1 else "discarded"
            await MatchAgentDecisionRepository(self.session).set_human_outcome(
                candidate.id, outcome
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "match_service._record_human_feedback.human_outcome_failed", exc_info=True
            )

        await self.session.flush()

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
        precio_mercado: Decimal | None = best_candidate.price_aed if best_candidate else None
        costo_compra: Decimal | None = last_lot.unit_cost_aed if last_lot else None

        margen_aed: Decimal | None = None
        margen_pct: Decimal | None = None
        if precio_mercado is not None and costo_compra is not None:
            margen_aed = (precio_mercado - costo_compra).quantize(Decimal("0.0001"))
            if precio_mercado != 0:
                margen_pct = (margen_aed / precio_mercado * 100).quantize(Decimal("0.0001"))

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

        # Cargar el calibrador conformal activo (None en fase bootstrap).
        conformal: Any | None = None
        try:
            from app.repositories.golden_labels import (  # noqa: PLC0415
                CalibratorVersionRepository,
                GoldenLabelRepository,
            )
            from app.services.matching.calibrator import ConformalWrapper  # noqa: PLC0415
            from app.services.matching.calibrator_storage import CalibratorStorage  # noqa: PLC0415

            storage = CalibratorStorage(CalibratorVersionRepository(self.session))
            base_cal = await storage.load_active()
            if base_cal is not None:
                labels = await GoldenLabelRepository(self.session).list_for_training()
                if len(labels) >= 200:
                    wrapper = ConformalWrapper(calibrator=base_cal, method="venn_abers")
                    wrapper.fit(
                        [float(row.score) for row in labels],
                        [int(row.label) for row in labels],
                    )
                    conformal = wrapper
        except Exception:  # noqa: BLE001
            logger.warning("refresh_candidates_enhanced.conformal_load_failed", exc_info=True)
            conformal = None

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
                if llm.get("end_connection_gender"):
                    current_specs["connection_gender"] = llm["end_connection_gender"]
                if llm.get("bore_type"):
                    current_specs["bore_type"] = llm["bore_type"]
                if llm.get("seat_material"):
                    current_specs["seat_material"] = llm["seat_material"]
                if llm.get("seal_material"):
                    current_specs["seal_material"] = llm["seal_material"]
                if llm.get("alloy_code"):
                    current_specs["alloy"] = llm["alloy_code"]

            # Actualizar score si el pipeline lo mejoró
            if result.score != candidate.score:
                candidate.score = result.score

            populate_conformal_fields(candidate, conformal)

            candidate.specs_jsonb = current_specs
            await self.session.flush()
            await self.session.refresh(candidate)

            results.append((candidate, result))

        # Ordenar por score DESC
        results.sort(key=lambda pair: pair[0].score, reverse=True)
        return results

    async def rematch_from_pool(
        self,
        sku: str,
        pool_candidates: list,  # list[UnmatchedOffer] — evitamos import circular
    ) -> list[MatchCandidate]:
        """Re-intenta matching de ofertas del pool contra un SKU del catálogo.

        Reconstruye un CandidateRaw desde cada UnmatchedOffer y lo pasa por
        el pipeline de scoring existente (_score_and_upsert). Las que pasen
        el umbral quedan en match_candidates; las que no, incrementan
        match_attempts en el pool.

        Returns:
            Lista de MatchCandidate que pasaron el umbral (score >= DROP_SCORE_THRESHOLD).
        """
        product = await self._products_repo.get_by_sku_for_matching(sku)
        if product is None:
            raise MatchSkuNotFoundError(sku)
        sku_dict = self._product_to_dict(product)

        if self._material_normalizer is None:
            self._material_normalizer = await MaterialNormalizer.from_db(self.session)

        matched: list[MatchCandidate] = []

        for offer in pool_candidates:
            # Reconstruir CandidateRaw desde los datos almacenados
            raw = CandidateRaw(
                source=offer.marketplace,
                external_id=offer.external_id,
                title=offer.title,
                brand=offer.brand,
                price_aed=offer.price_aed,
                delivery_text=offer.delivery_text,
                specs=dict(offer.specs_jsonb or {}),
                raw_payload={
                    "image_url": offer.image_url or "",
                    "url": offer.source_url or "",
                    "description_text": (offer.specs_jsonb or {}).get("_description_text", ""),
                },
            )

            try:
                row = await self._score_and_upsert(sku_dict, raw)
            except Exception:
                logger.warning(
                    "rematch_from_pool.score_failed",
                    extra={"offer_id": str(offer.id), "sku": sku},
                    exc_info=True,
                )
                if self._unmatched_repo is not None:
                    await self._unmatched_repo.increment_attempts(offer.id)
                continue

            if row.score < DROP_SCORE_THRESHOLD or row.kind == "unknown":
                # Sigue sin matchear — incrementar intentos y eliminar de match_candidates
                if self._unmatched_repo is not None:
                    await self._unmatched_repo.increment_attempts(offer.id)
                await self.session.delete(row)
                await self.session.flush()
            else:
                # Match exitoso — marcar en el pool
                if self._unmatched_repo is not None:
                    await self._unmatched_repo.mark_matched(offer.id)
                matched.append(row)
                logger.info(
                    "rematch_from_pool.matched",
                    extra={
                        "sku": sku,
                        "offer_id": str(offer.id),
                        "score": row.score,
                        "external_id": offer.external_id,
                    },
                )

        return matched

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
            # model hierarchy — populated when get_by_sku_for_matching() was used
            _model = getattr(product, "model", None)
            if _model is not None:
                base["model_code"] = getattr(_model, "code", None)
                base["model_connection_type"] = getattr(_model, "connection_type", None)
                base["model_thread_standard"] = getattr(_model, "thread_standard", None)
            else:
                base["model_code"] = None
                base["model_connection_type"] = None
                base["model_thread_standard"] = None
        # Alias `thread` ⇄ `connection` para que scoring lea ambos.
        if base.get("thread") is None and base.get("connection") is not None:
            base["thread"] = base["connection"]
        return base
