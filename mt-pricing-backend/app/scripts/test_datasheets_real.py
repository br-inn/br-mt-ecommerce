"""One-shot real test for FR-DOC-01 — runs preview + apply against the
11 fixture PDFs in /fixtures and reports DB/Storage/audit results.

Usage:
    docker exec mt-backend python /app/scripts/test_datasheets_real.py
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterable
from uuid import uuid4

from sqlalchemy import select, text

from app.db.engine import get_sessionmaker
from app.db.models.product import Product
from app.db.models.user import User
from app.services.importer_datasheets.importer_service import (
    ImporterDatasheetsService,
    ProductLookupProtocol,
)
from app.services.products.product_service import ProductService


FIXTURES_DIR = "/fixtures"
PDF_FILES = [
    "MTFT_87.pdf",
    "MTFT_647.pdf",
    "MTFT_4091.pdf",
    "MTFT_4295.pdf",
    "MTFT_5114.pdf",
    "MTFT_0912.pdf",
    "MTCE_87.pdf",
    "MTCE_647.pdf",
    "MTCE_5114.pdf",
    "MTMAN_4151.pdf",
    "MTMAN_5114.pdf",
]


class PrefixLikeResolver:
    """Resolver custom: cada suffix se asocia a TODOS los SKUs cuyo
    `sku` empieza por ese suffix (BR PIM convention).

    Devuelve un mapa ``suffix -> primer SKU encontrado`` (ProductLookupProtocol)
    pero también expone ``resolve_skus_full`` con la lista completa, ya que
    el applier procesa una sola asociación por filename y el N:M lo maneja
    el `attach_datasheet` (sku_list JSONB).

    Para que el flujo cree N:M correctamente, devolvemos un diff por cada
    SKU prefijado — eso requiere modificar el resolver. Como atajo para
    este test, devolvemos un mapa expandido donde cada suffix es una clave
    que el service procesa.
    """

    def __init__(self, session) -> None:  # noqa: ANN001
        self.session = session

    async def resolve_skus(self, suffixes: Iterable[str]) -> dict[str, str]:
        """Devuelve mapa ``suffix -> primer SKU`` (compat con Protocol).

        Solo se usa para detectar orphans. La asociación N:M la hace el
        post-processing en main().
        """
        out: dict[str, str] = {}
        for suf in suffixes:
            r = await self.session.execute(
                text("SELECT sku FROM public.products WHERE sku LIKE :p ORDER BY sku LIMIT 1"),
                {"p": f"{suf}%"},
            )
            row = r.fetchone()
            if row is not None:
                out[suf] = row[0]
        return out

    async def resolve_skus_full(self, suffixes: Iterable[str]) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for suf in suffixes:
            r = await self.session.execute(
                text("SELECT sku FROM public.products WHERE sku LIKE :p ORDER BY sku"),
                {"p": f"{suf}%"},
            )
            out[suf] = [row[0] for row in r.fetchall()]
        return out


async def get_or_make_actor(session) -> User:  # noqa: ANN001
    """Devuelve un User válido para el actor del run — el primero activo."""
    r = await session.execute(
        select(User).where(User.is_active.is_(True)).limit(1)
    )
    user = r.scalar_one_or_none()
    if user is None:
        raise RuntimeError("No hay usuarios activos para usar como actor del test")
    return user


async def main() -> None:
    Session = get_sessionmaker()
    async with Session() as session:
        resolver = PrefixLikeResolver(session)
        actor = await get_or_make_actor(session)
        print(f"[actor] {actor.email} ({actor.id})")

        # --- 1. Preview ---
        files: list[tuple[str, bytes]] = []
        for fname in PDF_FILES:
            path = os.path.join(FIXTURES_DIR, fname)
            if not os.path.exists(path):
                print(f"[skip] {fname} no existe en {FIXTURES_DIR}")
                continue
            with open(path, "rb") as fh:
                files.append((fname, fh.read()))
        print(f"[load] {len(files)} PDFs cargados")

        service = ImporterDatasheetsService(session, sku_resolver=resolver)
        state = await service.preview(files=files, actor=actor)

        print()
        print("=== PREVIEW ===")
        print(f"run_id: {state.run_id}")
        print(f"status: {state.status}")
        print(f"summary: {state.summary}")
        print(f"orphan_files ({len(state.orphan_files)}): {state.orphan_files}")
        print(f"orphan_skus ({len(state.orphan_skus)}): {state.orphan_skus[:20]}")
        print(f"diffs ({len(state.diffs)}):")
        for d in state.diffs:
            specs_summary = {k: v for k, v in d.specs.to_dict().items() if v is not None}
            print(
                f"  {d.filename:24s} kind={d.kind:14s} sku={d.product_sku:14s} "
                f"path={d.storage_path}  specs={specs_summary}"
            )

        # --- 2. Expand diffs N:M (cada PDF a TODOS los SKUs prefijados) ---
        suffix_to_skus = await resolver.resolve_skus_full(state.orphan_skus + [
            s for d in state.diffs
            for s in [d.product_sku.split('-V-')[-1] if 'MT-V-' in d.product_sku else None]
            if s
        ])
        # Recompute: extract suffix from each diff's filename and expand SKUs
        from app.services.importer_datasheets.spec_parser import parse_datasheet_filename

        expanded_diffs = []
        seen_storage_paths_for_test = set()
        for d in state.diffs:
            seen_storage_paths_for_test.add(d.storage_path)

        # Re-build expanded diffs from per_file
        from app.services.importer_datasheets.applier import DatasheetDiff
        for fname, payload in files:
            parsed = parse_datasheet_filename(fname)
            if not parsed.ok:
                continue
            for suffix in parsed.sku_suffixes:
                r = await session.execute(
                    text("SELECT sku FROM public.products WHERE sku LIKE :p ORDER BY sku"),
                    {"p": f"{suffix}%"},
                )
                skus_for_suffix = [row[0] for row in r.fetchall()]
                # Match the existing storage_path that preview built
                existing_diff = next(
                    (x for x in state.diffs if x.filename == fname),
                    None,
                )
                if existing_diff is None:
                    continue
                for sku in skus_for_suffix:
                    expanded_diffs.append(DatasheetDiff(
                        row_index=0,
                        filename=fname,
                        kind=parsed.kind,
                        product_sku=sku,
                        storage_path=existing_diff.storage_path,
                        specs=existing_diff.specs,
                        file_size_bytes=len(payload),
                    ))

        # Replace the state's diffs with expanded ones for full N:M coverage.
        state.diffs = expanded_diffs
        print()
        print(f"[expand] {len(expanded_diffs)} diffs (N:M) — un row por (PDF, SKU)")

        # --- 3. Apply ---
        product_service = ProductService(session)
        try:
            state2 = await service.apply(state.run_id, actor, product_service=product_service)
        except Exception as exc:
            print(f"[apply ERROR] {type(exc).__name__}: {exc}")
            raise
        await session.commit()

        print()
        print("=== APPLY ===")
        print(f"status: {state2.status}")
        print(f"summary: {state2.summary}")
        if state2.apply_result:
            print(f"apply_result: {state2.apply_result.to_dict()}")

        # --- 4. Verify ---
        print()
        print("=== VERIFICATION ===")
        r = await session.execute(text("SELECT COUNT(*) FROM public.product_datasheets"))
        print(f"product_datasheets rows: {r.scalar()}")
        r = await session.execute(text("""
            SELECT kind, COUNT(*), SUM(jsonb_array_length(sku_list)) AS total_assoc
            FROM public.product_datasheets GROUP BY kind ORDER BY 1
        """))
        for row in r.fetchall():
            print(f"  kind={row[0]:14s} files={row[1]} sku_associations={row[2]}")

        r = await session.execute(text("""
            SELECT original_filename, kind, jsonb_array_length(sku_list) AS skus, file_size_bytes
            FROM public.product_datasheets ORDER BY original_filename
        """))
        print()
        print("Per-file breakdown:")
        for row in r.fetchall():
            print(f"  {row[0]:24s} kind={row[1]:14s} skus={row[2]:>4d}  size={row[3]:>8d}B")

        r = await session.execute(text("""
            SELECT action, COUNT(*) FROM public.audit_events
            WHERE action LIKE 'product.datasheet%'
            GROUP BY action ORDER BY 1
        """))
        print()
        print("Audit events:")
        for row in r.fetchall():
            print(f"  {row[0]:40s} {row[1]}")

        # Storage check
        from app.core.supabase import get_supabase_admin
        sb = get_supabase_admin()
        try:
            objs = sb.storage.from_("product-datasheets").list()
            print()
            print(f"Storage bucket product-datasheets: {len(objs)} objects")
            for obj in objs[:15]:
                name = obj.get("name") if isinstance(obj, dict) else getattr(obj, "name", "?")
                size = (
                    (obj.get("metadata") or {}).get("size") if isinstance(obj, dict)
                    else getattr(getattr(obj, "metadata", None), "size", "?")
                )
                print(f"  {name}  size={size}")
        except Exception as exc:
            print(f"[storage check err] {exc}")


if __name__ == "__main__":
    asyncio.run(main())
