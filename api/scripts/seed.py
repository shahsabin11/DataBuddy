"""
Seed two fake institutions with three users each.

Usage (from api/):
  python -m scripts.seed
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    AgentStep,
    AnalysisSession,
    Artifact,
    Dataset,
    DatasetVersion,
    Institution,
    InstitutionBudget,
    InstitutionDomain,
    Membership,
    Project,
    ProjectMember,
    UsageLedger,
    User,
)
from app.models.enums import (
    ArtifactKind,
    MembershipRole,
    MembershipStatus,
    OAuthProvider,
    ProjectMemberSource,
)

# Stable IDs so tests and docs can refer to them.
INST_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
INST_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

USERS_A = [
    uuid.UUID("a1000000-0000-4000-8000-000000000001"),
    uuid.UUID("a1000000-0000-4000-8000-000000000002"),
    uuid.UUID("a1000000-0000-4000-8000-000000000003"),
]
USERS_B = [
    uuid.UUID("b1000000-0000-4000-8000-000000000001"),
    uuid.UUID("b1000000-0000-4000-8000-000000000002"),
    uuid.UUID("b1000000-0000-4000-8000-000000000003"),
]

PROJECT_A = uuid.UUID("aa100000-0000-4000-8000-000000000001")
PROJECT_B = uuid.UUID("bb100000-0000-4000-8000-000000000001")
DATASET_A = uuid.UUID("aa200000-0000-4000-8000-000000000001")
DATASET_B = uuid.UUID("bb200000-0000-4000-8000-000000000001")
VERSION_A = uuid.UUID("aa300000-0000-4000-8000-000000000001")
VERSION_B = uuid.UUID("bb300000-0000-4000-8000-000000000001")
SESSION_A = uuid.UUID("aa400000-0000-4000-8000-000000000001")
SESSION_B = uuid.UUID("bb400000-0000-4000-8000-000000000001")
STEP_A = uuid.UUID("aa500000-0000-4000-8000-000000000001")
STEP_B = uuid.UUID("bb500000-0000-4000-8000-000000000001")
ARTIFACT_A = uuid.UUID("aa600000-0000-4000-8000-000000000001")
ARTIFACT_B = uuid.UUID("bb600000-0000-4000-8000-000000000001")
USAGE_A = uuid.UUID("aa700000-0000-4000-8000-000000000001")
USAGE_B = uuid.UUID("bb700000-0000-4000-8000-000000000001")


def _seed_institution(
    db,
    *,
    inst_id: uuid.UUID,
    name: str,
    slug: str,
    domains: list[str],
    user_ids: list[uuid.UUID],
    email_domain: str,
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    session_id: uuid.UUID,
    step_id: uuid.UUID,
    artifact_id: uuid.UUID,
    usage_id: uuid.UUID,
) -> None:
    if db.get(Institution, inst_id) is None:
        db.add(Institution(id=inst_id, name=name, slug=slug, is_active=True))
        db.flush()
        db.add(
            InstitutionBudget(
                institution_id=inst_id,
                token_budget_usd=250,
                user_token_budget_usd=50,
            )
        )
        for domain in domains:
            db.add(
                InstitutionDomain(
                    institution_id=inst_id, domain=domain, is_approved=True
                )
            )

    for i, user_id in enumerate(user_ids):
        email = f"user{i + 1}@{email_domain}"
        if db.get(User, user_id) is None:
            db.add(
                User(
                    id=user_id,
                    oauth_provider=OAuthProvider.GOOGLE.value,
                    provider_subject=f"{slug}-sub-{i + 1}",
                    email=email,
                    display_name=f"{name} User {i + 1}",
                )
            )
            db.flush()
        role = (
            MembershipRole.INSTITUTION_ADMIN.value
            if i == 0
            else MembershipRole.STUDENT.value
        )
        existing = db.scalar(
            select(Membership).where(
                Membership.user_id == user_id,
                Membership.institution_id == inst_id,
            )
        )
        if existing is None:
            db.add(
                Membership(
                    institution_id=inst_id,
                    user_id=user_id,
                    role=role,
                    status=MembershipStatus.ACTIVE.value,
                )
            )

    owner = user_ids[1]  # first student owns the project
    if db.get(Project, project_id) is None:
        db.add(
            Project(
                id=project_id,
                institution_id=inst_id,
                owner_user_id=owner,
                title=f"{name} Capstone Project",
                description="Seed project for tenancy tests",
            )
        )
        db.flush()
        db.add(
            ProjectMember(
                institution_id=inst_id,
                project_id=project_id,
                user_id=owner,
                source=ProjectMemberSource.OWNER.value,
            )
        )
        # Second student is a collaborator
        db.add(
            ProjectMember(
                institution_id=inst_id,
                project_id=project_id,
                user_id=user_ids[2],
                source=ProjectMemberSource.INVITE.value,
            )
        )

    if db.get(Dataset, dataset_id) is None:
        db.add(
            Dataset(
                id=dataset_id,
                institution_id=inst_id,
                project_id=project_id,
                created_by_user_id=owner,
                name="survey.csv",
                original_filename="survey.csv",
                status="ready",
            )
        )
        db.flush()
        db.add(
            DatasetVersion(
                id=version_id,
                institution_id=inst_id,
                project_id=project_id,
                dataset_id=dataset_id,
                parent_version_id=None,
                created_by_user_id=owner,
                version_number=1,
                operation="upload",
                operation_params={},
                actor="student",
                storage_key=f"{inst_id}/{project_id}/{dataset_id}/v1.csv",
                row_count=100,
                column_count=5,
            )
        )
        db.flush()
        ds = db.get(Dataset, dataset_id)
        assert ds is not None
        ds.current_version_id = version_id

    if db.get(AnalysisSession, session_id) is None:
        db.add(
            AnalysisSession(
                id=session_id,
                institution_id=inst_id,
                project_id=project_id,
                dataset_id=dataset_id,
                dataset_version_id=version_id,
                created_by_user_id=owner,
                title="Seed analysis",
                research_question="Do groups differ on score?",
                status="open",
            )
        )
        db.flush()
        db.add(
            AgentStep(
                id=step_id,
                institution_id=inst_id,
                analysis_session_id=session_id,
                project_id=project_id,
                user_id=owner,
                step_index=1,
                tool_name="profile_table",
                status="succeeded",
                decided_by="agent_auto",
                code=None,
                outputs={"n_rows": 100},
                input_tokens=1000,
                output_tokens=200,
            )
        )
        db.add(
            Artifact(
                id=artifact_id,
                institution_id=inst_id,
                project_id=project_id,
                analysis_session_id=session_id,
                agent_step_id=step_id,
                created_by_user_id=owner,
                kind=ArtifactKind.PLOT.value,
                title="Histogram of score",
                storage_key=f"{inst_id}/{project_id}/plots/hist.png",
                media_type="image/png",
            )
        )
        db.add(
            UsageLedger(
                id=usage_id,
                institution_id=inst_id,
                user_id=owner,
                project_id=project_id,
                analysis_session_id=session_id,
                agent_step_id=step_id,
                model="claude-sonnet-5-20260514",
                input_tokens=1000,
                output_tokens=200,
                estimated_cost_usd="0.012000",
                event_type="usage",
            )
        )


def seed() -> None:
    db = SessionLocal()
    try:
        _seed_institution(
            db,
            inst_id=INST_A,
            name="Northfield University",
            slug="northfield",
            domains=["northfield.edu", "students.northfield.edu"],
            user_ids=USERS_A,
            email_domain="northfield.edu",
            project_id=PROJECT_A,
            dataset_id=DATASET_A,
            version_id=VERSION_A,
            session_id=SESSION_A,
            step_id=STEP_A,
            artifact_id=ARTIFACT_A,
            usage_id=USAGE_A,
        )
        _seed_institution(
            db,
            inst_id=INST_B,
            name="Cedar College",
            slug="cedar",
            domains=["cedar.edu"],
            user_ids=USERS_B,
            email_domain="cedar.edu",
            project_id=PROJECT_B,
            dataset_id=DATASET_B,
            version_id=VERSION_B,
            session_id=SESSION_B,
            step_id=STEP_B,
            artifact_id=ARTIFACT_B,
            usage_id=USAGE_B,
        )
        db.commit()
        print("Seeded institutions Northfield + Cedar (3 users each).")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
