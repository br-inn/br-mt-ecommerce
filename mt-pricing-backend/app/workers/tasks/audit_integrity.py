"""Task Celery — verificación nightly de integridad del hash chain de audit_events.

Task ``audit.nightly_integrity_check`` — registrada en job_definitions con
schedule ``0 3 * * *`` (03:00 Asia/Dubai = 23:00 UTC del día anterior).

Flujo:
1. Rango: ayer 00:00 UTC → ayer 23:59:59.999999 UTC.
2. SELECT todas las filas del rango, ORDER BY id ASC.
3. Recomputa cada hash usando la misma concatenación que el trigger SQL.
4. Si detecta tamper: log CRITICAL.
5. Firma el último ``current_hash`` del rango con HMAC-SHA256 y la
   ``AUDIT_SIGNING_KEY`` de settings.
6. Persiste firma en ``audit_chain_signatures``.
7. Retorna ``{"verified": bool, "rows_checked": int, "tampered_ids": list}``.

ADR-076 / R-005 / VAT UAE 2026.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.workers.worker import celery_app

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------

_SENTINEL_HASH = ""  # valor inicial del chain (igual que seed en audit_hash_state)


def _compute_row_hash(
    row_id: int,
    event_at: datetime,
    actor_id: str | None,
    entity_type: str,
    entity_id: str,
    action: str,
    payload_diff: dict | str | None,
    prev_hash: str,
) -> str:
    """Recomputa el hash de una fila con la misma lógica que el trigger SQL.

    Concatenación idéntica al trigger ``compute_audit_hash()``:
        id || event_at || actor_id || entity_type || entity_id ||
        action || payload_diff || prev_hash

    - ``event_at`` se serializa como Postgres lo haría: isoformat con timezone.
    - ``payload_diff`` se serializa como JSON compacto si es dict, o se usa
      el string directamente (igual que ``COALESCE(NEW.payload_diff::TEXT, '{}')``)
    - Valores NULL → string vacío (COALESCE(x, '')).
    """
    if isinstance(payload_diff, dict):
        payload_str = json.dumps(payload_diff, separators=(",", ":"), sort_keys=True)
    elif payload_diff is None:
        payload_str = "{}"
    else:
        payload_str = str(payload_diff)

    # Postgres muestra TIMESTAMPTZ con offset; Python devuelve isoformat() con +00:00.
    # La concatenación en SQL es: NEW.event_at::TEXT — que usa la representación
    # de la sesión Postgres. Para ser consistentes usamos isoformat() UTC tal como
    # el driver devuelve el valor.
    event_at_str = event_at.isoformat() if event_at is not None else ""

    row_data = (
        (str(row_id) if row_id is not None else "")
        + event_at_str
        + (str(actor_id) if actor_id is not None else "")
        + (entity_type or "")
        + (entity_id or "")
        + (action or "")
        + payload_str
        + (prev_hash or "")
    )
    return hashlib.sha256(row_data.encode()).hexdigest()


def _sign_hash(last_hash: str, signing_key_b64: str) -> str:
    """Genera HMAC-SHA256 del ``last_hash`` usando la clave en base64.

    Retorna la firma en hex. Si ``signing_key_b64`` está vacío retorna
    string vacío (modo dev/sin clave).
    """
    if not signing_key_b64:
        return ""
    import base64

    key_bytes = base64.b64decode(signing_key_b64)
    return hmac.new(key_bytes, last_hash.encode(), hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Lógica de verificación (compartida con el endpoint GET /audit/verify)
# ---------------------------------------------------------------------------


def verify_chain_range(
    conn: Any,
    range_start: datetime,
    range_end: datetime,
) -> dict[str, Any]:
    """Verifica el hash chain para el rango [range_start, range_end).

    Retorna dict con keys: verified, rows_checked, tampered_ids, last_hash.
    Ejecuta con una conexión SQLAlchemy síncrona (para uso en Celery task).
    """
    rows = conn.execute(
        text(
            """
            SELECT id, event_at, actor_id, entity_type, entity_id,
                   action, payload_diff, prev_hash, current_hash
            FROM audit_events
            WHERE event_at >= :start
              AND event_at < :end
            ORDER BY id ASC
            """
        ),
        {"start": range_start, "end": range_end},
    ).fetchall()

    tampered_ids: list[int] = []
    running_hash = _SENTINEL_HASH
    last_hash = _SENTINEL_HASH

    for row in rows:
        expected = _compute_row_hash(
            row_id=row.id,
            event_at=row.event_at,
            actor_id=str(row.actor_id) if row.actor_id is not None else None,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            action=row.action,
            payload_diff=row.payload_diff,
            prev_hash=running_hash,
        )
        if expected != row.current_hash:
            tampered_ids.append(row.id)
            logger.critical(
                "audit.hash_chain.tamper_detected",
                extra={
                    "event_id": row.id,
                    "expected_hash": expected,
                    "stored_hash": row.current_hash,
                },
            )
        # Avanzar el chain usando el stored hash (para detectar todos los tampers,
        # no solo el primero)
        running_hash = row.current_hash or running_hash
        last_hash = row.current_hash or last_hash

    return {
        "verified": len(tampered_ids) == 0,
        "rows_checked": len(rows),
        "tampered_ids": tampered_ids,
        "last_hash": last_hash,
    }


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------


@celery_app.task(
    name="audit.nightly_integrity_check",
    queue="default",
    bind=True,
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def nightly_integrity_check(self: Any) -> dict[str, Any]:  # noqa: ANN001
    """Verifica integridad del hash chain del día anterior y firma el último hash.

    Cron: 0 3 * * * Asia/Dubai (23:00 UTC). Registrado en job_definitions
    via script ``scripts/data/seed_audit_jobs.py``.
    """
    # 1. Rango: ayer 00:00 UTC → ayer 23:59:59.999999 UTC
    today_utc = date.today()
    yesterday = today_utc - timedelta(days=1)
    range_start = datetime(yesterday.year, yesterday.month, yesterday.day, tzinfo=UTC)
    range_end = range_start + timedelta(days=1)

    sync_url = str(settings.ALEMBIC_DATABASE_URL)
    engine = create_engine(sync_url, future=True)

    try:
        with engine.begin() as conn:
            # 2-4. Verificar cadena
            result = verify_chain_range(conn, range_start, range_end)

            rows_checked: int = result["rows_checked"]
            tampered_ids: list[int] = result["tampered_ids"]
            last_hash: str = result["last_hash"]
            verified: bool = result["verified"]

            # 5. Firmar el último hash del rango
            signing_key = settings.AUDIT_SIGNING_KEY.get_secret_value()
            signature = _sign_hash(last_hash, signing_key)

            # 6. Persistir firma en audit_chain_signatures
            conn.execute(
                text(
                    """
                    INSERT INTO audit_chain_signatures
                        (range_start, range_end, last_hash, signature,
                         rows_verified, tampered_count, passed)
                    VALUES
                        (:range_start, :range_end, :last_hash, :signature,
                         :rows_verified, :tampered_count, :passed)
                    """
                ),
                {
                    "range_start": range_start,
                    "range_end": range_end,
                    "last_hash": last_hash,
                    "signature": signature,
                    "rows_verified": rows_checked,
                    "tampered_count": len(tampered_ids),
                    "passed": verified,
                },
            )
    finally:
        engine.dispose()

    out: dict[str, Any] = {
        "verified": verified,
        "rows_checked": rows_checked,
        "tampered_ids": tampered_ids,
        "range_start": range_start.isoformat(),
        "range_end": range_end.isoformat(),
    }
    log_level = logging.INFO if verified else logging.CRITICAL
    logger.log(
        log_level,
        "audit.nightly_integrity_check.done",
        extra=out,
    )
    return out
