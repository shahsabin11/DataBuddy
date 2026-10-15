"""Teacher portal skips pending and owns a campus."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.auth.claims import IdentityClaims
from app.auth.provisioning import provision_teacher_from_claims
from app.models import AccessRequest, Institution, Membership
from app.models.enums import MembershipRole, OAuthProvider


def test_teacher_gmail_gets_campus_not_pending(owner_session):
    claims = IdentityClaims(
        provider=OAuthProvider.GOOGLE.value,
        subject=f"teacher-{uuid.uuid4()}",
        email=f"teacher-{uuid.uuid4().hex[:8]}@gmail.com",
        email_verified=True,
        name="Ada Teacher",
    )
    result = provision_teacher_from_claims(owner_session, claims)
    assert result.payload.status == "active"
    assert result.payload.role == MembershipRole.INSTITUTION_ADMIN.value
    assert result.payload.institution_id is not None
    assert result.access_request is None

    inst = owner_session.get(Institution, result.payload.institution_id)
    assert inst is not None
    assert inst.is_active
    membership = owner_session.scalar(
        select(Membership).where(Membership.user_id == result.user.id)
    )
    assert membership is not None
    assert membership.role == MembershipRole.INSTITUTION_ADMIN.value


def test_teacher_clears_prior_pending_request(owner_session):
    email = f"pending-teacher-{uuid.uuid4().hex[:8]}@outlook.com"
    # First: student-style pending path is not used; seed a pending request manually
    # by calling student provision then teacher provision.
    from app.auth.provisioning import provision_from_claims

    student_claims = IdentityClaims(
        provider=OAuthProvider.GOOGLE.value,
        subject=f"sub-{uuid.uuid4()}",
        email=email,
        email_verified=True,
        name="Pat",
    )
    pending = provision_from_claims(owner_session, student_claims)
    assert pending.payload.status == "pending"
    assert pending.access_request is not None

    teacher = provision_teacher_from_claims(owner_session, student_claims)
    assert teacher.payload.status == "active"
    assert teacher.payload.role == MembershipRole.INSTITUTION_ADMIN.value

    req = owner_session.get(AccessRequest, pending.access_request.id)
    assert req is not None
    assert req.status == "approved"
