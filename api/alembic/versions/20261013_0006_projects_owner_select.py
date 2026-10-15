"""Allow project owners to SELECT their new rows (INSERT RETURNING).

Revision ID: 20261013_0006
Revises: 20261013_0005
Create Date: 2026-10-13

PostgreSQL applies SELECT policies to INSERT...RETURNING. Students creating a
project were not yet project_members, so RETURNING failed RLS even when INSERT
WITH CHECK passed.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20261013_0006"
down_revision: Union[str, None] = "20261013_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS projects_select ON projects")
    op.execute(
        """
        CREATE POLICY projects_select ON projects
        FOR SELECT TO databuddy_app
        USING (
          institution_id = app_iid()
          AND (
            app_role() = 'institution_admin'
            OR app_is_project_member(id)
            OR owner_user_id = app_uid()
          )
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS projects_select ON projects")
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
