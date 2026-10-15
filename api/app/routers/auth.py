"""OAuth start/callback and session endpoints."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import AuthUser, get_current_user, get_owner_db
from app.auth.oauth import (
    OAuthError,
    exchange_google_code,
    exchange_microsoft_code,
    google_authorize_url,
    microsoft_authorize_url,
    new_state,
)
from app.auth.provisioning import (
    AuthProvisionError,
    provision_from_claims,
    provision_teacher_from_claims,
)
from app.auth.session import issue_session_token
from app.config import get_settings
from app.logging import get_logger
from app.models import AccessRequest

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)

# In-memory OAuth state for v1 (single-process). Replace with Redis later.
_oauth_states: dict[str, dict[str, str | None]] = {}
_PORTALS = frozenset({"student", "teacher"})


class MeResponse(BaseModel):
    user_id: str
    email: str
    institution_id: str | None
    role: str
    status: str


class AccessRequestBody(BaseModel):
    message: str | None = Field(default=None, max_length=2000)
    institution_slug: str | None = Field(default=None, max_length=80)


def _normalize_portal(portal: str | None) -> str:
    if portal and portal in _PORTALS:
        return portal
    return "student"


def _store_oauth_state(
    *, portal: str | None, invite: str | None = None
) -> str:
    state = new_state()
    _oauth_states[state] = {
        "portal": _normalize_portal(portal),
        "invite": invite or None,
    }
    return state


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        max_age=60 * 60 * 24 * 14,
        path="/",
    )


def _set_portal_cookie(response: Response, portal: str) -> None:
    """Remember which dashboard the user chose at sign-in (not an auth role)."""
    settings = get_settings()
    response.set_cookie(
        key="databuddy_portal",
        value=portal,
        httponly=False,
        secure=settings.environment == "production",
        samesite="lax",
        max_age=60 * 60 * 24 * 14,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie("databuddy_portal", path="/")


def _post_login_redirect(status: str, portal: str) -> str:
    settings = get_settings()
    if status == "pending":
        return f"{settings.app_url}/pending"
    if status == "institution_inactive":
        return f"{settings.app_url}/pending?reason=inactive"
    if portal == "teacher":
        return f"{settings.app_url}/teacher"
    return f"{settings.app_url}/workspace"


@router.get("/google/start")
def google_start(
    portal: str | None = None,
    invite: str | None = None,
) -> RedirectResponse:
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(503, detail="Google OAuth is not configured.")
    state = _store_oauth_state(portal=portal, invite=invite)
    return RedirectResponse(google_authorize_url(state, settings))


@router.get("/microsoft/start")
def microsoft_start(
    portal: str | None = None,
    invite: str | None = None,
) -> RedirectResponse:
    settings = get_settings()
    if not settings.microsoft_client_id:
        raise HTTPException(503, detail="Microsoft OAuth is not configured.")
    state = _store_oauth_state(portal=portal, invite=invite)
    return RedirectResponse(microsoft_authorize_url(state, settings))


@router.get("/google/callback")
def google_callback(
    db: Annotated[Session, Depends(get_owner_db)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    return _finish_oauth(
        provider="google", code=code, state=state, error=error, db=db
    )


@router.get("/microsoft/callback")
def microsoft_callback(
    db: Annotated[Session, Depends(get_owner_db)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    return _finish_oauth(
        provider="microsoft", code=code, state=state, error=error, db=db
    )


def _finish_oauth(
    *,
    provider: str,
    code: str | None,
    state: str | None,
    error: str | None,
    db: Session,
) -> RedirectResponse:
    settings = get_settings()
    if error:
        return RedirectResponse(
            f"{settings.app_url}/login?{urlencode({'error': error})}"
        )
    if not code or not state or state not in _oauth_states:
        return RedirectResponse(
            f"{settings.app_url}/login?{urlencode({'error': 'invalid_state'})}"
        )
    state_data = _oauth_states.pop(state)
    portal = _normalize_portal(
        state_data.get("portal") if isinstance(state_data, dict) else state_data
    )
    invite_token = (
        state_data.get("invite") if isinstance(state_data, dict) else None
    )

    try:
        if provider == "google":
            claims = exchange_google_code(code, settings)
        else:
            claims = exchange_microsoft_code(code, settings)
        if portal == "teacher":
            result = provision_teacher_from_claims(db, claims)
        else:
            result = provision_from_claims(
                db, claims, invite_token=invite_token
            )
        db.commit()
    except (OAuthError, AuthProvisionError) as exc:
        code_name = getattr(exc, "code", "auth_failed")
        logger.warning("oauth_failed", provider=provider, code=code_name)
        return RedirectResponse(
            f"{settings.app_url}/login?{urlencode({'error': code_name})}"
        )
    except Exception as exc:
        db.rollback()
        logger.exception("oauth_unexpected_error", provider=provider, error=str(exc))
        return RedirectResponse(
            f"{settings.app_url}/login?{urlencode({'error': 'auth_failed'})}"
        )

    token = issue_session_token(result.payload, settings)
    response = RedirectResponse(
        _post_login_redirect(result.payload.status, portal)
    )
    _set_session_cookie(response, token)
    _set_portal_cookie(response, portal)
    return response


@router.get("/me", response_model=MeResponse)
def me(user: Annotated[AuthUser, Depends(get_current_user)]) -> MeResponse:
    return MeResponse(
        user_id=str(user.user_id),
        email=user.email,
        institution_id=str(user.institution_id) if user.institution_id else None,
        role=user.role,
        status=user.status,
    )


@router.post("/logout")
def logout() -> Response:
    response = Response(status_code=204)
    _clear_session_cookie(response)
    return response


@router.post("/access-request")
def submit_access_request(
    body: AccessRequestBody,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_owner_db)],
) -> dict:
    """Pending users can add a note / preferred institution slug."""
    from sqlalchemy import select

    from app.models import Institution

    req = db.scalar(
        select(AccessRequest).where(
            AccessRequest.user_id == user.user_id,
            AccessRequest.status == "pending",
        )
    )
    if req is None:
        raise HTTPException(404, detail="No pending access request.")
    if body.message is not None:
        req.message = body.message
    if body.institution_slug:
        inst = db.scalar(
            select(Institution).where(Institution.slug == body.institution_slug)
        )
        if inst is not None:
            req.institution_id = inst.id
    db.add(req)
    db.commit()
    return {"status": "ok", "access_request_id": str(req.id)}
