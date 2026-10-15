"""Teacher portal: projects and student invites."""

from __future__ import annotations

import re
import uuid
from typing import Annotated

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.deps import (
    AuthUser,
    get_app_db_with_rls,
    require_institution_admin,
)
from app.config import get_settings
from app.emailer import student_invite_email
from app.invites import new_invite_token
from app.models import Project, ProjectInvite, ProjectMember, User
from app.models.enums import ProjectMemberSource

router = APIRouter(
    prefix="/teacher",
    tags=["teacher"],
    dependencies=[Depends(require_institution_admin)],
)

_EMAIL_SPLIT = re.compile(r"[\s,;]+")


class CreateProjectBody(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=4000)


class InviteStudentsBody(BaseModel):
    emails: list[str] = Field(min_length=1, max_length=100)


def _invite_url(token: str) -> str:
    return f"{get_settings().app_url}/invite/{token}"


@router.get("/projects")
def list_projects(
    user: Annotated[AuthUser, Depends(require_institution_admin)],
    db: Annotated[Session, Depends(get_app_db_with_rls)],
) -> list[dict]:
    assert user.institution_id is not None
    rows = db.scalars(
        select(Project)
        .where(Project.institution_id == user.institution_id)
        .order_by(Project.created_at.desc())
    ).all()
    out = []
    for p in rows:
        member_count = db.scalar(
            select(func.count())
            .select_from(ProjectMember)
            .where(ProjectMember.project_id == p.id)
        )
        pending = db.scalar(
            select(func.count())
            .select_from(ProjectInvite)
            .where(
                ProjectInvite.project_id == p.id,
                ProjectInvite.status == "pending",
            )
        )
        out.append(
            {
                "id": str(p.id),
                "title": p.title,
                "description": p.description,
                "owner_user_id": str(p.owner_user_id),
                "member_count": int(member_count or 0),
                "pending_invites": int(pending or 0),
                "created_at": p.created_at.isoformat(),
            }
        )
    return out


@router.post("/projects", status_code=201)
def create_project(
    body: CreateProjectBody,
    user: Annotated[AuthUser, Depends(require_institution_admin)],
    db: Annotated[Session, Depends(get_app_db_with_rls)],
) -> dict:
    assert user.institution_id is not None
    project = Project(
        institution_id=user.institution_id,
        owner_user_id=user.user_id,
        title=body.title.strip(),
        description=(body.description or "").strip() or None,
    )
    db.add(project)
    db.flush()
    db.add(
        ProjectMember(
            institution_id=user.institution_id,
            project_id=project.id,
            user_id=user.user_id,
            source=ProjectMemberSource.OWNER.value,
        )
    )
    db.flush()
    return {
        "id": str(project.id),
        "title": project.title,
        "description": project.description,
    }


@router.get("/projects/{project_id}")
def get_project(
    project_id: uuid.UUID,
    user: Annotated[AuthUser, Depends(require_institution_admin)],
    db: Annotated[Session, Depends(get_app_db_with_rls)],
) -> dict:
    assert user.institution_id is not None
    project = db.get(Project, project_id)
    if project is None or project.institution_id != user.institution_id:
        raise HTTPException(404, detail="Project not found.")

    members = db.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project.id)
        .order_by(ProjectMember.created_at)
    ).all()
    invites = db.scalars(
        select(ProjectInvite)
        .where(ProjectInvite.project_id == project.id)
        .order_by(ProjectInvite.created_at.desc())
    ).all()
    return {
        "id": str(project.id),
        "title": project.title,
        "description": project.description,
        "members": [
            {
                "user_id": str(u.id),
                "email": u.email,
                "display_name": u.display_name,
                "source": pm.source,
            }
            for pm, u in members
        ],
        "invites": [
            {
                "id": str(i.id),
                "email": i.email,
                "status": i.status,
                "invite_url": _invite_url(i.token),
                "created_at": i.created_at.isoformat(),
                "accepted_at": i.accepted_at.isoformat() if i.accepted_at else None,
            }
            for i in invites
        ],
    }


@router.post("/projects/{project_id}/invites")
def invite_students(
    project_id: uuid.UUID,
    body: InviteStudentsBody,
    user: Annotated[AuthUser, Depends(require_institution_admin)],
    db: Annotated[Session, Depends(get_app_db_with_rls)],
) -> dict:
    assert user.institution_id is not None
    settings = get_settings()
    project = db.get(Project, project_id)
    if project is None or project.institution_id != user.institution_id:
        raise HTTPException(404, detail="Project not found.")

    teacher = db.get(User, user.user_id)
    teacher_name = (
        (teacher.display_name if teacher else None)
        or (teacher.email if teacher else None)
        or "Your teacher"
    )

    raw: list[str] = []
    for chunk in body.emails:
        raw.extend(p for p in _EMAIL_SPLIT.split(chunk) if p)

    results: list[dict] = []
    seen: set[str] = set()
    for raw_email in raw:
        try:
            email = validate_email(raw_email, check_deliverability=False).normalized
        except EmailNotValidError:
            results.append(
                {
                    "email": raw_email,
                    "status": "invalid",
                    "error": "Invalid email address.",
                }
            )
            continue
        email = email.lower()
        if email in seen:
            continue
        seen.add(email)

        existing = db.scalar(
            select(ProjectInvite).where(
                ProjectInvite.project_id == project.id,
                ProjectInvite.email == email,
            )
        )
        if existing is not None and existing.status == "accepted":
            results.append(
                {
                    "email": email,
                    "status": "already_member",
                    "invite_url": _invite_url(existing.token),
                    "email_delivery": None,
                }
            )
            continue

        if existing is None:
            existing = ProjectInvite(
                institution_id=user.institution_id,
                project_id=project.id,
                email=email,
                invited_by_user_id=user.user_id,
                token=new_invite_token(),
                status="pending",
            )
            db.add(existing)
            db.flush()
        else:
            existing.status = "pending"
            existing.accepted_at = None
            existing.accepted_user_id = None
            if not existing.token:
                existing.token = new_invite_token()
            db.add(existing)
            db.flush()

        # If the student already has an account, attach them immediately too.
        existing_user = db.scalar(select(User).where(User.email == email))
        if existing_user is not None:
            from app.invites import accept_invites_for_user

            accept_invites_for_user(db, existing_user, invite_token=existing.token)
            existing = db.get(ProjectInvite, existing.id)

        url = _invite_url(existing.token)
        delivery = student_invite_email(
            student_email=email,
            project_title=project.title,
            teacher_name=teacher_name,
            invite_url=url,
            settings=settings,
        )
        results.append(
            {
                "email": email,
                "status": existing.status if existing else "pending",
                "invite_url": url,
                "email_delivery": delivery,
            }
        )

    return {
        "project_id": str(project.id),
        "smtp_configured": settings.smtp_configured,
        "invites": results,
    }
