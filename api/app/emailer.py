"""Send invite emails via SMTP, or log/write them locally when SMTP is unset."""

from __future__ import annotations

import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

from app.config import Settings, get_settings
from app.logging import get_logger

logger = get_logger(__name__)


def send_email(
    *,
    to: str,
    subject: str,
    text_body: str,
    settings: Settings | None = None,
) -> str:
    """
    Returns delivery mode: "sent" | "logged".
    """
    settings = settings or get_settings()
    if settings.smtp_configured:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from
        msg["To"] = to
        msg.set_content(text_body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
        logger.info("email_sent", to=to, subject=subject)
        return "sent"

    outbox = Path(settings.local_storage_path).parent / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_to = to.replace("@", "_at_").replace("/", "_")
    path = outbox / f"{stamp}_{safe_to}.txt"
    path.write_text(
        f"To: {to}\nSubject: {subject}\n\n{text_body}\n",
        encoding="utf-8",
    )
    logger.info(
        "email_logged",
        to=to,
        subject=subject,
        path=str(path),
    )
    return "logged"


def student_invite_email(
    *,
    student_email: str,
    project_title: str,
    teacher_name: str,
    invite_url: str,
    settings: Settings | None = None,
) -> str:
    subject = f"You're invited to {project_title} on DataBuddy"
    body = (
        f"Hi,\n\n"
        f"{teacher_name} invited you to the project “{project_title}” on DataBuddy.\n\n"
        f"Create an account or sign in with this email address to join:\n"
        f"{invite_url}\n\n"
        f"If you weren’t expecting this, you can ignore this message.\n"
    )
    return send_email(
        to=student_email, subject=subject, text_body=body, settings=settings
    )
