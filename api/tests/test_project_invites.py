"""Teacher project invites attach students on sign-in."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.auth.claims import IdentityClaims
from app.auth.provisioning import (
    provision_from_claims,
    provision_teacher_from_claims,
)
from app.invites import accept_invites_for_user, new_invite_token
from app.models import Membership, Project, ProjectInvite, ProjectMember
from app.models.enums import MembershipRole, OAuthProvider, ProjectMemberSource


def test_invite_accept_joins_project_and_skips_pending(owner_session):
    teacher_claims = IdentityClaims(
        provider=OAuthProvider.GOOGLE.value,
        subject=f"t-{uuid.uuid4()}",
        email=f"teach-{uuid.uuid4().hex[:8]}@gmail.com",
        email_verified=True,
        name="Teacher",
    )
    teacher = provision_teacher_from_claims(owner_session, teacher_claims)
    assert teacher.payload.institution_id is not None

    project = Project(
        institution_id=teacher.payload.institution_id,
        owner_user_id=teacher.user.id,
        title="Lab A",
    )
    owner_session.add(project)
    owner_session.flush()
    owner_session.add(
        ProjectMember(
            institution_id=teacher.payload.institution_id,
            project_id=project.id,
            user_id=teacher.user.id,
            source=ProjectMemberSource.OWNER.value,
        )
    )

    student_email = f"stu-{uuid.uuid4().hex[:8]}@gmail.com"
    token = new_invite_token()
    owner_session.add(
        ProjectInvite(
            institution_id=teacher.payload.institution_id,
            project_id=project.id,
            email=student_email,
            invited_by_user_id=teacher.user.id,
            token=token,
            status="pending",
        )
    )
    owner_session.flush()

    student_claims = IdentityClaims(
        provider=OAuthProvider.GOOGLE.value,
        subject=f"s-{uuid.uuid4()}",
        email=student_email,
        email_verified=True,
        name="Student",
    )
    result = provision_from_claims(
        owner_session, student_claims, invite_token=token
    )
    assert result.payload.status == "active"
    assert result.payload.role == MembershipRole.STUDENT.value
    assert result.payload.institution_id == teacher.payload.institution_id

    membership = owner_session.scalar(
        select(Membership).where(Membership.user_id == result.user.id)
    )
    assert membership is not None
    pm = owner_session.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == result.user.id,
        )
    )
    assert pm is not None

    invite = owner_session.scalar(
        select(ProjectInvite).where(ProjectInvite.token == token)
    )
    assert invite is not None
    assert invite.status == "accepted"


def test_accept_invites_helper_idempotent(owner_session):
    teacher_claims = IdentityClaims(
        provider=OAuthProvider.GOOGLE.value,
        subject=f"t2-{uuid.uuid4()}",
        email=f"teach2-{uuid.uuid4().hex[:8]}@example.edu",
        email_verified=True,
        name="T2",
    )
    teacher = provision_teacher_from_claims(owner_session, teacher_claims)
    project = Project(
        institution_id=teacher.payload.institution_id,
        owner_user_id=teacher.user.id,
        title="Lab B",
    )
    owner_session.add(project)
    owner_session.flush()

    student_claims = IdentityClaims(
        provider=OAuthProvider.GOOGLE.value,
        subject=f"s2-{uuid.uuid4()}",
        email=f"stu2-{uuid.uuid4().hex[:8]}@gmail.com",
        email_verified=True,
        name="S2",
    )
    # Create student user via teacher path? Use provision then invite — instead
    # create invite first then provision.
    token = new_invite_token()
    email = student_claims.email
    owner_session.add(
        ProjectInvite(
            institution_id=teacher.payload.institution_id,
            project_id=project.id,
            email=email,
            invited_by_user_id=teacher.user.id,
            token=token,
            status="pending",
        )
    )
    owner_session.flush()
    first = provision_from_claims(owner_session, student_claims, invite_token=token)
    second_id = accept_invites_for_user(
        owner_session, first.user, invite_token=token
    )
    assert second_id is None  # already accepted, nothing pending
