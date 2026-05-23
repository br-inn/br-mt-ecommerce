"""Celery task: mt.pricing.daily_digest — digest diario 18:00 UAE (US-1B-02-07).

Task name: ``mt.pricing.daily_digest``. Routing queue: ``pricing``.
Schedule: diario 14:00 UTC (18:00 Asia/Dubai) via ``BEAT_SCHEDULE``.

Flujo:
1. DigestService.get_daily_summary(today) → agrega conteos por estado.
2. Crea notificación in-app para todos los usuarios con rol ``gerente_comercial``.
3. Si SMTP_ENABLED=true → envía email con template HTML a los mismos usuarios.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from datetime import date, datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.db.engine import get_sessionmaker
from app.db.models.user import Role, User
from app.repositories.notifications import NotificationsRepository
from app.services.pricing.digest_service import DigestService
from app.workers.worker import celery_app

logger = logging.getLogger(__name__)

DIGEST_NOTIFICATION_KIND = "pricing.daily_digest"
MANAGER_ROLE_CODE = "gerente_comercial"

# Ruta al template HTML (relativa al paquete)
_TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "email" / "daily_digest.html"


def _render_email(summary: dict) -> str:
    """Renderiza el template HTML con valores del summary.

    Usa sustitución simple con ``{{key}}`` para evitar dependencia de Jinja2
    en el worker. Si se requiere lógica condicional compleja, migrar a Jinja2.
    """
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    pending = summary["pending_review"]
    escalated = summary["escalated"]

    # Bloques condicionales simples
    if pending > 0:
        pending_block = (
            f'<p style="color:#e65100;font-size:13px;">'
            f"&#9888; Hay <strong>{pending}</strong> precio(s) pendiente(s) de revisión. "
            f"Por favor revíselos a la brevedad.</p>"
        )
    else:
        pending_block = ""

    if escalated > 0:
        escalated_block = (
            f'<p style="color:#b71c1c;font-size:13px;">'
            f"&#128680; <strong>{escalated}</strong> precio(s) han sido escalados por superar el umbral de espera.</p>"
        )
    else:
        escalated_block = ""

    # Eliminar bloques de plantilla originales (template usa {% if %} que no procesamos)
    import re

    # Quitar bloques {% if ... %} ... {% endif %} del template
    template = re.sub(r"\{%.*?%\}", "", template, flags=re.DOTALL)

    replacements = {
        "{{date}}": summary["date"],
        "{{pending_review}}": str(summary["pending_review"]),
        "{{auto_approved}}": str(summary["auto_approved"]),
        "{{approved}}": str(summary["approved"]),
        "{{escalated}}": str(summary["escalated"]),
        "{{total}}": str(summary["total"]),
        "{{app_url}}": settings.APP_URL,
    }
    for key, val in replacements.items():
        template = template.replace(key, val)

    # Inyectar bloques condicionales tras la tabla
    template = template.replace(
        "<a href=",
        f"{pending_block}{escalated_block}<a href=",
        1,
    )
    return template


def _send_smtp(to_addresses: list[str], summary: dict) -> int:
    """Envía email via SMTP. Retorna cantidad de destinatarios enviados."""
    if not to_addresses:
        return 0

    html_body = _render_email(summary)
    subject = f"[MT Pricing] Digest diario — {summary['date']}"

    sent = 0
    context = ssl.create_default_context() if settings.SMTP_USE_TLS else None

    try:
        smtp_cls = smtplib.SMTP
        with smtp_cls(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            if settings.SMTP_USE_TLS:
                server.starttls(context=context)
            if settings.SMTP_USER:
                server.login(
                    settings.SMTP_USER,
                    settings.SMTP_PASSWORD.get_secret_value(),
                )
            for recipient in to_addresses:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = settings.SMTP_FROM
                msg["To"] = recipient
                msg.attach(MIMEText(html_body, "html", "utf-8"))
                server.sendmail(settings.SMTP_FROM, [recipient], msg.as_string())
                sent += 1
    except Exception:
        logger.exception("daily_digest: error enviando email SMTP")

    return sent


async def _run_async(target_date: date) -> dict:
    Session = get_sessionmaker()
    async with Session() as session:
        # 1. Calcular summary
        digest_svc = DigestService(session)
        summary = await digest_svc.get_daily_summary(target_date)

        # 2. Buscar usuarios con rol gerente_comercial
        stmt = (
            select(User)
            .join(Role, User.role_id == Role.id)
            .where(Role.code == MANAGER_ROLE_CODE)
            .where(User.is_active.is_(True))
        )
        result = await session.execute(stmt)
        managers: list[User] = list(result.scalars())

        # 3. Notificación in-app
        notif_repo = NotificationsRepository(session)
        for manager in managers:
            await notif_repo.create(
                recipient_user_id=manager.id,
                kind=DIGEST_NOTIFICATION_KIND,
                payload=summary,
            )

        await session.commit()

        # 4. Email opcional (fuera del commit — best-effort)
        emails_sent = 0
        if settings.SMTP_ENABLED and managers:
            emails = [m.email for m in managers if m.email]
            emails_sent = _send_smtp(emails, summary)

        return {
            **summary,
            "notifications_created": len(managers),
            "emails_sent": emails_sent,
        }


@celery_app.task(
    name="mt.pricing.daily_digest",
    queue="pricing",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def daily_digest(
    self: Any,  # noqa: ANN401 — celery bound task
    target_date_iso: str | None = None,
) -> dict:
    """Genera y distribuye el digest diario de precios.

    Args:
        target_date_iso: fecha ISO-8601 opcional (e.g. "2026-05-12"). Si None,
            usa la fecha UTC actual. Útil para re-runs manuales o tests.
    """
    target = (
        date.fromisoformat(target_date_iso)
        if target_date_iso
        else datetime.now(tz=timezone.utc).date()
    )
    result = asyncio.run(_run_async(target))
    logger.info(
        "daily_digest: date=%s pending=%d auto_approved=%d approved=%d escalated=%d notifications=%d emails=%d",
        result["date"],
        result["pending_review"],
        result["auto_approved"],
        result["approved"],
        result["escalated"],
        result["notifications_created"],
        result["emails_sent"],
    )
    return result


__all__ = ["daily_digest"]
