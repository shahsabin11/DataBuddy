"""
Request-scoped tenancy context and defense-in-depth query filters.

RLS is the fail-closed boundary. These helpers mirror the same rules in the
SQLAlchemy query layer so a forgotten filter still scopes by institution,
and so institution_admins never load student dataset rows in application code.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TypeVar

from sqlalchemy import Select, select, text
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from app.models import (
    AgentStep,
    AnalysisSession,
    Artifact,
    Dataset,
    DatasetVersion,
    InstitutionBudget,
    InstitutionDomain,
    Membership,
    Project,
    ProjectMember,
    UsageLedger,
)
from app.models.enums import MembershipRole

T = TypeVar("T")

# Tables that hold student research data — institution_admins do not read these
# unless they are also a project member (break-glass or invite).
STUDENT_DATA_MODELS = (
    Dataset,
    DatasetVersion,
    AnalysisSession,
    AgentStep,
    Artifact,
)


@dataclass(frozen=True, slots=True)
class TenantContext:
    user_id: uuid.UUID
    institution_id: uuid.UUID
    role: str  # student | institution_admin (platform_admin uses admin DB role)

    @property
    def is_institution_admin(self) -> bool:
        return self.role == MembershipRole.INSTITUTION_ADMIN.value

    @property
    def is_student(self) -> bool:
        return self.role == MembershipRole.STUDENT.value


def set_rls_context(session: Session, ctx: TenantContext) -> None:
    """SET LOCAL so pooled connections cannot leak campus A into campus B."""
    session.execute(
        text(
            "SELECT set_config('app.user_id', :uid, true), "
            "set_config('app.institution_id', :iid, true), "
            "set_config('app.role', :role, true)"
        ),
        {
            "uid": str(ctx.user_id),
            "iid": str(ctx.institution_id),
            "role": ctx.role,
        },
    )


def clear_rls_context(session: Session) -> None:
    session.execute(
        text(
            "SELECT set_config('app.user_id', '', true), "
            "set_config('app.institution_id', '', true), "
            "set_config('app.role', '', true)"
        )
    )


def _institution_clause(model: type, institution_id: uuid.UUID) -> ColumnElement[bool]:
    return model.institution_id == institution_id  # type: ignore[attr-defined]


def _project_member_exists(
    ctx: TenantContext, project_id_column: ColumnElement
) -> ColumnElement[bool]:
    return (
        select(ProjectMember.id)
        .where(
            ProjectMember.project_id == project_id_column,
            ProjectMember.user_id == ctx.user_id,
            ProjectMember.institution_id == ctx.institution_id,
        )
        .exists()
    )


def apply_tenant_filter(
    stmt: Select[tuple[T]], model: type[T], ctx: TenantContext
) -> Select[tuple[T]]:
    """
    Application-layer mirror of RLS.

    - Always require institution_id == session institution.
    - Students: project-scoped student data; own usage rows.
    - Institution admins: institution-wide metadata/usage; student data only
      when they are a project member.
    """
    if not hasattr(model, "institution_id"):
        return stmt

    stmt = stmt.where(_institution_clause(model, ctx.institution_id))

    if model is UsageLedger:
        if ctx.is_student:
            stmt = stmt.where(UsageLedger.user_id == ctx.user_id)
        return stmt

    if model is Membership:
        if ctx.is_student:
            stmt = stmt.where(Membership.user_id == ctx.user_id)
        return stmt

    if model is InstitutionDomain or model is InstitutionBudget:
        return stmt

    if model is Project:
        if ctx.is_student:
            stmt = stmt.where(_project_member_exists(ctx, Project.id))
        return stmt

    if model is ProjectMember:
        if ctx.is_student:
            stmt = stmt.where(
                (ProjectMember.user_id == ctx.user_id)
                | _project_member_exists(ctx, ProjectMember.project_id)
            )
        return stmt

    if model in STUDENT_DATA_MODELS:
        project_col = model.project_id  # type: ignore[attr-defined]
        stmt = stmt.where(_project_member_exists(ctx, project_col))
        return stmt

    return stmt


def tenant_select(model: type[T], ctx: TenantContext) -> Select[tuple[T]]:
    return apply_tenant_filter(select(model), model, ctx)
