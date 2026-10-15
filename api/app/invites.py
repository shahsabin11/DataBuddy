"""Accept project invites and attach students to the teacher's campus."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Membership, ProjectInvite, ProjectMember, User
from app.models.enums import MembershipRole, MembershipStatus, ProjectMemberSource


def new_invite_token() -> str:
    return secrets.token_urlsafe(32)


def accept_invites_for_user(
    db: Session,
    user: User,
    *,
    invite_token: str | None = None,
) -> uuid.UUID | None:
    """
    Accept pending invites for this user's email.

    Returns an institution_id when at least one invite was accepted (for session).
    """
    invites: list[ProjectInvite] = []
    if invite_token:
        preferred = db.scalar(
            select(ProjectInvite).where(
                ProjectInvite.token == invite_token,
                ProjectInvite.status == "pending",
                ProjectInvite.email == user.email,
            )
        )
        if preferred is not None:
            invites.append(preferred)

    others = db.scalars(
        select(ProjectInvite)
        .where(
            ProjectInvite.email == user.email,
            ProjectInvite.status == "pending",
        )
        .order_by(ProjectInvite.created_at)
    ).all()
    for inv in others:
        if all(inv.id != existing.id for existing in invites):
            invites.append(inv)

    if not invites:
        return None

    session_institution_id: uuid.UUID | None = None
    for inv in invites:
        membership = db.scalar(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.institution_id == inv.institution_id,
            )
        )
        if membership is None:
            db.add(
                Membership(
                    institution_id=inv.institution_id,
                    user_id=user.id,
                    role=MembershipRole.STUDENT.value,
                    status=MembershipStatus.ACTIVE.value,
                )
            )
            db.flush()
        elif membership.status != MembershipStatus.ACTIVE.value:
            membership.status = MembershipStatus.ACTIVE.value
            membership.ends_at = None
            if membership.role != MembershipRole.INSTITUTION_ADMIN.value:
                membership.role = MembershipRole.STUDENT.value

        existing_pm = db.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == inv.project_id,
                ProjectMember.user_id == user.id,
            )
        )
        if existing_pm is None:
            db.add(
                ProjectMember(
                    institution_id=inv.institution_id,
                    project_id=inv.project_id,
                    user_id=user.id,
                    source=ProjectMemberSource.INVITE.value,
                )
            )

        inv.status = "accepted"
        inv.accepted_user_id = user.id
        inv.accepted_at = datetime.now(UTC)
        db.add(inv)

        if session_institution_id is None:
            session_institution_id = inv.institution_id

    db.flush()
    return session_institution_id
