---
tags:
  - pricing-desk
  - manual
  - usuario
created: 2026-05-29
audience: comercial, analista de pricing, dirección
related:
  - "[[2026-05-28-pricing-desk-flujo-sistema]]"
---

# Manual de usuario — Pricing Desk

> **Para quién es este manual:** analista de pricing, director comercial, operador de marketplaces (Amazon UAE y Noon UAE). No se requieren conocimientos técnicos para usar el Pricing Desk.

## Índice

1. [Qué es el Pricing Desk](#1-qué-es-el-pricing-desk)
2. [Cómo acceder](#2-cómo-acceder)
3. [Estructura de la pantalla](#3-estructura-de-la-pantalla)
4. [Selección de canal y modelo de venta](#4-selección-de-canal-y-modelo-de-venta)
5. [El semáforo (6 indicadores)](#5-el-semáforo-6-indicadores)
6. [Panel lateral izquierdo](#6-panel-lateral-izquierdo)
7. [Filtros y búsqueda](#7-filtros-y-búsqueda)
8. [La tabla principal de productos](#8-la-tabla-principal-de-productos)
9. [Comparador de esquemas (modal)](#9-comparador-de-esquemas-modal)
10. [Proponer precios al flujo de aprobación](#10-proponer-precios-al-flujo-de-aprobación)
11. [Flujos de trabajo típicos](#11-flujos-de-trabajo-típicos)
12. [Preguntas frecuentes](#12-preguntas-frecuentes)
13. [Glosario](#13-glosario)
14. [Roles y permisos](#14-roles-y-permisos)

---

## 1. Qué es el Pricing Desk

El Pricing Desk es la **mesa de decisión de precios** para vender productos de MT España en marketplaces de Emiratos Árabes Unidos (Amazon y Noon). Te permite:

- **Calcular** el precio de venta óptimo para cada producto, considerando todos los costes (compra, flete España→Dubai, importación, comisiones del canal).
- **Comparar** los tres esquemas de fulfillment posibles (FBA, Easy Ship, Self-Ship en Amazon; FBN, FBM en Noon) y elegir el más rentable.
- **Decidir** el margen objetivo por familia de producto o por SKU individual.
- **Proponer** los precios calculados al flujo de aprobación para que dirección dé el visto bueno antes de publicar.

> **El Pricing Desk no publica precios directamente en Amazon o Noon.** Su salida es una propuesta que entra en el flujo `/precios/aprobaciones`. Tras aprobación, el operador publica desde el sistema de listings.

### El modelo de coste en 5 capas

Cada precio que ves en la pantalla se construye sumando estos 5 estratos:

| Capa | Qué incluye | Configurable en |
|------|------------|------|
| 1 · Compra a MT | `pe_eur` (precio compra unitario), descuento MT | Panel lateral ⚙ Parámetros |
| 2 · Ruta España → Dubai | FX EUR→AED, colchón cambio, flete €/kg | Panel lateral ⚙ Parámetros |
| 3 · Importación UAE | Arancel, almacén propio, manipulación | Panel lateral ⚙ Parámetros |
| 4 · Logística del canal | Tarifas FBA/FBN/etc. por SKU | Importación Excel |
| 5 · Comisiones del canal | Referral, IVA, PPC, devoluciones | Panel lateral ⚙ Parámetros |
| **+ Margen objetivo** | Margen sobre venta (%) | Por familia o por SKU |
| **= Precio venta AED** | Lo que ves en la tabla | — |

## 2. Cómo acceder

1. Inicia sesión en la aplicación con tu cuenta corporativa MT.
2. En el menú lateral izquierdo, navega a la sección **Precios** → **Pricing Desk** (icono de calculadora).
3. Necesitas el permiso `prices:read` como mínimo. Para cambiar valores necesitas `prices:propose`.

URL directa: `https://[tu-dominio]/pricing-desk`

## 3. Estructura de la pantalla

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PRICING DESK    [Canal: Amazon UAE ▾]  [Modelo: B2C ▾]                 │  ← Header
├─────────────────────────────────────────────────────────────────────────┤
│  [Catálogo]  [Publicables]  [Bloqueados]  [En pérdida]  [Esquemas] [..] │  ← Semáforo
├──────────────────┬──────────────────────────────────────────────────────┤
│  ⚙ Parámetros   │  [Familia ▾] [Señal ▾] [Buscar SKU…] [✕ Limpiar]      │  ← Filtros
│  ▸ Compra        │  [↑ Proponer N a aprobación]                          │  ← Acción bulk
│  ▸ Importación   │                                                       │
│  ▸ Comisiones    │  ┌────────────────────────────────────────────┐      │
│  ▸ Logística     │  │ ☐  ▸  SKU      Esquema  Coste  Techo  …    │      │
│                  │  ├────────────────────────────────────────────┤      │
│  Margen familia  │  │ ☐  ▸  4222015  FBA      9.43   41.82  …    │      │  ← Tabla
│  - Ball Valve    │  │ ☐  ▸  5120020  EasyShip 14.21  78.55  …    │      │
│  - Coupling      │  │ …                                          │      │
│  - Valve         │  └────────────────────────────────────────────┘      │
│                  │                                                       │
│  Optimización    │                                                       │
│  Escenarios A/B  │                                                       │
│  ⬆ Importar      │                                                       │
└──────────────────┴──────────────────────────────────────────────────────┘
   Panel lateral                  Zona principal
```

## 4. Selección de canal y modelo de venta

En el header tienes dos selectores que **definen el contexto** de toda la pantalla.

### Canal

| Canal | Descripción | Esquemas disponibles |
|-------|-------------|---------------------|
| **Amazon UAE** | Marketplace de Amazon en Emiratos | FBA · Easy Ship · Self-Ship |
| **Noon UAE** | Marketplace de Noon en Emiratos | FBN · FBM |

> **Cada canal tiene sus propias comisiones, tarifas y márgenes objetivo.** Al cambiar de canal, toda la tabla, el panel lateral y el semáforo se recalculan para el canal seleccionado.

### Modelo de venta

| Modelo | Unidad | Cuándo se usa |
|--------|--------|---------------|
| **B2C** | Por unidad suelta | Marketplaces (Amazon UAE, Noon UAE) — el cliente final compra unidades sueltas |
| **B2B** | Por caja completa | Clientes industriales directos — la unidad mínima es la caja MT (units_per_box) |

### Qué pasa cuando cambias canal o modelo

- **Cambia canal** → se recargan: parámetros del canal, tarifas logísticas, márgenes objetivo, productos del canal. Se reinician los filtros (familia, señal, búsqueda) y la selección de SKUs.
- **Cambia modelo** → cambian los márgenes objetivo (B2C y B2B son distintos) y los precios. No se reinician los filtros ni la selección (puedes seguir trabajando con los mismos SKUs).

## 5. El semáforo (6 indicadores)

Justo debajo del header verás una franja oscura con 6 cifras siempre visibles:

| Indicador | Significado |
|-----------|-------------|
| **Catálogo** | Total de productos con precio calculado en el canal actual |
| **Publicables** | Productos cuyo precio queda **por debajo del techo** (se pueden vender sin competir contra el catálogo MT) |
| **Bloqueados** | Productos cuyo precio **supera el techo** (no se pueden publicar — perderías la venta) |
| **En pérdida** | Productos con margen negativo (vendes bajo coste) |
| **Esquemas** | Reparto de productos por esquema de fulfillment óptimo (formato: `FBA·LastMile·Merchant`) |
| **Total productos** | Recuento total (referencia) |

> **El semáforo NO se ve afectado por los filtros de la tabla.** Siempre muestra el estado completo del catálogo del canal.

### Cómo leer el semáforo

- **Catálogo alto, Publicables bajo** → la mayoría de productos están bloqueados. Investiga: ¿está demasiado bajo el techo? ¿hay un parámetro mal configurado?
- **En pérdida > 0** → hay productos cuyo coste de operación supera lo que se puede facturar. Es **decisión de negocio**: renegociar coste con MT o sacar esas referencias del canal.

## 6. Panel lateral izquierdo

El panel lateral contiene 5 secciones colapsables, en este orden:

### 6.1 ⚙ Parámetros (configuración global de coste)

Pulsa la cabecera **⚙ Parámetros** para expandir/colapsar. Verás 4 escalones:

#### Escalón 1 · Compra a MT

| Parámetro | Descripción | Por defecto |
|-----------|-------------|-------------|
| Descuento factura | % que MT España aplica al PVP catálogo | 15% |
| Tipo cambio EUR→AED | FX directo aplicado a los precios EUR | 4.28 |
| Colchón FX | Margen extra para cubrir oscilación de cambio | 2% |

#### Escalón 2 · Importación y almacén

| Parámetro | Descripción | Por defecto |
|-----------|-------------|-------------|
| Arancel importación | Tasa aduanera UAE | 4.14% |
| Almacén propio | Coste de almacén MT en Dubai (% sobre valor) | 2% |
| Manipulación | Coste de preparación / pick & pack | 1.5% |
| Flete €/kg | Tarifa transitario España → Dubai | 0 (pendiente cotizar) |
| Flete mínimo AED | Mínimo de flete por envío | 0 (pendiente cotizar) |

#### Escalón 3 · Comisiones del canal

| Parámetro | Descripción | Por defecto Amazon |
|-----------|-------------|---------------------|
| Referral | Comisión Amazon/Noon por venta | 11% |
| IVA UAE | Impuesto al valor agregado | 5% |
| Publicidad PPC | % presupuestado para anuncios pagados | 8% |
| Devoluciones | Provisión por devoluciones | 2% |

#### Escalón 4 · Logística del canal

| Parámetro | Descripción | Por defecto |
|-----------|-------------|-------------|
| Multiplicador almacén | Factor sobre tarifa de almacén Amazon | 1.0 |

### Cómo cambiar un parámetro

1. Pulsa los botones **−** o **+** del stepper, o
2. Click en la casilla del valor y escribe directamente.
3. El cambio se aplica **inmediatamente** — toda la tabla y el semáforo se recalculan al instante.
4. Si el servidor rechaza el cambio (validación), el valor revierte automáticamente.

> **¿Y si me equivoco?** Cambia el valor de vuelta o consulta los Escenarios A/B (sección 6.4) para restaurar una configuración guardada.

### 6.2 Margen por familia

Establece el margen objetivo (%) para cada familia de producto en el canal y modelo de venta actuales.

```
Ball Valve                    12%
[− 12% +]  [0]  [15]  [25]  [40]   ← Presets rápidos

Coupling                       0%
[−  0% +]  [0]  [15]  [25]  [40]

Valve                         40%
[− 40% +]  [0]  [15]  [25]  [40]

Gate Valves                   25%
[− 25% +]  [0]  [15]  [25]  [40]
```

- **Stepper +/−** ajusta de 1% en 1%.
- **Presets** (0, 15, 25, 40) aplican el valor de un click.
- **Cuando cambias el margen de una familia**, todos los productos de esa familia que **no tengan override individual** adoptan el nuevo margen al instante.
- Los productos con override (ajustados a mano en la tabla) **mantienen** su valor.

### 6.3 Optimización

Un solo botón: **★ Optimización completa**.

```
★ Optimización completa
Para cada producto prueba todos los esquemas y el mejor margen bajo techo.
Persiste como overrides.
```

#### Qué hace

Para cada producto del catálogo:
1. Prueba los 3 esquemas (FBA / Easy Ship / Self-Ship en Amazon, o FBN / FBM en Noon).
2. Para cada esquema, busca el **margen máximo** que respeta el techo de catálogo.
3. Elige la **combinación esquema + margen** que maximiza el beneficio por unidad.
4. Persiste el resultado como override para cada SKU.

#### Cómo usarlo

1. Pulsa el botón → aparece la advertencia "¿Confirmas? — pulsa de nuevo".
2. Pulsa de nuevo dentro de 4 segundos para confirmar.
3. Los precios se recalculan y la tabla se actualiza con los valores óptimos.

> **Es una operación destructiva** sobre tus márgenes ajustados manualmente. Si quieres conservar tu configuración actual, **guarda primero un escenario A o B** (sección 6.4).

### 6.4 Escenarios A/B

Te permite guardar dos configuraciones completas (parámetros + márgenes por familia + overrides por SKU) y cargarlas cuando quieras.

```
Slot A                          28/05 18:42        Slot B                  vacío
[Guardar] [Cargar]                                 [Guardar] [Cargar]
```

#### Casos de uso

- **Comparar dos estrategias**: Guarda "Slot A — agresivo 40%" y "Slot B — conservador 15%", carga uno u otro para ver impacto en publicabilidad.
- **Backup antes de optimizar**: Guarda Slot A → ejecuta "Optimización completa" → si el resultado no convence, carga Slot A para volver.
- **Sesiones de revisión**: Guarda un escenario, comparte el dashboard con un compañero, vuelve a tu configuración después.

#### Cómo guardar

1. Pulsa "**Guardar**" en el slot (A o B).
2. El sistema te pide un **nombre opcional** (ej. "Estrategia conservadora").
3. La configuración se guarda con fecha/hora.

#### Cómo cargar

1. Pulsa "**Cargar**" en el slot que quieras restaurar.
2. Se sobreescriben los parámetros, márgenes por familia y overrides actuales.
3. La tabla se recalcula al instante.

> Los escenarios son **por canal y modelo de venta**: el Slot A de "Amazon UAE B2C" es distinto del Slot A de "Amazon UAE B2B".

### 6.5 ⬆ Importar Excel

Sube archivos Excel con datos masivos: o bien catálogo de productos, o bien tarifas logísticas.

```
[ Catálogo ]  [ Logística ]   ← Toggle

[ Elige archivo: producto.xlsx ]

[Vista previa]  [Confirmar]
```

#### Modo "Catálogo"

Para cargar/actualizar precios de compra MT (`pe_eur`), PVP catálogo (`catalog_pvp_eur`), unidades por caja (`units_per_box`) y peso por SKU.

Columnas esperadas en el Excel: `sku`, `pe_eur`, `pvp_eur`, `uds_caja`, `peso_kg`, `ceiling_basis` (opcional).

#### Modo "Logística"

Para cargar tarifas FBA/FBN por SKU: `inbound_fee_aed`, `storage_fee_aed`, `fulfillment_fee_aed`.

#### Flujo Vista previa → Confirmar

1. Selecciona el archivo (máximo 10 MB).
2. Pulsa **Vista previa**: el sistema valida el contenido sin tocar la base de datos. Muestra:
   - Total filas, válidas, errores.
   - Lista de los primeros 5 errores con número de fila + SKU + motivo.
3. Si está OK, pulsa **Confirmar** para persistir los cambios.
4. El catálogo se invalida y recarga.

## 7. Filtros y búsqueda

Encima de la tabla, dispones de tres filtros que se combinan:

| Filtro | Opciones |
|--------|----------|
| **Familia** | Dropdown con todas las familias del canal |
| **Señal** | PÉRDIDA · FRÁGIL · FINO · ÓPTIMO · EXCELENTE |
| **Buscar SKU** | Texto libre (case-insensitive, busca substring) |

Botón **✕ Limpiar** resetea los tres filtros.

> Los filtros afectan **solo a la tabla**, no al semáforo. El contador "Mostrando X de Y" te indica cuántos productos coinciden.

### Las 5 señales de margen

| Señal | Color | Rango |
|-------|-------|-------|
| **PÉRDIDA** | Rojo | margen < 0% |
| **FRÁGIL** | Naranja | 0% ≤ margen < 5% |
| **FINO** | Ámbar | 5% ≤ margen < 15% |
| **ÓPTIMO** | Verde | 15% ≤ margen ≤ 25% |
| **EXCELENTE** | Azul | margen > 25% |

## 8. La tabla principal de productos

```
┌───┬───┬─────────┬─────────┬────────┬───────┬────────┬────────┬────────┬───────┬──────────┐
│ ☐ │ ▸ │ SKU     │ Esquema │ Coste  │ Techo │ Margen │ Precio │ Benef. │ ROI   │ Señal    │
├───┼───┼─────────┼─────────┼────────┼───────┼────────┼────────┼────────┼───────┼──────────┤
│ ☐ │ ▸ │ 4222015 │ FBA     │  9.43  │ 41.82 │[−12+]% │ 16.85  │ +1.85  │ 19.6% │ FINO     │
│ ☑ │ ▸ │ 5120020 │ EasyShp │ 14.21  │ 78.55 │[−25+]% │ 29.12  │ +5.41  │ 38.1% │ EXCELENTE│
└───┴───┴─────────┴─────────┴────────┴───────┴────────┴────────┴────────┴───────┴──────────┘
```

### Columnas

| # | Columna | Significado |
|---|---------|-------------|
| ☐ | Checkbox de selección (para "Proponer a aprobación") |
| ▸ | Botón comparador 3 esquemas (abre modal) |
| SKU | Código del producto MT |
| Esquema | Esquema de fulfillment elegido como óptimo |
| Coste | Coste operacional total en AED (todas las capas 1-4) |
| Techo | Precio máximo permitido en AED (PVP catálogo MT + flete + importación) |
| Margen | Margen objetivo aplicado al producto (editable con stepper) |
| Precio | Precio de venta calculado en AED |
| Benef./ud | Beneficio por unidad en AED (rojo si negativo) |
| ROI | Retorno sobre el coste (%) |
| Señal | Una de las 5 señales (PÉRDIDA…EXCELENTE) |

### Filas

- **Fondo rojo claro** → el producto está bloqueado (precio > techo) o tiene señal PÉRDIDA.
- **Fondo blanco** → publicable.

### Cómo cambiar el margen de un SKU individual

1. Localiza el SKU en la tabla (usa el buscador si es necesario).
2. Pulsa **+** o **−** en la columna "Margen", o escribe el valor.
3. El cambio se aplica al instante (precio, beneficio, ROI, señal se recalculan).
4. Este cambio **persiste como override** — el SKU deja de seguir el margen de su familia.
5. Si quieres devolverlo al margen de familia, cambia el margen de la familia (panel lateral) o usa el botón "Limpiar overrides" (próximamente).

### Cómo seleccionar SKUs

- Click en el **checkbox** de cada fila para seleccionar/deseleccionar.
- Click en el checkbox del header para seleccionar/deseleccionar TODOS los SKUs **visibles** (respeta los filtros).
- Al cambiar de canal, la selección se borra automáticamente.
- Los SKUs seleccionados habilitan el botón "**↑ Proponer N a aprobación**".

## 9. Comparador de esquemas (modal)

Pulsa **▸** al inicio de cualquier fila para abrir el modal comparador.

```
┌─────────────────────────────────────────────────────────────────┐
│  Comparador de esquemas                            [✕ Cerrar]   │
│  SKU 4222015 · modelo B2C                                       │
├─────────────────────┬───────────────────────┬─────────────────-─┤
│  FBA  [Óptimo]      │  Easy Ship            │  Self-Ship        │
├─────────────────────┼───────────────────────┼───────────────────┤
│  Coste op.    9.43  │  Coste op.    14.21   │  Coste op.  16.34 │
│  Precio      16.85  │  Precio       25.42   │  Precio     29.21 │
│  Techo       41.82  │  Techo        41.82   │  Techo      41.82 │
│  Margen        12%  │  Margen         12%   │  Margen       12% │
│  Benef./ud   +1.85  │  Benef./ud    +2.78   │  Benef./ud  +3.20 │
│  ROI         19.6%  │  ROI          19.6%   │  ROI        19.6% │
│  Bajo techo    Sí   │  Bajo techo     Sí    │  Bajo techo   Sí  │
│  Señal       FINO   │  Señal       ÓPTIMO   │  Señal   EXCELENTE│
└─────────────────────┴───────────────────────┴───────────────────┘
```

- El esquema "Óptimo" (el elegido para esa SKU) está marcado con un badge azul y borde resaltado.
- Cierra el modal con **✕**, click fuera del recuadro o tecla **Esc**.
- Útil para entender por qué un esquema fue elegido sobre otro y para discutir alternativas con el equipo.

## 10. Proponer precios al flujo de aprobación

Botón **↑ Proponer N a aprobación** justo encima de la tabla.

```
[ Selecciona SKUs para proponer ]                  ← cuando no hay selección
[ ↑ Proponer 5 a aprobación ]                      ← cuando hay 5 seleccionados
[ ¿Proponer 5? — pulsa de nuevo ]                  ← tras primer click (4s)
[ Enviando… ]                                      ← mientras procesa
```

### Cómo proponer

1. Selecciona los SKUs con los checkboxes (puedes usar filtros + "select all" para selecciones masivas).
2. Pulsa el botón. Aparece confirmación amarilla.
3. Pulsa de nuevo dentro de 4 segundos para confirmar.
4. Espera la respuesta. Verás el resumen: `3 propuestos · 1 omitido · 1 con error`.
5. La selección se limpia automáticamente.

### Qué pasa cuando se propone

Por cada SKU seleccionado, el sistema:
1. Recalcula el precio con los parámetros actuales.
2. Crea un registro en la tabla `prices` con `status='pending_review'`.
3. Adjunta el desglose completo del coste como evidencia en el JSON `breakdown`.

> **Estos precios pasan al flujo de aprobación.** Dirección comercial los revisa en `/precios/aprobaciones` y decide aprobar o rechazar. Si aprueba → el listing queda listo para publicar en Amazon/Noon.

### Razones por las que un SKU queda "omitido"

- El producto no tiene tarifas logísticas para ese canal.
- El producto no existe en la tabla `products`.
- El margen actual produce un precio inviable (k ≤ 0 por comisiones muy altas).

## 11. Flujos de trabajo típicos

### Flujo 1 — Lanzamiento de un catálogo nuevo

1. **Importar catálogo**: panel lateral → ⬆ Importar Excel → modo Catálogo → sube el Excel maestro con `sku`, `pe_eur`, `pvp_eur`, `uds_caja`, `peso_kg`. Vista previa → Confirmar.
2. **Importar logística**: mismo panel → modo Logística → sube tarifas FBA por SKU. Vista previa → Confirmar.
3. **Configurar parámetros**: panel ⚙ Parámetros — actualiza FX, comisión Amazon real, flete del transitario.
4. **Configurar márgenes por familia**: panel "Margen por familia" — ajusta el objetivo de cada familia según tu estrategia.
5. **Guardar escenario base**: panel Escenarios → Guardar Slot A con nombre "Configuración inicial".
6. **Ejecutar Optimización completa**: para que cada SKU tome el mejor esquema + margen automáticamente.
7. **Revisar el semáforo**: ¿cuántos publicables? ¿en pérdida?
8. **Filtrar por señal "PÉRDIDA"**: revisar SKUs problemáticos — decisión: renegociar coste o excluir.
9. **Seleccionar los SKUs publicables** (filtro "Señal" + "ÓPTIMO/EXCELENTE") → **Proponer N a aprobación**.

### Flujo 2 — Simular impacto de subida del IVA

1. Panel ⚙ Parámetros → Comisiones → **IVA UAE**: ajustar al nuevo valor.
2. La tabla se recalcula al instante.
3. Mira el semáforo: ¿cuántos pasaron de publicables a bloqueados?
4. Filtrar por señal PÉRDIDA — ver qué productos quedan inviables.
5. Decisión:
   - Subir margen objetivo de las familias afectadas.
   - O cargar Slot A para revertir el cambio.

### Flujo 3 — Comparar Amazon vs Noon para un producto

1. Localiza el SKU en Amazon UAE (header: Amazon UAE).
2. Apunta su precio, margen, beneficio.
3. Cambia el header a Noon UAE.
4. Filtra/busca el mismo SKU.
5. Compara las cifras → decide en qué canal lo vendes con mejor rentabilidad.

### Flujo 4 — Negociar con MT España

1. Filtra por señal "PÉRDIDA" en Amazon UAE.
2. Toma nota de los SKUs y sus pe_eur (panel ⚙ Parámetros muestra el descuento actual).
3. Calcula cuánto descuento adicional necesitas para que pasen a FRÁGIL/FINO.
4. Una vez negociado, vuelve al Pricing Desk:
   - Importar nuevo Excel de catálogo con `pe_eur` actualizado, o
   - Ajustar manualmente el "Descuento factura" en ⚙ Parámetros para una estimación rápida.

### Flujo 5 — Test A/B antes de proponer

1. Trabaja libremente con la configuración del momento.
2. Guarda Slot A con nombre "Conservador 12-15%".
3. Sube todos los márgenes de familia en +10 puntos.
4. Guarda Slot B con nombre "Agresivo +10%".
5. Cargar Slot A → revisar semáforo.
6. Cargar Slot B → revisar semáforo.
7. Decide cuál promueves al flujo de aprobación.

## 12. Preguntas frecuentes

**P: He clickeado + tres veces en el margen y solo subió uno**
R: Era un bug ya arreglado en la última versión (PR #137). Si te ocurre, recarga la página. Si persiste, reporta al equipo técnico — el síntoma indica que los optimistic updates no están activos.

**P: ¿Por qué hay productos en "Bloqueados"?**
R: Su precio calculado supera el techo de catálogo. Causas comunes:
- Margen objetivo demasiado alto.
- Comisiones del canal demasiado altas.
- Coste de logística inflado.
- Precio de compra (`pe_eur`) demasiado cercano al PVP.

**P: ¿Por qué hay productos "En pérdida" (margen negativo)?**
R: El coste operacional supera lo que se puede facturar. Casi siempre es porque la tarifa de fulfillment FBA del SKU es muy alta para su precio. Decisión: renegociar coste MT o sacar del catálogo.

**P: Cambié el margen de una familia y un SKU no se actualizó**
R: Ese SKU tiene un **override individual**. Para devolverlo al margen de familia, ajusta el margen del SKU a mano, o (próximamente) usa el botón "Limpiar overrides".

**P: Ejecuté Optimización completa y se perdió mi trabajo**
R: La optimización persiste overrides en TODOS los SKUs. Es destructiva. Para evitar esto, **guarda un escenario A antes** de optimizar.

**P: El catálogo en Noon UAE está casi vacío**
R: Probablemente no se han importado tarifas logísticas para ese canal. Solo aparecen en la tabla SKUs con `channel_product_logistics` para el canal seleccionado.

**P: ¿Cuándo es B2C y cuándo B2B?**
R:
- **B2C**: vendes a consumidor final por unidades sueltas (Amazon, Noon). El cliente paga el precio por unidad.
- **B2B**: vendes a cliente industrial por cajas completas (MOQ = `units_per_box`). El cliente paga el precio por caja.

**P: ¿Qué pasa si dos personas estamos editando a la vez?**
R: La última escritura gana. No hay locking. Se recomienda coordinarse en el chat antes de hacer cambios masivos.

**P: ¿Se pueden deshacer cambios?**
R: No hay "undo" directo. Pero:
- Para parámetros individuales: cambia el valor de vuelta a mano.
- Para configuración completa: carga un escenario A o B previo.
- Para overrides masivos: ejecuta de nuevo "Optimización completa" desde el escenario base.

## 13. Glosario

| Término | Definición |
|---------|------------|
| **Canal** | Marketplace donde se vende (Amazon UAE, Noon UAE) |
| **Esquema de fulfillment** | Cómo se hace el almacenamiento + envío: FBA, FBN (canal full), Easy Ship (canal last-mile), Self-Ship, FBM (merchant managed) |
| **PVP catálogo** | Precio de venta al público del catálogo MT España (en EUR) — define el techo |
| **Techo** | Precio máximo en AED al que podemos vender sin competir contra MT España. Calculado como `pvp_eur × fx + flete + arancel` |
| **pe_eur** | Precio de compra unitario a MT España, en EUR, neto antes de descuento |
| **Margen objetivo** | Margen porcentual sobre el precio de venta que queremos obtener |
| **Override** | Margen ajustado a mano para un SKU específico, tiene prioridad sobre el margen de familia |
| **Selling model** | B2C (unidad suelta) o B2B (caja completa) |
| **Pending review** | Estado en que entra un precio al flujo de aprobación tras ser propuesto desde Pricing Desk |
| **Optimistic update** | Técnica UX para reflejar cambios al instante en pantalla, antes de la confirmación del servidor |

## 14. Roles y permisos

| Rol | Permiso | Puede |
|-----|---------|-------|
| **Comercial / lectura** | `prices:read` | Ver el Pricing Desk, navegar, filtrar. No puede cambiar nada. |
| **Analista de pricing** | `prices:propose` | Cambiar parámetros, márgenes, overrides; importar Excel; proponer precios al flujo de aprobación |
| **Director comercial** | `prices:approve` | Aprobar o rechazar precios en `/precios/aprobaciones` (separado del Pricing Desk) |
| **Operador canal** | `prices:publish` | Publicar listings aprobados en Amazon Seller Central / Noon Seller Hub |

> Si necesitas un permiso adicional, contacta con el administrador del sistema. Los permisos se gestionan en la tabla `roles` y se asignan al usuario en su perfil.

---

## Soporte

- **Bugs o mejoras**: abre un issue en el repositorio br-mt-ecommerce.
- **Dudas funcionales**: consulta con el equipo de Pricing.
- **Contexto técnico del flujo**: ver [[2026-05-28-pricing-desk-flujo-sistema]].

---

*Manual escrito el 29 mayo 2026. Versión vigente para PR #134 (v2) + bugfixes #137. Si la pantalla difiere de este manual, es posible que la versión desplegada sea más nueva o más antigua — verifica el commit hash en el footer de la app (si lo tiene) o pregunta a tu administrador.*
