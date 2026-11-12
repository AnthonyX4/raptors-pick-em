from typing import Annotated

# Fastapi
from fastapi import APIRouter, Depends, HTTPException, Query, status

# Database
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import func, select
import models

from config import settings

# Schemas
from schemas import PaginatedPlayersResponse, PlayerResponse

# resolving a tricode to a team is the same job as in the games router
from routers.games import team_id_for_tricode

router = APIRouter()


# GET, one page of players, by name (public)
# ?team= and ?search= are what a pick form needs: the two rosters for a game, narrowed as someone types
@router.get(
    "",
    response_model=PaginatedPlayersResponse,
)
async def get_players(
    db: Annotated[AsyncSession, Depends(get_db)],
    team: Annotated[str | None, Query(max_length=3)] = None, # tricode of the roster to limit to
    search: Annotated[str | None, Query(max_length=50)] = None, # matches anywhere in the full name, ignoring case
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.max_page_size)] = settings.items_per_page,
):

    filters = []
    if team is not None:
        filters.append(models.Player.team_id == await team_id_for_tricode(db, team))
    if search is not None:
        filters.append(models.Player.full_name.ilike(f"%{search}%"))

    count_result = await db.execute(
        select(func.count()).select_from(models.Player).where(*filters), # same filters as the page query
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(models.Player)
        .options(selectinload(models.Player.team)) # PlayerResponse nests the team
        .where(*filters)
        .order_by(models.Player.full_name, models.Player.player_id)
        .offset(skip)
        .limit(limit),
    )
    players = result.scalars().all()

    has_more = skip + len(players) < total

    return PaginatedPlayersResponse(
        players=[PlayerResponse.model_validate(player) for player in players],
        total=total,
        skip=skip,
        limit=limit,
        has_more=has_more,
    )


# GET, one player (public)
@router.get(
    "/{player_id}",
    response_model=PlayerResponse,
)
async def get_player(player_id: int, db: Annotated[AsyncSession, Depends(get_db)]):

    result = await db.execute(
        select(models.Player)
        .options(selectinload(models.Player.team))
        .where(models.Player.player_id == player_id),
    )
    player = result.scalars().first()

    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")

    return player
