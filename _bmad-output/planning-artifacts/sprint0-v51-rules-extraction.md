---
title: "Sprint 0 — Extracción de reglas del motor v5.1 + Golden Numbers"
status: "draft"
version: "1.0"
created: "2026-05-06"
project_name: "mt-pricing-mdm-phase1"
sprint: "S0"
gating: "decisión port-vs-rewrite del motor v5.1 antes de S4"
inputs:
  - "MT_Pricing_Run_Kit/src/pricing.py"
  - "MT_Pricing_Run_Kit/src/extractor_v51.py"
  - "MT_Pricing_Run_Kit/enrich_with_v51.py"
  - "MT_Pricing_Run_Kit/data/stock_dubai_v23_PRESENTACION_2026-05-01.xlsx"
  - "MT_Pricing_Run_Kit/data/validator_data_v4.json"
  - "MT_Pricing_Run_Kit/data/run_summary_v4.json"
  - "_bmad-output/planning-artifacts/prd-mt-pricing-mdm-phase1.md"
---

# Sprint 0 — Extracción de reglas del motor v5.1 + Golden Numbers

> Documento de entrada para la decisión port-vs-rewrite del motor de pricing v5.1, requerido como gate antes de Sprint 4 (Pricing Engine). Captura las reglas del motor actual como pseudocódigo determinista, fixtures con golden numbers extraídos del Excel calibrado por Juan Carlos, mapeo a la nueva arquitectura FastAPI + Postgres y un veredicto razonado de viabilidad de port.

---

## 0. Resumen ejecutivo

- **Total reglas extraídas:** 18 (cubre todo el grafo de decisión del motor + helpers de cálculo de costes y FX).
- **Total fixtures golden:** 15 SKUs (cobertura completa de tiers `T0_PEGLER`/`T0_ARCO`/`T0_GIACOMINI`/`T0_APOLLO`/`T0_NIBCO`/`T2_technical`/`T3_functional`/`T4_product_name`/`T5_fallback`/`NONE`, grupos `G1`/`G2`, esquemas FBA/FBM/B2B, alertas críticas y casos de margen negativo).
- **Veredicto port-vs-rewrite:** **Port mostly + rewrite parcial** — la lógica matemática del motor (`pricing.py`) es determinista, sin dependencias VBA crudas (las macros del Excel sólo refrescan FX y se replican como service); los costes desglosados que el motor consume vienen de la sheet `INVOICE ENRIQUECIDA v5` ya pre-calculada por Juan Carlos. **Rewrite obligatorio** sólo para: (a) la fuente de verdad de costes (de Excel a tabla `costs`), (b) la inferencia % real / refit dinámico de costes operativos (Postgres function), y (c) la carga del master maestro (de `mt_excel_loader.py` a importer + tabla `costs`).
- **Reglas críticas / riesgosas a portar:**
  1. **`regla_pvp_min_excel_master`** — depende del PVP_MIN golden del Excel. Riesgo: si el porting se hace sin tabla `costs.breakdown` JSONB con todos los componentes, perdemos auditoría de Juan Carlos.
  2. **`regla_recalculo_costes_dinamico`** — `compute_costs_from_master()` infiere los % reales por SKU dividiendo AED/ud por PVP de lanzamiento. Si el Excel cambia formato o el `pvp_lanzamiento_aed` está mal, se infieren % imposibles. Hay que reescribir esto como `pricing_recalc_costs(price_proposal, sku_id)` con validación.
  3. **`regla_premium_velocidad`** — única regla nueva en v5.1 cuyo input depende del extractor competitivo (`delivery_origin`, `delivery_days_*`); si el comparador R&D cambia el shape del candidato, esta regla rompe silenciosamente. Riesgo medio-alto, mitigable con contract test de fixture.

---

## 1. Contexto técnico relevante

### 1.1. Arquitectura actual del motor v5.1

```
validator_data_v4.json  ───┐
                            ├─► enrich_with_v51.py  ─► output enriquecido (.json + HTML)
stock_dubai_v23.xlsx ──────┘     │
                                 ├─ load_master_costs() (mt_excel_loader.py)
                                 ├─ apply_pricing_v5_1() (pricing.py)
                                 │     ├─ load_overrides()
                                 │     ├─ compute_pvp_min(coste, weight, grupo, master_data)
                                 │     ├─ analyze_candidates(candidates)
                                 │     ├─ apply_aggressive_policy(market, pvp_min, ...)
                                 │     ├─ compute_costs_from_master(pvp, master_data)
                                 │     └─ calc_margin_pct(pvp, total_costes)
                                 └─ parse_delivery_estimate() (extractor_competitive.py)
```

- `pricing.py` (582 líneas) es el corazón. **Estado**: limpio, tipado, comentado en español, sin side effects salvo `load_overrides()` (lee `data/pvp_overrides.json`) y `OVERRIDES_FILE` (Path).
- El motor consume: `ref` (datos del SKU), `candidates` (Amazon UAE scrape), `master_sku_data` (Excel maestro). Devuelve un dict con `pvp_aed`, `pvp_eur`, `pvp_min`, `total_costes`, `rule_applied`, `formula`, `margin_pct`, `breakdown`, `alerts`, `delivery_advantage_days`, `canal_recomendado`, etc.
- `enrich_with_v51.py` añade flags `has_critical_alerts`, `has_warnings`, `has_velocity_premium` (heurística: `rule_applied.startswith('premium_velocidad')`).

### 1.2. Tipo de cambio EUR/AED y dependencias VBA del Excel

El Excel `stock_dubai_v23_PRESENTACION_2026-05-01.xlsx` tiene 22 sheets, de las cuales sólo dos se consumen como entrada del motor:

- `INVOICE ENRIQUECIDA v5` (303 filas, 66 columnas): master de SKUs con costes desglosados, PVP_MIN viable, FBA fee real, referral, IVA, PPC, otros, envío FC, storage. El motor lee esta sheet vía `mt_excel_loader.load_master_costs()`.
- `⚙️ Tarifas FBA & FBM` (87 filas, 7 columnas): tabla de FBA fees por banda de peso, usada como **fallback** cuando el SKU no está en el Master. El motor v5.1 ya tiene los valores hard-coded en `config.FBA_FEE_*`.

**Macros VBA encontradas:**
- Sheet `⚙️ Macro VBA`: contiene un módulo VBA cuya única función operativa es **refrescar la celda `B2` de `Tarifas FBA & FBM`** con el FX EUR/AED del día (4.29 al 2026-05-01) — vista en headers como `[2]💱 TIPO DE CAMBIO EUR/AED — Se actualiz...`.
- **TODO de port:** sustituir esa macro por un job que llame a una API de FX (openexchangerates / CBUAE) y persista en tabla `fx_rates` con `effective_from`, `source`. Trivial, no bloquea el port.
- **No hay otra macro VBA** que afecte cálculos del motor — todas las fórmulas que el motor consume son fórmulas Excel evaluadas (data_only=True) y leídas como valores escalares por openpyxl.

### 1.3. Parámetros globales del motor (config.py)

| Parámetro | Default | Uso |
|-----------|---------|-----|
| `EUR_TO_AED` | 4.29 | Conversión `aed_to_eur` |
| `LOGISTICA_PCT` | 0.05 | Fallback PVP_MIN |
| `VAT_PCT` | 0.05 | Fallback PVP_MIN |
| `REFERRAL_PCT` | 0.13 | Fallback PVP_MIN |
| `BANCOS_PCT` | 0.015 | Fallback PVP_MIN |
| `DEVOLUCIONES_PCT` | 0.04 | Fallback PVP_MIN |
| `FBA_FEE_SMALL/MEDIUM/HEAVY` | 8.0 / 14.0 / 35.0 | Fallback |
| `WEIGHT_SMALL_KG / WEIGHT_MEDIUM_KG` | 0.5 / 2.0 | Bandas de peso |
| `MATCH_HIGH_THRESHOLD / MATCH_LOW_THRESHOLD` | 80 / 60 | Score de matching |
| `AGG_MATCH_PCT_OF_MEDIAN` | 0.98 | Política agresiva |
| `AGG_MIN_MARGIN_OVER_PVP_MIN` | 1.05 | Floor sobre PVP_MIN |
| `AGG_NO_MATCH_MULT` | 1.15 | Sin match |
| `MAX_PCT_OVER_MEDIAN` | 1.20 | Cap superior |
| `G2_MULTIPLIERS` | `{default:2.5, stainless:2.8, cast_iron:3.0}` | Sin match en G2 |
| `DELIVERY_PREMIUM_HIGH_DAYS / _MED_DAYS` | 7 / 3 | Premium velocidad |
| `DELIVERY_PREMIUM_HIGH_PCT / _MED_PCT` | 1.15 / 1.05 | Premium velocidad |
| `MT_DELIVERY_DAYS` | 2 | Velocidad MT desde Dubái |
| `PRICING_POLICY` | 'aggressive' | Modo activo |

---

## 2. Tarea 1 — Extracción de reglas (pseudocódigo en español)

> Cada regla incluye: nombre canónico, inputs, pseudocódigo, outputs, origen (archivo:funcion:lineas) y notas.

---

### 2.1. `regla_aed_to_eur` — conversión moneda

- **Inputs:** `aed: float`, `config.EUR_TO_AED` (default 4.29).
- **Outputs:** `pvp_eur: float (round 2)`.
- **Origen:** `src/pricing.py:71-72` (`aed_to_eur`).
- **Pseudocódigo:**
```
funcion aed_to_eur(aed):
    fx <- config.EUR_TO_AED, default 4.29
    devolver redondear(aed / fx, 2)
```
- **Notas:** Ningún manejo de FX as-of, ni cache. En la nueva arquitectura debe reemplazarse por un lookup en `fx_rates` con stamping `as-of` por línea de precio.

---

### 2.2. `regla_calcular_mediana` — mediana competitiva

- **Inputs:** `prices: list[float]` (precios AED de candidatos Amazon UAE).
- **Outputs:** `median: float (round 2) | None`.
- **Origen:** `src/pricing.py:75-79`.
- **Pseudocódigo:**
```
funcion calculate_median(prices):
    valid <- [p para p en prices si p > 0]
    si len(valid) == 0: devolver None
    devolver redondear(median_estadistica(valid), 2)
```
- **Notas:** Ignora 0 y None. No descarta outliers (ej. 3.000 AED en candidato vs 30 AED real).

---

### 2.3. `regla_calcular_margen_pct` — margen sobre PVP

- **Inputs:** `pvp: float`, `total_costes: float`.
- **Outputs:** `margin_pct: float (round 4)` — fracción decimal (`0.4225` = 42.25%).
- **Origen:** `src/pricing.py:82-86` (`calc_margin_pct`).
- **Pseudocódigo:**
```
funcion calc_margin_pct(pvp, total_costes):
    si pvp <= 0 o total_costes es None:
        devolver 0
    devolver redondear((pvp - total_costes) / pvp, 4)
```
- **Notas:** Margen sobre PVP (no sobre coste). Convención del Excel maestro de Juan Carlos.

---

### 2.4. `regla_recalculo_costes_dinamico` — refit de costes operativos para PVP arbitrario

- **Inputs:** `pvp: float` (nuevo precio propuesto), `master_sku_data: dict` (Excel maestro: `pvp_lanzamiento_aed`, `coste_aed_ud`, `arancel_aed_ud`, `referral_aed_ud`, `iva_aed_ud`, `ppc_aed_ud`, `otros_aed_ud`, `fba_fee_aed_ud`, `envio_fc_aed_ud`, `storage_aed_mes_ud`).
- **Outputs:** `dict` con `coste_base_aed`, `arancel_aed`, `referral_aed`, `iva_aed`, `ppc_aed`, `otros_aed`, `fba_fee_aed`, `envio_fc_aed`, `storage_aed`, `operativos_aed`, `total_costes_aed`, `pcts: {referral_pct, iva_pct, ppc_pct, otros_pct}`.
- **Origen:** `src/pricing.py:89-143` (`compute_costs_from_master`).
- **Pseudocódigo:**
```
funcion compute_costs_from_master(pvp, master):
    pvp_ref       <- master.pvp_lanzamiento_aed o 1
    coste_base    <- master.coste_aed_ud o 0
    arancel       <- master.arancel_aed_ud o 0

    # Inferir % reales operativos sobre el PVP de lanzamiento original
    pcts <- {}
    para cada (k_aed, k_pct) en [
        ('referral_aed_ud','referral_pct'),
        ('iva_aed_ud','iva_pct'),
        ('ppc_aed_ud','ppc_pct'),
        ('otros_aed_ud','otros_pct')
    ]:
        valor_aed <- master[k_aed]
        si valor_aed != None y pvp_ref:
            pcts[k_pct] <- valor_aed / pvp_ref

    # Costes fijos (NO escalan con PVP)
    fba       <- master.fba_fee_aed_ud o 0
    envio_fc  <- master.envio_fc_aed_ud o 0
    storage   <- master.storage_aed_mes_ud o 0

    # Recalcular operativos sobre el PVP NUEVO
    referral_aed <- pvp * pcts.referral_pct
    iva_aed      <- pvp * pcts.iva_pct
    ppc_aed      <- pvp * pcts.ppc_pct
    otros_aed    <- pvp * pcts.otros_pct

    operativos <- referral_aed + iva_aed + ppc_aed + otros_aed + fba + envio_fc + storage
    total      <- coste_base + arancel + operativos

    devolver {
        coste_base_aed, arancel_aed, referral_aed, iva_aed, ppc_aed, otros_aed,
        fba_fee_aed: fba, envio_fc_aed: envio_fc, storage_aed: storage,
        operativos_aed: operativos, total_costes_aed: total, pcts: pcts
    }
```
- **Notas:**
  - Es la regla **más sensible** del motor. Si `pvp_lanzamiento_aed` es 0 o None, usa fallback `1`, lo que infiere % absurdos (ej. referral_pct = 8.778 → 877.8%).
  - Asume que los % calibrados en el Excel valen para CUALQUIER PVP nuevo. En la práctica, marketplaces fijan referral % por categoría — esta inferencia rompe si el Excel se carga con la celda mal.
  - **Riesgo de port:** si la importación a `costs.breakdown` JSONB no captura `pvp_lanzamiento_aed`, el refit no funciona.

---

### 2.5. `regla_fba_fee_fallback` — FBA fee por peso cuando no hay master data

- **Inputs:** `weight_kg: float | None`, `grupo: str`.
- **Outputs:** `fba_fee_aed: float`.
- **Origen:** `src/pricing.py:156-166` (`get_fba_fee_fallback`).
- **Pseudocódigo:**
```
funcion get_fba_fee_fallback(weight_kg, grupo):
    si weight_kg es None:
        # Heurística: si es G2 (industrial), asumir pesado
        si 'G2' en upper(grupo): devolver FBA_FEE_HEAVY (35.0)
        sino: devolver FBA_FEE_MEDIUM (14.0)
    si weight_kg < WEIGHT_SMALL_KG (0.5): devolver FBA_FEE_SMALL (8.0)
    si weight_kg < WEIGHT_MEDIUM_KG (2.0): devolver FBA_FEE_MEDIUM (14.0)
    devolver FBA_FEE_HEAVY (35.0)
```
- **Notas:** Sólo se invoca cuando NO hay `master_sku_data.pvp_min_viable_aed`. Las bandas son aproximadas vs Amazon UAE real (Standard/Heavy/Bulky/Special). En el Excel hay tabla detallada en `⚙️ Tarifas FBA & FBM` (TODO porting de bandas reales).

---

### 2.6. `regla_detect_g2_subtype` — clasificación material para multiplicador

- **Inputs:** `subfamilia: str`, `name: str` (nombre EN).
- **Outputs:** `subtype: 'stainless' | 'cast_iron' | 'default'`.
- **Origen:** `src/pricing.py:169-175` (`detect_g2_subtype`).
- **Pseudocódigo:**
```
funcion detect_g2_subtype(subfamilia, name):
    texto <- lower(subfamilia + " " + name)
    si cualquiera de ['inox','stainless','s.s.','ss'] en texto: devolver 'stainless'
    si cualquiera de ['fundic','cast iron','hierro fund'] en texto: devolver 'cast_iron'
    devolver 'default'
```
- **Notas:** Heurística textual. Falla con typos. En la nueva arquitectura debería migrar a `products.material` (campo gobernado: `'brass'|'stainless_steel'|'cast_iron'|...`).

---

### 2.7. `regla_pvp_min_excel_master` — PVP_MIN golden de Juan Carlos

- **Inputs:** `master_sku_data` con clave `pvp_min_viable_aed`. También extrae `total_costes_aed_ud` y todos los componentes de breakdown (`coste_aed_ud`, `arancel_aed_ud`, `referral_aed_ud`, `fba_fee_aed_ud`, `iva_aed_ud`, `ppc_aed_ud`, `otros_aed_ud`, `envio_fc_aed_ud`, `storage_aed_mes_ud`).
- **Outputs:** `{pvp_min, total_costes, breakdown, source: 'excel_master'}`.
- **Origen:** `src/pricing.py:182-213` (`compute_pvp_min`, rama 1).
- **Pseudocódigo:**
```
funcion compute_pvp_min(coste, weight, grupo, master):
    # RAMA 1 — Master golden (preferida)
    si master existe y master.pvp_min_viable_aed:
        breakdown <- {}
        para (k_excel, k_breakdown) en [
            ('coste_aed_ud','coste_aed'),
            ('arancel_aed_ud','arancel_aed'),
            ('referral_aed_ud','referral_aed'),
            ('fba_fee_aed_ud','fba_fee_aed'),
            ('iva_aed_ud','iva_aed'),
            ('ppc_aed_ud','ppc_aed'),
            ('otros_aed_ud','otros_aed'),
            ('envio_fc_aed_ud','envio_fc_aed'),
            ('storage_aed_mes_ud','storage_aed_mes')
        ]:
            si master[k_excel] != None:
                breakdown[k_breakdown] <- redondear(master[k_excel], 4)
        devolver {
            pvp_min: redondear(master.pvp_min_viable_aed, 2),
            total_costes: redondear(master.total_costes_aed_ud, 2) o None,
            breakdown: breakdown,
            source: 'excel_master'
        }
    # RAMA 2 — fallback fórmula global → ver regla_pvp_min_formula_global
    ...
```
- **Notas:**
  - Esta es la regla que evita re-derivar costes operativos aproximados — confía en lo que Juan Carlos calibra en Excel (PPC real per-SKU, storage real, FBA fee real por peso, etc.).
  - Si master existe pero `pvp_min_viable_aed` es 0 o None, cae a fallback global.

---

### 2.8. `regla_pvp_min_formula_global` — fallback paramétrico

- **Inputs:** `coste: float`, `weight: float | None`, `grupo: str`, `config.{LOGISTICA_PCT, VAT_PCT, REFERRAL_PCT, BANCOS_PCT, DEVOLUCIONES_PCT, FBA_FEE_*}`.
- **Outputs:** `{pvp_min, total_costes, breakdown, source: 'formula_global' | 'error'}`.
- **Origen:** `src/pricing.py:215-251` (`compute_pvp_min`, rama 2).
- **Pseudocódigo:**
```
funcion compute_pvp_min(coste, weight, grupo, master=None):
    si NO master.pvp_min_viable_aed:
        si coste <= 0:
            devolver {pvp_min: 0, source: 'error', error: 'Coste invalido'}

        fba_fee   <- get_fba_fee_fallback(weight, grupo)
        logistica <- coste * LOGISTICA_PCT (0.05)
        numerador <- coste + logistica + fba_fee

        pct_sobre_venta <- VAT_PCT + REFERRAL_PCT + BANCOS_PCT + DEVOLUCIONES_PCT
                        # = 0.05 + 0.13 + 0.015 + 0.04 = 0.235

        si pct_sobre_venta >= 1.0:
            devolver {error: '%s suman ≥100%'}

        pvp_min <- numerador / (1 - pct_sobre_venta)
                # PVP_MIN tal que cubre coste + logistica + FBA + (VAT+ref+bancos+devol)*PVP

        # Recalcular componentes a posteriori
        vat_aed       <- pvp_min * VAT_PCT
        referral_aed  <- pvp_min * REFERRAL_PCT
        bancos_aed    <- pvp_min * BANCOS_PCT
        devol_aed     <- pvp_min * DEVOLUCIONES_PCT
        total_costes  <- coste + logistica + fba_fee + vat_aed + referral_aed
                          + bancos_aed + devol_aed

        devolver {
            pvp_min: redondear(pvp_min, 2),
            total_costes: redondear(total_costes, 2),
            breakdown: {coste_aed, logistica_aed, fba_fee_aed,
                         vat_aed, referral_aed, bancos_aed, devoluciones_aed},
            source: 'formula_global'
        }
```
- **Notas:**
  - Sólo se ejecuta si el SKU NO está en el Master. En el corpus actual (224 SKUs) todos están en master, así que el branch sólo aplica en SKUs nuevos sin coste calibrado.
  - **Caso None coste:** retorna `error`. El motor general manda alerta `🚨 Coste inválido`.

---

### 2.9. `regla_analyze_candidates` — análisis de mercado competitivo

- **Inputs:** `candidates: list[dict]` con campos `price_aed`, `score_v2`/`score`, `delivery_days_min`, `delivery_days_max`, `delivery_origin`, `prime_eligible`.
- **Outputs:** `{median_aed, best_score, has_match, has_low_match, delivery_advantage_days, n_from_china, n_from_uae, n_prime, n_total}`.
- **Origen:** `src/pricing.py:258-302` (`analyze_candidates`).
- **Pseudocódigo:**
```
funcion analyze_candidates(candidates):
    median       <- calculate_median([c.price_aed para c en candidates])
    best_score   <- max(c.score_v2 o c.score o 0 para c en candidates)
    has_match    <- best_score >= 80 (MATCH_HIGH_THRESHOLD)
    has_low_match<- 60 <= best_score < 80

    # Ventaja de entrega (días que MT entrega ANTES que el competidor)
    mt_days <- 2 (MT_DELIVERY_DAYS)
    advantages <- []
    n_from_china = n_from_uae = n_prime = 0

    para c en candidates:
        si c.delivery_days_min y c.delivery_days_max:
            comp_avg <- (c.delivery_days_min + c.delivery_days_max) / 2
            advantages.append(comp_avg - mt_days)

        origin <- upper(c.delivery_origin)
        si origin en ['CN','CHINA']: n_from_china += 1
        sino si origin en ['UAE','AE']: n_from_uae += 1
        si c.prime_eligible: n_prime += 1

    delivery_advantage <- promedio(advantages) si advantages no vacio sino None

    devolver {median_aed, best_score, has_match, has_low_match,
              delivery_advantage_days, n_from_china, n_from_uae, n_prime, n_total}
```
- **Notas:** `delivery_advantage_days` es un número con signo: positivo = MT entrega ANTES (ventaja). Negativo = competidor más rápido.

---

### 2.10. `regla_premium_velocidad` — premium por ventaja de entrega

- **Inputs:** `market.delivery_advantage_days`, `market.median_aed`, `market.has_match` o `market.has_low_match`, `pvp_min`, `config.{DELIVERY_PREMIUM_HIGH_DAYS=7, DELIVERY_PREMIUM_HIGH_PCT=1.15, DELIVERY_PREMIUM_MED_DAYS=3, DELIVERY_PREMIUM_MED_PCT=1.05, AGG_MIN_MARGIN_OVER_PVP_MIN=1.05}`.
- **Outputs:** `{pvp_target, rule: 'premium_velocidad_alta' | 'premium_velocidad_media', formula, delivery_premium_applied: True}`.
- **Origen:** `src/pricing.py:309-341` (`apply_aggressive_policy`, ramas 1-2).
- **Pseudocódigo:**
```
funcion apply_aggressive_policy(market, pvp_min, grupo, subf, name, coste):
    delivery_adv <- market.delivery_advantage_days
    median       <- market.median_aed

    # RAMA 1 — Premium velocidad ALTA (≥7 días ventaja)
    si median y (has_match o has_low_match) y delivery_adv != None:
        si delivery_adv >= 7:
            mult <- 1.15
            pvp <- max(median * 1.15, pvp_min * 1.05)
            devolver {pvp_target: pvp, rule: 'premium_velocidad_alta',
                      formula: f"mediana × 1.15 — competidores +{delivery_adv}d más lentos",
                      delivery_premium_applied: True, delivery_advantage_days: delivery_adv}

        # RAMA 2 — Premium velocidad MEDIA (3-6 días)
        si delivery_adv >= 3:
            mult <- 1.05
            pvp <- max(median * 1.05, pvp_min * 1.05)
            devolver {pvp_target: pvp, rule: 'premium_velocidad_media',
                      formula: f"mediana × 1.05 — ventaja entrega {delivery_adv}d",
                      delivery_premium_applied: True, delivery_advantage_days: delivery_adv}

    # Si no aplica premium → continuar a politica estándar
    ...
```
- **Notas:**
  - Solo se activa con `match` decente (score ≥ 60). Si NO hay candidatos o todos desconocen `delivery_days_*`, no aplica.
  - **El cap superior (`MAX_PCT_OVER_MEDIAN`) NO se aplica cuando premium velocidad es válido** — la velocidad justifica el sobreprecio (regla explícita en línea 486 de `pricing.py`).
  - `enrich_with_v51.py:70` añade `has_velocity_premium = rule_applied.startswith('premium_velocidad')` como flag derivado.

---

### 2.11. `regla_aggressive_match_high` — política agresiva con match alto

- **Inputs:** `market.has_match==True`, `market.median_aed`, `pvp_min`, `config.AGG_MATCH_PCT_OF_MEDIAN=0.98`, `config.AGG_MIN_MARGIN_OVER_PVP_MIN=1.05`.
- **Outputs:** `{pvp_target: max(mediana*0.98, pvp_min*1.05), rule: 'aggressive_match_high', formula}`.
- **Origen:** `src/pricing.py:344-352`.
- **Pseudocódigo:**
```
si has_match y median:
    pvp <- max(median * 0.98, pvp_min * 1.05)
    devolver {rule: 'aggressive_match_high',
              formula: 'max(mediana × 0.98, PVP_MIN × 1.05)'}
```
- **Notas:** Ataca la mediana con 2% por debajo, garantizando margen ≥ 5% sobre PVP_MIN.

---

### 2.12. `regla_aggressive_match_low` — match incierto (60 ≤ score < 80)

- **Inputs:** `market.has_low_match==True`, `market.median_aed`, `pvp_min`.
- **Outputs:** `{pvp_target: max(mediana*1.10, pvp_min*1.10), rule: 'aggressive_match_low', formula}`.
- **Origen:** `src/pricing.py:353-360`.
- **Pseudocódigo:**
```
si has_low_match y median:
    pvp <- max(median * 1.10, pvp_min * 1.10)
    devolver {rule: 'aggressive_match_low',
              formula: 'max(mediana × 1.10, PVP_MIN × 1.10) — match incierto'}
```
- **Notas:** Sube 10% sobre mediana (compensa incertidumbre) y exige margen ≥ 10% sobre PVP_MIN. Genera además alerta `⚠ Match calidad media`.

---

### 2.13. `regla_aggressive_g2_no_match` — sin match en industrial

- **Inputs:** `grupo contiene 'G2'`, `subfamilia`, `name`, `coste`, `pvp_min`, `config.G2_MULTIPLIERS={default:2.5, stainless:2.8, cast_iron:3.0}`, `config.AGG_NO_MATCH_MULT=1.15`.
- **Outputs:** `{pvp_target: max(coste*mult, pvp_min*1.15), rule: 'aggressive_g2_no_match_<subtype>'}`.
- **Origen:** `src/pricing.py:362-371`.
- **Pseudocódigo:**
```
si 'G2' en upper(grupo):
    subtype <- detect_g2_subtype(subfamilia, name)
    mult    <- G2_MULTIPLIERS[subtype]   # 2.5 / 2.8 / 3.0
    pvp     <- max(coste * mult, pvp_min * 1.15)
    devolver {rule: f'aggressive_g2_no_match_{subtype}',
              formula: f'max(coste × {mult}, PVP_MIN × 1.15)'}
```

---

### 2.14. `regla_aggressive_g1_no_match` — sin match en hidrosanitario

- **Inputs:** `pvp_min`, `config.AGG_NO_MATCH_MULT=1.15`.
- **Outputs:** `{pvp_target: pvp_min*1.15, rule: 'aggressive_g1_no_match'}`.
- **Origen:** `src/pricing.py:372-378`.
- **Pseudocódigo:**
```
# fallback final: G1 sin match
pvp <- pvp_min * 1.15
devolver {rule: 'aggressive_g1_no_match',
          formula: 'PVP_MIN × 1.15 — G1 sin referencia'}
```

---

### 2.15. `regla_override_manual` — override administrativo

- **Inputs:** `data/pvp_overrides.json`, `sku`, opcionalmente `hasta` (fecha ISO de validez).
- **Outputs:** `{pvp_aed, rule_applied: 'override', formula: 'OVERRIDE — <razon>'}` con alerta crítica si override está bajo PVP_MIN.
- **Origen:** `src/pricing.py:415-447` (`apply_pricing_v5_1` paso 1) + `src/pricing.py:146-153` (`load_overrides`).
- **Pseudocódigo:**
```
overrides <- load_overrides() desde data/pvp_overrides.json
si sku en overrides:
    ov <- overrides[sku]
    valido <- True
    si ov tiene 'hasta':
        valido <- (parse_iso(ov.hasta).date() >= hoy.date())
    si valido:
        pmin    <- compute_pvp_min(...)
        pvp     <- ov.pvp_aed
        alerts  <- []
        si pvp < pmin.pvp_min:
            alerts.append('🚨 OVERRIDE bajo PVP_MIN: pvp < pmin')
        devolver dict completo con rule='override', formula='OVERRIDE — <razon>'
```
- **Notas:** Si `hasta` no parsea, asume válido. Si no existe `data/pvp_overrides.json`, el override no aplica (vacío).

---

### 2.16. `regla_cap_superior_y_floor` — cap arriba y floor abajo

- **Inputs:** `pvp_target`, `median`, `pvp_min`, `config.MAX_PCT_OVER_MEDIAN=1.20`, flag `delivery_premium_applied`.
- **Outputs:** `pvp_aed_final` (post-cap, post-floor) + alerts añadidas.
- **Origen:** `src/pricing.py:484-496` (paso 5-6 de `apply_pricing_v5_1`).
- **Pseudocódigo:**
```
# Paso 5 — CAP arriba
si median y pvp > median * 1.20 y NO delivery_premium_applied:
    cap_value <- median * 1.20
    alerts.append(f'⬇ Cap aplicado: {pvp} > mediana×1.20 ({cap_value})')
    pvp <- cap_value
    cap_applied <- True

# Paso 6 — FLOOR estricto
si pvp < pvp_min:
    alerts.append(f'🚨 FLOOR forzado: target {pvp} < PVP_MIN {pvp_min}')
    pvp <- pvp_min
```
- **Notas:** Si premium velocidad activo, NO se aplica cap (regla explícita). Floor PVP_MIN siempre se respeta. Genera alertas críticas/warnings.

---

### 2.17. `regla_alertas_automaticas` — generación de alerts

- **Inputs:** `market`, `policy_result`, `pvp_min`, `pvp`, `median`, `config.MAX_PCT_OVER_MEDIAN`.
- **Outputs:** `alerts: list[str]` con prefijos `⚠` (warning) o `🚨` (critical).
- **Origen:** `src/pricing.py:476-500` (paso 4-7).
- **Pseudocódigo:**
```
alerts <- []
# Match incierto
si market.has_low_match:
    alerts.append(f'⚠ Match calidad media (score={market.best_score})')

# Mediana vs PVP_MIN — competimos pero margen ajustado
si median y pvp_min > median * 1.05:
    alerts.append(f'⚠ Mediana ({median}) bajo PVP_MIN×1.05 — margen ajustado')

# Premium velocidad activado
si policy_result.delivery_premium_applied:
    alerts.append(f'🚀 Premium velocidad — competidores +{adv}d más lentos')

# Cap (ver regla_cap_superior_y_floor)
si cap_applied: alerts.append('⬇ Cap aplicado: ...')

# Floor (CRÍTICO)
si floor_aplicado: alerts.append('🚨 FLOOR forzado: ...')

# Producto inviable
si median y pvp_min > median * MAX_PCT_OVER_MEDIAN:
    alerts.append(f'🚨 PVP_MIN > mediana × cap — producto inviable competitivamente')

# Override bajo PVP_MIN
si override y pvp < pvp_min: alerts.append('🚨 OVERRIDE bajo PVP_MIN')

# Coste inválido
si compute_pvp_min retorna error: alerts.append(f'🚨 {error_msg}')

# Flags derivados (enrich_with_v51.py:68-70)
has_critical_alerts <- cualquier alert contiene '🚨'
has_warnings        <- cualquier alert contiene '⚠'
has_velocity_premium<- rule_applied.startswith('premium_velocidad')
```

---

### 2.18. `regla_canal_recomendado_passthrough` — recomendación de canal

- **Inputs:** `master_sku_data.canal_recomendado`, `master_sku_data.estado_fba`, `master_sku_data.roi_fba`, `master_sku_data.margen_fbm`.
- **Outputs:** `canal_recomendado`, `estado_fba_excel`, `roi_fba_excel`, `margen_fbm_excel`.
- **Origen:** `src/pricing.py:531-535` (paso 8 final del return).
- **Pseudocódigo:**
```
# El motor v5.1 NO calcula canal_recomendado; lo lee del Excel maestro pre-calibrado.
return {
    ...,
    canal_recomendado:  master.canal_recomendado,    # 'FBA' | 'FBM / B2B' | 'B2B'
    estado_fba_excel:   master.estado_fba,            # texto: '✅ Rentable >35% — Margen 59.9%'
    roi_fba_excel:      master.roi_fba,
    margen_fbm_excel:   master.margen_fbm,
}
```
- **Notas:**
  - **Importante**: la lógica de cómo se decide `canal_recomendado` vive en una macro VBA / fórmula del Excel — **no se pudo extraer del Python**. **TODO de port:** decompilar la fórmula de la columna `Canal recomendado` (col 42) o re-derivarla con regla nueva en backend (e.g. `if margen_fba > 0.35 → 'FBA' elif margen_fbm > 0.30 → 'FBM' else 'B2B'`).

---

## 3. Tarea 2 — Test fixtures con golden numbers

15 fixtures completas, extraídas del Excel `INVOICE ENRIQUECIDA v5` (sheet calibrada por Juan Carlos al 2026-05-01) cruzadas con `validator_data_v4.json` (Amazon UAE scrape 2026-05-04). FX aplicado: **EUR/AED = 4.29**.

> **Nota sobre golden numbers:** los valores de `pvp_aed`, `pvp_min`, `total_costes`, `breakdown`, `margen_fba`, `roi_fba`, `canal_recomendado` y `estado_fba_excel` son los del Excel master. Los valores de `pvp_aed` propuestos por el motor v5.1 (post-policy + post-cap/floor) y las `alerts` reales **no están en `validator_data_v4.json`** porque ese JSON contiene el output del shim `apply_pricing_formula` v3, no del motor v5.1. Se anotan como _"no disponible en demo data — re-correr `enrich_with_v51.py` para obtenerlos"_ donde aplique.

```json
{
  "fixtures": [
    {
      "id": "FX01_PEGLER_T0_HIGH_MATCH",
      "descripcion": "T0_PEGLER, G1, score 64 (match medio bajo umbral), ventaja entrega negativa (MT más lento)",
      "inputs": {
        "codigo": "4222015",
        "sku_upper": "4222015",
        "familia_ficha": "4222",
        "nombre_en": "F-F  PN30 LONG NECK THREADED BALL VALVE 'CARLA' TYPE  1/2\"",
        "subfamilia": "VALV.LATÓN CARLAS+EMPOTRAR",
        "familia": "HIDROSANITARIO",
        "grupo": "G1",
        "category_amz": "Plumbing",
        "tier_used": "T0_PEGLER",
        "v4_query": "pegler ball valve brass 1/2",
        "coste_aed": 13.163865,
        "arancel_aed_ud": 0.544984011,
        "peso_neto_kg": 0.21,
        "material": "brass",
        "pn": 30,
        "end_connection": "threaded",
        "image_url_pim": "https://d7rh5s3nxmpy4.cloudfront.net/CMP8164/2/4222-4222.jpg",
        "fx_eur_aed": 4.29,
        "channel": "amazon_uae",
        "scheme": "FBA"
      },
      "candidates_summary": {
        "n_total": 3,
        "best_score": 64,
        "median_aed": 45.0,
        "delivery_advantage_days": -1.0,
        "n_from_china": 0,
        "n_from_uae": 2,
        "n_prime": 0
      },
      "expected_outputs_excel_master": {
        "pvp_lanzamiento_aed": 110.671,
        "pvp_lanzamiento_eur": 25.7974358974359,
        "pvp_min_viable_aed": 33.245571292704,
        "total_costes_aed_ud": 37.460709027443,
        "breakdown": {
          "coste_aed": 13.163865,
          "arancel_aed": 0.544984011,
          "referral_aed": 16.60065,
          "fba_fee_aed": 9.2,
          "iva_aed": 1.2900325,
          "ppc_aed": 6.861602,
          "otros_aed": 1.328052,
          "envio_fc_aed": 1.5,
          "storage_aed_mes": 0.680372527443034
        },
        "benef_fba_aed_ud": 60.046425972557,
        "margen_fba": 0.54256694140793,
        "roi_fba": 4.561458657663,
        "benef_fbm_aed_ud": 71.8867985,
        "margen_fbm": 0.649554070171951,
        "roi_fbm": 5.4609188486816,
        "estado_fba": "✅ Rentable >35% — Margen 59.9%",
        "canal_recomendado": "FBA",
        "formula_excel": "Mediana + 10% cert. EU"
      },
      "expected_motor_v51_outputs": {
        "pvp_min_source": "excel_master",
        "rule_applied_predicted": "aggressive_match_low",
        "formula_predicted": "max(mediana × 1.10, PVP_MIN × 1.10) — match incierto",
        "pvp_aed_predicted": 49.5,
        "pvp_eur_predicted": 11.54,
        "alerts_predicted": [
          "⚠ Match calidad media (score=64) — validar manualmente"
        ],
        "has_velocity_premium": false,
        "delivery_advantage_days": -1.0,
        "cap_applied": false,
        "_note": "max(45*1.10=49.5, 33.25*1.10=36.57) = 49.5 ; bajo cap=54 ; sobre floor=33.25"
      }
    },
    {
      "id": "FX02_PEGLER_T0_HANDLE_LOW",
      "descripcion": "T0_PEGLER, G1, score 77 (low match), accesorio handle",
      "inputs": {
        "codigo": "422401",
        "familia_ficha": "4224",
        "nombre_en": "CHROME HANDLE FOR LONG NECK VALVES",
        "subfamilia": "VALV.LATÓN CARLAS+EMPOTRAR",
        "familia": "HIDROSANITARIO",
        "grupo": "G1",
        "tier_used": "T0_PEGLER",
        "coste_aed": 7.694115,
        "peso_neto_kg": 0.172,
        "material": "brass",
        "fx_eur_aed": 4.29,
        "channel": "amazon_uae",
        "scheme": "FBA"
      },
      "candidates_summary": {"n_total": 3, "best_score": 77, "median_aed": 64.5},
      "expected_outputs_excel_master": {
        "pvp_lanzamiento_aed": 58.52,
        "pvp_min_viable_aed": 26.7869001485373,
        "total_costes_aed_ud": 26.1204614031509,
        "margen_fba": 0.422170601449916,
        "roi_fba": 3.21095065473405,
        "estado_fba": "✅ Rentable >35% — Margen 51.3%",
        "canal_recomendado": "FBA"
      },
      "expected_motor_v51_outputs": {
        "rule_applied_predicted": "aggressive_match_low",
        "formula_predicted": "max(mediana × 1.10, PVP_MIN × 1.10)",
        "pvp_aed_predicted": 70.95,
        "pvp_min_source": "excel_master",
        "alerts_predicted": ["⚠ Match calidad media (score=77)"]
      }
    },
    {
      "id": "FX03_ARCO_T0_BLACK_HANDLE",
      "descripcion": "T0_ARCO, G1, score 79 (low match)",
      "inputs": {
        "codigo": "4224011",
        "nombre_en": "BLACK HANDLE FOR LONG NECK VALVES",
        "tier_used": "T0_ARCO",
        "grupo": "G1",
        "coste_aed": 7.94937,
        "peso_neto_kg": 0.172,
        "fx_eur_aed": 4.29,
        "channel": "amazon_uae",
        "scheme": "FBA"
      },
      "candidates_summary": {"n_total": 3, "best_score": 79, "median_aed": 28.85},
      "expected_outputs_excel_master": {
        "pvp_lanzamiento_aed": 58.52,
        "pvp_min_viable_aed": 27.1327980756681,
        "total_costes_aed_ud": 26.1204614031509,
        "margen_fba": 0.417808759344653,
        "estado_fba": "✅ Rentable >35% — Margen 42%",
        "canal_recomendado": "FBA"
      },
      "expected_motor_v51_outputs": {
        "rule_applied_predicted": "aggressive_match_low",
        "pvp_aed_predicted": 31.74,
        "_note": "max(28.85*1.10=31.74, 27.13*1.10=29.85) = 31.74 ; bajo cap mediana×1.20=34.62"
      }
    },
    {
      "id": "FX04_ARCO_T0_BUTTERFLY_HIGH",
      "descripcion": "T0_ARCO, G1, score 90 (HIGH MATCH)",
      "inputs": {
        "codigo": "4074201520",
        "nombre_en": "BALL VALVE PN30 F-F 1/2\"-LN 3/4\" BLUE BUTTERFLY HANDLE",
        "tier_used": "T0_ARCO",
        "grupo": "G1",
        "coste_aed": 15.424695,
        "peso_neto_kg": 0.22,
        "fx_eur_aed": 4.29,
        "channel": "amazon_uae",
        "scheme": "FBA"
      },
      "candidates_summary": {"n_total": 3, "best_score": 90, "median_aed": 53.2},
      "expected_outputs_excel_master": {
        "pvp_lanzamiento_aed": 58.52,
        "pvp_min_viable_aed": 36.3092386472909,
        "total_costes_aed_ud": 25.387752527443,
        "margen_fba": 0.302589755170146,
        "estado_fba": "✅ Rentable >20% — Margen 30%",
        "canal_recomendado": "FBA"
      },
      "expected_motor_v51_outputs": {
        "rule_applied_predicted": "aggressive_match_high",
        "formula_predicted": "max(mediana × 0.98, PVP_MIN × 1.05)",
        "pvp_aed_predicted": 38.12,
        "_note": "max(53.2*0.98=52.14, 36.31*1.05=38.12) = 52.14 ; bajo cap=63.84 ; ¡atención!: golden=52.14 (match high gana)"
      }
    },
    {
      "id": "FX05_GIACOMINI_T0_PN25",
      "descripcion": "T0_GIACOMINI, G1, score 90 (HIGH MATCH)",
      "inputs": {
        "codigo": "4092020",
        "nombre_en": "F-F BRASS BALL VALVE PN-25 BLUE ERGONOMIC CARBON STEEL HANDLE",
        "tier_used": "T0_GIACOMINI",
        "grupo": "G1",
        "coste_aed": 10.611315,
        "peso_neto_kg": 0.192,
        "fx_eur_aed": 4.29,
        "channel": "amazon_uae",
        "scheme": "FBA"
      },
      "candidates_summary": {"n_total": 3, "best_score": 90, "median_aed": 46.48},
      "expected_outputs_excel_master": {
        "pvp_lanzamiento_aed": 51.128,
        "pvp_min_viable_aed": 29.7865920213963,
        "total_costes_aed_ud": 23.676504527443,
        "margen_fba": 0.329372955573403,
        "estado_fba": "✅ Rentable >20% — Margen 33%",
        "canal_recomendado": "FBA"
      },
      "expected_motor_v51_outputs": {
        "rule_applied_predicted": "aggressive_match_high",
        "pvp_aed_predicted": 45.55,
        "_note": "max(46.48*0.98=45.55, 29.79*1.05=31.28) = 45.55"
      }
    },
    {
      "id": "FX06_APOLLO_T0_GATE_BIG_INDUSTRIAL",
      "descripcion": "T0_APOLLO, G2 cast_iron, alto coste 1350 AED — caso de margen ajustado",
      "inputs": {
        "codigo": "5113250",
        "nombre_en": "EPDM RESILIENT WEDGE GATE VALVE, FLANGED ENDS  250",
        "subfamilia": "VÁLVULAS FUNDICIÓN-COMPUERTAS",
        "familia": "INDUSTRIAL",
        "tier_used": "T0_APOLLO",
        "grupo": "G2",
        "coste_aed": 1350.88239,
        "peso_neto_kg": 86.25,
        "material": "cast_iron",
        "pn": 16,
        "end_connection": "flanged",
        "fx_eur_aed": 4.29,
        "channel": "amazon_uae",
        "scheme": "FBA"
      },
      "candidates_summary": {"n_total": 3, "best_score": 82, "median_aed": 2100.0},
      "expected_outputs_excel_master": {
        "pvp_lanzamiento_aed": 2310.0,
        "pvp_min_viable_aed": 1845.11245406116,
        "total_costes_aed_ud": 545.925,
        "margen_fba": 0.17887125974026,
        "roi_fba": 0.305868677435347,
        "estado_fba": "⚠ Ajustado — Margen 18%",
        "canal_recomendado": "FBM / B2B"
      },
      "expected_motor_v51_outputs": {
        "rule_applied_predicted": "aggressive_match_high",
        "pvp_aed_predicted": 2058.0,
        "_note": "max(2100*0.98=2058, 1845.11*1.05=1937.37) = 2058 ; bajo cap=2520"
      }
    },
    {
      "id": "FX07_APOLLO_T0_CHECK_VALVE_LOSS",
      "descripcion": "T0_APOLLO, G2, score 77 (low match), MARGEN NEGATIVO en FBA — alert crítica esperada",
      "inputs": {
        "codigo": "5142050",
        "nombre_en": "CHECK VALVE THREADED END NBR BALL PN 10 2\"",
        "tier_used": "T0_APOLLO",
        "grupo": "G2",
        "coste_aed": 102.867765,
        "peso_neto_kg": 3.0,
        "material": "cast_iron",
        "fx_eur_aed": 4.29,
        "channel": "amazon_uae",
        "scheme": "FBA"
      },
      "candidates_summary": {"n_total": 3, "best_score": 77, "median_aed": 127.32},
      "expected_outputs_excel_master": {
        "pvp_lanzamiento_aed": 140.052,
        "pvp_min_viable_aed": 160.799881616425,
        "total_costes_aed_ud": 48.8702565512225,
        "benef_fba_aed_ud": -11.6860215512226,
        "margen_fba": -0.0834405902894821,
        "estado_fba": "❌ Pérdida — Margen -08%",
        "canal_recomendado": "FBA",
        "_caveat": "PVP lanzamiento (140) está por debajo de PVP_MIN (160.8) — Excel marca pérdida"
      },
      "expected_motor_v51_outputs": {
        "rule_applied_predicted": "aggressive_match_low → FLOOR",
        "alerts_predicted": [
          "⚠ Match calidad media (score=77)",
          "⚠ Mediana mercado (127.32) bajo PVP_MIN×1.05 — competimos pero margen ajustado",
          "🚨 PVP_MIN (160.80) > mediana × cap (152.78) — producto inviable competitivamente",
          "🚨 FLOOR forzado: target X < PVP_MIN 160.80"
        ],
        "pvp_aed_predicted": 176.88,
        "_note": "max(127.32*1.10=140.05, 160.80*1.10=176.88) = 176.88 ; alert crítica producto inviable"
      }
    },
    {
      "id": "FX08_NIBCO_T0_SS_BIG_LOSS_SEVERE",
      "descripcion": "T0_NIBCO, G2 stainless, MARGEN -100% (PÉRDIDA SEVERA)",
      "inputs": {
        "codigo": "5128150",
        "nombre_en": "TWO PIECES BALL VALVE S.S. FLANGED END PN16   6\"",
        "subfamilia": "VÁLVULAS INOXIDABLES-ESFERA",
        "tier_used": "T0_NIBCO",
        "grupo": "G2",
        "coste_aed": 2560.20765,
        "peso_neto_kg": 41.0,
        "material": "stainless_steel",
        "fx_eur_aed": 4.29,
        "channel": "amazon_uae",
        "scheme": "FBA"
      },
      "candidates_summary": {"n_total": 3, "best_score": 64, "median_aed": 127.86},
      "expected_outputs_excel_master": {
        "pvp_lanzamiento_aed": 140.646,
        "pvp_min_viable_aed": 3505.2377966298,
        "total_costes_aed_ud": 60.134549,
        "margen_fba": -17.6307623323806,
        "estado_fba": "❌ Pérdida severa — Margen <-100%",
        "canal_recomendado": "FBM / B2B",
        "_caveat": "Producto IMPOSIBLE de vender al precio del mercado UAE"
      },
      "expected_motor_v51_outputs": {
        "rule_applied_predicted": "aggressive_match_low → FLOOR",
        "alerts_predicted": [
          "⚠ Match calidad media (score=64)",
          "🚨 PVP_MIN (3505.24) > mediana × cap (153.43) — producto INVIABLE",
          "🚨 FLOOR forzado: target X < PVP_MIN 3505.24"
        ],
        "pvp_aed_predicted": 3855.76,
        "_note": "max(127.86*1.10, 3505.24*1.10) = 3855.76 — irreal pero matemáticamente correcto"
      }
    },
    {
      "id": "FX09_T2_TECHNICAL_PN25_2OUT",
      "descripcion": "T2_technical, G1, score 90 (high match)",
      "inputs": {
        "codigo": "4099025",
        "nombre_en": "BALL VALVE PN25 F-F 2 OUTLETS CARBON STEEL RED HANDLE 1\"",
        "tier_used": "T2_technical",
        "grupo": "G1",
        "coste_aed": 27.34875,
        "peso_neto_kg": 0.452,
        "material": "brass",
        "fx_eur_aed": 4.29,
        "channel": "amazon_uae",
        "scheme": "FBA"
      },
      "candidates_summary": {"n_total": 3, "best_score": 90, "median_aed": 97.32},
      "expected_outputs_excel_master": {
        "pvp_lanzamiento_aed": 107.052,
        "pvp_min_viable_aed": 52.4903138931225,
        "total_costes_aed_ud": 36.6403559768646,
        "margen_fba": 0.402261461935651,
        "estado_fba": "✅ Rentable >35% — Margen 40%",
        "canal_recomendado": "FBA"
      },
      "expected_motor_v51_outputs": {
        "rule_applied_predicted": "aggressive_match_high",
        "pvp_aed_predicted": 95.37,
        "_note": "max(97.32*0.98=95.37, 52.49*1.05=55.11) = 95.37"
      }
    },
    {
      "id": "FX10_T2_TECHNICAL_PN30_3_4",
      "descripcion": "T2_technical, G1, score 90",
      "inputs": {
        "codigo": "4074202020",
        "nombre_en": "BALL VALVE PN30 F-F 3/4\"-LN 3/4\" BLUE BUTTERFLY HANDLE",
        "tier_used": "T2_technical",
        "grupo": "G1",
        "coste_aed": 20.383935,
        "peso_neto_kg": 0.3,
        "material": "brass",
        "fx_eur_aed": 4.29,
        "channel": "amazon_uae",
        "scheme": "FBA"
      },
      "candidates_summary": {"n_total": 3, "best_score": 90, "median_aed": 53.2},
      "expected_outputs_excel_master": {
        "pvp_lanzamiento_aed": 58.52,
        "pvp_min_viable_aed": 43.0295412315459,
        "total_costes_aed_ud": 25.387752527443,
        "margen_fba": 0.217845394267891,
        "estado_fba": "✅ Rentable >20% — Margen 22%",
        "canal_recomendado": "FBA"
      },
      "expected_motor_v51_outputs": {
        "rule_applied_predicted": "aggressive_match_high",
        "pvp_aed_predicted": 52.14,
        "_note": "max(53.2*0.98=52.14, 43.03*1.05=45.18) = 52.14"
      }
    },
    {
      "id": "FX11_T3_FUNCTIONAL_EXPANSION_LOSS",
      "descripcion": "T3_functional, G2, score 23 (NO MATCH), margen negativo",
      "inputs": {
        "codigo": "5120025",
        "nombre_en": "EPDM DOUBLE SPHERE RUBBER EXPANSION JOINT THREADED ENDS 1\"",
        "subfamilia": "MANGUITOS ELASTICOS(SF)",
        "tier_used": "T3_functional",
        "grupo": "G2",
        "coste_aed": 40.950195,
        "peso_neto_kg": 1.0,
        "material": null,
        "pn": 16,
        "fx_eur_aed": 4.29,
        "channel": "amazon_uae",
        "scheme": "FBA"
      },
      "candidates_summary": {"n_total": 3, "best_score": 23, "median_aed": 68.99},
      "expected_outputs_excel_master": {
        "pvp_lanzamiento_aed": 75.889,
        "pvp_min_viable_aed": 153.483514841044,
        "total_costes_aed_ud": 92.8748515823425,
        "margen_fba": -0.763431414069793,
        "estado_fba": "❌ Pérdida — Margen -76%",
        "canal_recomendado": "FBA"
      },
      "expected_motor_v51_outputs": {
        "rule_applied_predicted": "aggressive_g2_no_match_default",
        "formula_predicted": "max(coste × 2.5, PVP_MIN × 1.15)",
        "pvp_aed_predicted": 176.51,
        "alerts_predicted": [
          "🚨 PVP_MIN (153.48) > mediana × cap (82.79) — inviable competitivamente",
          "🚨 FLOOR forzado"
        ],
        "_note": "max(40.95*2.5=102.38, 153.48*1.15=176.50) = 176.50"
      }
    },
    {
      "id": "FX12_T4_PRODUCT_NAME_GATE_LOSS",
      "descripcion": "T4_product_name, G1, score 90, MARGEN -50% (PVP lanzamiento muy bajo en Excel)",
      "inputs": {
        "codigo": "4113050",
        "nombre_en": "F-F GATE VALVE PN10 STANDARD FLOW 2\"",
        "tier_used": "T4_product_name",
        "grupo": "G1",
        "coste_aed": 51.19686,
        "peso_neto_kg": 0.97,
        "material": "brass",
        "fx_eur_aed": 4.29,
        "channel": "amazon_uae",
        "scheme": "FBA"
      },
      "candidates_summary": {"n_total": 3, "best_score": 90, "median_aed": 45.31},
      "expected_outputs_excel_master": {
        "pvp_lanzamiento_aed": 49.841,
        "pvp_min_viable_aed": 84.8548539268769,
        "total_costes_aed_ud": 23.4327367388049,
        "margen_fba": -0.497353518966411,
        "estado_fba": "❌ Pérdida — Margen -50%",
        "canal_recomendado": "FBA"
      },
      "expected_motor_v51_outputs": {
        "rule_applied_predicted": "aggressive_match_high → FLOOR",
        "pvp_aed_predicted": 89.10,
        "alerts_predicted": [
          "⚠ Mediana (45.31) bajo PVP_MIN×1.05 — margen ajustado",
          "🚨 PVP_MIN (84.85) > mediana × cap (54.37) — inviable",
          "🚨 FLOOR forzado: target 44.40 < PVP_MIN 84.85"
        ],
        "_note": "max(45.31*0.98=44.40, 84.85*1.05=89.10) = 89.10"
      }
    },
    {
      "id": "FX13_T4_BUTTERFLY_SS_LOSS",
      "descripcion": "T4_product_name, G2 stainless, score 73 (low match), pérdida -100%",
      "inputs": {
        "codigo": "51142100",
        "nombre_en": "BUTTERFLY VALVE WAFER TYPE S. S. DISC A-316 NBR  4\"",
        "subfamilia": "VÁLVULAS FUNDICIÓN-MARIPOSAS GOLD",
        "tier_used": "T4_product_name",
        "grupo": "G2",
        "coste_aed": 218.315955,
        "peso_neto_kg": 5.1,
        "material": "stainless_steel",
        "fx_eur_aed": 4.29,
        "channel": "amazon_uae",
        "scheme": "FBA"
      },
      "candidates_summary": {"n_total": 3, "best_score": 73, "median_aed": 89.99},
      "expected_outputs_excel_master": {
        "pvp_lanzamiento_aed": 98.989,
        "pvp_min_viable_aed": 310.363351381913,
        "total_costes_aed_ud": 34.0759535,
        "margen_fba": -1.54969651678469,
        "estado_fba": "❌ Pérdida severa — Margen <-100%",
        "canal_recomendado": "FBA"
      },
      "expected_motor_v51_outputs": {
        "rule_applied_predicted": "aggressive_match_low → FLOOR",
        "pvp_aed_predicted": 341.40,
        "_note": "max(89.99*1.10=98.99, 310.36*1.10=341.40) = 341.40 ; alerta INVIABLE"
      }
    },
    {
      "id": "FX14_T5_FALLBACK_PN30_BUTTERFLY_LOSS",
      "descripcion": "T5_fallback, G1, score 85 (HIGH MATCH), margen -3%",
      "inputs": {
        "codigo": "4102010",
        "nombre_en": "F-F BRASS BALL VALVE PN-30 FULL BORE WITH RED BUTTERFLY HANDLE",
        "tier_used": "T5_fallback",
        "grupo": "G1",
        "coste_aed": 8.350485,
        "peso_neto_kg": 0.097,
        "material": "brass",
        "fx_eur_aed": 4.29,
        "channel": "amazon_uae",
        "scheme": "FBA"
      },
      "candidates_summary": {"n_total": 3, "best_score": 85, "median_aed": 20.72},
      "expected_outputs_excel_master": {
        "pvp_lanzamiento_aed": 22.792,
        "pvp_min_viable_aed": 23.9903287006416,
        "total_costes_aed_ud": 15.016720527443,
        "margen_fba": -0.0252371677537309,
        "estado_fba": "❌ Pérdida — Margen -03%",
        "canal_recomendado": "FBA"
      },
      "expected_motor_v51_outputs": {
        "rule_applied_predicted": "aggressive_match_high → FLOOR",
        "pvp_aed_predicted": 25.19,
        "alerts_predicted": [
          "⚠ Mediana (20.72) bajo PVP_MIN×1.05 — margen ajustado",
          "🚨 FLOOR forzado: target 20.31 < PVP_MIN 23.99"
        ],
        "_note": "max(20.72*0.98=20.31, 23.99*1.05=25.19) = 25.19"
      }
    },
    {
      "id": "FX15_NONE_BIBCOCK_NO_CANDIDATES",
      "descripcion": "Tier NONE — sin candidatos suficientes (Top3 incompleto: '—' / '⏳'), formula Excel = 'Coste + 40%' (NO 'Mediana + 10% cert. EU')",
      "inputs": {
        "codigo": "411101520",
        "nombre_en": "BRASS BALL BIBCOCK GARDEN PN-16 WITH HOSE CONNECTOR 1/2\"X3/4\"",
        "subfamilia": "VALV.LATÓN GRIFOS",
        "tier_used": "NONE",
        "grupo": "G1",
        "coste_aed": 10.13727,
        "peso_neto_kg": 0.18,
        "material": "brass",
        "fx_eur_aed": 4.29,
        "channel": "amazon_uae",
        "scheme": "FBA"
      },
      "candidates_summary": {
        "n_total": 2,
        "best_score": 85,
        "median_aed": null,
        "_note": "Top3 incompleto: top1=30.75, top2=179.59, top3='—'"
      },
      "expected_outputs_excel_master": {
        "pvp_lanzamiento_aed": 14.192178,
        "pvp_lanzamiento_eur": 3.3082,
        "pvp_min_viable_aed": 26.411614190557,
        "total_costes_aed_ud": 13.025861734443,
        "margen_fba": -0.632105497439719,
        "estado_fba": "❌ Pérdida — Margen -63%",
        "canal_recomendado": "FBA",
        "formula_excel": "Coste + 40%",
        "_caveat": "Excel usa fórmula NO-mediana cuando candidatos insuficientes — TODO confirmar lógica"
      },
      "expected_motor_v51_outputs": {
        "rule_applied_predicted": "aggressive_g1_no_match",
        "formula_predicted": "PVP_MIN × 1.15 — G1 sin referencia",
        "pvp_aed_predicted": 30.37,
        "alerts_predicted": [
          "🚨 FLOOR/sin match"
        ],
        "_note": "26.41 * 1.15 = 30.37 ; sin median no aplica cap ni premium"
      }
    }
  ]
}
```

---

## 4. Tarea 3 — Decisión port vs rewrite

### 4.1. Tabla por regla

| # | Regla | ¿Port directo? | Justificación |
|---|-------|---------------|---------------|
| 1 | `regla_aed_to_eur` | **No (rewrite)** | El motor usa FX hardcoded en `config.EUR_TO_AED`. La nueva arquitectura exige `fx_rates` con `effective_from`/`effective_to`. Función trivial pero la fuente cambia. |
| 2 | `regla_calcular_mediana` | **Sí (port)** | Función pura, 5 líneas. |
| 3 | `regla_calcular_margen_pct` | **Sí (port)** | Función pura. |
| 4 | `regla_recalculo_costes_dinamico` | **Parcial** | Lógica matemática portable, pero la fuente (`master_sku_data`) cambia: hoy lee del Excel; mañana de tabla `costs.breakdown` JSONB. Necesita validador anti-divisiones-por-cero y test de invariante (% reales en rango 0-100). |
| 5 | `regla_fba_fee_fallback` | **Parcial** | Las bandas de peso son hardcoded en `config`. Hay tabla más detallada en sheet `Tarifas FBA & FBM` (87 filas). Mejor migrar a tabla `fba_fee_tiers` (weight_max_kg, fee_aed) y leer dinámicamente. |
| 6 | `regla_detect_g2_subtype` | **No (rewrite)** | Heurística textual frágil. Reemplazar por `products.material` enum gobernado y tabla `material_multipliers`. |
| 7 | `regla_pvp_min_excel_master` | **Parcial** | Lógica simple. Pero el path `master_sku_data.pvp_min_viable_aed` se pierde — hay que persistir el PVP_MIN calculado por sub-rutina dedicada. Idealmente: `costs.breakdown.pvp_min_viable_aed` o columna calculada. |
| 8 | `regla_pvp_min_formula_global` | **Sí (port)** | Función pura. Migra `config.*_PCT` a tabla `pricing_params` versionada. |
| 9 | `regla_analyze_candidates` | **Sí (port)** | Función pura sobre lista. Asume shape de candidato del scraper — añadir contract test. |
| 10 | `regla_premium_velocidad` | **Sí (port)** | Lógica condicional simple. **RIESGO**: depende de que `delivery_advantage_days` esté poblado, lo que depende del scraper R&D. |
| 11 | `regla_aggressive_match_high` | **Sí (port)** | Trivial. |
| 12 | `regla_aggressive_match_low` | **Sí (port)** | Trivial. |
| 13 | `regla_aggressive_g2_no_match` | **Parcial** | Depende de `regla_detect_g2_subtype` (rewrite). |
| 14 | `regla_aggressive_g1_no_match` | **Sí (port)** | Trivial. |
| 15 | `regla_override_manual` | **No (rewrite)** | Hoy es lectura de un JSON en disco. Migra a tabla `price_overrides` con RBAC, validez `valid_from`/`valid_to`, audit. |
| 16 | `regla_cap_superior_y_floor` | **Sí (port)** | Trivial. |
| 17 | `regla_alertas_automaticas` | **Sí (port)** | Migra strings con emoji a `alerts JSONB DEFAULT '[]'` con shape `{level, code, message, vars}` (PRD §10.1, tabla `prices`). |
| 18 | `regla_canal_recomendado_passthrough` | **No (rewrite)** | El motor v5.1 NO calcula canal — lo lee del Excel. **TODO bloqueante**: extraer la lógica VBA del Excel o re-derivarla con regla nueva (sugerido: `if margen_fba >= 0.35 and estado_fba like '✅' → 'FBA'`). |

**Resumen**: 8 port directo, 6 parciales, 4 rewrite — **veredicto: port-mostly + rewrite parcial**.

### 4.2. Estimación de esfuerzo (story points Fibonacci)

| Regla | SP | Justificación |
|-------|----|----|
| `regla_aed_to_eur` + tabla `fx_rates` | 5 | Tabla + as-of stamping + jobs FX |
| `regla_calcular_mediana` | 1 | Pure function |
| `regla_calcular_margen_pct` | 1 | Pure function |
| `regla_recalculo_costes_dinamico` | 8 | Validación + tests invariantes + JSONB schema |
| `regla_fba_fee_fallback` + tabla `fba_fee_tiers` | 5 | Migración tabla + parser sheet |
| `regla_detect_g2_subtype` → `material_multipliers` | 5 | Schema + seed + reemplazo heurística |
| `regla_pvp_min_excel_master` (lectura desde `costs`) | 5 | Mapeo a JSONB |
| `regla_pvp_min_formula_global` + `pricing_params` | 5 | Tabla versionada + service |
| `regla_analyze_candidates` + contract tests | 3 | Function + fixtures |
| `regla_premium_velocidad` | 3 | Function + tests |
| `regla_aggressive_match_*` (4 reglas) | 3 | Block consolidado |
| `regla_override_manual` → `price_overrides` | 8 | Schema + RBAC + audit + UI |
| `regla_cap_superior_y_floor` | 2 | Function |
| `regla_alertas_automaticas` (con shape JSONB) | 5 | Migración strings → códigos estructurados + i18n |
| `regla_canal_recomendado` (rewrite con criterios explícitos) | 13 | Decompilación VBA + decisión negocio + impl |
| Test fixtures + golden numbers (suite completa) | 8 | 15 fixtures × assertions × snapshot |
| Importer Excel `INVOICE ENRIQUECIDA v5` → `costs` + `prices` | 13 | Parser robusto + dry-run + dedup |
| `PricingService` orquestador FastAPI | 8 | API + DTOs + retries |
| **Total motor v5.1 + soporte** | **~100 SP** | ~3-4 sprints (a 25-30 SP/sprint) |

### 4.3. Riesgos del port y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|-------|------------|---------|------------|
| **R1: divergencia silenciosa Excel ↔ Postgres** post-cutover | Media | Alto | Parallel run ≥ 2 semanas con diff diaria sobre los 15 fixtures + 50 SKUs random; bloquea cutover si `pvp_aed` diff > 0.01 AED. |
| **R2: pérdida de contexto VBA `canal_recomendado`** | Alta | Alto | Sesión de 2h con Juan Carlos para extraer la fórmula explícita; documentar en `_bmad-output/research/canal-recomendado-derivacion.md` antes de codificar. |
| **R3: shape de candidato del scraper R&D cambia** | Alta | Medio | Pydantic models versionados + contract tests; el scraper R&D firma un contrato `CompetitorCandidate v1`. |
| **R4: % operativos inferidos absurdos** (ej. PPC 800%) | Media | Alto | Validador en `compute_costs_from_master`: si pct ∉ [0, 0.5] log warning + flag `cost_data_quality='suspect'`. |
| **R5: golden numbers del Excel desactualizados** post-FX update | Alta | Medio | Re-generar fixtures con FX as-of stamping en cada batch + commit en repo. |
| **R6: alertas con emojis rompen i18n / DB sort** | Baja | Bajo | Sustituir `'🚨'`/`'⚠'`/`'🚀'` por códigos `'critical'`/`'warning'`/`'info'` en JSONB. |
| **R7: precisión flotante (round 2 vs round 4)** | Media | Bajo | Usar `Decimal` en Python service (NUMERIC en Postgres) en lugar de `float`. |

---

## 5. Tarea 4 — Mapeo a la nueva arquitectura

| Regla | Tabla destino | Servicio FastAPI | ¿Postgres function o Python? | Test sugerido |
|-------|---------------|------------------|-----------------------------|----------------|
| `regla_aed_to_eur` | `fx_rates` | `FxService.get_rate(from, to, as_of)` | Postgres function `fn_fx_rate(from, to, ts)` | `test_fx_as_of_stamping_returns_4_29_for_2026_05_01` |
| `regla_calcular_mediana` | (in-memory) | `MarketAnalysisService` | Python | `test_median_with_3_prices` |
| `regla_calcular_margen_pct` | (in-memory) | `PricingService._calc_margin` | Python | `test_margin_pct_42_percent` |
| `regla_recalculo_costes_dinamico` | `costs.breakdown` JSONB | `CostService.recalc_for_price(sku_id, new_price)` | Postgres function `fn_recalc_costs(sku_id, price)` por performance | `test_recalc_costs_for_4222015_at_pvp_49_5` |
| `regla_fba_fee_fallback` | `fba_fee_tiers` | `FbaFeeService.get_fee(weight_kg, group)` | Postgres function | `test_fba_fee_for_0_21kg_returns_smallest_tier` |
| `regla_detect_g2_subtype` | `products.material` + `material_multipliers` | `RuleEngine` | Python (lookup table) | `test_g2_stainless_uses_2_8_multiplier` |
| `regla_pvp_min_excel_master` | `costs.breakdown.pvp_min_viable_aed` | `PvpMinService.compute(sku_id)` | Postgres function | `test_pvp_min_4222015_equals_33_25` |
| `regla_pvp_min_formula_global` | `pricing_params` | idem | Postgres function fallback | `test_pvp_min_no_master_uses_formula` |
| `regla_analyze_candidates` | `competitor_listings` | `MarketAnalysisService` | Python (con queries `competitor_listings`) | `test_analyze_3_candidates_includes_delivery_advantage` |
| `regla_premium_velocidad` | (motor) | `RuleEngine.apply_velocity_premium` | Python | `test_premium_velocidad_alta_with_7d_advantage` |
| `regla_aggressive_match_*` | (motor) | `RuleEngine.apply_aggressive_policy` | Python | `test_aggressive_high_returns_max_median_pvp_min` |
| `regla_override_manual` | `price_overrides` | `OverrideService` (admin only) | Postgres (UPSERT con RBAC) | `test_override_below_pvp_min_creates_critical_alert` |
| `regla_cap_superior_y_floor` | (motor) | `RuleEngine.apply_caps` | Python | `test_cap_at_120_pct_median_unless_velocity_premium` |
| `regla_alertas_automaticas` | `prices.alerts` JSONB | `AlertGenerator` | Python | `test_alerts_include_warning_when_low_match` |
| `regla_canal_recomendado` (rewrite) | `prices.channel_recommendation` o tabla `channel_recommendations` | `ChannelRecommender` | **Decisión pendiente** | `test_canal_fba_when_margen_fba_gte_35_pct` |
| Orquestación (`apply_pricing_v5_1` completo) | `prices` | `PricingService.calculate_proposal(sku, channel, scheme, fx_id)` | Python orquesta + invoca Postgres functions | `test_full_pipeline_4222015_amazon_uae_fba` |

### 5.1. Servicios FastAPI propuestos

```
backend/services/pricing/
├── pricing_service.py          # PricingService (orquestador principal)
├── fx_service.py               # aed_to_eur, get_rate(as_of)
├── pvp_min_service.py          # compute_pvp_min (master + fallback)
├── cost_service.py             # compute_costs_from_master (refit dinámico)
├── market_analysis_service.py  # analyze_candidates, calculate_median
├── rule_engine.py              # apply_aggressive_policy + premium_velocidad
├── alert_generator.py          # build alerts list (JSONB)
├── exception_evaluator.py      # decide auto_approved vs pending_review (PRD §10)
├── override_service.py         # price_overrides admin
└── channel_recommender.py      # rewrite de canal_recomendado VBA
```

### 5.2. Postgres functions propuestas

```sql
-- PVP_MIN dinámico desde costs.breakdown
CREATE FUNCTION fn_pvp_min(p_product_id BIGINT, p_scheme_id INT)
RETURNS NUMERIC LANGUAGE plpgsql ...

-- FX rate as-of stamping
CREATE FUNCTION fn_fx_rate(p_from VARCHAR, p_to VARCHAR, p_at TIMESTAMPTZ)
RETURNS NUMERIC LANGUAGE plpgsql ...

-- Recalcular costes para PVP nuevo
CREATE FUNCTION fn_recalc_costs(p_product_id BIGINT, p_pvp NUMERIC, p_scheme_id INT)
RETURNS JSONB LANGUAGE plpgsql ...
```

---

## 6. Tarea 5 — Estructura de tests pytest

### 6.1. Plantilla base

```python
# tests/unit/pricing/test_motor_v51_rules.py
import pytest
from decimal import Decimal
from app.services.pricing import PricingService
from app.services.fx import FxService

# ────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────

@pytest.fixture
def fx_2026_05_01():
    """FX as-of 2026-05-01 (EUR/AED = 4.29) snapshot."""
    return Decimal("4.29")

@pytest.fixture
def pricing_engine(db_session, fx_2026_05_01):
    """PricingService con dependencias inyectadas."""
    return PricingService(db=db_session, fx_rate=fx_2026_05_01)

# ────────────────────────────────────────────────────────────
# 1) test_regla_pvp_min_excel_master
# ────────────────────────────────────────────────────────────

def test_regla_pvp_min_excel_master_4222015(pricing_engine):
    """FX01: PVP_MIN debe venir del breakdown del Excel master, NO del fallback."""
    # Given
    sku_data = {
        "codigo": "4222015",
        "nombre_en": "F-F  PN30 LONG NECK THREADED BALL VALVE 'CARLA' TYPE  1/2\"",
        "grupo": "G1",
        "coste_aed": Decimal("13.163865"),
        "peso_neto_kg": Decimal("0.21"),
        "master_breakdown": {
            "coste_aed_ud": Decimal("13.163865"),
            "arancel_aed_ud": Decimal("0.544984"),
            "referral_aed_ud": Decimal("16.60065"),
            "fba_fee_aed_ud": Decimal("9.20"),
            "iva_aed_ud": Decimal("1.290033"),
            "ppc_aed_ud": Decimal("6.861602"),
            "otros_aed_ud": Decimal("1.328052"),
            "envio_fc_aed_ud": Decimal("1.50"),
            "storage_aed_mes_ud": Decimal("0.680373"),
            "pvp_lanzamiento_aed": Decimal("110.671"),
            "pvp_min_viable_aed": Decimal("33.245571"),
            "total_costes_aed_ud": Decimal("37.460709"),
        },
    }
    # When
    result = pricing_engine.compute_pvp_min(sku_data)
    # Then
    assert result.source == "excel_master"
    assert result.pvp_min == pytest.approx(Decimal("33.25"), abs=Decimal("0.01"))
    assert result.total_costes == pytest.approx(Decimal("37.46"), abs=Decimal("0.01"))
    assert result.breakdown["fba_fee_aed"] == Decimal("9.20")


# ────────────────────────────────────────────────────────────
# 2) test_regla_premium_velocidad_alta
# ────────────────────────────────────────────────────────────

def test_regla_premium_velocidad_alta_when_competitors_7d_slower(pricing_engine):
    """Si delivery_advantage_days >= 7 y hay match, aplicar mediana × 1.15."""
    # Given
    sku_data = {"codigo": "TEST_VEL", "coste_aed": Decimal("10"), "grupo": "G1"}
    candidates = [
        {"price_aed": Decimal("100"), "score_v2": 85,
         "delivery_days_min": 9, "delivery_days_max": 11, "delivery_origin": "CN"},
        {"price_aed": Decimal("110"), "score_v2": 82,
         "delivery_days_min": 8, "delivery_days_max": 10, "delivery_origin": "CN"},
    ]
    pvp_min = Decimal("50")
    # When
    result = pricing_engine.apply_aggressive_policy(
        market=pricing_engine.analyze_candidates(candidates),
        pvp_min=pvp_min,
        sku_data=sku_data,
    )
    # Then
    assert result.rule == "premium_velocidad_alta"
    assert "mediana × 1.15" in result.formula
    assert result.delivery_premium_applied is True
    # mediana=105 (entre 100 y 110), advantage=(10-2)=8 días -> mult 1.15
    assert result.pvp_target == pytest.approx(Decimal("120.75"), abs=Decimal("0.01"))


# ────────────────────────────────────────────────────────────
# 3) test_regla_aggressive_match_high
# ────────────────────────────────────────────────────────────

def test_regla_aggressive_match_high_returns_max_median_pvp_min(pricing_engine):
    """FX04: Match alto → max(mediana × 0.98, pvp_min × 1.05)."""
    # Given (fixture FX04 4074201520)
    sku_data = {"codigo": "4074201520", "coste_aed": Decimal("15.42"), "grupo": "G1"}
    candidates = [{"price_aed": Decimal("53.20"), "score_v2": 90}]
    pvp_min = Decimal("36.31")
    # When
    market = pricing_engine.analyze_candidates(candidates)
    result = pricing_engine.apply_aggressive_policy(market, pvp_min, sku_data)
    # Then
    assert result.rule == "aggressive_match_high"
    # max(53.20 * 0.98, 36.31 * 1.05) = max(52.14, 38.13) = 52.14
    assert result.pvp_target == pytest.approx(Decimal("52.14"), abs=Decimal("0.01"))


# ────────────────────────────────────────────────────────────
# 4) test_regla_floor_forzado_cuando_inviable
# ────────────────────────────────────────────────────────────

def test_regla_floor_forzado_genera_alerta_critica_inviable(pricing_engine):
    """FX07 5142050: PVP_MIN > mediana×1.20 → alert crítica + floor forzado."""
    # Given
    sku_data = {"codigo": "5142050", "coste_aed": Decimal("102.87"), "grupo": "G2"}
    candidates = [{"price_aed": Decimal("127.32"), "score_v2": 77}]
    pvp_min = Decimal("160.80")
    # When
    result = pricing_engine.calculate(sku_data, candidates,
                                       channel="amazon_uae", scheme="FBA",
                                       master_breakdown={"pvp_min_viable_aed": pvp_min, ...})
    # Then
    assert result.pvp_aed >= pvp_min  # FLOOR respetado
    assert any("inviable competitivamente" in a["message"] for a in result.alerts)
    assert any(a["level"] == "critical" for a in result.alerts)
    assert result.has_critical_alerts is True


# ────────────────────────────────────────────────────────────
# 5) test_regla_no_match_g2_stainless_multiplier
# ────────────────────────────────────────────────────────────

def test_regla_aggressive_g2_no_match_stainless(pricing_engine):
    """FX13: G2 stainless steel sin match → coste × 2.8."""
    # Given
    sku_data = {
        "codigo": "51142100",
        "subfamilia": "VÁLVULAS FUNDICIÓN-MARIPOSAS",
        "nombre_en": "BUTTERFLY VALVE WAFER TYPE S. S. DISC A-316 NBR  4\"",
        "coste_aed": Decimal("218.32"),
        "grupo": "G2",
        "material": "stainless_steel",
    }
    candidates = []  # sin match
    pvp_min = Decimal("310.36")
    # When
    market = pricing_engine.analyze_candidates(candidates)
    result = pricing_engine.apply_aggressive_policy(market, pvp_min, sku_data)
    # Then
    assert result.rule == "aggressive_g2_no_match_stainless"
    # max(218.32 * 2.8, 310.36 * 1.15) = max(611.30, 356.91) = 611.30
    assert result.pvp_target == pytest.approx(Decimal("611.30"), abs=Decimal("0.01"))
```

### 6.2. Test data builders

```python
# tests/builders/sku_builder.py
class SkuFixtureBuilder:
    """Construye SKU fixtures a partir de los goldens del Excel master."""

    @classmethod
    def fx01_pegler_carla(cls):
        return {
            "codigo": "4222015",
            "tier_used": "T0_PEGLER",
            "grupo": "G1",
            "coste_aed": Decimal("13.163865"),
            "master_breakdown": {
                "pvp_min_viable_aed": Decimal("33.246"),
                "total_costes_aed_ud": Decimal("37.461"),
                "margen_fba": Decimal("0.5426"),
                "estado_fba": "✅ Rentable >35% — Margen 59.9%",
                "canal_recomendado": "FBA",
                # ... resto del breakdown
            },
            "expected_pvp_aed": Decimal("49.50"),
            "expected_rule": "aggressive_match_low",
        }

    # ... fx02 a fx15
```

### 6.3. Cobertura mínima sugerida

- 1 test por **regla** (18 reglas × 1 test = 18 tests).
- 1 test por **fixture** (15 fixtures × 1 test E2E = 15 tests) — usa golden numbers como assertions.
- 5 tests de **invariantes** (ej. `pvp >= pvp_min` siempre, `margen_pct ∈ [-2, 1]`, alerts no vacías cuando aplica, etc.).
- 3 tests de **cap/floor** independientes (con/sin premium velocidad).
- 5 tests de **integración** (lectura desde tabla `costs`, escritura a `prices` con `audit_events`).
- **Total**: ~46 tests, ~95% cobertura del motor.

---

## 7. Apéndice — Cosas que NO se pudieron extraer (TODOs)

1. **Macro VBA `canal_recomendado`** (Regla 18). La columna 42 del Excel master tiene el valor calculado pero no extrajimos la fórmula. **Bloqueo S4 si no se decompila.**
2. **Tabla detallada FBA fees** (`⚙️ Tarifas FBA & FBM` sheet). PowerShell COM no abre el sheet por encoding del nombre con emoji. **Workaround**: leer con openpyxl en Python (ya hay alternativa).
3. **Macro de refresh FX EUR/AED** del sheet `⚙️ Macro VBA`. Sólo refresca celda B2 con valor manual; **NO calcula FX automáticamente** desde API. Reemplazo trivial.
4. **Lógica de "Mediana + 10% cert. EU" vs "Coste + 40%"** (columna 23 `Fórmula` del Excel). El motor v5.1 NO usa estas fórmulas — usa su propia política agresiva. **Decidir si migramos las fórmulas Excel como reglas alternativas (excepción rules) o sólo como anotación histórica.**
5. **Estado "✅ Rentable" / "⚠ Ajustado" / "❌ Pérdida"** (columna 41). Es texto generado por fórmula Excel — necesita decompilación o re-derivación con thresholds explícitos.
6. **Sheets de simulación `Amazon UAE 30%`, `Noon UAE 30%`, `B2B MT 40%`**: parecen escenarios de mix de stock × márgenes. NO consume el motor v5.1, NO bloquea el port pero hay que decidir si replicamos esa simulación en la nueva app (FR de simulación what-if del PRD).

---

## 8. Próximos pasos

1. **Validar este documento con Juan Carlos** — confirmar pseudocódigo de cada regla y golden numbers.
2. **Sesión decompilación VBA `canal_recomendado`** (2h con JC + Pablo) — extraer fórmula explícita.
3. **Re-correr `enrich_with_v51.py`** sobre los 15 fixtures para confirmar `pvp_aed` predicho con golden real (y reemplazar los `_note` heurísticos del JSON).
4. **Codificar test suite mínimo (5 tests Tarea 5) en repo `mt-pricing-backend/tests/`** como gate del Sprint 4.
5. **Decisión final port-vs-rewrite** firmada por sponsor (Christian) + technical validator (Paula) antes del kick-off de Sprint 4.
