from typing import Annotated

# Fastapi
from fastapi import APIRouter, Depends

# Database
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import models

# Schemas
from schemas import CategoryKind, LeaderStat, PickCategoryResponse

router = APIRouter()


def category_key(kind: CategoryKind, stat: LeaderStat | None) -> str:
    """The unique key for a category: "winner", "margin", or "leader:<stat>"."""
    return f"leader:{stat}" if kind == CategoryKind.STAT_LEADER else str(kind)


# the six categories the game launches with. weights are hand-picked, harder to predict = more points:
# the winner is right well over half the time, the steals leader is close to a coin flip between several
# players. meant to be recalibrated from real box scores (see HANDOFF.md)
DEFAULT_CATEGORIES = [
    dict(kind=CategoryKind.WINNER, stat=None, name="Winner", points=1, is_required=True, sort_order=1),
    dict(kind=CategoryKind.MARGIN, stat=None, name="Margin of victory", points=3, sort_order=2),
    dict(kind=CategoryKind.STAT_LEADER, stat=LeaderStat.POINTS, name="Raptors' top scorer", points=2, sort_order=3),
    dict(kind=CategoryKind.STAT_LEADER, stat=LeaderStat.REBOUNDS_TOTAL, name="Raptors' top rebounder", points=3, sort_order=4),
    dict(kind=CategoryKind.STAT_LEADER, stat=LeaderStat.ASSISTS, name="Raptors' assists leader", points=2, sort_order=5),
    dict(kind=CategoryKind.STAT_LEADER, stat=LeaderStat.STEALS, name="Raptors' steals leader", points=5, sort_order=6),
]


async def ensure_default_categories(db: AsyncSession) -> None:
    """Add any default category that's missing. Runs at startup.

    Only ever inserts: a default an admin has renamed, reweighted or deactivated is left as they set it.
    """
    result = await db.execute(select(models.PickCategory.key))
    existing = set(result.scalars())

    for category in DEFAULT_CATEGORIES:
        key = category_key(category["kind"], category["stat"])
        if key not in existing:
            db.add(models.PickCategory(key=key, **category))
    await db.commit()


# GET, the categories a user can pick in, in form order (public)
# not paginated: it's a handful of rows, the form needs all of them at once
@router.get(
    "",
    response_model=list[PickCategoryResponse],
)
async def get_pick_categories(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.PickCategory)
        .where(models.PickCategory.is_active.is_(True))
        .order_by(models.PickCategory.sort_order, models.PickCategory.pick_category_id),
    )
    return result.scalars().all()
