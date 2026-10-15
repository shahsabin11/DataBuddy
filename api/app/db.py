"""SQLAlchemy engine and session factory."""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# Owner / migrator URL (table owner). Used for Alembic and seed.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
)

# App role: RLS forced, no BYPASSRLS. FastAPI request path uses this.
app_engine = create_engine(
    settings.database_app_url,
    pool_pre_ping=True,
    future=True,
)

# Platform-admin role only: BYPASSRLS. Never used for student requests.
admin_engine = create_engine(
    settings.database_admin_url,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    class_=Session,
    future=True,
)

AppSessionLocal = sessionmaker(
    bind=app_engine,
    autocommit=False,
    autoflush=False,
    class_=Session,
    future=True,
)

AdminSessionLocal = sessionmaker(
    bind=admin_engine,
    autocommit=False,
    autoflush=False,
    class_=Session,
    future=True,
)


@event.listens_for(app_engine, "connect")
def _set_app_role_search_path(dbapi_connection, _connection_record) -> None:
    # Ensure app role always sees public schema objects it was granted.
    cursor = dbapi_connection.cursor()
    cursor.execute("SET search_path TO public")
    cursor.close()


def get_db() -> Generator[Session, None, None]:
    """Owner session — reserved for migrations/admin tasks."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_app_db() -> Generator[Session, None, None]:
    """Request-scoped session as databuddy_app (RLS applies)."""
    db = AppSessionLocal()
    try:
        yield db
    finally:
        db.close()
