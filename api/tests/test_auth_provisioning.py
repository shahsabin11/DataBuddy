"""Auth provisioning: domain match, blocked consumer mail, unverified, inactive campus."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.auth.claims import IdentityClaims
from app.auth.provisioning import (
    AuthProvisionError,
    lookup_institution_for_email,
    provision_from_claims,
)
from app.models import (
    Institution,
    InstitutionBudget,
    InstitutionDomain,
    Membership,
)
from app.models.enums import OAuthProvider
from scripts.seed import INST_A


def _claims(
    *,
    email: str,
    verified: bool = True,
    provider: str = OAuthProvider.GOOGLE.value,
    subject: str | None = None,
    entra_tenant_id: str | None = None,
) -> IdentityClaims:
    return IdentityClaims(
        provider=provider,
        subject=subject or f"sub-{uuid.uuid4()}",
        email=email,
        email_verified=verified,
        name="Test User",
        entra_tenant_id=entra_tenant_id,
    )


def _make_institution(
    db,
    *,
    domains: list[str],
    is_active: bool = True,
    entra_tenants: list[str] | None = None,
) -> Institution:
    slug = f"t-{uuid.uuid4().hex[:10]}"
    inst = Institution(
        name=f"Test {slug}",
        slug=slug,
        is_active=is_active,
        allowed_entra_tenant_ids=entra_tenants or [],
    )
    db.add(inst)
    db.flush()
    db.add(
        InstitutionBudget(
            institution_id=inst.id,
            token_budget_usd=100,
            user_token_budget_usd=25,
        )
    )
    for d in domains:
        db.add(
            InstitutionDomain(
                institution_id=inst.id, domain=d, is_approved=True
            )
        )
    db.flush()
    return inst


def test_matching_domain_attaches_as_student(owner_session):
    inst = _make_institution(owner_session, domains=["auth-match.edu"])
    result = provision_from_claims(
        owner_session,
        _claims(email="alice@auth-match.edu"),
    )
    assert result.created_user is True
    assert result.created_membership is True
    assert result.payload.institution_id == inst.id
    assert result.payload.role == "student"
    assert result.payload.status == "active"
    assert result.access_request is None

    membership = owner_session.scalar(
        select(Membership).where(Membership.user_id == result.user.id)
    )
    assert membership is not None
    assert membership.institution_id == inst.id


def test_subdomain_students_exact_match_only(owner_session):
    """students.uni.edu matches only when that exact domain row exists."""
    inst = _make_institution(
        owner_session,
        domains=["auth-uni.edu", "students.auth-uni.edu"],
    )

    parent = provision_from_claims(
        owner_session,
        _claims(email="faculty@auth-uni.edu"),
    )
    assert parent.payload.institution_id == inst.id
    assert parent.payload.status == "active"

    student = provision_from_claims(
        owner_session,
        _claims(email="bob@students.auth-uni.edu"),
    )
    assert student.payload.institution_id == inst.id
    assert student.payload.role == "student"

    # Unregistered subdomain must not inherit from parent domain.
    orphan = provision_from_claims(
        owner_session,
        _claims(email="cs@cs.auth-uni.edu"),
    )
    assert orphan.payload.status == "pending"
    assert orphan.payload.institution_id is None
    assert orphan.access_request is not None
    assert orphan.access_request.email_domain == "cs.auth-uni.edu"


def test_unknown_domain_creates_pending_access_request(owner_session):
    result = provision_from_claims(
        owner_session,
        _claims(email="someone@brand-new-college.example"),
    )
    assert result.payload.role == "pending"
    assert result.payload.status == "pending"
    assert result.payload.institution_id is None
    assert result.created_membership is False
    assert result.access_request is not None
    assert result.access_request.status == "pending"
    assert result.access_request.email_domain == "brand-new-college.example"


@pytest.mark.parametrize(
    "email",
    ["person@gmail.com", "person@outlook.com"],
)
def test_personal_consumer_mailbox_stays_pending(owner_session, email):
    result = provision_from_claims(owner_session, _claims(email=email))
    assert result.payload.status == "pending"
    assert result.payload.institution_id is None
    assert result.created_membership is False
    # Blocked domains must never auto-map even if someone inserts a row.
    assert lookup_institution_for_email(
        owner_session, email=email, entra_tenant_id=None
    ) is None


def test_unverified_email_rejected(owner_session):
    with pytest.raises(AuthProvisionError) as exc:
        provision_from_claims(
            owner_session,
            _claims(email="alice@auth-unverified.edu", verified=False),
        )
    assert exc.value.code == "email_unverified"


def test_deactivated_institution_does_not_attach(owner_session):
    inst = _make_institution(
        owner_session,
        domains=["auth-inactive.edu"],
        is_active=False,
    )
    result = provision_from_claims(
        owner_session,
        _claims(email="student@auth-inactive.edu"),
    )
    assert result.payload.status == "institution_inactive"
    assert result.payload.role == "pending"
    assert result.payload.institution_id is None
    assert result.created_membership is False
    assert result.access_request is not None
    assert result.access_request.institution_id == inst.id

    memberships = owner_session.scalars(
        select(Membership).where(Membership.user_id == result.user.id)
    ).all()
    assert memberships == []


def test_microsoft_entra_tenant_must_match_allow_list(owner_session):
    inst = _make_institution(
        owner_session,
        domains=["auth-entra.edu"],
        entra_tenants=["allowed-tenant-111"],
    )
    ok = provision_from_claims(
        owner_session,
        _claims(
            email="a@auth-entra.edu",
            provider=OAuthProvider.MICROSOFT.value,
            entra_tenant_id="allowed-tenant-111",
        ),
    )
    assert ok.payload.institution_id == inst.id

    denied = provision_from_claims(
        owner_session,
        _claims(
            email="b@auth-entra.edu",
            provider=OAuthProvider.MICROSOFT.value,
            entra_tenant_id="other-tenant-999",
        ),
    )
    assert denied.payload.status == "pending"
    assert denied.payload.institution_id is None


def test_seeded_northfield_subdomain_row_exists(owner_session):
    """Regression: seed registers students.northfield.edu as its own domain."""
    mapping = owner_session.scalar(
        select(InstitutionDomain).where(
            InstitutionDomain.domain == "students.northfield.edu"
        )
    )
    assert mapping is not None
    assert mapping.institution_id == INST_A

    found = lookup_institution_for_email(
        owner_session,
        email="x@students.northfield.edu",
        entra_tenant_id=None,
    )
    assert found is not None
    assert found.id == INST_A
