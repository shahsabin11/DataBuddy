"""Platform-admin: institutions, domains, budgets, approve access requests."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import AuthUser, get_admin_db, require_platform_admin
from app.models import (
    AccessRequest,
    BlockedEmailDomain,
    Institution,
    InstitutionBudget,
    InstitutionDomain,
    Membership,
)
from app.models.enums import MembershipRole, MembershipStatus

router = APIRouter(
    prefix="/platform",
    tags=["platform-admin"],
    dependencies=[Depends(require_platform_admin)],
)

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")
_DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")


class CreateInstitutionBody(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=80)
    domains: list[str] = Field(min_length=1)
    user_token_budget_usd: Decimal = Field(default=Decimal("50"), ge=0)
    institution_token_budget_usd: Decimal = Field(default=Decimal("250"), ge=0)
    enforce_institution_budget: bool = False
    allowed_entra_tenant_ids: list[str] = Field(default_factory=list)


class AddDomainBody(BaseModel):
    domain: str = Field(min_length=3, max_length=255)


class UpdateBudgetBody(BaseModel):
    user_token_budget_usd: Decimal | None = Field(default=None, ge=0)
    institution_token_budget_usd: Decimal | None = Field(default=None, ge=0)
    enforce_institution_budget: bool | None = None


class ApproveAccessBody(BaseModel):
    institution_id: uuid.UUID
    role: str = Field(default="student")


def _normalize_domain(domain: str) -> str:
    d = domain.strip().lower().lstrip("@")
    if not _DOMAIN_RE.match(d):
        raise HTTPException(400, detail=f"Invalid domain: {domain}")
    return d


@router.get("/institutions")
def list_institutions(db: Annotated[Session, Depends(get_admin_db)]) -> list[dict]:
    rows = db.scalars(select(Institution).order_by(Institution.name)).all()
    out = []
    for inst in rows:
        domains = db.scalars(
            select(InstitutionDomain).where(
                InstitutionDomain.institution_id == inst.id
            )
        ).all()
        budget = db.get(InstitutionBudget, inst.id)
        out.append(
            {
                "id": str(inst.id),
                "name": inst.name,
                "slug": inst.slug,
                "is_active": inst.is_active,
                "domains": [d.domain for d in domains],
                "allowed_entra_tenant_ids": list(inst.allowed_entra_tenant_ids or []),
                "user_token_budget_usd": str(budget.user_token_budget_usd)
                if budget
                else None,
                "institution_token_budget_usd": str(budget.token_budget_usd)
                if budget
                else None,
                "enforce_institution_budget": bool(
                    budget.enforce_institution_budget if budget else False
                ),
            }
        )
    return out


@router.post("/institutions", status_code=201)
def create_institution(
    body: CreateInstitutionBody,
    db: Annotated[Session, Depends(get_admin_db)],
) -> dict:
    slug = body.slug.strip().lower()
    if not _SLUG_RE.match(slug):
        raise HTTPException(400, detail="Invalid slug.")
    if db.scalar(select(Institution).where(Institution.slug == slug)):
        raise HTTPException(409, detail="Slug already exists.")

    domains = [_normalize_domain(d) for d in body.domains]
    for d in domains:
        if db.get(BlockedEmailDomain, d) is not None:
            raise HTTPException(
                400,
                detail=f"{d} is a consumer mailbox and cannot be an institution domain.",
            )
        if db.scalar(select(InstitutionDomain).where(InstitutionDomain.domain == d)):
            raise HTTPException(409, detail=f"Domain already registered: {d}")

    inst = Institution(
        name=body.name.strip(),
        slug=slug,
        is_active=True,
        allowed_entra_tenant_ids=body.allowed_entra_tenant_ids,
    )
    db.add(inst)
    db.flush()
    for d in domains:
        db.add(
            InstitutionDomain(
                institution_id=inst.id, domain=d, is_approved=True
            )
        )
    db.add(
        InstitutionBudget(
            institution_id=inst.id,
            token_budget_usd=body.institution_token_budget_usd,
            user_token_budget_usd=body.user_token_budget_usd,
            enforce_institution_budget=body.enforce_institution_budget,
        )
    )
    db.flush()
    return {"id": str(inst.id), "slug": inst.slug}


@router.post("/institutions/{institution_id}/domains", status_code=201)
def add_domain(
    institution_id: uuid.UUID,
    body: AddDomainBody,
    db: Annotated[Session, Depends(get_admin_db)],
) -> dict:
    inst = db.get(Institution, institution_id)
    if inst is None:
        raise HTTPException(404, detail="Institution not found.")
    domain = _normalize_domain(body.domain)
    if db.get(BlockedEmailDomain, domain) is not None:
        raise HTTPException(400, detail="Consumer domains cannot be institution domains.")
    if db.scalar(select(InstitutionDomain).where(InstitutionDomain.domain == domain)):
        raise HTTPException(409, detail="Domain already registered.")
    row = InstitutionDomain(
        institution_id=institution_id, domain=domain, is_approved=True
    )
    db.add(row)
    db.flush()
    return {"id": str(row.id), "domain": domain}


@router.patch("/institutions/{institution_id}/budget")
def update_budget(
    institution_id: uuid.UUID,
    body: UpdateBudgetBody,
    db: Annotated[Session, Depends(get_admin_db)],
) -> dict:
    budget = db.get(InstitutionBudget, institution_id)
    if budget is None:
        raise HTTPException(404, detail="Budget not found.")
    if body.user_token_budget_usd is not None:
        budget.user_token_budget_usd = body.user_token_budget_usd
    if body.institution_token_budget_usd is not None:
        budget.token_budget_usd = body.institution_token_budget_usd
    if body.enforce_institution_budget is not None:
        budget.enforce_institution_budget = body.enforce_institution_budget
    db.add(budget)
    db.flush()
    return {
        "user_token_budget_usd": str(budget.user_token_budget_usd),
        "institution_token_budget_usd": str(budget.token_budget_usd),
        "enforce_institution_budget": budget.enforce_institution_budget,
    }


@router.get("/access-requests")
def list_access_requests(
    db: Annotated[Session, Depends(get_admin_db)],
    status_filter: str = "pending",
) -> list[dict]:
    q = select(AccessRequest).order_by(AccessRequest.created_at.desc())
    if status_filter:
        q = q.where(AccessRequest.status == status_filter)
    rows = db.scalars(q).all()
    return [
        {
            "id": str(r.id),
            "user_id": str(r.user_id),
            "email": r.email,
            "email_domain": r.email_domain,
            "institution_id": str(r.institution_id) if r.institution_id else None,
            "status": r.status,
            "message": r.message,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.post("/access-requests/{request_id}/approve")
def approve_access_request(
    request_id: uuid.UUID,
    body: ApproveAccessBody,
    user: Annotated[AuthUser, Depends(require_platform_admin)],
    db: Annotated[Session, Depends(get_admin_db)],
) -> dict:
    req = db.get(AccessRequest, request_id)
    if req is None or req.status != "pending":
        raise HTTPException(404, detail="Pending request not found.")
    inst = db.get(Institution, body.institution_id)
    if inst is None or not inst.is_active:
        raise HTTPException(400, detail="Institution missing or inactive.")
    if body.role not in {
        MembershipRole.STUDENT.value,
        MembershipRole.INSTITUTION_ADMIN.value,
    }:
        raise HTTPException(400, detail="Invalid role.")

    existing = db.scalar(
        select(Membership).where(
            Membership.user_id == req.user_id,
            Membership.institution_id == inst.id,
        )
    )
    if existing is None:
        db.add(
            Membership(
                user_id=req.user_id,
                institution_id=inst.id,
                role=body.role,
                status=MembershipStatus.ACTIVE.value,
            )
        )
    else:
        existing.status = MembershipStatus.ACTIVE.value
        existing.role = body.role
        existing.ends_at = None

    req.status = "approved"
    req.institution_id = inst.id
    req.resolved_by_user_id = user.user_id
    req.resolved_at = datetime.now(UTC)
    db.add(req)
    db.flush()
    return {"status": "approved", "user_id": str(req.user_id)}


@router.post("/access-requests/{request_id}/reject")
def reject_access_request(
    request_id: uuid.UUID,
    user: Annotated[AuthUser, Depends(require_platform_admin)],
    db: Annotated[Session, Depends(get_admin_db)],
) -> dict:
    req = db.get(AccessRequest, request_id)
    if req is None or req.status != "pending":
        raise HTTPException(404, detail="Pending request not found.")
    req.status = "rejected"
    req.resolved_by_user_id = user.user_id
    req.resolved_at = datetime.now(UTC)
    db.add(req)
    db.flush()
    return {"status": "rejected"}
