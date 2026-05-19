"""run_poc.py — runner CLI del POC 500 SKUs × 3 marketplaces.

Uso::

    # Con stubs (CI-safe, sin credenciales externas):
    python scripts/poc/run_poc.py --use-stubs --n-skus 50

    # Todos los marketplaces, 500 SKUs, stubs:
    python scripts/poc/run_poc.py --use-stubs --n-skus 500 --marketplace all

    # Sólo Amazon, real (requiere scraper live activo):
    python scripts/poc/run_poc.py --marketplace amazon --n-skus 100

    # Generar reporte G4 al final:
    python scripts/poc/run_poc.py --use-stubs --n-skus 500 --report

Salidas:
    docs/rnd/poc-results-YYYY-MM-DD.json
    docs/rnd/poc-results-YYYY-MM-DD.csv
    docs/rnd/g4-decision-report.md  (si --report)

El runner es async end-to-end. Cada SKU se procesa de forma secuencial
(no paralela) para no saturar las APIs reales. Con --use-stubs es rápido
(<1 s para 500 SKUs en local).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_sessionmaker
from app.db.models.product import Product
from app.services.matching.ports import FetcherPort, Query
from app.services.matching.query_builder import QueryBuilder
from app.services.matching.scoring import compute_scoring
from scripts.poc.metrics_collector import (
    CandidateRecord,
    MetricsCollector,
    PocMetrics,
)

logger = logging.getLogger("poc.runner")

DOCS_RND = Path(__file__).resolve().parents[3] / "docs" / "rnd"

# ---------------------------------------------------------------------------
# Fetcher factory
# ---------------------------------------------------------------------------

def _build_fetchers(marketplace: str, *, use_stubs: bool) -> list[FetcherPort]:
    """Construye la lista de fetchers según marketplace y modo."""
    fetchers: list[FetcherPort] = []

    want_amazon = marketplace in ("all", "amazon")
    want_noon = marketplace in ("all", "noon")
    want_shopify = marketplace in ("all", "shopify")

    if want_amazon:
        if use_stubs:
            from app.services.matching.adapters.amazon_uae_stub import (
                AmazonUaeStubFetcher,
            )
            fetchers.append(AmazonUaeStubFetcher())
        else:
            try:
                from app.services.matching.adapters.curl_cffi_amazon_uae import (
                    CurlCffiAmazonUaeFetcher,
                )
                fetchers.append(CurlCffiAmazonUaeFetcher())
            except Exception as exc:
                logger.warning("Real Amazon fetcher unavailable (%s) — falling back to stub", exc)
                from app.services.matching.adapters.amazon_uae_stub import (
                    AmazonUaeStubFetcher,
                )
                fetchers.append(AmazonUaeStubFetcher())

    if want_noon:
        if use_stubs:
            from app.services.matching.adapters.noon_uae_stub import (
                NoonUaeStubFetcher,
            )
            fetchers.append(NoonUaeStubFetcher())
        else:
            try:
                from app.services.matching.adapters.playwright_noon_uae import (
                    PlaywrightNoonUaeFetcher,
                )
                fetchers.append(PlaywrightNoonUaeFetcher())
            except Exception as exc:
                logger.warning("Real Noon fetcher unavailable (%s) — falling back to stub", exc)
                from app.services.matching.adapters.noon_uae_stub import (
                    NoonUaeStubFetcher,
                )
                fetchers.append(NoonUaeStubFetcher())

    if want_shopify:
        # Shopify: sólo stub disponible (Fase 1.5+ para real).
        try:
            from scripts.poc.shopify_stub import ShopifyUaeStubFetcher
            fetchers.append(ShopifyUaeStubFetcher())
        except ImportError as exc:
            logger.warning("Shopify stub unavailable (%s) — skipping shopify marketplace", exc)

    return fetchers


# ---------------------------------------------------------------------------
# SKU loader
# ---------------------------------------------------------------------------

async def _load_skus(session: AsyncSession, n: int) -> list[str]:
    """Carga hasta N SKUs activos del catálogo."""
    stmt = (
        select(Product.sku)
        .where(
            Product.deleted_at.is_(None),
            Product.lifecycle_status == "active",
        )
        .order_by(Product.sku.asc())
        .limit(n)
    )
    result = await session.execute(stmt)
    skus = [row[0] for row in result.all()]
    if not skus:
        # Fallback: cualquier producto (incluso sin lifecycle_status).
        stmt2 = (
            select(Product.sku)
            .where(Product.deleted_at.is_(None))
            .order_by(Product.sku.asc())
            .limit(n)
        )
        result2 = await session.execute(stmt2)
        skus = [row[0] for row in result2.all()]
    return skus


def _synthetic_skus(n: int) -> list[str]:
    """Genera SKUs sintéticos para cuando no hay DB (modo --no-db)."""
    return [f"MTBR{str(i).zfill(7)}" for i in range(1, n + 1)]


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

async def run_poc(
    *,
    n_skus: int,
    marketplace: str,
    use_stubs: bool,
    no_db: bool,
    report: bool,
    verbose: bool,
) -> PocMetrics:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    logger.info(
        "POC START — n_skus=%d marketplace=%s use_stubs=%s no_db=%s",
        n_skus, marketplace, use_stubs, no_db,
    )

    fetchers = _build_fetchers(marketplace, use_stubs=use_stubs)
    query_builder = QueryBuilder()
    collector = MetricsCollector(n_skus_total=n_skus, use_stubs=use_stubs)

    t0 = time.monotonic()

    if no_db:
        skus = _synthetic_skus(n_skus)
        logger.info("no-db mode: usando %d SKUs sintéticos", len(skus))
        sku_dicts = [
            {
                "sku": s,
                "family": "ball_valve",
                "material": "brass",
                "pn": "PN16",
                "connection": "BSP",
                "brand": None,
                "specs": {},
            }
            for s in skus
        ]
    else:
        async with get_sessionmaker()() as session:
            skus = await _load_skus(session, n_skus)

        if not skus:
            logger.warning("No SKUs en DB — usando sintéticos como fallback")
            skus = _synthetic_skus(n_skus)
            sku_dicts = [
                {"sku": s, "family": "ball_valve", "material": "brass",
                 "pn": "PN16", "connection": "BSP", "brand": None, "specs": {}}
                for s in skus
            ]
        else:
            # Cargamos los dicts mínimos para el scoring.
            async with get_sessionmaker()() as session:
                stmt = select(Product).where(Product.sku.in_(skus))
                result = await session.execute(stmt)
                products = list(result.scalars().all())
            sku_by_sku = {p.sku: p for p in products}
            sku_dicts = []
            for s in skus:
                p = sku_by_sku.get(s)
                if p is None:
                    sku_dicts.append({"sku": s, "specs": {}})
                else:
                    sku_dicts.append({
                        "sku": p.sku,
                        "family": p.family,
                        "subfamily": p.subfamily,
                        "material": p.material,
                        "dn": p.dn,
                        "pn": p.pn,
                        "connection": p.connection,
                        "brand": p.brand,
                        "specs": dict(p.specs or {}),
                    })

    logger.info("Procesando %d SKUs contra %d fetchers", len(sku_dicts), len(fetchers))

    n_ok = 0
    n_err = 0
    for idx, sku_dict in enumerate(sku_dicts):
        sku = str(sku_dict.get("sku", f"UNKNOWN_{idx}"))
        queries = query_builder.build_for_sku(sku_dict)

        for fetcher in fetchers:
            channel_queries = [q for q in queries if q.source == fetcher.channel]
            if not channel_queries:
                # El query builder sólo produce queries para canales conocidos;
                # para shopify_uae generamos una query genérica.
                channel_queries = [
                    Query(
                        text=str(sku_dict.get("family") or sku),
                        source=fetcher.channel,
                    )
                ]
            primary = channel_queries[0]
            try:
                candidates_raw = await fetcher.fetch(primary, sku=sku)
            except Exception as exc:
                msg = f"fetch error sku={sku} channel={fetcher.channel}: {exc}"
                logger.warning(msg)
                collector.add_error(msg)
                n_err += 1
                continue

            for raw in candidates_raw:
                cand_dict: dict = {
                    "brand": raw.brand,
                    "price_aed": raw.price_aed,
                    "delivery_text": raw.delivery_text,
                    "specs": dict(raw.specs),
                }
                for k, v in (raw.specs or {}).items():
                    cand_dict.setdefault(k, v)

                try:
                    breakdown = compute_scoring(sku_dict, cand_dict)
                    collector.add(
                        CandidateRecord(
                            sku=sku,
                            channel=raw.source,
                            external_id=raw.external_id,
                            kind=_classify(breakdown.score, breakdown.notes),
                            score=breakdown.score,
                            label=None,  # Sin labels reales en POC stub
                            calibrated_confidence=None,
                        )
                    )
                except Exception as exc:
                    msg = f"scoring error sku={sku} channel={fetcher.channel} ext={raw.external_id}: {exc}"
                    logger.warning(msg)
                    collector.add_error(msg)
                    n_err += 1
        n_ok += 1
        if verbose and idx % 50 == 0:
            logger.debug("Progreso: %d/%d SKUs procesados", idx + 1, len(sku_dicts))

    elapsed = time.monotonic() - t0
    collector.set_elapsed(elapsed)
    logger.info(
        "POC FIN — %d SKUs OK, %d errores, elapsed=%.1fs",
        n_ok, n_err, elapsed,
    )

    metrics = collector.compute()

    # Exportar resultados.
    today = date.today().isoformat()
    DOCS_RND.mkdir(parents=True, exist_ok=True)
    json_path = DOCS_RND / f"poc-results-{today}.json"
    csv_path = DOCS_RND / f"poc-results-{today}.csv"
    collector.export_json(metrics, json_path)
    collector.export_csv(metrics, csv_path)
    logger.info("Resultados: %s | %s", json_path, csv_path)

    # Resumen en consola.
    _print_summary(metrics)

    if report:
        from scripts.poc.g4_report import generate_g4_report
        report_path = DOCS_RND / "g4-decision-report.md"
        generate_g4_report(metrics, report_path)
        logger.info("Reporte G4: %s", report_path)

    return metrics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _classify(score: int, notes: list[str]) -> str:
    blocking = {"pn_below_sku_requirement", "thread_mismatch", "material_mismatch"}
    if blocking.intersection(notes):
        return "unknown"
    if score >= 70:
        return "peer"
    if score >= 40:
        return "drop"
    return "unknown"


def _print_summary(metrics: PocMetrics) -> None:
    agg = metrics.aggregate()
    print("\n" + "=" * 60)
    print(f"  POC RESULTADOS  —  {metrics.run_date}")
    print("=" * 60)
    print(f"  SKUs procesados : {metrics.n_skus_total}")
    print(f"  Elapsed         : {metrics.elapsed_seconds:.1f}s")
    print(f"  Stubs           : {metrics.use_stubs}")
    print(f"  Errores         : {len(metrics.errors)}")
    print()
    print(f"  {'Marketplace':<18} {'Cands':>6} {'FP%':>6} {'FN%':>6} {'ECE%':>6} {'Cob%':>6} {'AC':>4}")
    print(f"  {'-'*18} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*4}")
    for m in metrics.marketplaces:
        ac_ok = "OK" if m.all_ac_pass() else "FAIL"
        print(
            f"  {m.marketplace:<18} {m.n_candidates:>6} "
            f"{m.fp_rate * 100:>5.1f}% {m.fn_rate * 100:>5.1f}% "
            f"{m.ece * 100:>5.1f}% {m.cobertura * 100:>5.1f}% {ac_ok:>4}"
        )
    ac_ok = "OK" if agg.all_ac_pass() else "FAIL"
    print(f"  {'ALL':<18} {agg.n_candidates:>6} "
          f"{agg.fp_rate * 100:>5.1f}% {agg.fn_rate * 100:>5.1f}% "
          f"{agg.ece * 100:>5.1f}% {agg.cobertura * 100:>5.1f}% {ac_ok:>4}")
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="POC 500 SKUs × 3 marketplaces — matching pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--n-skus", type=int, default=500,
        help="Número de SKUs a procesar",
    )
    parser.add_argument(
        "--marketplace",
        choices=["all", "amazon", "noon", "shopify"],
        default="all",
        help="Marketplace(s) a testear",
    )
    parser.add_argument(
        "--use-stubs", action="store_true",
        help="Usar adapters stub (sin credenciales externas; CI-safe)",
    )
    parser.add_argument(
        "--no-db", action="store_true",
        help="No conectar a DB — usar SKUs sintéticos (útil en entornos sin Postgres)",
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Generar reporte G4 en docs/rnd/g4-decision-report.md",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Logging DEBUG",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    _metrics = asyncio.run(
        run_poc(
            n_skus=args.n_skus,
            marketplace=args.marketplace,
            use_stubs=args.use_stubs,
            no_db=args.no_db,
            report=args.report,
            verbose=args.verbose,
        )
    )
    # Exit non-zero so CI detects broken runs.
    _n_err = len(_metrics.errors)
    _error_rate = _n_err / max(_metrics.n_skus_total, 1)
    if _error_rate >= 0.20:
        logger.error("Error rate %.0f%% ≥ 20%% threshold (%d errors) — exit 1", _error_rate * 100, _n_err)
        sys.exit(1)
