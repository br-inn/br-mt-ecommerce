"""force_logout_events — tabla cola para Realtime broadcast (ADR-032).

Sprint 2 — Wave 3 infra. Crea la tabla `public.force_logout_events` que el
backend popula cuando TI Integración revoca un rol o ejecuta force-logout. La
tabla está enrolada en la publication `supabase_realtime`, por lo que cada
INSERT dispara un evento Realtime que el frontend del usuario afectado consume
para deslogarse inmediatamente (sin esperar TTL JWT 1h).

Reglas:
- RLS habilitado: cada user lee solo `user_id = auth.uid()`.
- INSERT solo permitido a `service_role` (backend) — no a usuarios anon/authenticated.
- Cleanup periódico (Celery task `mt.audit.cleanup_force_logout_events`):
  borra rows > 24h. Ver job_definition seed añadido aquí.

Revision ID: 20260507_013
Revises: 20260507_012
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260507_013"
down_revision: str | None = "20260507_012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- Tabla --------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.force_logout_events (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
            reason      TEXT        NOT NULL,
            actor_id    UUID        REFERENCES public.users(id) ON DELETE SET NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_force_logout_user_created
            ON public.force_logout_events (user_id, created_at DESC);
        """
    )

    # ---- Realtime publication ----------------------------------------------
    # `supabase_realtime` es la publication que Supabase configura por defecto.
    # En entornos sin Supabase (testcontainers), envolvemos en bloque DO para
    # no fallar la migration.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
                ALTER PUBLICATION supabase_realtime ADD TABLE public.force_logout_events;
            END IF;
        EXCEPTION
            WHEN duplicate_object THEN
                -- Tabla ya en la publication, ignorar.
                NULL;
        END $$;
        """
    )

    # ---- RLS ----------------------------------------------------------------
    op.execute("ALTER TABLE public.force_logout_events ENABLE ROW LEVEL SECURITY;")

    # User puede leer solo SUS eventos. `auth.uid()` lo provee Supabase Auth en
    # JWT-validated requests; mt_app role hereda el contexto.
    op.execute(
        """
        DROP POLICY IF EXISTS users_read_own_logout_events ON public.force_logout_events;
        CREATE POLICY users_read_own_logout_events
            ON public.force_logout_events
            FOR SELECT
            USING (user_id::text = COALESCE(auth.uid()::text, ''));
        """
    )

    # Solo service_role puede INSERT (backend admin). Bypass RLS efectivo.
    op.execute(
        """
        DROP POLICY IF EXISTS service_role_inserts_logout_events ON public.force_logout_events;
        CREATE POLICY service_role_inserts_logout_events
            ON public.force_logout_events
            FOR INSERT
            TO service_role
            WITH CHECK (true);
        """
    )

    # ---- Seed Celery cleanup job -------------------------------------------
    # Cron 03:00 UTC diario — borra eventos > 24h para evitar growth indefinido.
    op.execute(
        """
        INSERT INTO job_definitions
            (code, task_name, description, owner,
             schedule_type, cron_expression, queue, enabled,
             args, kwargs)
        VALUES
            ('cleanup_force_logout_events',
             'mt.audit.cleanup_force_logout_events',
             'Borra force_logout_events > 24h (ADR-032 cleanup)',
             'infra', 'cron', '0 3 * * *', 'audit', true,
             '[]'::jsonb, '{}'::jsonb)
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # ---- Inicializar next_run_at en jobs sin schedule iniciado --------------
    # DatabaseScheduler (ADR-046) dispara cuando next_run_at <= now(). Para que
    # los jobs ya seed-eados arranquen sin reseed manual, fijamos next_run_at=now().
    op.execute(
        """
        UPDATE public.job_definitions
        SET next_run_at = now()
        WHERE next_run_at IS NULL AND enabled = true;
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM job_definitions WHERE code = 'cleanup_force_logout_events';"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
                ALTER PUBLICATION supabase_realtime DROP TABLE public.force_logout_events;
            END IF;
        EXCEPTION
            WHEN OTHERS THEN
                NULL;
        END $$;
        """
    )
    op.execute("DROP POLICY IF EXISTS users_read_own_logout_events ON public.force_logout_events;")
    op.execute(
        "DROP POLICY IF EXISTS service_role_inserts_logout_events ON public.force_logout_events;"
    )
    op.execute("DROP INDEX IF EXISTS ix_force_logout_user_created;")
    op.execute("DROP TABLE IF EXISTS public.force_logout_events;")
