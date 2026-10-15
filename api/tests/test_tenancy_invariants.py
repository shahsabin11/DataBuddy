"""
Multi-tenancy invariants (docs/tenancy.md §7).

Logs in as institution A and asserts no read/update/delete of institution B
rows for every tenant-owned table. Also covers unset context and admin
dataset isolation.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import DBAPIError, StatementError
from sqlalchemy.orm import Session

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
from app.tenancy import apply_tenant_filter, tenant_select
from scripts.seed import (
    ARTIFACT_B,
    DATASET_B,
    INST_A,
    INST_B,
    PROJECT_B,
    SESSION_B,
    STEP_B,
    USAGE_B,
    USERS_B,
    VERSION_B,
)
from tests.conftest import login_as

# Every tenant-owned table + the B-side primary key to probe.
TENANT_PROBE = [
    (InstitutionDomain, "institution_id", INST_B),
    (InstitutionBudget, "institution_id", INST_B),
    (Membership, "institution_id", INST_B),
    (Project, "id", PROJECT_B),
    (ProjectMember, "institution_id", INST_B),
    (Dataset, "id", DATASET_B),
    (DatasetVersion, "id", VERSION_B),
    (AnalysisSession, "id", SESSION_B),
    (AgentStep, "id", STEP_B),
    (Artifact, "id", ARTIFACT_B),
    (UsageLedger, "id", USAGE_B),
]


def _pk_column(model):
    return list(model.__table__.primary_key.columns)[0]


@pytest.mark.parametrize("model,filter_attr,b_value", TENANT_PROBE)
def test_student_a_cannot_read_institution_b_rows(
    student_a, model, filter_attr, b_value
) -> None:
    session, _ctx = student_a
    col = getattr(model, filter_attr)
    rows = session.scalars(select(model).where(col == b_value)).all()
    assert rows == [], f"{model.__tablename__}: student A read B rows"


@pytest.mark.parametrize("model,filter_attr,b_value", TENANT_PROBE)
def test_student_a_cannot_update_institution_b_rows(
    student_a, model, filter_attr, b_value
) -> None:
    session, _ctx = student_a
    col = getattr(model, filter_attr)
    # Pick a harmless text/int column to touch when present.
    values: dict = {}
    if hasattr(model, "title"):
        values["title"] = "hijacked"
    elif hasattr(model, "name"):
        values["name"] = "hijacked"
    elif hasattr(model, "status"):
        values["status"] = "hijacked"
    elif hasattr(model, "domain"):
        values["domain"] = "evil.example"
    elif hasattr(model, "retention_days"):
        values["retention_days"] = 1
    elif hasattr(model, "role"):
        values["role"] = "institution_admin"
    elif hasattr(model, "source"):
        values["source"] = "break_glass"
    elif hasattr(model, "operation"):
        values["operation"] = "hijacked"
    elif hasattr(model, "model"):
        values["model"] = "hijacked"
    elif hasattr(model, "kind"):
        values["kind"] = "report"
    else:
        pytest.skip(f"no mutable probe column on {model.__tablename__}")

    result = session.execute(update(model).where(col == b_value).values(**values))
    assert result.rowcount == 0, f"{model.__tablename__}: student A updated B rows"


@pytest.mark.parametrize("model,filter_attr,b_value", TENANT_PROBE)
def test_student_a_cannot_delete_institution_b_rows(
    student_a, model, filter_attr, b_value
) -> None:
    session, _ctx = student_a
    col = getattr(model, filter_attr)
    result = session.execute(delete(model).where(col == b_value))
    assert result.rowcount == 0, f"{model.__tablename__}: student A deleted B rows"


def test_student_a_cannot_insert_into_institution_b(student_a) -> None:
    session, ctx = student_a
    with pytest.raises((DBAPIError, StatementError)):
        session.execute(
            text(
                """
                INSERT INTO projects (id, institution_id, owner_user_id, title)
                VALUES (:id, :iid, :uid, 'cross-tenant')
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "iid": str(INST_B),
                "uid": str(ctx.user_id),
            },
        )
        session.flush()


def test_unset_rls_context_returns_no_tenant_rows(app_session, migrated_db) -> None:
    session: Session = app_session
    session.begin()
    session.execute(
        text(
            "SELECT set_config('app.user_id', '', true), "
            "set_config('app.institution_id', '', true), "
            "set_config('app.role', '', true)"
        )
    )
    for model, _, _ in TENANT_PROBE:
        rows = session.scalars(select(model)).all()
        assert rows == [], f"{model.__tablename__}: visible with empty GUC"


def test_student_a_can_read_own_institution_project(student_a) -> None:
    session, ctx = student_a
    projects = session.scalars(
        select(Project).where(Project.institution_id == INST_A)
    ).all()
    assert len(projects) >= 1
    assert all(p.institution_id == ctx.institution_id for p in projects)


def test_institution_admin_sees_usage_but_not_foreign_datasets(admin_a) -> None:
    """Admins see campus usage aggregates; not other institutions' datasets."""
    session, _ctx = admin_a
    usage = session.scalars(select(UsageLedger)).all()
    assert usage
    assert all(u.institution_id == INST_A for u in usage)

    foreign = session.scalars(
        select(Dataset).where(Dataset.institution_id == INST_B)
    ).all()
    assert foreign == []


def test_institution_admin_without_membership_cannot_read_own_campus_datasets(
    admin_a,
) -> None:
    """Per product rule: admins do not see student datasets unless project members."""
    session, _ctx = admin_a
    # Seed admin (USERS_A[0]) is not a project member — only students 2 and 3 are.
    datasets = session.scalars(select(Dataset)).all()
    assert datasets == []


def test_query_layer_also_blocks_institution_b(student_a) -> None:
    """Defense in depth: apply_tenant_filter never returns B rows."""
    session, ctx = student_a
    for model, _, _ in TENANT_PROBE:
        if not hasattr(model, "institution_id"):
            continue
        stmt = apply_tenant_filter(select(model), model, ctx)
        rows = session.scalars(stmt).all()
        assert all(
            r.institution_id == INST_A for r in rows
        ), f"query layer leaked B for {model.__tablename__}"


def test_student_b_cannot_read_institution_a(app_session, migrated_db) -> None:
    ctx = login_as(
        app_session,
        user_id=USERS_B[1],
        institution_id=INST_B,
        role="student",
    )
    rows = app_session.scalars(
        select(Dataset).where(Dataset.institution_id == INST_A)
    ).all()
    assert rows == []
    stmt = tenant_select(Dataset, ctx)
    assert app_session.scalars(stmt).all()  # own campus ok
    assert all(d.institution_id == INST_B for d in app_session.scalars(stmt).all())


def test_app_role_has_no_bypassrls(owner_session) -> None:
    row = owner_session.execute(
        text("SELECT rolbypassrls FROM pg_roles WHERE rolname = 'databuddy_app'")
    ).one()
    assert row[0] is False


def test_admin_role_has_bypassrls(owner_session) -> None:
    row = owner_session.execute(
        text("SELECT rolbypassrls FROM pg_roles WHERE rolname = 'databuddy_admin'")
    ).one()
    assert row[0] is True


def test_forged_institution_id_in_insert_rejected(student_a) -> None:
    session, ctx = student_a
    # WITH CHECK requires institution_id = app_iid(); forging B must fail.
    with pytest.raises((DBAPIError, StatementError)):
        session.add(
            Project(
                institution_id=INST_B,
                owner_user_id=ctx.user_id,
                title="forged",
            )
        )
        session.flush()
