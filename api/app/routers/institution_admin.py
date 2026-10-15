"""Institution-admin: usage totals for their campus only."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.deps import (
    AuthUser,
    get_app_db_with_rls,
    require_institution_admin,
)
from app.models import Membership, UsageLedger

router = APIRouter(
    prefix="/institution",
    tags=["institution-admin"],
    dependencies=[Depends(require_institution_admin)],
)


@router.get("/usage")
def institution_usage(
    user: Annotated[AuthUser, Depends(require_institution_admin)],
    db: Annotated[Session, Depends(get_app_db_with_rls)],
) -> dict:
    """
    Aggregate token usage for the admin's institution only.

    institution_id comes from the verified session, never from the client.
    """
    assert user.institution_id is not None

    totals = db.execute(
        select(
            func.coalesce(func.sum(UsageLedger.input_tokens), 0),
            func.coalesce(func.sum(UsageLedger.output_tokens), 0),
            func.coalesce(func.sum(UsageLedger.cache_read_tokens), 0),
            func.coalesce(func.sum(UsageLedger.estimated_cost_usd), 0),
            func.count(UsageLedger.id),
        ).where(UsageLedger.institution_id == user.institution_id)
    ).one()

    per_user = db.execute(
        select(
            UsageLedger.user_id,
            func.coalesce(func.sum(UsageLedger.estimated_cost_usd), 0),
            func.coalesce(func.sum(UsageLedger.input_tokens), 0),
            func.coalesce(func.sum(UsageLedger.output_tokens), 0),
            func.count(UsageLedger.id),
        )
        .where(UsageLedger.institution_id == user.institution_id)
        .group_by(UsageLedger.user_id)
        .order_by(func.sum(UsageLedger.estimated_cost_usd).desc())
    ).all()

    member_count = db.scalar(
        select(func.count())
        .select_from(Membership)
        .where(
            Membership.institution_id == user.institution_id,
            Membership.status == "active",
        )
    )

    return {
        "institution_id": str(user.institution_id),
        "active_members": int(member_count or 0),
        "totals": {
            "input_tokens": int(totals[0]),
            "output_tokens": int(totals[1]),
            "cache_read_tokens": int(totals[2]),
            "estimated_cost_usd": str(Decimal(totals[3])),
            "events": int(totals[4]),
        },
        "by_user": [
            {
                "user_id": str(row[0]),
                "estimated_cost_usd": str(Decimal(row[1])),
                "input_tokens": int(row[2]),
                "output_tokens": int(row[3]),
                "events": int(row[4]),
            }
            for row in per_user
        ],
    }
