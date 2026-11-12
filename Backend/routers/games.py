from typing import Annotated

# Fastapi
from fastapi import APIRouter, Depends, HTTPException, Query, status

# Database
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import func, or_, select
import models

from config import settings

# Schemas
from schemas import GameDetail, GameStatus, PaginatedGamesResponse, GameResponse

router = APIRouter()

# GameResponse nests both teams, and an async session can't lazy load them on access
TEAM_LOADERS = (selectinload(models.Game.home_team), selectinload(models.Game.away_team))


async def team_id_for_tricode(db: AsyncSession, tricode: str) -> int:
    result = await db.execute(
        select(models.Team.team_id).where(models.Team.tricode == tricode.upper()),
    )
    team_id = result.scalars().first()

    if team_id is None:
        # a 400 rather than an empty page, so a typo in the filter is visible instead of silent
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown team tricode: {tricode}",
        )
    return team_id


# GET, one page of games, oldest first, so ?status=scheduled puts the next game at the top (public)
@router.get(
    "",
    response_model=PaginatedGamesResponse,
)
async def get_games(
    db: Annotated[AsyncSession, Depends(get_db)],
    season: Annotated[str | None, Query(max_length=7)] = None, # "2026-27"
    status_filter: Annotated[GameStatus | None, Query(alias="status")] = None, # ?status=, renamed so it doesn't shadow fastapi's status module
    opponent: Annotated[str | None, Query(max_length=3)] = None, # a tricode: every game here involves our team, so this matches the other side
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.max_page_size)] = settings.games_per_page,
):

    filters = []
    if season is not None:
        filters.append(models.Game.season == season)
    if status_filter is not None:
        filters.append(models.Game.status == status_filter)
    if opponent is not None:
        opponent_id = await team_id_for_tricode(db, opponent)
        filters.append(or_(
            models.Game.home_team_id == opponent_id,
            models.Game.away_team_id == opponent_id,
        ))

    count_query = select(func.count()).select_from(models.Game).where(*filters) # same filters as the page query
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    result = await db.execute(
        select(models.Game)
        .options(*TEAM_LOADERS)
        .where(*filters)
        .order_by(models.Game.tipoff_utc, models.Game.game_id) # game_id breaks ties between games tipping off together
        .offset(skip)
        .limit(limit),
    )
    games = result.scalars().all()

    has_more = skip + len(games) < total

    return PaginatedGamesResponse(
        games=[GameResponse.model_validate(game) for game in games],
        total=total,
        skip=skip,
        limit=limit,
        has_more=has_more,
    )


# GET, one game with its box score (empty until the game is final and has been ingested) (public)
@router.get(
    "/{game_id}",
    response_model=GameDetail,
)
async def get_game(game_id: str, db: Annotated[AsyncSession, Depends(get_db)]):

    result = await db.execute(
        select(models.Game)
        .options(
            *TEAM_LOADERS,
            selectinload(models.Game.player_stats) # each stat line carries the player, who carries their team
            .selectinload(models.PlayerGameStat.player)
            .selectinload(models.Player.team),
        )
        .where(models.Game.game_id == game_id),
    )
    game = result.scalars().first()

    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")

    # highest scorer first: the box score is read to see who led, not in roster order
    game.player_stats.sort(key=lambda stat: stat.points, reverse=True)

    return game
