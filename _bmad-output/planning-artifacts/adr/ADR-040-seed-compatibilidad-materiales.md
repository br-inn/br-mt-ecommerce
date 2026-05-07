# ADR-040: `Compatibilidad de Materiales MT V4` como seed inicial del Knowledge Graph PVF

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT, Ontólogo PVF (TBD)
- Supersedes: —
- Relacionados: ADR-038 (roadmap), ADR-039 (ontología), ADR-041 (CDC)

## Contexto

El cliente entregó como input curado el archivo `Documentos referencia de articulos/Copia de Compatibilidad de Materiales MT V4.xlsx`:

- **657 filas** × **14 columnas**.
- Matriz `Producto × Temperatura × Material`.
- Materiales cubiertos (12): `Latón CW604N`, `Latón CW617N`, `Latón CW602N`, `Acero al Carbono`, `Fundición GG25`, `Fundición GGG40`, `Fundición GGG50`, `SS304 / A304L`, `SS316 / A316L`, `EPDM`, `NBR Buna`, `FKM/FPM Vitón`, `PTFE Teflón`, `RPTFE+15% FG`, `RPTFE+15% Graphite`.
- Cada fila tiene un link a `tecno-products.com` como referencia externa.
- Datos curados internamente por MT a lo largo de su operación.

Es el activo más valioso para los edges `HECHO_DE` y `COMPATIBLE_CON` del knowledge graph (ADR-039). Sin él, esos edges habría que re-derivarlos por LLM extraction sobre fichas técnicas — caro y menos preciso que el dato curado del cliente.

## Decisión

**El archivo `Copia de Compatibilidad de Materiales MT V4.xlsx` actúa como seed inicial directo de los edges `HECHO_DE` y `COMPATIBLE_CON` cuando se construya el knowledge graph en Fase 2. Linked a `tecno-products.com` se conserva como propiedad del edge `external_reference_url` para auditoría.**

### Mapping del seed

| Columna del Excel | Destino en el grafo |
|-------------------|---------------------|
| `producto_sku` o `producto_name` | nodo `Producto` (match por sku canónico o lookup) |
| Material col-wise (12 materiales) | edge `HECHO_DE` con propiedad `material_codigo` |
| Compatibilidad celda (booleano + temp) | edge `COMPATIBLE_CON` con propiedad `temp_max` (`°C`) y `permitido` (boolean) |
| `link_tecno_products` | propiedad `external_reference_url` del edge |
| Fila completa | propiedad `seed_source = 'compat_materiales_v4'` y `seed_loaded_at` |

### ETL conceptual (pseudocódigo)

```python
# loader_seed_compat_materiales.py (Fase 2)
import pandas as pd
from neo4j import GraphDatabase

df = pd.read_excel("Copia de Compatibilidad de Materiales MT V4.xlsx")
material_cols = ["CW604N", "CW617N", "CW602N", "AceroAlCarbono",
                 "GG25", "GGG40", "GGG50", "A304L", "A316L",
                 "EPDM", "NBR", "Vitón", "Teflón", "RPTFE_FG", "RPTFE_Graphite"]

with driver.session() as s:
    for _, row in df.iterrows():
        sku = row["producto_sku"]
        for mat in material_cols:
            cell = row[mat]
            if pd.isna(cell): continue
            temp_max = parse_temp(cell)              # "120°C OK" → 120
            permitido = parse_permitido(cell)         # "OK" / "NO" / "—"
            s.run("""
              MERGE (p:Producto {sku: $sku})
              MERGE (m:Material {codigo: $mat})
              MERGE (p)-[r:HECHO_DE]->(m)
                ON CREATE SET r.seed_source = 'compat_materiales_v4',
                              r.seed_loaded_at = datetime(),
                              r.external_reference_url = $url
              MERGE (m)-[c:COMPATIBLE_CON {temp_max: $temp_max}]->(p)
                ON CREATE SET c.permitido = $permitido,
                              c.seed_source = 'compat_materiales_v4'
            """, sku=sku, mat=mat, url=row["link_tecno_products"],
                 temp_max=temp_max, permitido=permitido)
```

### Política de overwrite

- Datos de Fase 2 derivados por LLM extraction (fichas técnicas) NO sobreescriben el seed sin revisión humana.
- Conflicto se resuelve creando edge paralelo con `seed_source = 'llm_extraction'` y flag `needs_human_review = true`.

## Alternativas evaluadas

- **Ignorar el archivo y empezar de cero** con LLM extraction sobre fichas: rechazada. Desperdicia input curado del cliente; calidad LLM sobre PDFs en fase temprana es 70-85 %, vs 95 %+ del archivo curado.
- **Mantener como tabla relacional en Postgres sin grafo**: rechazada. Pierde la potencia de queries Cypher tipo "dame productos hechos de un material compatible con material del input a temp ≥ T y norma X" sin múltiples joins recursivos. Apropiado solo Fase 1 (cuando no hay grafo).
- **Convertir el archivo en CSV manualmente y entregar al ontólogo para que diseñe el seed**: rechazada por timing. La estructura es estable y el mapping directo; el ontólogo refina (no re-construye) en Fase 2.

## Consecuencias positivas

- **657 edges válidos desde el día 1 del grafo**, sin necesidad de extraction.
- **Coste cero de seed**: el archivo ya existe.
- **Trazabilidad** vía `external_reference_url` y `seed_source`.
- **Validación cruzada**: si LLM extraction sobre ficha técnica contradice al seed, alerta para curación humana.

## Consecuencias negativas / riesgos

- **Excel puede tener errores / encoding inconsistente**: mitigación — pre-validar con script ETL antes del load; reporte de filas no cargadas.
- **Mapping `producto_sku ↔ nodo Producto`** depende de la calidad de SKUs en PIM: mitigación — ejecutar ETL después del seed PIM y reportar SKUs huérfanos.
- **Datos curados pueden envejecer**: mitigación — política de revisión anual; CDC desde el Excel (si se mantiene como archivo vivo) o promover a fuente DB en Fase 3.
- **Materiales no estandarizados** en columnas (encoding, abreviaturas): mitigación — tabla `materiales_alias` Postgres con sinónimos.

## Cuándo revisar

- **Pre-Fase 2 S1**: ontólogo PVF revisa el mapping y los códigos de material para canonicalización.
- **Tras carga inicial**: reporte de cobertura — qué % de SKUs del PIM tienen al menos un edge `HECHO_DE` cargado del seed.
- **Cierre Fase 2**: evaluar si el archivo se mantiene como Excel o se promueve a tabla DB con UI de edición (mantenibilidad).
