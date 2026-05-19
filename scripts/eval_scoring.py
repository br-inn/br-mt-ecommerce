"""Evaluación directa de las 3 reglas nuevas + diagnóstico de taxonomía."""
import asyncio
from decimal import Decimal
from app.services.matching.scoring import compute_scoring, _handle_score
from app.services.matching.taxonomy_rules import get_profile, TAXONOMY_PROFILES


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def check(label, condition, detail=""):
    icon = "✅" if condition else "❌"
    print(f"  {icon} {label}" + (f"  → {detail}" if detail else ""))


# ─── 1. HANDLE MISMATCH ─────────────────────────────────────────────────────
section("1. Handle (maneta) soft blocker")

# SKU sin specs de maneta → no debe emitir nota
notes = _handle_score({}, {"handle_color": "red"})
check("SKU sin handle_color: sin nota", notes == [], str(notes))

# SKU con handle pero candidato sin datos → sin nota
notes = _handle_score({"handle_color": "black"}, {})
check("Candidato sin handle data: sin nota", notes == [], str(notes))

# Match de color → sin nota
notes = _handle_score({"handle_color": "red"}, {"handle_color": "red"})
check("Mismo color (red==red): sin nota", notes == [], str(notes))

# Color distinto → handle_mismatch
notes = _handle_score({"handle_color": "red"}, {"handle_color": "blue"})
check("Color distinto (red vs blue): nota handle_mismatch", "handle_mismatch" in notes, str(notes))

# Material distinto → handle_mismatch
notes = _handle_score({"handle_material": "steel"}, {"handle_material": "aluminum"})
check("Material distinto (steel vs aluminum): nota handle_mismatch", "handle_mismatch" in notes, str(notes))

# Pool-relativa: scoring completo con handle en specs
sku = {
    "sku": "TEST001", "family": "ball_valve", "material": "brass",
    "dn": "15", "pn": "16", "connection": "BSP",
    "specs": {"handle_color": "red"},
}
cand_ok = {"title": "Brass Ball Valve 1/2\"", "material": "brass", "dn": "15", "pn": "16",
           "connection": "BSP", "specs": {"handle_color": "red"}}
cand_bad = {"title": "Brass Ball Valve 1/2\" Blue", "material": "brass", "dn": "15", "pn": "16",
            "connection": "BSP", "specs": {"handle_color": "blue"}}

bd_ok = compute_scoring(sku, cand_ok)
bd_bad = compute_scoring(sku, cand_bad)
check("Candidato handle OK: sin nota handle_mismatch", "handle_mismatch" not in bd_ok.notes, str(bd_ok.notes))
check("Candidato handle BAD: nota handle_mismatch presente", "handle_mismatch" in bd_bad.notes, str(bd_bad.notes))
check("Score no cambia por handle (sin peso propio)", bd_ok.score == bd_bad.score,
      f"ok={bd_ok.score} bad={bd_bad.score}")


# ─── 2. WAYS_MISMATCH UNIVERSAL ──────────────────────────────────────────────
section("2. ways_mismatch blocker universal en válvulas")

families_valve = ["ball_valve", "gate_valve", "globe_valve", "check_valve", "butterfly_valve"]
for fam in families_valve:
    profile = get_profile(fam)
    check(f"{fam}: ways_mismatch en hard_blockers", "ways_mismatch" in profile.hard_blockers)

# Verificar que ball_valve (FULL) también lo tiene
check("ball_valve (FULL blocker set): ways_mismatch incluido",
      "ways_mismatch" in get_profile("ball_valve").hard_blockers)

# Scoring: 2-way SKU vs 3-way candidato → ways_mismatch → kind=unknown
from app.services.matching.match_service import _classify_candidate
sku_2way = {
    "sku": "V001", "family": "ball_valve", "material": "brass",
    "dn": "15", "pn": "16", "connection": "BSP",
    "product_type": "2-way Ball Valve", "specs": {},
}
cand_3way = {
    "title": "3-Way Brass Ball Valve 1/2\" DN15 BSP",
    "material": "brass", "dn": "15", "pn": "16", "specs": {},
}
bd = compute_scoring(sku_2way, cand_3way)
kind = _classify_candidate(bd.score, bd.notes, family="ball_valve")
check("2-way SKU vs 3-way cand: nota ways_mismatch", "ways_mismatch" in bd.notes, str(bd.notes))
check("2-way SKU vs 3-way cand: kind=unknown (blocker duro)", kind == "unknown", f"kind={kind}")

# Strainer también tiene ways_mismatch en _BASE_VALVE_BLOCKERS
check("strainer: ways_mismatch en hard_blockers", "ways_mismatch" in get_profile("strainer").hard_blockers)
check("FILTROS: ways_mismatch en hard_blockers", "ways_mismatch" in get_profile("FILTROS").hard_blockers)


# ─── 3. THREAD_STANDARD DEMOTADO ─────────────────────────────────────────────
section("3. thread_standard_mismatch: nota pero NO blocker duro")

for fam in ["ball_valve", "gate_valve", "butterfly_valve", "strainer"]:
    profile = get_profile(fam)
    check(f"{fam}: thread_standard_mismatch FUERA de hard_blockers",
          "thread_standard_mismatch" not in profile.hard_blockers)

# Scoring: BSP vs NPT → nota pero candidato sigue siendo válido
sku_bsp = {
    "sku": "V002", "family": "ball_valve", "material": "brass",
    "dn": "15", "pn": "16", "connection": "BSP",
    "specs": {},
}
cand_npt = {
    "title": "Brass Ball Valve 1/2\" NPT",
    "material": "brass", "dn": "15", "pn": "16",
    "thread": "NPT", "specs": {},
}
bd = compute_scoring(sku_bsp, cand_npt)
kind = _classify_candidate(bd.score, bd.notes, family="ball_valve")
check("BSP vs NPT: nota thread_standard_mismatch emitida", "thread_standard_mismatch" in bd.notes, str(bd.notes))
check(f"BSP vs NPT: kind≠unknown (no bloquea), kind={kind}", kind != "unknown", f"score={bd.score}")
thread_weight = next(v for k, v in bd.weights.items() if "thread" in k)
check(f"thread_standard sigue pesando en score ({float(thread_weight):.0%})", float(thread_weight) > 0)


# ─── 4. DIAGNÓSTICO TAXONOMÍA ─────────────────────────────────────────────────
section("4. Diagnóstico: familias del catálogo vs perfiles registrados")

import asyncio as _asyncio

async def check_families():
    from app.db.session import get_sessionmaker
    from sqlalchemy import text
    sm = get_sessionmaker()
    async with sm() as s:
        r = await s.execute(text("SELECT DISTINCT family, COUNT(*) FROM products WHERE family IS NOT NULL GROUP BY family ORDER BY 2 DESC"))
        rows = r.fetchall()

    print(f"\n  {'Familia en DB':<30} {'SKUs':>5}  {'Perfil encontrado'}")
    print(f"  {'-'*60}")
    for fam, cnt in rows:
        profile_key = None
        if fam in TAXONOMY_PROFILES:
            profile_key = fam
        elif fam.upper() in TAXONOMY_PROFILES:
            profile_key = fam.upper()

        if profile_key:
            icon = "✅"
            pname = profile_key
        else:
            icon = "⚠️ "
            pname = "_default (fallback)"

        print(f"  {icon} {fam:<30} {cnt:>5}  → {pname}")

_asyncio.run(check_families())

print("\n")
