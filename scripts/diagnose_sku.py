"""Diagnóstico completo de candidatos para un SKU — recomputa scoring con reglas actuales."""
import asyncio, json, sys

SKU = sys.argv[1] if len(sys.argv) > 1 else "4097015"

async def run():
    from app.db.session import get_sessionmaker
    from sqlalchemy import text
    from app.services.matching.scoring import compute_scoring, _extract_ways, _normalize_dn
    from app.services.matching.match_service import _classify_candidate
    from app.services.matching.taxonomy_rules import get_profile
    from app.services.matching.material_normalizer import STATIC_NORMALIZER

    sm = get_sessionmaker()
    async with sm() as s:
        # ── Datos del SKU ────────────────────────────────────────────────────
        sku_row = await s.execute(text("""
            SELECT p.sku, p.family, p.material, p.dn, p.pn, p.connection,
                   p.erp_name, p.type, p.specs, p.brand,
                   pm.code as model_code, pm.thread_standard, pm.connection_type
            FROM products p
            LEFT JOIN product_models pm ON p.model_id = pm.id
            WHERE p.sku = :sku
        """), {"sku": SKU})
        sku_data = sku_row.fetchone()
        if not sku_data:
            print(f"SKU {SKU} no encontrado")
            return

        print(f"\n{'='*70}")
        print(f"  SKU: {sku_data[0]}")
        print(f"  family: {sku_data[1]}  →  perfil: {type(get_profile(sku_data[1])).__name__} [{', '.join(list(get_profile(sku_data[1]).hard_blockers)[:4])}...]")
        print(f"  material: {sku_data[2]}  dn: {sku_data[3]}  pn: {sku_data[4]}  connection: {sku_data[5]}")
        print(f"  erp_name: {sku_data[6]}  type: {sku_data[7]}")
        print(f"  model_code: {sku_data[10]}  thread_std: {sku_data[11]}  conn_type: {sku_data[12]}")
        specs = sku_data[8] or {}
        ways_in_type = _extract_ways(str(sku_data[7] or ""))
        print(f"  ways extraídas del type: {ways_in_type}")
        print(f"{'='*70}\n")

        # Construir sku_dict equivalente al de match_service
        sku_dict = {
            "sku": sku_data[0], "family": sku_data[1], "material": sku_data[2],
            "dn": sku_data[3], "pn": sku_data[4], "connection": sku_data[5],
            "erp_name": sku_data[6], "product_type": sku_data[7], "brand": sku_data[9],
            "specs": specs,
            "model_code": sku_data[10], "model_thread_standard": sku_data[11],
            "model_connection_type": sku_data[12],
        }
        if sku_dict.get("thread") is None and sku_dict.get("connection"):
            sku_dict["thread"] = sku_dict["connection"]

        # ── Candidatos ───────────────────────────────────────────────────────
        cands = await s.execute(text("""
            SELECT mc.id, mc.title, mc.score, mc.kind, mc.price_aed,
                   mc.price_confidence_score, mc.specs_jsonb, mc.status, mc.channel
            FROM match_candidates mc
            WHERE mc.product_sku = :sku
            ORDER BY mc.score DESC
        """), {"sku": SKU})
        rows = cands.fetchall()
        print(f"  {len(rows)} candidatos en DB (status actual)\n")

        for i, row in enumerate(rows, 1):
            jsonb = row[6] or {}
            old_scoring = jsonb.get("_scoring") or {}
            old_notes = old_scoring.get("notes", [])

            # Reconstruir cand_dict para recomputar con reglas actuales
            cand_dict = {
                "title": row[1], "brand": jsonb.get("brand"),
                "material": jsonb.get("material") or jsonb.get("material_type"),
                "dn": jsonb.get("dn") or jsonb.get("size"),
                "pn": jsonb.get("pn"),
                "thread": jsonb.get("thread") or jsonb.get("thread_type"),
                "delivery_text": jsonb.get("delivery_text"),
                "specs": {k: v for k, v in jsonb.items() if not k.startswith("_")},
            }

            # Recomputar scoring con reglas actuales
            new_bd = compute_scoring(sku_dict, cand_dict, material_normalizer=STATIC_NORMALIZER)
            new_kind = _classify_candidate(new_bd.score, new_bd.notes, family=sku_dict.get("family"))

            # Detectar discrepancias
            score_changed = abs(new_bd.score - row[2]) > 1
            kind_changed = new_kind != row[3]
            notes_changed = set(new_bd.notes) != set(old_notes)
            changed = score_changed or kind_changed or notes_changed

            status_icon = "🔴" if kind_changed and new_kind == "unknown" else ("🟡" if changed else "🟢")
            print(f"  {status_icon} [{i:>2}] score: DB={row[2]:>3}→NEW={new_bd.score:>3}  kind: DB={row[3]:<8}→NEW={new_kind:<8}  status={row[7]}")
            print(f"       title: {(row[1] or '')[:72]}")

            # Mostrar razón del cambio
            if notes_changed:
                added = set(new_bd.notes) - set(old_notes)
                removed = set(old_notes) - set(new_bd.notes)
                if added:   print(f"       NOTAS NUEVAS: {list(added)}")
                if removed: print(f"       NOTAS QUITADAS: {list(removed)}")

            # Mostrar material del candidato (para diagnóstico)
            mat_src = jsonb.get("material") or jsonb.get("material_type") or "(no material)"
            ways_cand = _extract_ways(row[1])
            print(f"       material={mat_src}  dn={cand_dict.get('dn')}  pn={cand_dict.get('pn')}  ways_cand={ways_cand}  ch={row[8]}")

            # Alerta si debería ser unknown pero no lo es
            if new_kind != "unknown" and ("dn_mismatch" in new_bd.notes or "material_mismatch" in new_bd.notes):
                profile = get_profile(sku_dict.get("family"))
                blocking = profile.hard_blockers.intersection(new_bd.notes)
                if blocking:
                    print(f"       ⚠️  DEBERIA SER UNKNOWN — blockers activos: {blocking}")
            print()

asyncio.run(run())
