"""
Map a verified OAuth identity to a DataBuddy user + institution.

No campus domain is hardcoded. Matching is an exact lookup in institution_domains.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.claims import IdentityClaims, email_domain
from app.auth.session import SessionPayload
from app.invites import accept_invites_for_user
from app.models import (
    AccessRequest,
    BlockedEmailDomain,
    Institution,
    InstitutionBudget,
    InstitutionDomain,
    Membership,
    PlatformAdmin,
    User,
)
from app.models.enums import MembershipRole, MembershipStatus, OAuthProvider


@dataclass(frozen=True, slots=True)
class ProvisionResult:
    user: User
    payload: SessionPayload
    created_user: bool
    created_membership: bool
    access_request: AccessRequest | None


class AuthProvisionError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _active_membership(db: Session, user_id: uuid.UUID) -> Membership | None:
    now = datetime.now(UTC)
    rows = db.scalars(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.status == MembershipStatus.ACTIVE.value,
        )
    ).all()
    active: list[Membership] = []
    for m in rows:
        if m.ends_at is not None and m.ends_at <= now:
            continue
        inst = db.get(Institution, m.institution_id)
        if inst is None or not inst.is_active:
            continue
        active.append(m)
    if not active:
        return None
    # Session stores exactly one institution; prefer the oldest membership.
    return sorted(active, key=lambda m: m.starts_at)[0]


def lookup_institution_for_email(
    db: Session,
    *,
    email: str,
    entra_tenant_id: str | None,
) -> Institution | None:
    """
    Exact domain match only. students.uni.edu does not match uni.edu.
    Blocked consumer domains never auto-attach.
    Microsoft: if the institution lists Entra tenants, tid must be in that list.
    """
    domain = email_domain(email)
    if db.get(BlockedEmailDomain, domain) is not None:
        return None

    mapping = db.scalar(
        select(InstitutionDomain).where(
            InstitutionDomain.domain == domain,
            InstitutionDomain.is_approved.is_(True),
        )
    )
    if mapping is None:
        return None

    institution = db.get(Institution, mapping.institution_id)
    if institution is None:
        return None

    if entra_tenant_id and institution.allowed_entra_tenant_ids:
        if entra_tenant_id not in institution.allowed_entra_tenant_ids:
            return None

    return institution


def _upsert_user_from_claims(
    db: Session, claims: IdentityClaims
) -> tuple[User, bool]:
    """Create or update the global users row. Returns (user, created)."""
    if not claims.email or "@" not in claims.email:
        raise AuthProvisionError("missing_email", "Provider did not return an email.")
    if not claims.email_verified:
        raise AuthProvisionError(
            "email_unverified",
            "Sign in with a verified email address from your provider.",
        )

    email = claims.email.strip().lower()
    user = db.scalar(
        select(User).where(
            User.oauth_provider == claims.provider,
            User.provider_subject == claims.subject,
        )
    )
    if user is None:
        existing_email = db.scalar(select(User).where(User.email == email))
        if existing_email is not None:
            raise AuthProvisionError(
                "email_in_use",
                "This email is already linked to another sign-in method.",
            )
        user = User(
            oauth_provider=claims.provider,
            provider_subject=claims.subject,
            email=email,
            display_name=claims.name,
            last_login_at=datetime.now(UTC),
        )
        db.add(user)
        db.flush()
        return user, True

    user.email = email
    user.display_name = claims.name or user.display_name
    user.last_login_at = datetime.now(UTC)
    return user, False


def _create_teacher_campus(db: Session, *, user: User) -> Institution:
    """
    Teachers own their campus in v1 (no platform-admin approval gate).

    Consumer mailbox domains are never added to institution_domains.
    """
    local = user.email.split("@", 1)[0]
    safe = "".join(c if c.isalnum() else "-" for c in local.lower())[:40].strip("-")
    slug = f"t-{safe}-{uuid.uuid4().hex[:6]}"
    label = (user.display_name or local).strip() or "Teacher"
    inst = Institution(
        name=f"{label}'s class",
        slug=slug,
        is_active=True,
        allowed_entra_tenant_ids=[],
    )
    db.add(inst)
    db.flush()
    db.add(
        InstitutionBudget(
            institution_id=inst.id,
            token_budget_usd=250,
            user_token_budget_usd=50,
            enforce_institution_budget=False,
        )
    )
    domain = email_domain(user.email)
    if db.get(BlockedEmailDomain, domain) is None:
        # University-style domains: register so future students can auto-join.
        existing = db.scalar(
            select(InstitutionDomain).where(InstitutionDomain.domain == domain)
        )
        if existing is None:
            db.add(
                InstitutionDomain(
                    institution_id=inst.id, domain=domain, is_approved=True
                )
            )
    db.flush()
    return inst


def provision_teacher_from_claims(
    db: Session, claims: IdentityClaims
) -> ProvisionResult:
    """
    Teacher portal: never pending. Teacher becomes institution_admin on a campus
    they own (created on first teacher sign-in if needed).
    """
    user, created_user = _upsert_user_from_claims(db, claims)
    created_membership = False

    # Drop stale access-request rows; teachers do not use that queue.
    for req in db.scalars(
        select(AccessRequest).where(
            AccessRequest.user_id == user.id,
            AccessRequest.status == "pending",
        )
    ).all():
        req.status = "approved"
        req.resolved_at = datetime.now(UTC)

    membership = _active_membership(db, user.id)
    if membership is None:
        institution = _create_teacher_campus(db, user=user)
        membership = Membership(
            institution_id=institution.id,
            user_id=user.id,
            role=MembershipRole.INSTITUTION_ADMIN.value,
            status=MembershipStatus.ACTIVE.value,
        )
        db.add(membership)
        db.flush()
        created_membership = True
    elif membership.role != MembershipRole.INSTITUTION_ADMIN.value:
        membership.role = MembershipRole.INSTITUTION_ADMIN.value
        db.add(membership)
        db.flush()

    return ProvisionResult(
        user=user,
        payload=SessionPayload(
            user_id=user.id,
            email=user.email,
            institution_id=membership.institution_id,
            role=MembershipRole.INSTITUTION_ADMIN.value,
            status="active",
        ),
        created_user=created_user,
        created_membership=created_membership,
        access_request=None,
    )


def provision_from_claims(
    db: Session,
    claims: IdentityClaims,
    *,
    invite_token: str | None = None,
) -> ProvisionResult:
    email = claims.email.strip().lower() if claims.email else ""
    domain = email_domain(email) if email else ""
    created_membership = False
    access_request: AccessRequest | None = None

    user, created_user = _upsert_user_from_claims(db, claims)

    is_platform_admin = db.get(PlatformAdmin, user.id) is not None

    # Teacher project invites beat domain matching / pending (Gmail students OK).
    invite_institution_id = accept_invites_for_user(
        db, user, invite_token=invite_token
    )
    membership = _active_membership(db, user.id)
    if membership is not None:
        role = "platform_admin" if is_platform_admin else membership.role
        return ProvisionResult(
            user=user,
            payload=SessionPayload(
                user_id=user.id,
                email=user.email,
                institution_id=membership.institution_id,
                role=role,
                status="active",
            ),
            created_user=created_user,
            created_membership=bool(invite_institution_id),
            access_request=None,
        )

    if invite_institution_id is not None:
        return ProvisionResult(
            user=user,
            payload=SessionPayload(
                user_id=user.id,
                email=user.email,
                institution_id=invite_institution_id,
                role=MembershipRole.STUDENT.value,
                status="active",
            ),
            created_user=created_user,
            created_membership=True,
            access_request=None,
        )

    if is_platform_admin:
        return ProvisionResult(
            user=user,
            payload=SessionPayload(
                user_id=user.id,
                email=user.email,
                institution_id=None,
                role="platform_admin",
                status="active",
            ),
            created_user=created_user,
            created_membership=False,
            access_request=None,
        )

    institution = lookup_institution_for_email(
        db,
        email=email,
        entra_tenant_id=claims.entra_tenant_id
        if claims.provider == OAuthProvider.MICROSOFT.value
        else None,
    )

    if institution is not None and not institution.is_active:
        access_request = _ensure_access_request(
            db, user=user, email=email, domain=domain, institution_id=institution.id
        )
        return ProvisionResult(
            user=user,
            payload=SessionPayload(
                user_id=user.id,
                email=user.email,
                institution_id=None,
                role="pending",
                status="institution_inactive",
            ),
            created_user=created_user,
            created_membership=False,
            access_request=access_request,
        )

    if institution is not None and institution.is_active:
        membership = Membership(
            institution_id=institution.id,
            user_id=user.id,
            role=MembershipRole.STUDENT.value,
            status=MembershipStatus.ACTIVE.value,
        )
        db.add(membership)
        db.flush()
        created_membership = True
        return ProvisionResult(
            user=user,
            payload=SessionPayload(
                user_id=user.id,
                email=user.email,
                institution_id=institution.id,
                role=MembershipRole.STUDENT.value,
                status="active",
            ),
            created_user=created_user,
            created_membership=created_membership,
            access_request=None,
        )

    # Unknown / blocked domain → pending
    access_request = _ensure_access_request(
        db, user=user, email=email, domain=domain, institution_id=None
    )
    return ProvisionResult(
        user=user,
        payload=SessionPayload(
            user_id=user.id,
            email=user.email,
            institution_id=None,
            role="pending",
            status="pending",
        ),
        created_user=created_user,
        created_membership=False,
        access_request=access_request,
    )


def _ensure_access_request(
    db: Session,
    *,
    user: User,
    email: str,
    domain: str,
    institution_id: uuid.UUID | None,
) -> AccessRequest:
    existing = db.scalar(
        select(AccessRequest).where(
            AccessRequest.user_id == user.id,
            AccessRequest.status == "pending",
        )
    )
    if existing is not None:
        if institution_id and existing.institution_id is None:
            existing.institution_id = institution_id
        return existing
    req = AccessRequest(
        user_id=user.id,
        email=email,
        email_domain=domain,
        institution_id=institution_id,
        status="pending",
    )
    db.add(req)
    db.flush()
    return req
