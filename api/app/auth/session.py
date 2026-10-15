"""HTTP-only signed session cookies (never trust client-supplied institution_id)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import Settings, get_settings

SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 14  # 14 days


@dataclass(frozen=True, slots=True)
class SessionPayload:
    user_id: uuid.UUID
    email: str
    institution_id: uuid.UUID | None
    role: str  # student | institution_admin | platform_admin | pending
    status: str  # active | pending | institution_inactive


def _serializer(settings: Settings | None = None) -> URLSafeTimedSerializer:
    settings = settings or get_settings()
    return URLSafeTimedSerializer(
        secret_key=settings.session_secret,
        salt="databuddy-session-v1",
    )


def issue_session_token(payload: SessionPayload, settings: Settings | None = None) -> str:
    data: dict[str, Any] = {
        "user_id": str(payload.user_id),
        "email": payload.email,
        "institution_id": str(payload.institution_id) if payload.institution_id else None,
        "role": payload.role,
        "status": payload.status,
    }
    return _serializer(settings).dumps(data)


def parse_session_token(
    token: str, settings: Settings | None = None
) -> SessionPayload:
    settings = settings or get_settings()
    try:
        data = _serializer(settings).loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except SignatureExpired as exc:
        raise ValueError("session_expired") from exc
    except BadSignature as exc:
        raise ValueError("session_invalid") from exc

    institution_raw = data.get("institution_id")
    return SessionPayload(
        user_id=uuid.UUID(data["user_id"]),
        email=str(data["email"]),
        institution_id=uuid.UUID(institution_raw) if institution_raw else None,
        role=str(data["role"]),
        status=str(data["status"]),
    )
