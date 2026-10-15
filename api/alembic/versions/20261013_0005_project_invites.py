"""Project email invites for teachers.

Revision ID: 20261013_0005
Revises: 20261013_0004
Create Date: 2026-10-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261013_0005"
down_revision: Union[str, None] = "20261013_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_invites",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "institution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institutions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column(
            "invited_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending", nullable=False),
        sa.Column(
            "accepted_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("token", name="uq_project_invites_token"),
        sa.UniqueConstraint(
            "project_id",
            "email",
            name="uq_project_invites_project_email",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'revoked')",
            name="ck_project_invites_status",
        ),
    )
    op.create_index(
        "ix_project_invites_institution_id", "project_invites", ["institution_id"]
    )
    op.create_index("ix_project_invites_email", "project_invites", ["email"])
    op.create_index(
        "ix_project_invites_project_status",
        "project_invites",
        ["project_id", "status"],
    )

    op.execute("ALTER TABLE project_invites ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE project_invites FORCE ROW LEVEL SECURITY")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON project_invites TO databuddy_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON project_invites TO databuddy_admin"
    )
    # Teachers (institution_admin) manage invites for their campus.
    op.execute(
        """
        CREATE POLICY project_invites_admin ON project_invites
        FOR ALL TO databuddy_app
        USING (
          institution_id = app_iid()
          AND app_role() = 'institution_admin'
        )
        WITH CHECK (
          institution_id = app_iid()
          AND app_role() = 'institution_admin'
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS project_invites_admin ON project_invites")
    op.drop_table("project_invites")
