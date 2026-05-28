# Channel Pricing Engine — Diseño Técnico

**Fecha:** 28 mayo 2026  
**Sprint de análisis:** S17 (propuesto)  
**Canales iniciales:** Amazon UAE · Noon UAE  
**Modelos de venta:** B2C (por unidad) · B2B (por caja)  
**Reemplaza:** `MT_Amazon_UAE_App_Pricing_Desk_260526_1947.html` (herramienta manual standalone)

---

## 1. Contexto y problema

MT Middle East vende productos de MT España en marketplaces de UAE. El equipo usa actualmente un fichero HTML standalone (Pricing Desk) que calcula precios para Amazon UAE con datos hardcodeados. Este fichero:

- No guarda datos entre sesiones
- Solo cubre Amazon UAE (Noon y Tradeling no están modelados)
- Tiene el precio techo precalculado manualmente en el Excel maestro sin reflejar el coste real de traslado España → UAE
- No modela la diferencia B2C (unidades) vs B2B (cajas)
- No tiene trazabilidad de quién cambió qué parámetro ni cuándo

Este diseño reemplaza el Pricing Desk por un módulo nativo en `mt-pricing-backend` + `mt-pricing-frontend`, generalizado para cualquier canal, con fórmulas correctas y persistencia completa.

---

## 2. Conceptos clave

### 2.1 Los cinco estratos del coste

Todo precio de venta en un marketplace se construye apilando cinco estratos:

| Estrato | Qué cubre | Alcance |
|---------|-----------|---------|
| 1 · Compra | Precio neto a MT España | Por producto |
| 2 · Ruta | FX EUR→AED + colchón + flete España→Dubai | Por ruta (es_to_uae) |
| 3 · Importación | Arancel UAE + almacén propio + manipulación | Por destino (uae) |
| 4 · Logística canal | Tarifas fulfillment del canal (FBA/FBN/…) | Por SKU × canal |
| 5 · Comisiones canal | Referral %, IVA, PPC, devoluciones | Por canal |

Los estratos 2 y 3 son **idénticos para Amazon UAE y Noon UAE** (misma ruta, misma aduana). Solo los estratos 4 y 5 cambian entre canales.

### 2.2 Modelos de venta

| Modelo | Unidad | Canal típico | Diferencia en coste |
|--------|--------|-------------|---------------------|
| `b2c` | Unidad suelta | Amazon UAE, Noon UAE, tienda directa | +`b2c_labeling_aed` por unidad (etiquetado y preparación unitaria) |
| `b2b` | Caja completa | Tradeling, clientes directos | Sin coste de preparación unitaria; precio por caja = precio unit × units_per_box |

### 2.3 Esquemas de fulfillment (genéricos)

Tres categorías que cubren todos los canales:

| Esquema genérico | Amazon UAE | Noon UAE | Quién almacena | Quién envía |
|------------------|------------|----------|----------------|-------------|
| `canal_full` | FBA | FBN | Canal | Canal |
| `canal_lastmile` | Easy Ship | — (pendiente confirmar) | MT | Canal |
| `merchant_managed` | Self-Ship | FBM | MT | MT |

### 2.4 Precio techo (ceiling)

El techo es el precio por encima del cual no se puede vender sin que el cliente prefiera comprar directamente de MT España. Se calcula dinámicamente — **no se almacena como valor fijo**.

**B2C:**
```
ceiling_b2c = (catalog_pvp_eur / units_per_box)  # ya es por unidad si ceiling_basis='catalog_pvp'
              × fx_rate
              + freight_per_unit_aed               # flete ÷ unidades_por_caja
              × (1 + import_tariff + local_wh + handling)
              + b2c_labeling_aed
```

**B2B:**
```
ceiling_b2b = catalog_pvp_eur × units_per_box
              × fx_rate
              + freight_per_box_aed
              × (1 + import_tariff + local_wh + handling)
```

**Excepción — `ceiling_basis='margin_floor'`:** productos sin PVP en catálogo MT (ej. válvulas de fondo de cuba). El techo se calcula como el precio mínimo que garantiza un margen fijo configurable (por defecto 35%).

---

## 3. Modelo de datos

### 3.1 Enums PG nuevos

Se crean en la migración **antes** que cualquier columna que los use. En `app/models/enums.py` se declaran con `create_type=False` (patrón del proyecto).

```python
# app/models/enums.py — añadir a los enums existentes

class SellingModel(str, enum.Enum):
    b2c = "b2c"
    b2b = "b2b"

class FulfillmentScheme(str, enum.Enum):
    canal_full      = "canal_full"
    canal_lastmile  = "canal_lastmile"
    merchant_managed = "merchant_managed"

class CeilingBasis(str, enum.Enum):
    catalog_pvp  = "catalog_pvp"
    margin_floor = "margin_floor"
```

### 3.2 Campos nuevos en `products`

```sql
ALTER TABLE products
  ADD COLUMN pe_eur            NUMERIC(14,4),
  ADD COLUMN catalog_pvp_eur   NUMERIC(14,4),
  ADD COLUMN units_per_box     INTEGER DEFAULT 1,
  ADD COLUMN b2c_labeling_aed  NUMERIC(10,4) DEFAULT 0,
  ADD COLUMN ceiling_basis     ceiling_basis NOT NULL DEFAULT 'catalog_pvp';
```

- `pe_eur` — precio de compra a MT España por unidad (neto, antes del descuento `mt_discount_pct`)
- `catalog_pvp_eur` — PVP del catálogo MT por unidad (referencia para el techo)
- `units_per_box` — unidades por caja de MT (MOQ). Para B2C, el flete se divide entre este valor
- `b2c_labeling_aed` — coste de etiquetado y preparación unitaria para canal B2C
- `ceiling_basis` — `catalog_pvp` (normal) | `margin_floor` (sin PVP en catálogo)

### 3.3 `trade_route_params`

Parámetros de coste compartidos por todos los canales que usan la misma ruta de importación. Amazon UAE y Noon UAE comparten la ruta `es_to_uae`.

```sql
CREATE TABLE trade_route_params (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  route_code            TEXT NOT NULL UNIQUE,        -- 'es_to_uae'
  description           TEXT,
  fx_rate               NUMERIC(10,6) NOT NULL,      -- EUR→AED (ej. 4.28)
  fx_buffer_pct         NUMERIC(5,2)  NOT NULL DEFAULT 2,
  freight_rate_per_kg   NUMERIC(8,4)  NOT NULL DEFAULT 0,  -- €/kg; 0 = sin flete modelado aún
  freight_min_aed       NUMERIC(8,2)  NOT NULL DEFAULT 0,  -- mínimo por envío (en AED)
  import_tariff_pct     NUMERIC(5,2)  NOT NULL DEFAULT 4.14,
  local_warehouse_pct   NUMERIC(5,2)  NOT NULL DEFAULT 2,
  handling_pct          NUMERIC(5,2)  NOT NULL DEFAULT 1.5,
  updated_at            TIMESTAMPTZ   NOT NULL DEFAULT now(),
  updated_by            TEXT
);
```

> **Nota flete:** `freight_rate_per_kg` y `freight_min_aed` arrancan en 0 (valor placeholder) hasta que MT confirme la tarifa real del transitario. El motor de cálculo trata 0 como "sin flete" — los precios siguen siendo calculables; solo el techo será ligeramente subestimado hasta tener el dato real.

### 3.4 `channel_fee_params`

Comisiones y parámetros financieros específicos de cada canal. Una fila por canal.

```sql
CREATE TABLE channel_fee_params (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel_id          UUID NOT NULL REFERENCES channels(id) ON DELETE RESTRICT,
  route_id            UUID NOT NULL REFERENCES trade_route_params(id) ON DELETE RESTRICT,
  mt_discount_pct     NUMERIC(5,2)  NOT NULL DEFAULT 15,   -- descuento MT España sobre PVP
  commission_pct      NUMERIC(5,2)  NOT NULL DEFAULT 11,   -- referral Amazon/Noon
  vat_pct             NUMERIC(5,2)  NOT NULL DEFAULT 5,    -- IVA UAE
  advertising_pct     NUMERIC(5,2)  NOT NULL DEFAULT 8,    -- PPC
  returns_pct         NUMERIC(5,2)  NOT NULL DEFAULT 2,    -- provisión devoluciones
  storage_multiplier  NUMERIC(6,4)  NOT NULL DEFAULT 1.0,  -- multiplicador tarifa almacén FBA
  updated_at          TIMESTAMPTZ   NOT NULL DEFAULT now(),
  updated_by          TEXT,
  UNIQUE (channel_id)
);
```

### 3.5 `channel_scheme_params`

Configuración de cada esquema de fulfillment disponible en un canal. Una fila por canal × esquema.

```sql
CREATE TABLE channel_scheme_params (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel_id            UUID NOT NULL REFERENCES channels(id) ON DELETE RESTRICT,
  fulfillment_scheme    fulfillment_scheme NOT NULL,
  scheme_label          TEXT NOT NULL,        -- 'FBA', 'Easy Ship', 'Self-Ship', 'FBN', 'FBM'
  is_available          BOOLEAN NOT NULL DEFAULT true,
  flat_supplement_aed   NUMERIC(8,2) NOT NULL DEFAULT 0,  -- suplemento fijo (ej. Easy Ship: 6 AED)
  pct_surcharge         NUMERIC(5,2) NOT NULL DEFAULT 0,  -- recargo % sobre base (ej. Self-Ship: 15%)
  max_weight_kg         NUMERIC(8,2),                     -- NULL = sin límite; FBA Amazon = 25
  UNIQUE (channel_id, fulfillment_scheme)
);
```

**Datos iniciales Amazon UAE:**

| fulfillment_scheme | scheme_label | flat_supplement_aed | pct_surcharge | max_weight_kg |
|---|---|---|---|---|
| `canal_full` | FBA | 0 | 0 | 25 |
| `canal_lastmile` | Easy Ship | 6.00 | 0 | NULL |
| `merchant_managed` | Self-Ship | 0 | 15 | NULL |

**Datos iniciales Noon UAE:**

| fulfillment_scheme | scheme_label | flat_supplement_aed | pct_surcharge | max_weight_kg |
|---|---|---|---|---|
| `canal_full` | FBN | 0 | 0 | NULL |
| `merchant_managed` | FBM | 0 | 0 | NULL |

### 3.6 `channel_product_logistics`

Tarifas de fulfillment por SKU × canal. Estos datos se importan del Excel maestro o del panel de datos del canal.

```sql
CREATE TABLE channel_product_logistics (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_sku          TEXT NOT NULL REFERENCES products(sku) ON DELETE CASCADE,
  channel_id           UUID NOT NULL REFERENCES channels(id) ON DELETE RESTRICT,
  inbound_fee_aed      NUMERIC(8,4) NOT NULL DEFAULT 0,    -- fba_env / noon_inbound
  storage_fee_aed      NUMERIC(10,4) NOT NULL DEFAULT 0,   -- fba_alm / noon_storage
  fulfillment_fee_aed  NUMERIC(8,4) NOT NULL DEFAULT 0,    -- fba_fee / noon_fulfillment
  default_scheme       fulfillment_scheme NOT NULL DEFAULT 'canal_full',
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_by           TEXT,
  UNIQUE (product_sku, channel_id)
);
```

### 3.7 `channel_margin_targets`

Margen objetivo por canal × familia de producto × modelo de venta. El motor usa este margen como punto de partida si el producto no tiene override.

`family_id` apunta a `families.id` (tabla de vocabulario existente en el proyecto, con `code` y `name`).

```sql
CREATE TABLE channel_margin_targets (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel_id        UUID NOT NULL REFERENCES channels(id) ON DELETE RESTRICT,
  family_id         UUID NOT NULL REFERENCES families(id) ON DELETE RESTRICT,
  selling_model     selling_model NOT NULL DEFAULT 'b2c',
  margin_target_pct NUMERIC(5,2) NOT NULL DEFAULT 12,
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_by        TEXT,
  UNIQUE (channel_id, family_id, selling_model)
);
```

El JOIN para obtener el margen base de un producto:
```sql
SELECT mt.margin_target_pct
FROM   channel_margin_targets mt
WHERE  mt.channel_id   = :channel_id
  AND  mt.family_id    = :product.family_id   -- FK directo, sin string matching
  AND  mt.selling_model = :selling_model
```

### 3.8 `channel_margin_overrides`

Override de margen para un SKU específico. Tiene precedencia sobre el margen de familia. Cuando se cambia el margen de familia, los overrides de esa familia se eliminan (mismo comportamiento que el Pricing Desk original).

```sql
CREATE TABLE channel_margin_overrides (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_sku          TEXT NOT NULL REFERENCES products(sku) ON DELETE CASCADE,
  channel_id           UUID NOT NULL REFERENCES channels(id) ON DELETE RESTRICT,
  selling_model        selling_model NOT NULL DEFAULT 'b2c',
  margin_override_pct  NUMERIC(5,2) NOT NULL,
  reason               TEXT,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by           TEXT,
  UNIQUE (product_sku, channel_id, selling_model)
);
```

### 3.9 `pricing_scenarios`

Snapshots A/B de la configuración completa (parámetros de ruta + comisiones + márgenes por familia + overrides). Permiten comparar dos estrategias antes de proponer precios.

```sql
CREATE TABLE pricing_scenarios (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel_id    UUID NOT NULL REFERENCES channels(id) ON DELETE RESTRICT,
  selling_model selling_model NOT NULL DEFAULT 'b2c',
  slot          CHAR(1) NOT NULL CHECK (slot IN ('A','B')),
  label         TEXT,
  config_jsonb  JSONB NOT NULL,
  snapshot_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by    TEXT,
  UNIQUE (channel_id, selling_model, slot)
);
```

`config_jsonb` guarda un snapshot de: parámetros de ruta, comisiones del canal, márgenes objetivo por familia, y lista de overrides activos.

---

## 4. Plan de migraciones Alembic

### Migración 147 — `20260603_147_channel_pricing_engine`

Una migración única que crea todo. El orden dentro de `upgrade()` es obligatorio por las dependencias de FK y enum.

```python
# alembic/versions/20260603_147_channel_pricing_engine.py
"""channel pricing engine: routes, fees, schemes, logistics, margins, scenarios

Revision ID: 20260603_147
Revises: 20260602_146  (merge_heads_scraper_sources)
"""

def upgrade() -> None:
    # ── 1. Tipos PG (PRIMERO — las columnas los necesitan) ──────────────
    op.execute("CREATE TYPE selling_model AS ENUM ('b2c', 'b2b')")
    op.execute(
        "CREATE TYPE fulfillment_scheme AS ENUM "
        "('canal_full', 'canal_lastmile', 'merchant_managed')"
    )
    op.execute("CREATE TYPE ceiling_basis AS ENUM ('catalog_pvp', 'margin_floor')")

    # ── 2. Campos nuevos en products ────────────────────────────────────
    op.add_column('products', sa.Column('pe_eur', sa.Numeric(14, 4), nullable=True))
    op.add_column('products', sa.Column('catalog_pvp_eur', sa.Numeric(14, 4), nullable=True))
    op.add_column('products', sa.Column('units_per_box', sa.Integer(), server_default='1'))
    op.add_column('products', sa.Column('b2c_labeling_aed', sa.Numeric(10, 4), server_default='0'))
    op.add_column('products', sa.Column(
        'ceiling_basis',
        sa.Enum('catalog_pvp', 'margin_floor', name='ceiling_basis', create_type=False),
        server_default='catalog_pvp', nullable=False
    ))

    # ── 3. trade_route_params ────────────────────────────────────────────
    op.create_table('trade_route_params',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('route_code', sa.Text(), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('fx_rate', sa.Numeric(10, 6), nullable=False),
        sa.Column('fx_buffer_pct', sa.Numeric(5, 2), nullable=False, server_default='2'),
        sa.Column('freight_rate_per_kg', sa.Numeric(8, 4), nullable=False, server_default='0'),
        sa.Column('freight_min_aed', sa.Numeric(8, 2), nullable=False, server_default='0'),
        sa.Column('import_tariff_pct', sa.Numeric(5, 2), nullable=False, server_default='4.14'),
        sa.Column('local_warehouse_pct', sa.Numeric(5, 2), nullable=False, server_default='2'),
        sa.Column('handling_pct', sa.Numeric(5, 2), nullable=False, server_default='1.5'),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_by', sa.Text()),
        sa.UniqueConstraint('route_code', name='uq_trade_route_params_code'),
    )

    # ── 4. channel_fee_params ────────────────────────────────────────────
    op.create_table('channel_fee_params',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('channel_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('route_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('mt_discount_pct', sa.Numeric(5, 2), nullable=False, server_default='15'),
        sa.Column('commission_pct', sa.Numeric(5, 2), nullable=False, server_default='11'),
        sa.Column('vat_pct', sa.Numeric(5, 2), nullable=False, server_default='5'),
        sa.Column('advertising_pct', sa.Numeric(5, 2), nullable=False, server_default='8'),
        sa.Column('returns_pct', sa.Numeric(5, 2), nullable=False, server_default='2'),
        sa.Column('storage_multiplier', sa.Numeric(6, 4), nullable=False, server_default='1.0'),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_by', sa.Text()),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'],
                                name='fk_channel_fee_params_channel'),
        sa.ForeignKeyConstraint(['route_id'], ['trade_route_params.id'],
                                name='fk_channel_fee_params_route'),
        sa.UniqueConstraint('channel_id', name='uq_channel_fee_params_channel'),
    )

    # ── 5. channel_scheme_params ─────────────────────────────────────────
    op.create_table('channel_scheme_params',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('channel_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('fulfillment_scheme',
                  sa.Enum('canal_full', 'canal_lastmile', 'merchant_managed',
                          name='fulfillment_scheme', create_type=False),
                  nullable=False),
        sa.Column('scheme_label', sa.Text(), nullable=False),
        sa.Column('is_available', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('flat_supplement_aed', sa.Numeric(8, 2), nullable=False, server_default='0'),
        sa.Column('pct_surcharge', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('max_weight_kg', sa.Numeric(8, 2)),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'],
                                name='fk_channel_scheme_params_channel'),
        sa.UniqueConstraint('channel_id', 'fulfillment_scheme',
                            name='uq_channel_scheme_params'),
    )

    # ── 6. channel_product_logistics ─────────────────────────────────────
    op.create_table('channel_product_logistics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('product_sku', sa.Text(), nullable=False),
        sa.Column('channel_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('inbound_fee_aed', sa.Numeric(8, 4), nullable=False, server_default='0'),
        sa.Column('storage_fee_aed', sa.Numeric(10, 4), nullable=False, server_default='0'),
        sa.Column('fulfillment_fee_aed', sa.Numeric(8, 4), nullable=False, server_default='0'),
        sa.Column('default_scheme',
                  sa.Enum('canal_full', 'canal_lastmile', 'merchant_managed',
                          name='fulfillment_scheme', create_type=False),
                  nullable=False, server_default='canal_full'),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_by', sa.Text()),
        sa.ForeignKeyConstraint(['product_sku'], ['products.sku'],
                                ondelete='CASCADE',
                                name='fk_channel_product_logistics_sku'),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'],
                                name='fk_channel_product_logistics_channel'),
        sa.UniqueConstraint('product_sku', 'channel_id',
                            name='uq_channel_product_logistics'),
    )

    # ── 7. channel_margin_targets ─────────────────────────────────────────
    op.create_table('channel_margin_targets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('channel_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('selling_model',
                  sa.Enum('b2c', 'b2b', name='selling_model', create_type=False),
                  nullable=False, server_default='b2c'),
        sa.Column('margin_target_pct', sa.Numeric(5, 2), nullable=False, server_default='12'),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_by', sa.Text()),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'],
                                name='fk_channel_margin_targets_channel'),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'],
                                name='fk_channel_margin_targets_family'),
        sa.UniqueConstraint('channel_id', 'family_id', 'selling_model',
                            name='uq_channel_margin_targets'),
    )

    # ── 8. channel_margin_overrides ───────────────────────────────────────
    op.create_table('channel_margin_overrides',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('product_sku', sa.Text(), nullable=False),
        sa.Column('channel_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('selling_model',
                  sa.Enum('b2c', 'b2b', name='selling_model', create_type=False),
                  nullable=False, server_default='b2c'),
        sa.Column('margin_override_pct', sa.Numeric(5, 2), nullable=False),
        sa.Column('reason', sa.Text()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.Text()),
        sa.ForeignKeyConstraint(['product_sku'], ['products.sku'],
                                ondelete='CASCADE',
                                name='fk_channel_margin_overrides_sku'),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'],
                                name='fk_channel_margin_overrides_channel'),
        sa.UniqueConstraint('product_sku', 'channel_id', 'selling_model',
                            name='uq_channel_margin_overrides'),
    )

    # ── 9. pricing_scenarios ──────────────────────────────────────────────
    op.create_table('pricing_scenarios',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('channel_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('selling_model',
                  sa.Enum('b2c', 'b2b', name='selling_model', create_type=False),
                  nullable=False, server_default='b2c'),
        sa.Column('slot', sa.CHAR(1), nullable=False),
        sa.Column('label', sa.Text()),
        sa.Column('config_jsonb', postgresql.JSONB(), nullable=False),
        sa.Column('snapshot_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.Text()),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'],
                                name='fk_pricing_scenarios_channel'),
        sa.CheckConstraint("slot IN ('A','B')", name='ck_pricing_scenarios_slot'),
        sa.UniqueConstraint('channel_id', 'selling_model', 'slot',
                            name='uq_pricing_scenarios_slot'),
    )

    # ── 10. Índices de lookup (críticos para el motor de cálculo) ─────────
    op.create_index('idx_channel_fee_params_channel',
                    'channel_fee_params', ['channel_id'])
    op.create_index('idx_channel_scheme_params_lookup',
                    'channel_scheme_params', ['channel_id', 'fulfillment_scheme'])
    op.create_index('idx_channel_product_logistics_sku_ch',
                    'channel_product_logistics', ['product_sku', 'channel_id'])
    op.create_index('idx_channel_product_logistics_channel',
                    'channel_product_logistics', ['channel_id'])
    op.create_index('idx_channel_margin_targets_lookup',
                    'channel_margin_targets', ['channel_id', 'family_id', 'selling_model'])
    op.create_index('idx_channel_margin_overrides_sku',
                    'channel_margin_overrides', ['product_sku', 'channel_id', 'selling_model'])
    op.create_index('idx_pricing_scenarios_lookup',
                    'pricing_scenarios', ['channel_id', 'selling_model'])


def downgrade() -> None:
    # Índices
    op.drop_index('idx_pricing_scenarios_lookup')
    op.drop_index('idx_channel_margin_overrides_sku')
    op.drop_index('idx_channel_margin_targets_lookup')
    op.drop_index('idx_channel_product_logistics_channel')
    op.drop_index('idx_channel_product_logistics_sku_ch')
    op.drop_index('idx_channel_scheme_params_lookup')
    op.drop_index('idx_channel_fee_params_channel')
    # Tablas (orden inverso por FKs)
    op.drop_table('pricing_scenarios')
    op.drop_table('channel_margin_overrides')
    op.drop_table('channel_margin_targets')
    op.drop_table('channel_product_logistics')
    op.drop_table('channel_scheme_params')
    op.drop_table('channel_fee_params')
    op.drop_table('trade_route_params')
    # Columnas en products
    for col in ['ceiling_basis','b2c_labeling_aed','units_per_box',
                'catalog_pvp_eur','pe_eur']:
        op.drop_column('products', col)
    # Tipos PG (orden inverso)
    op.execute("DROP TYPE IF EXISTS ceiling_basis")
    op.execute("DROP TYPE IF EXISTS fulfillment_scheme")
    op.execute("DROP TYPE IF EXISTS selling_model")
```

---

## 5. Motor de cálculo — `PricingEngine`

### 5.1 Ubicación

```
app/
  services/
    pricing/
      __init__.py
      engine.py          ← PricingEngine (función pura, sin I/O)
      loader.py          ← ParameterLoader (una query JOIN, devuelve dataclasses)
      optimizer.py       ← ChannelOptimizer (envuelve engine, prueba todos los schemes)
      schemas.py         ← PriceInput, PriceResult, CostBreakdown (dataclasses)
```

### 5.2 Fórmula B2C completa

```python
def compute_b2c(
    product: ProductPricingData,
    route: TradeRouteParams,
    fees: ChannelFeeParams,
    scheme_cfg: ChannelSchemeParams,
    logistics: ChannelProductLogistics,
    margin_pct: float,
) -> PriceResult:
    # Capa 1: Compra
    net_eur = product.pe_eur * (1 - fees.mt_discount_pct / 100)
    # Capa 2: Ruta España → Dubai
    fx = route.fx_rate * (1 + route.fx_buffer_pct / 100)
    aed = net_eur * fx
    freight = max(
        route.freight_min_aed / max(product.units_per_box, 1),
        route.freight_rate_per_kg * product.weight_kg * route.fx_rate,
    )
    # Capa 3: Importación UAE
    landed = (aed + freight) * (
        1 + route.import_tariff_pct / 100
          + route.local_warehouse_pct / 100
          + route.handling_pct / 100
    )
    # Capa B2C: preparación unitaria
    cost_pre_channel = landed + product.b2c_labeling_aed
    # Capa 4: Logística del canal
    channel_logistics = _logistics_cost(logistics, scheme_cfg, fees)
    cost_op = cost_pre_channel + channel_logistics
    # Capa 5: Comisiones del canal → sobre el precio de venta
    fees_frac = (fees.commission_pct + fees.vat_pct
                 + fees.advertising_pct + fees.returns_pct) / 100
    k = 1 - fees_frac - margin_pct / 100
    if k <= 0:
        return PriceResult.infeasible(cost_op)
    selling_price = cost_op / k
    # Techo y publicabilidad
    ceiling = _compute_ceiling_b2c(product, route)
    benefit = selling_price * (1 - fees_frac) - cost_op
    roi = (benefit / cost_op * 100) if cost_op > 0 else 0
    return PriceResult(
        selling_price=selling_price,
        ceiling_aed=ceiling,
        cost_op_aed=cost_op,
        benefit_per_unit=benefit,
        roi_pct=roi,
        margin_pct=margin_pct,
        margin_to_ceiling_pct=(ceiling - selling_price) / ceiling * 100 if ceiling > 0 else 0,
        is_publishable=selling_price <= ceiling,
        signal=_signal(margin_pct),
        breakdown=CostBreakdown(
            net_eur=net_eur, fx=fx, freight_aed=freight,
            landed_aed=landed, labeling_aed=product.b2c_labeling_aed,
            channel_logistics_aed=channel_logistics,
            fees_frac=fees_frac, cost_op_aed=cost_op,
        ),
    )
```

### 5.3 Logística del canal según esquema

```python
def _logistics_cost(
    logistics: ChannelProductLogistics,
    scheme: ChannelSchemeParams,
    fees: ChannelFeeParams,
) -> float:
    ff = logistics.fulfillment_fee_aed  # fulfillment fee base (usada por los 3 esquemas)
    if scheme.fulfillment_scheme == FulfillmentScheme.canal_full:
        # FBA / FBN: inbound + storage × multiplicador + fulfillment
        return (
            logistics.inbound_fee_aed
            + logistics.storage_fee_aed * fees.storage_multiplier
            + ff
        )
    elif scheme.fulfillment_scheme == FulfillmentScheme.canal_lastmile:
        # Easy Ship / Noon Express: fulfillment fee + suplemento fijo del canal
        return ff + scheme.flat_supplement_aed
    else:
        # Merchant managed (Self-Ship / FBM): (fulfillment + suplemento) × (1 + recargo %)
        return (ff + scheme.flat_supplement_aed) * (1 + scheme.pct_surcharge / 100)
```

### 5.4 Señales de margen

| Señal | Rango |
|-------|-------|
| `PÉRDIDA` | margen < 0% |
| `FRÁGIL` | 0% ≤ margen < 5% |
| `FINO` | 5% ≤ margen < 15% |
| `ÓPTIMO` | 15% ≤ margen ≤ 25% |
| `EXCELENTE` | margen > 25% |

---

## 6. API Endpoints

Base path: `/api/v1/pricing/{channel_code}`

### Cálculo

| Método | Path | Descripción |
|--------|------|-------------|
| `GET` | `/{channel_code}/product/{sku}` | Precio completo B2C + B2B para un SKU. Query: `?scheme=canal_full&margin_pct=15` |
| `GET` | `/{channel_code}/catalog` | Resumen catálogo completo. Filtros: `?family=&scheme=&signal=&selling_model=b2c` |
| `POST` | `/{channel_code}/optimize` | Optimización: prueba todos los schemes, devuelve mejor combinación. Body: `{"selling_model": "b2c", "skus": null}` |
| `POST` | `/{channel_code}/optimize/apply` | Persiste resultado de optimización como overrides. Rol: `pricing_analyst` |

### Configuración

| Método | Path | Descripción |
|--------|------|-------------|
| `GET` | `/{channel_code}/params` | Devuelve route_params + fee_params + scheme_params del canal |
| `PATCH` | `/{channel_code}/route-params` | Actualiza parámetros de ruta (FX, flete, arancel). Rol: `pricing_admin` |
| `PATCH` | `/{channel_code}/fee-params` | Actualiza comisiones del canal. Rol: `pricing_admin` |
| `PUT` | `/{channel_code}/margin-targets` | Upsert margen objetivo por familia × selling_model. Rol: `pricing_analyst` |
| `PUT` | `/{channel_code}/margin-overrides/{sku}` | Upsert override de margen para un SKU |
| `DELETE` | `/{channel_code}/margin-overrides/{sku}` | Elimina override — el SKU vuelve al margen de familia |

### Escenarios

| Método | Path | Descripción |
|--------|------|-------------|
| `POST` | `/{channel_code}/scenarios/{slot}` | Guarda escenario A o B con snapshot de config actual |
| `GET` | `/{channel_code}/scenarios/compare` | Compara escenarios A vs B producto a producto |
| `POST` | `/{channel_code}/scenarios/{slot}/load` | Restaura config guardada en el escenario |

### Importación de catálogo

| Método | Path | Descripción |
|--------|------|-------------|
| `POST` | `/{channel_code}/catalog/import` | Importa Excel MT (products: pe_eur, catalog_pvp_eur, units_per_box). Devuelve errores + preview de techo calculado antes de confirmar |
| `POST` | `/{channel_code}/logistics/import` | Importa Excel tarifas logísticas por SKU (inbound, storage, fulfillment fees) |

### Flujo de aprobación

| Método | Path | Descripción |
|--------|------|-------------|
| `POST` | `/{channel_code}/prices/propose` | Crea registros en `prices` con `status=pending_review` y `breakdown` JSONB completo |
| `GET` | `/{channel_code}/prices/pending` | Lista precios pendientes de aprobación |
| `POST` | `/{channel_code}/prices/{price_id}/approve` | Aprueba precio → `status=approved`. Rol: `pricing_admin` |
| `POST` | `/{channel_code}/prices/{price_id}/reject` | Rechaza con motivo. Rol: `pricing_admin` |

---

## 7. Proceso de reimportación del catálogo MT

El catálogo actual importado tiene el precio techo mal calculado. El proceso correcto:

```
[Excel MT] → [1. Validar] → [2. Preview techo] → [3. Confirmar] → [4. Upsert products]
              SKU existe?    Calcula ceiling       Usuario ve delta   pe_eur, pvp, uds_caja
              pe > 0?        con params actuales   vs datos actuales
              pvp > pe?
              uds_caja > 0?
```

**Campos requeridos en el Excel de importación:**

| Columna | Campo en BD | Validación |
|---------|-------------|------------|
| `sku` | `products.sku` | Debe existir en BD |
| `pe_eur` | `products.pe_eur` | > 0 |
| `pvp_eur` | `products.catalog_pvp_eur` | > pe_eur |
| `uds_caja` | `products.units_per_box` | ≥ 1, entero |
| `peso_kg` | `products.weight` | > 0 |
| `familia` | Informativo | — |

---

## 8. Frontend — Pricing Desk generalizado

*(Sección pendiente de diseño detallado — se aborda en sprint siguiente)*

El Pricing Desk frontend debe:
- Selector de canal (Amazon UAE / Noon UAE) y modelo de venta (B2C / B2B) en el header
- Semáforo: publicables, bloqueados, en pérdida, por esquema de fulfillment
- Tabla de productos con stepper de margen, selector de esquema (FBA/ES/SS o FBN/FBM), comparador de los 3 esquemas expandible
- Panel lateral: parámetros de ruta + comisiones (colapsable), márgenes por familia, optimización, escenarios A/B, exportación Excel
- Filtros: familia, esquema, señal, estado publicabilidad
- El frontend no recalcula — consume los endpoints del backend

---

## 9. Puntos abiertos (bloquean producción)

| # | Punto | Propietario | Impacto |
|---|-------|-------------|---------|
| 1 | **Tarifa transitario España → Dubai** (`freight_rate_per_kg`) | MT España / ops Dubai | Techo calculado subestimado hasta tener el dato real |
| 2 | **Comisión referral real de Amazon UAE** (actualmente 11%, puede ser 15% según categoría) | MT / Seller Central | 4 puntos de margen en todo el catálogo |
| 3 | **43 referencias de latón en pérdida** | Dirección MT | Decisión: renegociar coste o excluir de Amazon |
| 4 | **Tarifas Noon UAE** (FBN fees por producto) | MT / Noon account | Sin datos → logística Noon iniciará con valores 0 |
| 5 | **Coste etiquetado B2C** (`b2c_labeling_aed`) | Ops Dubai | Hasta definirlo, se puede usar 0 como placeholder |

---

## 10. Testing

- `PricingEngine` es una función pura → tests unitarios con fixtures de dataclasses, sin DB, sin fixtures de SQLAlchemy
- Tests de integración para los endpoints de importación de catálogo (validación de errores, preview de techo)
- Test de regresión: reproducir los 232 productos del Pricing Desk original y verificar que el motor produce los mismos precios con los mismos parámetros
- Cobertura mínima del motor: ≥ 90% (función crítica de negocio)

---

*Spec generado en sesión de brainstorming · Mary (BA) · 28 mayo 2026*  
*Aprobado por: psierra*
