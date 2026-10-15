"""Access requests + Entra tenant allow-list on institutions.

Revision ID: 20261013_0004
Revises: 20261013_0003
Create Date: 2026-10-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261013_0004"
down_revision: Union[str, None] = "20261013_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "institutions",
        sa.Column(
            "allowed_entra_tenant_ids",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("ARRAY[]::text[]"),
            nullable=False,
        ),
    )

    op.create_table(
        "access_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("email_domain", sa.String(255), nullable=False),
        sa.Column(
            "institution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institutions.id", ondelete="SET NULL"),
        ),
        sa.Column("status", sa.String(32), server_default="pending", nullable=False),
        sa.Column("message", sa.Text()),
        sa.Column(
            "resolved_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_access_requests_status",
        ),
    )
    op.create_index(
        "ix_access_requests_user_status", "access_requests", ["user_id", "status"]
    )
    op.create_index(
        "ix_access_requests_institution_status",
        "access_requests",
        ["institution_id", "status"],
    )

    # RLS: users see their own requests; institution_admins see campus queue;
    # writes of new pending rows by the requester; approvals via admin policies.
    op.execute("ALTER TABLE access_requests ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE access_requests FORCE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON access_requests TO databuddy_app")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON access_requests TO databuddy_admin"
    )
    op.execute(
        """
        CREATE POLICY access_requests_select ON access_requests
        FOR SELECT TO databuddy_app
        USING (
          user_id = app_uid()
          OR (
            institution_id IS NOT NULL
            AND institution_id = app_iid()
            AND app_role() = 'institution_admin'
          )
        );
        """
    )
    op.execute(
        """
        CREATE POLICY access_requests_insert ON access_requests
        FOR INSERT TO databuddy_app
        WITH CHECK (user_id = app_uid());
        """
    )
    op.execute(
        """
        CREATE POLICY access_requests_admin_update ON access_requests
        FOR UPDATE TO databuddy_app
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
    op.execute("DROP POLICY IF EXISTS access_requests_select ON access_requests")
    op.execute("DROP POLICY IF EXISTS access_requests_insert ON access_requests")
    op.execute("DROP POLICY IF EXISTS access_requests_admin_update ON access_requests")
    op.drop_table("access_requests")
    op.drop_column("institutions", "allowed_entra_tenant_ids")
