"""Institution, domains, and budgets (docs/tenancy.md)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # Optional Entra tenant IDs for Microsoft sign-in (empty = domain-only check).
    allowed_entra_tenant_ids: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("ARRAY[]::text[]"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    domains: Mapped[list[InstitutionDomain]] = relationship(back_populates="institution")
    budget: Mapped[InstitutionBudget | None] = relationship(
        back_populates="institution", uselist=False
    )


class InstitutionDomain(Base):
    """Exact email-domain → institution map. Unique across the whole table."""

    __tablename__ = "institution_domains"
    __table_args__ = (UniqueConstraint("domain", name="uq_institution_domains_domain"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
    )
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    is_approved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    institution: Mapped[Institution] = relationship(back_populates="domains")


class InstitutionBudget(Base):
    """
    Per-institution budgets and settings (token caps, models, retention, region).
    One row per institution. Named institution_budgets in the product list;
    covers docs/tenancy.md institution_settings.
    """

    __tablename__ = "institution_budgets"

    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    token_budget_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, server_default="250"
    )
    user_token_budget_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, server_default="50"
    )
    enforce_institution_budget: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    allowed_models: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("ARRAY['claude-sonnet-5-20260514']::text[]"),
    )
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="365")
    region_code: Mapped[str] = mapped_column(String(32), nullable=False, server_default="us")
    allow_data_to_leave_region: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    institution: Mapped[Institution] = relationship(back_populates="budget")


class BlockedEmailDomain(Base):
    """Consumer domains that may never become institution_domains."""

    __tablename__ = "blocked_email_domains"

    domain: Mapped[str] = mapped_column(String(255), primary_key=True)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PlatformSettings(Base):
    """Single-row platform ceilings."""

    __tablename__ = "platform_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, server_default="1")
    allowed_models: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text(
            "ARRAY['claude-sonnet-5-20260514','claude-haiku-4-5-20251001']::text[]"
        ),
    )
    max_retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="730"
    )
    home_region: Mapped[str] = mapped_column(String(32), nullable=False, server_default="us")
    region_pin_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
