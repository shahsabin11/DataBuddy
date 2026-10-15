"""FastAPI dependencies: session verification + RLS context."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.session import parse_session_token
from app.config import get_settings
from app.db import AdminSessionLocal, AppSessionLocal, SessionLocal
from app.tenancy import TenantContext, set_rls_context


@dataclass(frozen=True, slots=True)
class AuthUser:
    user_id: uuid.UUID
    email: str
    institution_id: uuid.UUID | None
    role: str
    status: str

    @property
    def is_platform_admin(self) -> bool:
        return self.role == "platform_admin"

    @property
    def is_pending(self) -> bool:
        return self.role == "pending" or self.status in {
            "pending",
            "institution_inactive",
        }

    @property
    def is_institution_admin(self) -> bool:
        return self.role == "institution_admin"

    def as_tenant_context(self) -> TenantContext:
        if self.institution_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No active institution membership.",
            )
        rls_role = self.role
        if rls_role == "platform_admin":
            rls_role = "institution_admin"
        return TenantContext(
            user_id=self.user_id,
            institution_id=self.institution_id,
            role=rls_role,
        )


def get_current_user(request: Request) -> AuthUser:
    """
    Verify the HTTP-only session cookie issued by FastAPI.

    institution_id and role come only from the signed cookie, never from
    query/body parameters.
    """
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not signed in.",
        )
    try:
        payload = parse_session_token(token, settings=settings)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    return AuthUser(
        user_id=payload.user_id,
        email=payload.email,
        institution_id=payload.institution_id,
        role=payload.role,
        status=payload.status,
    )


def require_member(user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
    if user.institution_id is None or user.role == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": user.status,
                "message": (
                    "Your institution isn't on DataBuddy yet — request access."
                    if user.status == "pending"
                    else "Your institution is inactive. Contact your admin."
                ),
            },
        )
    if user.role not in {"student", "institution_admin", "platform_admin"}:
        raise HTTPException(status_code=403, detail="Insufficient role.")
    return user


def require_institution_admin(
    user: Annotated[AuthUser, Depends(require_member)],
) -> AuthUser:
    if user.role not in {"institution_admin", "platform_admin"}:
        raise HTTPException(status_code=403, detail="Institution admin required.")
    return user


def require_platform_admin(
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> AuthUser:
    if not user.is_platform_admin:
        raise HTTPException(status_code=403, detail="Platform admin required.")
    return user


def get_app_db_with_rls(
    user: Annotated[AuthUser, Depends(require_member)],
) -> Generator[Session, None, None]:
    """App DB role + SET LOCAL from verified session (never from the client)."""
    db = AppSessionLocal()
    try:
        set_rls_context(db, user.as_tenant_context())
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_admin_db(
    _user: Annotated[AuthUser, Depends(require_platform_admin)],
) -> Generator[Session, None, None]:
    """BYPASSRLS connection for platform-admin routes only."""
    db = AdminSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_owner_db() -> Generator[Session, None, None]:
    """Owner connection for auth provisioning before an RLS context exists."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
