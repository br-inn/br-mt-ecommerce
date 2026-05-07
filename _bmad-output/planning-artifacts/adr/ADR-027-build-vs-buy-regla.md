# ADR-027: Build vs Buy — regla operativa con threshold por tamaño de catálogo + POC paralelo

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), Comercial Online MT, Gerente Comercial, TI MT
- Related: ADR-012, ADR-015 (build custom Fase 1)

## Contexto

ADR-015 acepta "build custom" para el conjunto del producto (PIM + pricing + workflow). Para el **subsistema de comparación específicamente**, ADR-012 lo trata como research workstream y descarta explícitamente "comprar herramienta dedicada (Trax, Bossa, ProductIQ)" por ser nicho industrial UAE.

La recomendación externa al sponsor (2026-05-06) **matiza esa decisión** introduciendo una **regla operativa con threshold** por tamaño de catálogo + un POC con números reales para gatear build-vs-buy:

- Catálogo < 10 000 SKUs + competidores estables → **comprar** (Centric / Intelligence Node / DataWeave) sale más barato.
- Catálogo > 50 000 SKUs + alta especificación técnica → **construir** da mejor precisión a largo plazo (puedes codificar reglas del dominio).
- MT actual a 224 SKUs con visión a crecer → **arrancar con build mínimo viable + pedir demos a 2-3 vendors comerciales en paralelo** (no son mutuamente excluyentes). Si la demo comercial supera al build mínimo en accuracy + costo total al cierre del POC → **pivotar**.

Adicionalmente, la recomendación define un POC concreto que reemplaza el plan de calibración de §5.3 / §8.2 del spike:

- 500 SKUs representativos (no 50 mínimos).
- 3 marketplaces simultáneos (Amazon UAE + Noon UAE + uno de Tradeling / Mistermart / Ubuy / fabricante).
- Métricas reales (precisión + recall, no proxies).
- Demos comerciales en paralelo con el mismo set.
- Decision gate post-POC.

## Decisión

1. **Regla operativa documentada**:
   - **< 10 000 SKUs + competidores estables** → comprar.
   - **> 50 000 SKUs + alta especificación técnica** → construir.
   - **Caso MT actual (224 SKUs, visión a crecer)** → build mínimo + demos comerciales en paralelo; pivot si la demo comercial gana en números reales.
2. **POC obligatorio pre-G2 / G4** con:
   - 500 SKUs estratificados por familia / marca / DN bin.
   - 3 marketplaces simultáneos.
   - Métricas reales (precisión, recall, ECE, coste tecnológico, tiempo humano por par).
   - Demos comerciales arrancadas en S0 (proceso comercial + NDAs largos): mínimo Intelligence Node + Skuuudle; ideal añadir Centric o DataWeave.
3. **Decision gate G2 (S2-S3)**: comparar accuracy del build mínimo vs primeras devoluciones de demos. Si una vendor entrega ≥ build con menor coste total a 12 meses → pivot a buy + integration; si build mínimo gana → continuar con build hasta G4.
4. **Decision gate G4 (S6)**: cierre Fase 1b. Build-vs-buy final con números completos. Pivot tardío posible.

## Alternativas evaluadas

- **Build-only desde el día 1 (status quo ADR-012)**: pierde la opción de pivot; no hay datos para refutar build si demo comercial sale ganadora. Descartado.
- **Buy-only**: nicho industrial PVF en UAE no está cubierto por suites genéricas (probado en ADR-012). Descartado.
- **POC sólo con build, sin demos**: pierde la opción de pivot. Descartado.
- **Demos sin POC propio**: pierdes baseline para comparar. Descartado.

## Consecuencias positivas

- Decisión basada en evidencia, no en convicción.
- Optionality preservada: el build no impide pivot a buy y viceversa.
- Coste de demos comerciales: bajo (la mayoría ofrecen trial / piloto gratis o low-cost para ganar el contrato).
- Skuuudle ofrece trials con catálogos reales explícitamente; aprovechar.

## Consecuencias negativas / riesgos

- POC más caro y más largo que plan original (500 SKUs + 3 marketplaces vs 50 SKUs + 1).
- Demos comerciales requieren NDA + process; Comercial / Gerente deben dedicar tiempo en S0.
- Riesgo de "parálisis por análisis" si las demos prometen pero no entregan en tiempo. Mitigación: gate G2 con datos parciales OK; el build no se detiene esperando demos.
- Pivot tardío (G4) implica desestimar trabajo del build → riesgo motivacional. Mitigación: documentar que el build mínimo era un POC instrumentado, no producto final.

## Cuándo revisar

- **G2 (S2-S3)**: primer chequeo build-vs-buy con datos parciales.
- **G4 (S6)**: cierre Fase 1b.
- Anualmente (post-Fase 2): si catálogo cruza 10k → reconsiderar buy; si cruza 50k → ratificar build.
- Cuando aparezca un vendor con cobertura PVF UAE explícita (hoy ninguno la tiene documentada).
