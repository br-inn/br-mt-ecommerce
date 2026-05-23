"""One-shot real test for FR-DOC-01 — runs preview + 1-row-per-PDF apply
against the 11 fixture PDFs in /fixtures and reports DB/Storage/audit results.

Usage:
    docker exec mt-backend python /app/app/scripts/test_datasheets_real.py
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

from sqlalchemy import select, text

from app.core.config import settings
from app.core.supabase import get_supabase_admin
from app.db.engine import get_sessionmaker
from app.db.models.datasheet_import_run import ProductDatasheet
from app.db.models.user import User
from app.repositories.audit import AuditRepository
from app.services.importer_datasheets.pdf_extractor import (
    PDFExtractionError,
    extract_text_from_pdf,
)
from app.services.importer_datasheets.spec_parser import (
    parse_datasheet_filename,
    parse_specs_from_text,
)
from app.services.storage import upload_bytes


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


async def main() -> None:
    started = datetime.now(tz=timezone.utc)
    bucket = settings.SUPABASE_STORAGE_BUCKET_DATASHEETS
    Session = get_sessionmaker()

    files: list[tuple[str, bytes]] = []
    for fname in PDF_FILES:
        path = os.path.join(FIXTURES_DIR, fname)
        if not os.path.exists(path):
            print(f"[skip] {fname} no existe en {FIXTURES_DIR}")
            continue
        with open(path, "rb") as fh:
            files.append((fname, fh.read()))
    print(f"[load] {len(files)} PDFs cargados, total {sum(len(p) for _, p in files):,} bytes")

    async with Session() as session:
        actor = (
            await session.execute(select(User).where(User.is_active.is_(True)).limit(1))
        ).scalar_one_or_none()
        if actor is None:
            raise RuntimeError("No hay usuario activo")
        actor_id = actor.id
        actor_email = actor.email
    print(f"[actor] {actor_email}")

    per_file: list[dict] = []
    orphan_files: list[dict] = []
    for fname, payload in files:
        parsed = parse_datasheet_filename(fname)
        if not parsed.ok:
            orphan_files.append({"filename": fname, "reason": parsed.error})
            continue
        try:
            text_content = extract_text_from_pdf(payload)
        except PDFExtractionError as exc:
            orphan_files.append({"filename": fname, "reason": exc.code})
            continue
        specs = parse_specs_from_text(text_content)
        per_file.append(
            {
                "filename": fname,
                "payload": payload,
                "kind": parsed.kind,
                "suffixes": parsed.sku_suffixes,
                "specs": specs,
                "size": len(payload),
            }
        )

    async with Session() as session:
        for entry in per_file:
            all_skus: list[str] = []
            for suf in entry["suffixes"]:
                r = await session.execute(
                    text("SELECT sku FROM public.products WHERE sku LIKE :p ORDER BY sku"),
                    {"p": f"{suf}%"},
                )
                all_skus.extend(row[0] for row in r.fetchall())
            entry["resolved_skus"] = sorted(set(all_skus))

    print()
    print("=== PREVIEW ===")
    print(f"matched files: {len(per_file)}, orphan files: {len(orphan_files)}")
    for e in per_file:
        specs_summary = {k: v for k, v in e["specs"].to_dict().items() if v is not None}
        print(
            f"  {e['filename']:24s} kind={e['kind']:14s} skus={len(e['resolved_skus']):>4d}  "
            f"size={e['size']:>8,d}B  specs={specs_summary}"
        )
    if orphan_files:
        print(f"orphans: {orphan_files}")

    matchable = [e for e in per_file if e["resolved_skus"]]
    print(f"\nfiles with >=1 resolved SKU: {len(matchable)}")
    if not matchable:
        print("[abort] no hay matches")
        return

    print()
    print("=== STORAGE UPLOAD ===")
    sb = get_supabase_admin()
    upload_results = []
    for e in matchable:
        object_path = e["filename"]

        def _do(p=object_path, body=e["payload"]) -> None:
            upload_bytes(p, body, content_type="application/pdf", bucket=bucket, upsert=True)

        try:
            await asyncio.to_thread(_do)
            upload_results.append({"filename": e["filename"], "ok": True})
            print(f"  OK {object_path}")
        except Exception as exc:  # noqa: BLE001
            upload_results.append({"filename": e["filename"], "ok": False, "err": str(exc)})
            print(f"  FAIL {object_path}: {exc}")

    uploaded = sum(1 for r in upload_results if r["ok"])
    print(f"uploaded: {uploaded}/{len(matchable)}")

    print()
    print("=== DB INSERT (1 row per PDF) ===")
    async with Session() as session:
        audit = AuditRepository(session)
        for e in matchable:
            stmt = select(ProductDatasheet).where(
                ProductDatasheet.storage_path == f"{bucket}/{e['filename']}"
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing is not None:
                merged = sorted(set(existing.sku_list or []) | set(e["resolved_skus"]))
                existing.sku_list = merged
                await session.flush()
                action = "product.datasheet.updated"
            else:
                ds = ProductDatasheet(
                    kind=e["kind"],
                    storage_path=f"{bucket}/{e['filename']}",
                    original_filename=e["filename"],
                    file_size_bytes=e["size"],
                    sku_list=e["resolved_skus"],
                    specs_extracted=e["specs"].to_dict(),
                    uploaded_by=actor_id,
                )
                session.add(ds)
                await session.flush()
                action = "product.datasheet.attached"
            await audit.record(
                entity_type="product_datasheet",
                entity_id=e["filename"],
                action=action,
                actor_id=actor_id,
                actor_email=actor_email,
                after={
                    "filename": e["filename"],
                    "kind": e["kind"],
                    "sku_list_size": len(e["resolved_skus"]),
                    "first_sku": e["resolved_skus"][0] if e["resolved_skus"] else None,
                    "size_bytes": e["size"],
                },
            )
            print(f"  OK {e['filename']:24s} -> {len(e['resolved_skus'])} SKUs ({action})")
        await session.commit()

    print()
    print("=== VERIFICATION ===")
    async with Session() as session:
        r = await session.execute(text("SELECT COUNT(*) FROM public.product_datasheets"))
        print(f"product_datasheets rows: {r.scalar()}")
        r = await session.execute(
            text("""
            SELECT kind, COUNT(*) AS files,
                   SUM(jsonb_array_length(sku_list)) AS total_assoc,
                   SUM(file_size_bytes) AS total_bytes
            FROM public.product_datasheets GROUP BY kind ORDER BY 1
        """)
        )
        for row in r.fetchall():
            print(f"  kind={row[0]:14s} files={row[1]} sku_associations={row[2]} bytes={row[3]:,}")

        r = await session.execute(
            text("""
            SELECT original_filename, kind, jsonb_array_length(sku_list) AS skus,
                   file_size_bytes, specs_extracted
            FROM public.product_datasheets ORDER BY original_filename
        """)
        )
        print()
        print("Per-file detail:")
        for row in r.fetchall():
            specs = {k: v for k, v in row[4].items() if v} if isinstance(row[4], dict) else {}
            print(
                f"  {row[0]:24s} kind={row[1]:14s} skus={row[2]:>4d}  size={row[3]:>8,}B  specs={specs}"
            )

        r = await session.execute(
            text("""
            SELECT action, COUNT(*) FROM public.audit_events
            WHERE action LIKE 'product.datasheet%' AND event_at >= :since
            GROUP BY action ORDER BY 1
        """),
            {"since": started},
        )
        print("\nAudit events (this run):")
        for row in r.fetchall():
            print(f"  {row[0]:40s} {row[1]}")

    objs = sb.storage.from_(bucket).list()
    print(f"\nStorage bucket {bucket!r}: {len(objs)} objects")
    for obj in objs[:15]:
        name = obj.get("name") if isinstance(obj, dict) else getattr(obj, "name", "?")
        size = (obj.get("metadata") or {}).get("size") if isinstance(obj, dict) else "?"
        print(f"  {name}  size={size}")

    if objs:
        first_name = (
            objs[0].get("name") if isinstance(objs[0], dict) else getattr(objs[0], "name", None)
        )
        if first_name:
            from app.services.storage import create_signed_url

            try:
                url_info = create_signed_url(first_name, ttl_seconds=300, bucket=bucket)
                print(
                    f"\nSigned URL test ({first_name}): {url_info['signed_url'][:80]}... TTL={url_info['expires_in']}s"
                )
            except Exception as exc:
                print(f"\nSigned URL test: FAIL - {exc}")

    elapsed = (datetime.now(tz=timezone.utc) - started).total_seconds()
    print(f"\n[done] elapsed={elapsed:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
