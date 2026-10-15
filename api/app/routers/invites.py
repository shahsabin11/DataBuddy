"""Public invite lookup (no session required)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import get_owner_db
from app.models import Project, ProjectInvite, User

router = APIRouter(prefix="/invites", tags=["invites"])


@router.get("/{token}")
def get_invite(
    token: str,
    db: Annotated[Session, Depends(get_owner_db)],
) -> dict:
    invite = db.scalar(select(ProjectInvite).where(ProjectInvite.token == token))
    if invite is None:
        raise HTTPException(404, detail="Invite not found.")
    project = db.get(Project, invite.project_id)
    teacher = db.get(User, invite.invited_by_user_id)
    return {
        "token": invite.token,
        "email": invite.email,
        "status": invite.status,
        "project_title": project.title if project else "Project",
        "teacher_name": (
            (teacher.display_name or teacher.email) if teacher else "Teacher"
        ),
    }
