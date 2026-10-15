"""Pytest fixtures for tenancy invariant tests against real Postgres."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.tenancy import TenantContext, set_rls_context
from scripts.seed import (
    INST_A,
    INST_B,
    USERS_A,
    USERS_B,
    seed,
)


def pytest_configure() -> None:
    # Ensure settings cache sees test env if provided.
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def settings():
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture(scope="session")
def owner_engine(settings):
    engine = create_engine(settings.database_url, future=True)
    # Fail fast with a clear message if Postgres is down.
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return engine


@pytest.fixture(scope="session")
def app_engine(settings):
    return create_engine(settings.database_app_url, future=True)


@pytest.fixture(scope="session")
def migrated_db(owner_engine, settings):
    """Run Alembic migrations + seed once per test session."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")
    seed()
    return True


@pytest.fixture
def app_session(app_engine, migrated_db) -> Session:
    SessionLocal = sessionmaker(bind=app_engine, future=True, class_=Session)
    session = SessionLocal()
    try:
        yield session
        session.rollback()
    finally:
        session.close()


@pytest.fixture
def owner_session(owner_engine, migrated_db) -> Session:
    SessionLocal = sessionmaker(bind=owner_engine, future=True, class_=Session)
    session = SessionLocal()
    try:
        yield session
        session.rollback()
    finally:
        session.close()


def login_as(
    session: Session,
    *,
    user_id: uuid.UUID,
    institution_id: uuid.UUID,
    role: str,
) -> TenantContext:
    """Simulate FastAPI setting RLS GUC from a verified login."""
    ctx = TenantContext(
        user_id=user_id, institution_id=institution_id, role=role
    )
    # SET LOCAL binds to the current transaction (SQLAlchemy autobegins).
    set_rls_context(session, ctx)
    return ctx


@pytest.fixture
def student_a(app_session) -> tuple[Session, TenantContext]:
    ctx = login_as(
        app_session,
        user_id=USERS_A[1],
        institution_id=INST_A,
        role="student",
    )
    return app_session, ctx


@pytest.fixture
def admin_a(app_session) -> tuple[Session, TenantContext]:
    ctx = login_as(
        app_session,
        user_id=USERS_A[0],
        institution_id=INST_A,
        role="institution_admin",
    )
    return app_session, ctx


# Re-export seed IDs for tests
__all__ = [
    "INST_A",
    "INST_B",
    "USERS_A",
    "USERS_B",
    "student_a",
    "admin_a",
]
