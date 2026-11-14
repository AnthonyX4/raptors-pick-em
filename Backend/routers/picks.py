from datetime import datetime, UTC
from typing import Annotated

# Fastapi
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

# Database
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import func, select
import models

from config import settings

# Dependencies
from auth import CurrentUser

# Schemas
from schemas import (
    CategoryKind, GameStatus, PaginatedGamePicksResponse, PaginatedPicksResponse,
    PickCreate, PickResponse, PickUpdate, PickWithUser,
)

router = APIRouter()

# swagger's "try it out" pre-fills a body with every field, which sends all three answers and gets a
# 422. these give it one valid body per kind of category instead, picked from a dropdown. the ids
# are the ones a fresh database gets: categories from GET /api/pick-categories, Raptors 1610612761,
# Scottie Barnes 1630567, game 0022600241 (NYK @ TOR)
CREATE_EXAMPLES = {
    "winner": {
        "summary": "Winner: fill in team_id",
        "value": {"game_id": "0022600241", "pick_category_id": 1, "team_id": 1610612761},
    },
    "margin": {
        "summary": "Margin of victory: fill in margin",
        "description": "The winning margin in points, whoever wins. It only scores if your winner pick is right too.",
        "value": {"game_id": "0022600241", "pick_category_id": 2, "margin": 7},
    },
    "stat_leader": {
        "summary": "Stat leader: fill in player_id",
        "description": "A Raptor, from GET /api/players?team=TOR.",
        "value": {"game_id": "0022600241", "pick_category_id": 3, "player_id": 1630567},
    },
}
UPDATE_EXAMPLES = {
    "winner": {"summary": "Change a winner pick", "value": {"team_id": 1610612752}},
    "margin": {"summary": "Change a margin pick", "value": {"margin": 12}},
    "stat_leader": {"summary": "Change a stat leader pick", "value": {"player_id": 1630567}},
}

# everything PickResponse/PickWithUser nests, an async session can't lazy load any of it
PICK_LOADERS = (
    selectinload(models.Pick.category),
    selectinload(models.Pick.team),
    selectinload(models.Pick.player).selectinload(models.Player.team),
    selectinload(models.Pick.user),
)

# which answer field each kind of category fills in
ANSWER_FIELD = {
    CategoryKind.WINNER: "team_id",
    CategoryKind.MARGIN: "margin",
    CategoryKind.STAT_LEADER: "player_id",
}


def utcnow() -> datetime:
    # the one place this router reads the clock, so tests can move it instead of waiting for tipoff
    return datetime.now(UTC)


def picks_open(game: models.Game) -> bool:
    """Picks can be made, edited and withdrawn only before a scheduled game tips off.

    A postponed game is closed until the schedule refresh moves it back to scheduled with a new
    tipoff, at which point it reopens: the picks already made carry over to the new date.
    """
    return game.status == GameStatus.SCHEDULED and utcnow() < game.tipoff_utc


def game_started(game: models.Game) -> bool:
    """Picks are revealed once a game has actually started, not merely once it's closed.

    The difference is a postponed game: closed, but never played. Revealing its picks would let
    anyone copy them once it reopens on its new date.
    """
    if game.status in (GameStatus.LIVE, GameStatus.FINAL):
        return True
    return game.status == GameStatus.SCHEDULED and utcnow() >= game.tipoff_utc


def locked() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Picks for this game are locked")


async def get_open_game(db: AsyncSession, game_id: str) -> models.Game:
    game = await db.get(models.Game, game_id)
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    if not picks_open(game):
        raise locked()
    return game


async def get_owned_pick(db: AsyncSession, pick_id: int, user: models.User) -> models.Pick:
    pick = await db.get(models.Pick, pick_id)
    # 404 rather than 403 for someone else's pick: picks are secret until tipoff, so the
    # response shouldn't confirm that a pick with this id exists
    if not pick or pick.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pick not found")
    return pick


async def load_pick(db: AsyncSession, pick_id: int) -> models.Pick:
    """Re-read a pick with everything the response nests."""
    result = await db.execute(
        select(models.Pick).options(*PICK_LOADERS).where(models.Pick.pick_id == pick_id),
    )
    return result.scalars().one()


async def check_answer(db: AsyncSession, game: models.Game, category: models.PickCategory, answer: dict) -> None:
    """The answer fills in exactly the field the category asks for, with a value that fits this game."""
    kind = CategoryKind(category.kind)
    field = ANSWER_FIELD[kind]

    given = {name for name, value in answer.items() if value is not None}
    if given != {field}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A '{category.name}' pick needs {field} and nothing else",
        )

    if kind == CategoryKind.WINNER and answer["team_id"] not in (game.home_team_id, game.away_team_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pick one of the two teams in this game")

    if kind == CategoryKind.STAT_LEADER:
        # stat leader picks are about the followed team's players only (decided: "Raptors' top scorer",
        # not the whole game's). checked against the roster as last harvested
        result = await db.execute(
            select(models.Player.player_id)
            .join(models.Team, models.Player.team_id == models.Team.team_id)
            .where(models.Player.player_id == answer["player_id"], models.Team.tricode == settings.team_tricode),
        )
        if result.first() is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pick a player on the {settings.team_tricode} roster",
            )


async def missing_required(db: AsyncSession, user_id: int, game_id: str) -> list[str]:
    """Names of the required categories this user hasn't picked yet for this game."""
    required = (await db.execute(
        select(models.PickCategory)
        .where(models.PickCategory.is_required.is_(True), models.PickCategory.is_active.is_(True))
        .order_by(models.PickCategory.sort_order),
    )).scalars().all()
    made = set((await db.execute(
        select(models.Pick.pick_category_id).where(models.Pick.user_id == user_id, models.Pick.game_id == game_id),
    )).scalars())
    return [category.name for category in required if category.pick_category_id not in made]


# POST, make a pick for one category of one game
@router.post(
    "",
    response_model=PickResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pick(
    pick: Annotated[PickCreate, Body(openapi_examples=CREATE_EXAMPLES)],
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):

    game = await get_open_game(db, pick.game_id)

    category = await db.get(models.PickCategory, pick.pick_category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pick category not found")
    if not category.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This category isn't open for picks")

    answer = pick.model_dump(include={"team_id", "player_id", "margin"})
    await check_answer(db, game, category, answer)

    result = await db.execute(
        select(models.Pick.pick_id).where(
            models.Pick.user_id == user.user_id,
            models.Pick.game_id == game.game_id,
            models.Pick.pick_category_id == category.pick_category_id,
        ),
    )
    if result.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a pick in this category, edit it instead",
        )

    # the winner first: optional bonus picks only count alongside the main one
    if not category.is_required:
        missing = await missing_required(db, user.user_id, game.game_id)
        if missing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Make your {', '.join(missing)} pick first",
            )

    new_pick = models.Pick(
        user_id=user.user_id,
        game_id=game.game_id,
        pick_category_id=category.pick_category_id,
        **answer,
    )
    db.add(new_pick)
    await db.commit()

    return await load_pick(db, new_pick.pick_id)


# GET, the logged in user's picks, newest game first (optionally just one game's)
# declared before /{pick_id} so "me" is not parsed as a pick id
@router.get(
    "/me",
    response_model=PaginatedPicksResponse,
)
async def get_my_picks(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    game_id: Annotated[str | None, Query(max_length=20)] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.max_page_size)] = settings.items_per_page,
):

    filters = [models.Pick.user_id == user.user_id]
    if game_id is not None:
        filters.append(models.Pick.game_id == game_id)

    count_result = await db.execute(select(func.count()).select_from(models.Pick).where(*filters)) # same filters as the page
    total = count_result.scalar() or 0

    result = await db.execute(
        select(models.Pick)
        .options(*PICK_LOADERS)
        .join(models.Pick.game)
        .join(models.Pick.category)
        .where(*filters)
        .order_by(models.Game.tipoff_utc.desc(), models.PickCategory.sort_order, models.Pick.pick_id)
        .offset(skip)
        .limit(limit),
    )
    picks = result.scalars().all()

    return PaginatedPicksResponse(
        picks=[PickResponse.model_validate(pick) for pick in picks],
        total=total,
        skip=skip,
        limit=limit,
        has_more=skip + len(picks) < total,
    )


# GET, everyone's picks for one game, revealed once it starts (public)
@router.get(
    "",
    response_model=PaginatedGamePicksResponse,
)
async def get_game_picks(
    db: Annotated[AsyncSession, Depends(get_db)],
    game_id: Annotated[str, Query(max_length=20)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.max_page_size)] = settings.items_per_page,
):

    game = await db.get(models.Game, game_id)
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")

    # hidden until tipoff, otherwise the last person to pick could copy everyone else
    if not game_started(game):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Picks are revealed at tipoff")

    count_result = await db.execute(
        select(func.count()).select_from(models.Pick).where(models.Pick.game_id == game_id), # same filter as the page
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(models.Pick)
        .options(*PICK_LOADERS)
        .join(models.Pick.category)
        .where(models.Pick.game_id == game_id)
        .order_by(models.Pick.user_id, models.PickCategory.sort_order, models.Pick.pick_id) # each user's picks together, in form order
        .offset(skip)
        .limit(limit),
    )
    picks = result.scalars().all()

    return PaginatedGamePicksResponse(
        picks=[PickWithUser.model_validate(pick) for pick in picks],
        total=total,
        skip=skip,
        limit=limit,
        has_more=skip + len(picks) < total,
    )


# PATCH, change the answer of one of your picks, until tipoff
@router.patch(
    "/{pick_id}",
    response_model=PickResponse,
)
async def update_pick(
    pick_id: int,
    update: Annotated[PickUpdate, Body(openapi_examples=UPDATE_EXAMPLES)],
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):

    pick = await get_owned_pick(db, pick_id, user)
    game = await get_open_game(db, pick.game_id)
    category = await db.get(models.PickCategory, pick.pick_category_id)

    answer = update.model_dump()
    await check_answer(db, game, category, answer)

    # all three are written: the one the category asks for gets the new value, the others stay None
    for field, value in answer.items():
        setattr(pick, field, value)
    await db.commit()

    return await load_pick(db, pick.pick_id)


# DELETE, withdraw one of your picks, until tipoff
@router.delete(
    "/{pick_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_pick(pick_id: int, user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):

    pick = await get_owned_pick(db, pick_id, user)
    await get_open_game(db, pick.game_id)
    category = await db.get(models.PickCategory, pick.pick_category_id)

    # the mirror of the create rule: bonus picks can't be left standing without the winner pick.
    # refused rather than cascaded, so withdrawing one pick never silently removes others
    if category.is_required:
        result = await db.execute(
            select(models.Pick.pick_id)
            .join(models.Pick.category)
            .where(
                models.Pick.user_id == user.user_id,
                models.Pick.game_id == pick.game_id,
                models.PickCategory.is_required.is_(False),
            )
            .limit(1),
        )
        if result.first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Withdraw your other picks for this game before your {category.name} pick",
            )

    await db.delete(pick)
    await db.commit()
