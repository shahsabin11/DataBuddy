"""Database roles + forced RLS policies for multi-institution tenancy.

Revision ID: 20261013_0003
Revises: 20261013_0002
Create Date: 2026-10-13

Roles:
- databuddy_app: FastAPI requests. RLS forced. No BYPASSRLS.
- databuddy_admin: platform_admin paths only. BYPASSRLS.
Table owner (migrator) keeps ownership; neither app role owns tables.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20261013_0003"
down_revision: Union[str, None] = "20261013_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tenant-owned tables that always carry institution_id.
TENANT_TABLES = (
    "institution_domains",
    "institution_budgets",
    "memberships",
    "projects",
    "project_members",
    "datasets",
    "dataset_versions",
    "analysis_sessions",
    "agent_steps",
    "artifacts",
    "usage_ledger",
)


def upgrade() -> None:
    # Passwords match .env.example defaults; rotate in real deploys.
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'databuddy_app') THEN
            CREATE ROLE databuddy_app LOGIN PASSWORD 'databuddy_app' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'databuddy_admin') THEN
            CREATE ROLE databuddy_admin LOGIN PASSWORD 'databuddy_admin' NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS;
          END IF;
        END $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
          EXECUTE format(
            'GRANT CONNECT ON DATABASE %I TO databuddy_app, databuddy_admin',
            current_database()
          );
        END $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO databuddy_app, databuddy_admin")

    # Session helpers — empty/missing settings fail closed (return NULL).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_uid() RETURNS uuid
        LANGUAGE plpgsql STABLE AS $$
        BEGIN
          RETURN NULLIF(current_setting('app.user_id', true), '')::uuid;
        EXCEPTION WHEN others THEN
          RETURN NULL;
        END;
        $$;

        CREATE OR REPLACE FUNCTION app_iid() RETURNS uuid
        LANGUAGE plpgsql STABLE AS $$
        BEGIN
          RETURN NULLIF(current_setting('app.institution_id', true), '')::uuid;
        EXCEPTION WHEN others THEN
          RETURN NULL;
        END;
        $$;

        CREATE OR REPLACE FUNCTION app_role() RETURNS text
        LANGUAGE sql STABLE AS $$
          SELECT NULLIF(current_setting('app.role', true), '');
        $$;

        -- SECURITY DEFINER: membership check without RLS recursion.
        CREATE OR REPLACE FUNCTION app_is_project_member(p_project_id uuid)
        RETURNS boolean
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = public
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM project_members
            WHERE project_id = p_project_id
              AND user_id = app_uid()
          );
        $$;

        REVOKE ALL ON FUNCTION app_is_project_member(uuid) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION app_is_project_member(uuid) TO databuddy_app;
        GRANT EXECUTE ON FUNCTION app_uid() TO databuddy_app;
        GRANT EXECUTE ON FUNCTION app_iid() TO databuddy_app;
        GRANT EXECUTE ON FUNCTION app_role() TO databuddy_app;
        """
    )

    # Grants: app role DML; admin role DML (bypasses RLS).
    for table in (
        "institutions",
        "blocked_email_domains",
        "platform_settings",
        "users",
        "platform_admins",
        *TENANT_TABLES,
    ):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO databuddy_app")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO databuddy_admin")

    # ---- institutions (catalog; not institution_id-scoped the same way) ----
    op.execute("ALTER TABLE institutions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE institutions FORCE ROW LEVEL SECURITY")
    # Students/admins may read their own campus row only.
    op.execute(
        """
        CREATE POLICY institutions_select ON institutions
        FOR SELECT TO databuddy_app
        USING (id = app_iid());
        """
    )
    # No inserts/updates via app role — platform_admin uses databuddy_admin.
    op.execute(
        """
        CREATE POLICY institutions_deny_write ON institutions
        FOR ALL TO databuddy_app
        USING (false)
        WITH CHECK (false);
        """
    )

    # ---- users (global): see self, or members of your institution if admin ----
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY users_select ON users
        FOR SELECT TO databuddy_app
        USING (
          id = app_uid()
          OR (
            app_role() = 'institution_admin'
            AND EXISTS (
              SELECT 1 FROM memberships m
              WHERE m.user_id = users.id
                AND m.institution_id = app_iid()
            )
          )
        );
        """
    )
    op.execute(
        """
        CREATE POLICY users_update_self ON users
        FOR UPDATE TO databuddy_app
        USING (id = app_uid())
        WITH CHECK (id = app_uid());
        """
    )

    # ---- platform_admins: invisible to app role (admin DB role only) ----
    op.execute("ALTER TABLE platform_admins ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE platform_admins FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY platform_admins_deny_app ON platform_admins
        FOR ALL TO databuddy_app
        USING (false)
        WITH CHECK (false);
        """
    )

    # ---- blocked_email_domains / platform_settings: read-only for app ----
    for table in ("blocked_email_domains", "platform_settings"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_select ON {table}
            FOR SELECT TO databuddy_app
            USING (true);
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_deny_write ON {table}
            FOR ALL TO databuddy_app
            USING (false)
            WITH CHECK (false);
            """
        )

    # Generic enable FORCE for tenant tables
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # ---- institution_domains ----
    # Read domains for the session campus; writes only via admin DB role.
    op.execute(
        """
        CREATE POLICY institution_domains_select ON institution_domains
        FOR SELECT TO databuddy_app
        USING (institution_id = app_iid());
        """
    )
    op.execute(
        """
        CREATE POLICY institution_domains_deny_write ON institution_domains
        FOR ALL TO databuddy_app
        USING (false)
        WITH CHECK (false);
        """
    )

    # ---- institution_budgets ----
    # Campus members may read their budget row; only admin DB role may change it.
    op.execute(
        """
        CREATE POLICY institution_budgets_select ON institution_budgets
        FOR SELECT TO databuddy_app
        USING (institution_id = app_iid());
        """
    )
    op.execute(
        """
        CREATE POLICY institution_budgets_deny_write ON institution_budgets
        FOR ALL TO databuddy_app
        USING (false)
        WITH CHECK (false);
        """
    )

    # ---- memberships ----
    # Students see own memberships; institution_admins see all memberships on campus.
    op.execute(
        """
        CREATE POLICY memberships_select ON memberships
        FOR SELECT TO databuddy_app
        USING (
          institution_id = app_iid()
          AND (
            user_id = app_uid()
            OR app_role() = 'institution_admin'
          )
        );
        """
    )
    # Institution admins may update memberships on their campus (suspend/grant).
    op.execute(
        """
        CREATE POLICY memberships_admin_write ON memberships
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

    # ---- projects ----
    # Students: projects they belong to. Admins: all projects on campus (metadata).
    op.execute(
        """
        CREATE POLICY projects_select ON projects
        FOR SELECT TO databuddy_app
        USING (
          institution_id = app_iid()
          AND (
            app_role() = 'institution_admin'
            OR app_is_project_member(id)
          )
        );
        """
    )
    op.execute(
        """
        CREATE POLICY projects_insert ON projects
        FOR INSERT TO databuddy_app
        WITH CHECK (
          institution_id = app_iid()
          AND owner_user_id = app_uid()
        );
        """
    )
    op.execute(
        """
        CREATE POLICY projects_update ON projects
        FOR UPDATE TO databuddy_app
        USING (
          institution_id = app_iid()
          AND app_is_project_member(id)
        )
        WITH CHECK (institution_id = app_iid());
        """
    )
    op.execute(
        """
        CREATE POLICY projects_delete ON projects
        FOR DELETE TO databuddy_app
        USING (
          institution_id = app_iid()
          AND owner_user_id = app_uid()
        );
        """
    )

    # ---- project_members ----
    # Same campus; students limited to projects they are on.
    op.execute(
        """
        CREATE POLICY project_members_select ON project_members
        FOR SELECT TO databuddy_app
        USING (
          institution_id = app_iid()
          AND (
            app_role() = 'institution_admin'
            OR user_id = app_uid()
            OR app_is_project_member(project_id)
          )
        );
        """
    )
    op.execute(
        """
        CREATE POLICY project_members_write ON project_members
        FOR ALL TO databuddy_app
        USING (
          institution_id = app_iid()
          AND (
            app_role() = 'institution_admin'
            OR app_is_project_member(project_id)
          )
        )
        WITH CHECK (institution_id = app_iid());
        """
    )

    # ---- Student data tables ----
    # Institution admins do NOT see datasets/versions/sessions/steps/artifacts
    # unless they are a project member (invite or break-glass).
    for table in (
        "datasets",
        "dataset_versions",
        "analysis_sessions",
        "agent_steps",
        "artifacts",
    ):
        op.execute(
            f"""
            CREATE POLICY {table}_select ON {table}
            FOR SELECT TO databuddy_app
            USING (
              institution_id = app_iid()
              AND app_is_project_member(project_id)
            );
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_insert ON {table}
            FOR INSERT TO databuddy_app
            WITH CHECK (
              institution_id = app_iid()
              AND app_is_project_member(project_id)
            );
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_update ON {table}
            FOR UPDATE TO databuddy_app
            USING (
              institution_id = app_iid()
              AND app_is_project_member(project_id)
            )
            WITH CHECK (
              institution_id = app_iid()
              AND app_is_project_member(project_id)
            );
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_delete ON {table}
            FOR DELETE TO databuddy_app
            USING (
              institution_id = app_iid()
              AND app_is_project_member(project_id)
            );
            """
        )

    # ---- usage_ledger ----
    # Students see only their own spend; institution_admins see campus aggregate.
    op.execute(
        """
        CREATE POLICY usage_ledger_select ON usage_ledger
        FOR SELECT TO databuddy_app
        USING (
          institution_id = app_iid()
          AND (
            user_id = app_uid()
            OR app_role() = 'institution_admin'
          )
        );
        """
    )
    op.execute(
        """
        CREATE POLICY usage_ledger_insert ON usage_ledger
        FOR INSERT TO databuddy_app
        WITH CHECK (
          institution_id = app_iid()
          AND user_id = app_uid()
        );
        """
    )
    # Usage rows are append-only for the app role.
    op.execute(
        """
        CREATE POLICY usage_ledger_deny_mutate ON usage_ledger
        FOR UPDATE TO databuddy_app
        USING (false);
        """
    )
    op.execute(
        """
        CREATE POLICY usage_ledger_deny_delete ON usage_ledger
        FOR DELETE TO databuddy_app
        USING (false);
        """
    )


def downgrade() -> None:
    for table in (
        "institutions",
        "users",
        "platform_admins",
        "blocked_email_domains",
        "platform_settings",
        *TENANT_TABLES,
    ):
        op.execute(f"DROP POLICY IF EXISTS {table}_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_update ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_delete ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_write ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_deny_write ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_admin_write ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_deny_mutate ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_deny_delete ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_deny_app ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_update_self ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    # Named extras
    for pol, table in (
        ("institutions_deny_write", "institutions"),
        ("users_update_self", "users"),
        ("platform_admins_deny_app", "platform_admins"),
        ("memberships_admin_write", "memberships"),
        ("project_members_write", "project_members"),
        ("projects_insert", "projects"),
        ("projects_update", "projects"),
        ("projects_delete", "projects"),
        ("usage_ledger_deny_mutate", "usage_ledger"),
        ("usage_ledger_deny_delete", "usage_ledger"),
    ):
        op.execute(f"DROP POLICY IF EXISTS {pol} ON {table}")

    op.execute("DROP FUNCTION IF EXISTS app_is_project_member(uuid)")
    op.execute("DROP FUNCTION IF EXISTS app_uid()")
    op.execute("DROP FUNCTION IF EXISTS app_iid()")
    op.execute("DROP FUNCTION IF EXISTS app_role()")
