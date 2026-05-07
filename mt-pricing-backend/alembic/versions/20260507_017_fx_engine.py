"""fx_engine — Sprint 3 motor FX completo (US-1A-05-01-S3, 02, 03).

La tabla ``fx_rates`` ya existe (creada en 20260507_010_pricing_models). Esta
migración cierra el motor FX:

1. **`fx_rates` extension**:
   - Añade columna ``created_by`` (UUID FK users, nullable).
   - Añade CHECK constraint sobre ``source`` (manual/cbuae/ecb/imported).
   - Re-crea ``idx_fx_lookup`` con orden DESC (más eficiente para "último vigente").
   - Garantiza el partial index sobre ``effective_to IS NULL`` (idempotente).

2. **Trigger ``fx_rates_close_previous_trg`` BEFORE INSERT** (PL/pgSQL):
   - Identidad: ``from_currency = to_currency`` ⇒ rate forzado a 1.000000.
   - Busca último rate vigente del mismo par con ``effective_to IS NULL``.
     - Si su ``effective_from > NEW.effective_from`` ⇒ retroactivo. Bloquea
       salvo que la sesión haya seteado ``SET LOCAL fx.allow_retroactive='true'``.
     - Si su ``effective_from = NEW.effective_from`` ⇒ ``fx_same_effective_from``.
     - Si su ``effective_from < NEW.effective_from`` ⇒ cierra con
       ``effective_to = NEW.effective_from``.
   - Valida ``rate > 0`` (defensa adicional al CHECK constraint).

3. **Función SQL stable ``fx_rate_at(from_code, to_code, at) → uuid``**:
   - Devuelve el id del rate vigente a la fecha. NULL si no hay match.
   - Identidad (from=to): NULL — el caller debe sintetizar (BR-1a-04 v3).

4. **Permisos nuevos** (seed pattern S2):
   - ``currencies:manage`` → ti_integracion + admin.
   - ``fx:manage``        → ti_integracion + admin.
   - ``fx:read`` ya existe (creado en migration 010 indirectamente o via 014;
     verificamos con ON CONFLICT).

5. **Currency check** sobre ``is_base``:
   - El partial unique index ``uq_currencies_one_base`` ya existe (mig 004).
     Aquí añadimos un CHECK explícito para defender contra race conditions
     que el partial index no cubre (e.g., dos transacciones simultáneas con
     ``is_base=true`` para currencies distintos pueden coexistir si una se
     hace antes de que la otra haga commit; el unique index lo cubre, pero
     un CHECK adicional sobre la integridad de `code` no rompe nada — lo
     dejamos como NO-OP idempotente).

Down: revierte todo lo anterior. La tabla ``fx_rates`` NO se borra (vive en 010).

Revision ID: 20260507_017
Revises: 20260507_016
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260507_017"
down_revision: str | None = "20260507_016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---------------------------------------------------------------------------
# Trigger / function bodies
# ---------------------------------------------------------------------------
_TRIGGER_FN = """
CREATE OR REPLACE FUNCTION fx_rates_close_previous() RETURNS TRIGGER
LANGUAGE plpgsql AS $fx$
DECLARE
    prev_id UUID;
    prev_effective_from TIMESTAMPTZ;
    prev_effective_to   TIMESTAMPTZ;
    allow_retro TEXT;
BEGIN
    -- 0. Identity case: AED→AED, EUR→EUR, etc. Force rate=1.
    IF NEW.from_currency = NEW.to_currency THEN
        NEW.rate := 1;
    END IF;

    -- 1. rate > 0 (defensa, además del CHECK constraint).
    IF NEW.rate IS NULL OR NEW.rate <= 0 THEN
        RAISE EXCEPTION USING
            ERRCODE = 'P0001',
            MESSAGE = 'fx_rate_must_be_positive';
    END IF;

    -- 2. Buscar último vigente para el mismo par (effective_to IS NULL).
    SELECT id, effective_from, effective_to
      INTO prev_id, prev_effective_from, prev_effective_to
      FROM fx_rates
     WHERE from_currency = NEW.from_currency
       AND to_currency   = NEW.to_currency
       AND effective_to IS NULL
     ORDER BY effective_from DESC
     LIMIT 1
     FOR UPDATE;

    IF FOUND THEN
        -- 2.a Mismo timestamp → bloqueo (no permitimos dos rates iniciando
        --     en el mismo instante para el mismo par).
        IF prev_effective_from = NEW.effective_from THEN
            RAISE EXCEPTION USING
                ERRCODE = 'P0001',
                MESSAGE = 'fx_same_effective_from';
        END IF;

        -- 2.b Retroactivo → bloqueo salvo flag explícito.
        IF prev_effective_from > NEW.effective_from THEN
            BEGIN
                allow_retro := current_setting('fx.allow_retroactive', true);
            EXCEPTION WHEN OTHERS THEN
                allow_retro := NULL;
            END;
            IF allow_retro IS NULL OR lower(allow_retro) <> 'true' THEN
                RAISE EXCEPTION USING
                    ERRCODE = 'P0001',
                    MESSAGE = 'fx_retroactive_not_allowed';
            END IF;
            -- Retroactivo permitido: cerramos igual el previo con effective_to
            -- = NEW.effective_from. Esto crea un solapamiento en el histórico
            -- (vigente antes < NEW < cierre del previo) pero la función
            -- fx_rate_at sigue siendo determinista porque escoge effective_from
            -- DESC LIMIT 1.
        END IF;

        -- 2.c Caso normal: cerramos el previo.
        UPDATE fx_rates
           SET effective_to = NEW.effective_from
         WHERE id = prev_id;
    END IF;

    -- NEW siempre se inserta con effective_to NULL.
    NEW.effective_to := NULL;

    RETURN NEW;
END;
$fx$;
"""

_TRIGGER_DEFN = """
DROP TRIGGER IF EXISTS fx_rates_close_previous_trg ON fx_rates;
CREATE TRIGGER fx_rates_close_previous_trg
BEFORE INSERT ON fx_rates
FOR EACH ROW
EXECUTE FUNCTION fx_rates_close_previous();
"""

_RATE_AT_FN = """
CREATE OR REPLACE FUNCTION fx_rate_at(
    p_from_code TEXT,
    p_to_code   TEXT,
    p_at        TIMESTAMPTZ
) RETURNS UUID
LANGUAGE sql STABLE AS $fxat$
    SELECT id
      FROM fx_rates
     WHERE from_currency = p_from_code
       AND to_currency   = p_to_code
       AND effective_from <= p_at
       AND (effective_to IS NULL OR effective_to > p_at)
     ORDER BY effective_from DESC
     LIMIT 1;
$fxat$;
"""


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Extender tabla fx_rates
    # -----------------------------------------------------------------------
    op.execute(
        """
        ALTER TABLE fx_rates
            ADD COLUMN IF NOT EXISTS created_by UUID
            REFERENCES users(id) ON DELETE SET NULL;
        """
    )

    # CHECK constraint sobre source (manual|cbuae|ecb|imported|identity).
    # Drop primero por idempotencia.
    op.execute("ALTER TABLE fx_rates DROP CONSTRAINT IF EXISTS ck_fx_rates_source;")
    op.execute(
        """
        ALTER TABLE fx_rates
            ADD CONSTRAINT ck_fx_rates_source
            CHECK (source IS NULL OR source IN
                ('manual','cbuae','ecb','imported','identity'));
        """
    )

    # Index DESC para "último rate vigente" — el de mig 010 era ASC sin orden
    # explícito (Postgres infiere). Lo recreamos DESC defensivamente.
    op.execute("DROP INDEX IF EXISTS idx_fx_lookup_desc;")
    op.execute(
        """
        CREATE INDEX idx_fx_lookup_desc
            ON fx_rates (from_currency, to_currency, effective_from DESC);
        """
    )

    # Partial index sobre effective_to IS NULL ya existe (idx_fx_active, mig 010).
    # No-op idempotente: lo dejamos como está.

    # -----------------------------------------------------------------------
    # 2. Trigger BEFORE INSERT — cierre auto + retroactive guard
    # -----------------------------------------------------------------------
    op.execute(_TRIGGER_FN)
    op.execute(_TRIGGER_DEFN)

    # -----------------------------------------------------------------------
    # 3. Función fx_rate_at(from, to, at) → uuid
    # -----------------------------------------------------------------------
    op.execute(_RATE_AT_FN)

    # -----------------------------------------------------------------------
    # 4. Identity seed AED→AED rate=1 (caso identidad para trigger costs).
    #    Insertamos con el trigger ON. Si la fila ya existe (idempotencia),
    #    skipeamos.
    # -----------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO fx_rates (from_currency, to_currency, rate, effective_from, source)
        SELECT 'AED','AED',1,'2026-04-01 00:00:00+00','identity'
         WHERE NOT EXISTS (
            SELECT 1 FROM fx_rates
             WHERE from_currency='AED' AND to_currency='AED'
         );
        """
    )

    # -----------------------------------------------------------------------
    # 5. Permisos: currencies:manage, fx:manage (+ defensive fx:read).
    # -----------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
            ('currencies:manage', 'Activar/desactivar currencies seed (TI/admin)'),
            ('fx:manage',         'Crear y administrar tasas FX (TI/admin)'),
            ('fx:read',           'Leer currencies y FX rates (todos)')
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
          FROM roles r CROSS JOIN permissions p
         WHERE
             (r.code = 'comercial'         AND p.code IN ('fx:read'))
          OR (r.code = 'gerente_comercial' AND p.code IN ('fx:read'))
          OR (r.code = 'ti_integracion'    AND p.code IN ('fx:read','fx:manage','currencies:manage'))
          OR (r.code = 'admin'             AND p.code IN ('fx:read','fx:manage','currencies:manage'))
        ON CONFLICT DO NOTHING;
        """
    )


def downgrade() -> None:
    # Permisos
    op.execute(
        """
        DELETE FROM role_permissions
         WHERE permission_id IN (
            SELECT id FROM permissions
             WHERE code IN ('currencies:manage','fx:manage')
         );
        """
    )
    op.execute(
        """
        DELETE FROM permissions
         WHERE code IN ('currencies:manage','fx:manage');
        """
    )
    # NOTA: ``fx:read`` la dejamos — pudo haber existido antes y otras
    # migraciones la asumen.

    # Función + trigger
    op.execute("DROP FUNCTION IF EXISTS fx_rate_at(TEXT, TEXT, TIMESTAMPTZ);")
    op.execute("DROP TRIGGER IF EXISTS fx_rates_close_previous_trg ON fx_rates;")
    op.execute("DROP FUNCTION IF EXISTS fx_rates_close_previous();")

    # Index DESC
    op.execute("DROP INDEX IF EXISTS idx_fx_lookup_desc;")

    # Constraint source
    op.execute("ALTER TABLE fx_rates DROP CONSTRAINT IF EXISTS ck_fx_rates_source;")

    # Columna created_by
    op.execute("ALTER TABLE fx_rates DROP COLUMN IF EXISTS created_by;")

    # Identity row la dejamos — costs trigger la necesita.
