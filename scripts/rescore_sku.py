"""Rescora los candidatos existentes en DB sin hacer fetch nuevo."""
import asyncio, sys

SKU = sys.argv[1] if len(sys.argv) > 1 else "4097015"

async def run():
    from app.db.session import get_sessionmaker
    from sqlalchemy import text, update
    from app.db.models.match_candidate import MatchCandidate
    from sqlalchemy import select
    from app.services.matching.scoring import compute_scoring
    from app.services.matching.match_service import _classify_candidate, DROP_SCORE_THRESHOLD
    from app.services.matching.material_normalizer import STATIC_NORMALIZER

    sm = get_sessionmaker()
    async with sm() as s:
        # SKU dict
        sku_row = (await s.execute(text("""
            SELECT p.sku, p.family, p.material, p.dn, p.pn, p.connection,
                   p.erp_name, p.type, p.specs, p.brand,
                   pm.code, pm.thread_standard, pm.connection_type
            FROM products p LEFT JOIN product_models pm ON p.model_id=pm.id
            WHERE p.sku=:sku
        """), {"sku": SKU})).fetchone()

        sku_dict = {
            "sku": sku_row[0], "family": sku_row[1], "material": sku_row[2],
            "dn": sku_row[3], "pn": sku_row[4], "connection": sku_row[5],
            "erp_name": sku_row[6], "product_type": sku_row[7], "brand": sku_row[9],
            "specs": sku_row[8] or {},
            "model_code": sku_row[10], "model_thread_standard": sku_row[11],
            "model_connection_type": sku_row[12],
        }
        if not sku_dict.get("thread") and sku_dict.get("connection"):
            sku_dict["thread"] = sku_dict["connection"]

        # Candidatos
        result = await s.execute(
            select(MatchCandidate).where(MatchCandidate.product_sku == SKU)
        )
        candidates = result.scalars().all()

        deleted = 0
        updated = 0
        print(f"\nRescorando {len(candidates)} candidatos para {SKU}...\n")

        for mc in candidates:
            jsonb = dict(mc.specs_jsonb or {})
            # Extraer PN y thread del título + description si no están en jsonb
            from app.services.matching.match_service import _pdp_pn_parse
            desc_text = jsonb.get("description_text") or jsonb.get("_description_text") or ""
            title_str = mc.title or ""
            full_text = title_str + " " + desc_text

            stored_pn = jsonb.get("pn")
            if not stored_pn:
                stored_pn = _pdp_pn_parse(full_text) or None

            stored_thread = jsonb.get("thread") or jsonb.get("thread_type")
            if not stored_thread:
                full_upper = full_text.upper()
                for _std in ("BSPT", "BSPP", "BSP", "NPTF", "NPT"):
                    if _std in full_upper:
                        stored_thread = _std
                        break

            cand_dict = {
                "title": mc.title, "brand": mc.brand,
                "material": jsonb.get("material") or jsonb.get("material_type"),
                "dn": jsonb.get("dn") or jsonb.get("size"),
                "pn": stored_pn,
                "thread": stored_thread,
                "delivery_text": mc.delivery_text,
                "specs": {k: v for k, v in jsonb.items() if not k.startswith("_")},
            }

            bd = compute_scoring(sku_dict, cand_dict, material_normalizer=STATIC_NORMALIZER)
            kind = _classify_candidate(bd.score, bd.notes, family=sku_dict.get("family"))

            if bd.score < DROP_SCORE_THRESHOLD or kind == "unknown":
                print(f"  🗑️  DELETE  score={bd.score}  kind={kind}  notes={bd.notes}")
                print(f"       {(mc.title or '')[:72]}")
                await s.delete(mc)
                deleted += 1
            else:
                old_score, old_kind = mc.score, mc.kind
                mc.score = bd.score
                mc.kind = kind
                jsonb["_scoring"] = bd.as_dict()
                # Persistir valores extraídos por fallback para que el frontend los vea
                for _key, _val in (("pn", stored_pn), ("thread", stored_thread)):
                    if _val is not None:
                        jsonb.setdefault(_key, _val)
                mc.specs_jsonb = jsonb
                updated += 1
                marker = "↑" if bd.score > old_score else ("↓" if bd.score < old_score else "=")
                kind_marker = f"  KIND: {old_kind}→{kind}" if old_kind != kind else ""
                print(f"  ✅ KEEP   score={old_score}{marker}{bd.score}  kind={kind}{kind_marker}  notes={bd.notes}")
                print(f"       {(mc.title or '')[:72]}")

        # ── Pool logic: maneta ──────────────────────────────────────────────
        # Si hay candidatos sin handle_mismatch → eliminar los que tienen mismatch.
        # Si no hay ninguno sin mismatch → mantenerlos (con confidence reducida).
        surviving = [mc for mc in candidates if mc not in []]  # reconstruir lista vivos
        # Reclasificar después del loop (algunos ya fueron eliminados con s.delete)
        handle_mismatch_rows = []
        ok_count = 0
        for mc in candidates:
            notes_now = (mc.specs_jsonb or {}).get("_scoring", {}).get("notes", [])
            if "handle_mismatch" in notes_now:
                handle_mismatch_rows.append(mc)
            else:
                ok_count += 1

        if handle_mismatch_rows:
            if ok_count > 0:
                for mc in handle_mismatch_rows:
                    print(f"  🗑️  POOL-DELETE handle_mismatch (ok_count={ok_count})  score={mc.score}")
                    print(f"       {(mc.title or '')[:72]}")
                    await s.delete(mc)
                    deleted += 1
                    updated -= 1  # ya no es un "actualizado"
            else:
                for mc in handle_mismatch_rows:
                    mc.price_confidence_score = max(0, (mc.price_confidence_score or 0) - 15)
                print(f"  ⚠️  POOL-KEEP {len(handle_mismatch_rows)} handle_mismatch (no hay otros candidatos), -15 confidence")

        await s.flush()
        await s.commit()
        print(f"\nResultado: {updated} actualizados, {deleted} eliminados")

asyncio.run(run())
