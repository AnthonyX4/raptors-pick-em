from typing import Annotated

# Fastapi
from fastapi import APIRouter, Depends, HTTPException, Query, status

# Database
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import case, distinct, func, select
import models

from config import settings

# Schemas
from schemas import LeaderboardEntry, LeaderboardResponse, UserPublic

router = APIRouter()

# the leaderboard is derived on every request, never stored: a sum over the points written on each pick.
# so there's no running total to drift out of sync, and rescoring a corrected game fixes the standings
# with no second write
TOTAL = func.sum(models.Pick.points_awarded)


async def leaderboard_page(db: AsyncSession, filters: list, skip: int, limit: int) -> LeaderboardResponse:
    # only scored picks count: an unscored pick has points_awarded None, and leaving it out also
    # means a game's picks can't leak through here before it has been played
    filters = [models.Pick.points_awarded.is_not(None), *filters]

    count_result = await db.execute(
        select(func.count(distinct(models.Pick.user_id)))
        .select_from(models.Pick)
        .join(models.Pick.game) # the season filter is on Game
        .where(*filters), # same filters as the page query
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(
            models.User,
            TOTAL.label("total_points"),
            # rank() is a sql window function: computed over the whole result before offset/limit,
            # so page 3 still shows true ranks, and tied totals share one (1, 2, 2, 4)
            func.rank().over(order_by=TOTAL.desc()).label("rank"),
            func.count(models.Pick.pick_id).label("picks_scored"),
            func.sum(case((models.Pick.points_awarded > 0, 1), else_=0)).label("correct_picks"),
            func.count(distinct(models.Pick.game_id)).label("games_played"),
        )
        .join(models.Pick, models.Pick.user_id == models.User.user_id)
        .join(models.Pick.game)
        .where(*filters)
        .group_by(models.User.user_id)
        .order_by(TOTAL.desc(), models.User.username) # username keeps the order inside a tie stable across pages
        .offset(skip)
        .limit(limit),
    )

    entries = [
        LeaderboardEntry(
            rank=row.rank,
            user=UserPublic.model_validate(row.User),
            total_points=row.total_points,
            picks_scored=row.picks_scored,
            correct_picks=row.correct_picks,
            games_played=row.games_played,
        )
        for row in result
    ]

    return LeaderboardResponse(
        entries=entries,
        total=total,
        skip=skip,
        limit=limit,
        has_more=skip + len(entries) < total,
    )


# GET, overall standings, for one season or all time (public)
@router.get(
    "",
    response_model=LeaderboardResponse,
)
async def get_leaderboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    season: Annotated[str | None, Query(max_length=7)] = None, # "2026-27", all time when left out
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.max_page_size)] = settings.items_per_page,
):
    filters = [models.Game.season == season] if season is not None else []
    return await leaderboard_page(db, filters, skip, limit)


# GET, standings for one game, empty until it has been scored (public)
@router.get(
    "/games/{game_id}",
    response_model=LeaderboardResponse,
)
async def get_game_leaderboard(
    game_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.max_page_size)] = settings.items_per_page,
):
    if not await db.get(models.Game, game_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")

    return await leaderboard_page(db, [models.Pick.game_id == game_id], skip, limit)
