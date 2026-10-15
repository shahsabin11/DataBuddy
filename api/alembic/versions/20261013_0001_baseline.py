"""Baseline schema placeholder.

Revision ID: 20261013_0001
Revises:
Create Date: 2026-10-13

Tenant tables (institutions, users, projects, …) land in follow-up migrations
per docs/tenancy.md. This revision exists so `alembic upgrade head` succeeds
on a fresh database.
"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "20261013_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
