"""Tenancy schema: institutions through usage_ledger.

Revision ID: 20261013_0002
Revises: 20261013_0001
Create Date: 2026-10-13

Adjustments from the prompt list (docs/tenancy.md):
- users has no institution_id/role — memberships carry campus + role.
- institution_budgets holds token caps + settings (tenancy institution_settings).
- datasets / dataset_versions replace files + cleaning_log chain.
- analysis_sessions / agent_steps / artifacts / usage_ledger match the product list.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261013_0002"
down_revision: Union[str, None] = "20261013_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "institutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("slug", name="uq_institutions_slug"),
    )

    op.create_table(
        "institution_domains",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("is_approved", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("domain", name="uq_institution_domains_domain"),
    )
    op.create_index("ix_institution_domains_institution_id", "institution_domains", ["institution_id"])

    op.create_table(
        "institution_budgets",
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("token_budget_usd", sa.Numeric(12, 4), server_default="250", nullable=False),
        sa.Column("user_token_budget_usd", sa.Numeric(12, 4), server_default="50", nullable=False),
        sa.Column("enforce_institution_budget", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("allowed_models", postgresql.ARRAY(sa.Text()), server_default=sa.text("ARRAY['claude-sonnet-5-20260514']::text[]"), nullable=False),
        sa.Column("retention_days", sa.Integer(), server_default="365", nullable=False),
        sa.Column("region_code", sa.String(32), server_default="us", nullable=False),
        sa.Column("allow_data_to_leave_region", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "blocked_email_domains",
        sa.Column("domain", sa.String(255), primary_key=True),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "platform_settings",
        sa.Column("id", sa.Integer(), server_default="1", primary_key=True),
        sa.Column(
            "allowed_models",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("ARRAY['claude-sonnet-5-20260514','claude-haiku-4-5-20251001']::text[]"),
            nullable=False,
        ),
        sa.Column("max_retention_days", sa.Integer(), server_default="730", nullable=False),
        sa.Column("home_region", sa.String(32), server_default="us", nullable=False),
        sa.Column("region_pin_available", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("extra", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_platform_settings_singleton"),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("oauth_provider", sa.String(32), nullable=False),
        sa.Column("provider_subject", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("oauth_provider", "provider_subject", name="uq_users_provider_subject"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "platform_admins",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("granted_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
    )

    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), server_default="student", nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("user_token_budget_override_usd", sa.Numeric(12, 4)),
        sa.Column("starts_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "institution_id", name="uq_memberships_user_institution"),
        sa.CheckConstraint("role IN ('student', 'institution_admin')", name="ck_memberships_role"),
        sa.CheckConstraint("status IN ('active', 'left', 'suspended')", name="ck_memberships_status"),
    )
    op.create_index("ix_memberships_institution_id", "memberships", ["institution_id"])
    op.create_index("ix_memberships_user_status", "memberships", ["user_id", "status"])

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_projects_institution_id", "projects", ["institution_id"])
    op.create_index("ix_projects_owner_user_id", "projects", ["owner_user_id"])

    op.create_table(
        "project_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(32), server_default="invite", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),
        sa.CheckConstraint("source IN ('owner', 'invite', 'break_glass')", name="ck_project_members_source"),
    )
    op.create_index("ix_project_members_institution_id", "project_members", ["institution_id"])
    op.create_index("ix_project_members_user_id", "project_members", ["user_id"])
    op.create_index("ix_project_members_project_user", "project_members", ["project_id", "user_id"])

    # datasets first without current_version FK; add FK after dataset_versions exists
    op.create_table(
        "datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending", nullable=False),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_datasets_institution_id", "datasets", ["institution_id"])
    op.create_index("ix_datasets_project_id", "datasets", ["project_id"])

    op.create_table(
        "dataset_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dataset_versions.id", ondelete="SET NULL")),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("operation_params", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("actor", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("row_count", sa.Integer()),
        sa.Column("column_count", sa.Integer()),
        sa.Column("byte_size", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("dataset_id", "version_number", name="uq_dataset_versions_dataset_version"),
    )
    op.create_index("ix_dataset_versions_institution_id", "dataset_versions", ["institution_id"])
    op.create_index("ix_dataset_versions_project_id", "dataset_versions", ["project_id"])
    op.create_index("ix_dataset_versions_dataset_id", "dataset_versions", ["dataset_id"])

    op.create_foreign_key(
        "fk_datasets_current_version",
        "datasets",
        "dataset_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "analysis_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(300)),
        sa.Column("research_question", sa.Text()),
        sa.Column("status", sa.String(32), server_default="open", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_analysis_sessions_institution_id", "analysis_sessions", ["institution_id"])
    op.create_index("ix_analysis_sessions_project_id", "analysis_sessions", ["project_id"])
    op.create_index("ix_analysis_sessions_created_by", "analysis_sessions", ["created_by_user_id"])

    op.create_table(
        "agent_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(64)),
        sa.Column("status", sa.String(32), server_default="pending", nullable=False),
        sa.Column("decided_by", sa.String(32)),
        sa.Column("recommendation", sa.Text()),
        sa.Column("alternatives", postgresql.JSONB()),
        sa.Column("student_choice", sa.Text()),
        sa.Column("code", sa.Text()),
        sa.Column("outputs", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cache_read_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("analysis_session_id", "step_index", name="uq_agent_steps_session_index"),
    )
    op.create_index("ix_agent_steps_institution_id", "agent_steps", ["institution_id"])
    op.create_index("ix_agent_steps_session_id", "agent_steps", ["analysis_session_id"])
    op.create_index("ix_agent_steps_project_id", "agent_steps", ["project_id"])

    op.create_table(
        "artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_step_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_steps.id", ondelete="SET NULL")),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("title", sa.String(300)),
        sa.Column("storage_key", sa.String(1024)),
        sa.Column("content_json", postgresql.JSONB()),
        sa.Column("media_type", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('plot', 'table', 'report', 'result_json')", name="ck_artifacts_kind"),
    )
    op.create_index("ix_artifacts_institution_id", "artifacts", ["institution_id"])
    op.create_index("ix_artifacts_session_id", "artifacts", ["analysis_session_id"])
    op.create_index("ix_artifacts_project_id", "artifacts", ["project_id"])

    op.create_table(
        "usage_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="SET NULL")),
        sa.Column("analysis_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_sessions.id", ondelete="SET NULL")),
        sa.Column("agent_step_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_steps.id", ondelete="SET NULL")),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cache_read_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 6), server_default="0", nullable=False),
        sa.Column("event_type", sa.String(32), server_default="usage", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_usage_ledger_institution_created", "usage_ledger", ["institution_id", "created_at"])
    op.create_index("ix_usage_ledger_user_created", "usage_ledger", ["user_id", "created_at"])
    op.create_index("ix_usage_ledger_institution_user", "usage_ledger", ["institution_id", "user_id"])

    # Keep project_members.institution_id aligned with the parent project.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_project_member_institution()
        RETURNS trigger AS $$
        DECLARE
          proj_institution uuid;
        BEGIN
          SELECT institution_id INTO proj_institution FROM projects WHERE id = NEW.project_id;
          IF proj_institution IS NULL THEN
            RAISE EXCEPTION 'project % not found', NEW.project_id;
          END IF;
          IF NEW.institution_id IS DISTINCT FROM proj_institution THEN
            RAISE EXCEPTION 'project_members.institution_id must equal projects.institution_id';
          END IF;
          -- Member must have a membership at that institution
          IF NOT EXISTS (
            SELECT 1 FROM memberships m
            WHERE m.user_id = NEW.user_id
              AND m.institution_id = NEW.institution_id
              AND m.status = 'active'
          ) THEN
            RAISE EXCEPTION 'user must have an active membership at the project institution';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_project_members_institution
        BEFORE INSERT OR UPDATE ON project_members
        FOR EACH ROW EXECUTE PROCEDURE enforce_project_member_institution();
        """
    )

    op.execute(
        """
        INSERT INTO platform_settings (id) VALUES (1)
        ON CONFLICT (id) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO blocked_email_domains (domain, reason) VALUES
          ('gmail.com', 'consumer mailbox'),
          ('yahoo.com', 'consumer mailbox'),
          ('outlook.com', 'consumer mailbox'),
          ('hotmail.com', 'consumer mailbox')
        ON CONFLICT DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_project_members_institution ON project_members")
    op.execute("DROP FUNCTION IF EXISTS enforce_project_member_institution()")
    for table in (
        "usage_ledger",
        "artifacts",
        "agent_steps",
        "analysis_sessions",
        "dataset_versions",
        "datasets",
        "project_members",
        "projects",
        "memberships",
        "platform_admins",
        "users",
        "platform_settings",
        "blocked_email_domains",
        "institution_budgets",
        "institution_domains",
        "institutions",
    ):
        op.drop_table(table)
