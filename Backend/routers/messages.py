from datetime import datetime, timedelta, UTC
from typing import Annotated

# Fastapi
from fastapi import APIRouter, Depends, HTTPException, Query, status

# Database
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select
import models

from config import settings

# Dependencies
from auth import CurrentUser, OptionalUser

# Schemas
from schemas import ChatMessageCreate, ChatMessagePage, ChatMessageResponse, ChatMessageUpdate, GameStatus, UserPublic

# one router for both shapes of path: the collection lives under its game (/games/{game_id}/messages),
# a single message is addressed by its own id (/messages/{message_id}). mounted at /api in main.py
router = APIRouter()

OPENS_BEFORE = timedelta(hours=settings.chat_opens_hours_before)
CLOSES_AFTER = timedelta(hours=settings.chat_closes_hours_after)
EDIT_WINDOW = timedelta(minutes=settings.message_edit_minutes)


def utcnow() -> datetime:
    # the one place this router reads the clock, so tests can move it (same pattern as routers/picks.py)
    return datetime.now(UTC)


def room_opens_at(game: models.Game) -> datetime:
    return game.tipoff_utc - OPENS_BEFORE


def room_closes_at(game: models.Game) -> datetime | None:
    return game.final_at + CLOSES_AFTER if game.final_at else None


def room_open(game: models.Game, now: datetime) -> bool:
    """Posting is allowed on game day only (decided): 24h before tipoff until 3h after the game goes final.

    Reading is always allowed; this only decides posting, editing and liking.
    """
    if now < room_opens_at(game):
        return False
    if game.status in (GameStatus.SCHEDULED, GameStatus.LIVE):
        return True
    if game.status == GameStatus.FINAL:
        # no final_at means the game was already over when we learned of it: nothing to talk about live
        return game.final_at is not None and now < room_closes_at(game)
    return False # postponed: the room reopens when the game gets its new date


async def get_game(db: AsyncSession, game_id: str) -> models.Game:
    game = await db.get(models.Game, game_id)
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    return game


def closed() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This game's chat is closed")


async def check_not_muted(db: AsyncSession, user: models.User, now: datetime) -> None:
    mute = await db.get(models.Mute, user.user_id)
    if mute and mute.muted_until > now: # an expired mute simply stops counting, no cleanup job needed
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You're muted until {mute.muted_until.isoformat()}",
        )


async def get_message(db: AsyncSession, message_id: int) -> models.Message:
    message = await db.get(models.Message, message_id)
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return message


def check_author(message: models.Message, user: models.User) -> None:
    # a 403, not a 404 like someone else's pick: messages are public, there's nothing to hide
    if message.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your message")


async def to_responses(
    db: AsyncSession, messages: list[models.Message], reader: models.User | None,
) -> list[ChatMessageResponse]:
    """Messages with their like counts, two queries for the whole page rather than two per message."""
    ids = [m.message_id for m in messages]
    counts, mine = {}, set()
    if ids:
        counts = dict((await db.execute(
            select(models.MessageLike.message_id, func.count())
            .where(models.MessageLike.message_id.in_(ids))
            .group_by(models.MessageLike.message_id),
        )).all())
        if reader is not None:
            mine = set((await db.execute(
                select(models.MessageLike.message_id)
                .where(models.MessageLike.message_id.in_(ids), models.MessageLike.user_id == reader.user_id),
            )).scalars())
    return [
        ChatMessageResponse(
            message_id=m.message_id,
            game_id=m.game_id,
            author=UserPublic.model_validate(m.author) if m.author else None,
            body=m.body,
            created_at=m.created_at,
            edited_at=m.edited_at,
            editable_until=m.created_at + EDIT_WINDOW,
            like_count=counts.get(m.message_id, 0),
            liked_by_me=m.message_id in mine,
        )
        for m in messages
    ]


async def message_response(db: AsyncSession, message_id: int, reader: models.User) -> ChatMessageResponse:
    result = await db.execute(
        select(models.Message).options(selectinload(models.Message.author)).where(models.Message.message_id == message_id),
    )
    return (await to_responses(db, [result.scalars().one()], reader))[0]


# GET, a page of a game's chat, oldest first (public)
# no cursor: the newest page. ?before=<id>: the page just older than that message (scrolling back).
# ?after=<id>: messages newer than that one, which is what the frontend polls every few seconds
@router.get(
    "/games/{game_id}/messages",
    response_model=ChatMessagePage,
)
async def get_messages(
    game_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    reader: OptionalUser,
    before: Annotated[int | None, Query(ge=1)] = None,
    after: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=settings.max_page_size)] = settings.messages_per_page,
):
    game = await get_game(db, game_id)
    if before is not None and after is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pass before or after, not both")

    in_room = models.Message.game_id == game_id
    query = select(models.Message).options(selectinload(models.Message.author)).where(in_room)
    if after is not None:
        query = query.where(models.Message.message_id > after).order_by(models.Message.message_id).limit(limit)
        page = list((await db.execute(query)).scalars())
    else:
        if before is not None:
            query = query.where(models.Message.message_id < before)
        # the newest `limit` of them, then flipped so the page reads oldest first
        query = query.order_by(models.Message.message_id.desc()).limit(limit)
        page = list(reversed((await db.execute(query)).scalars().all()))

    # what lies either side of this page, for scrolling back and for polling. worked out from the
    # cursor when the page is empty, so an empty ?after= poll correctly says there's nothing newer
    if page:
        older_than, newer_than = page[0].message_id, page[-1].message_id
    else:
        older_than = before if before is not None else (after + 1 if after is not None else None)
        newer_than = after if after is not None else (before - 1 if before is not None else None)

    async def exists(condition) -> bool:
        return (await db.execute(select(models.Message.message_id).where(in_room, condition).limit(1))).first() is not None

    return ChatMessagePage(
        messages=await to_responses(db, page, reader),
        has_older=older_than is not None and await exists(models.Message.message_id < older_than),
        has_newer=newer_than is not None and await exists(models.Message.message_id > newer_than),
        room_open=room_open(game, utcnow()),
        opens_at=room_opens_at(game),
        closes_at=room_closes_at(game),
    )


# POST, say something in a game's chat, while its room is open
@router.post(
    "/games/{game_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_message(
    game_id: str,
    message: ChatMessageCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    game = await get_game(db, game_id)
    now = utcnow()
    if not room_open(game, now):
        raise closed()
    await check_not_muted(db, user, now)

    # stamped from the chat's clock, not the column default: the 5 minute edit window measures from it
    new_message = models.Message(game_id=game_id, user_id=user.user_id, body=message.body, created_at=now)
    db.add(new_message)
    await db.commit()

    return await message_response(db, new_message.message_id, user)


# PATCH, fix one of your messages, within 5 minutes of posting it
@router.patch(
    "/messages/{message_id}",
    response_model=ChatMessageResponse,
)
async def update_message(
    message_id: int,
    update: ChatMessageUpdate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    message = await get_message(db, message_id)
    check_author(message, user)
    now = utcnow()
    if now - message.created_at > EDIT_WINDOW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Messages can only be edited for {settings.message_edit_minutes} minutes",
        )
    # a muted user editing an old message would be posting by another route
    await check_not_muted(db, user, now)

    message.body = update.body
    message.edited_at = now
    await db.commit()

    return await message_response(db, message.message_id, user)


# DELETE, withdraw one of your messages, any time (an admin deletes others' through /api/admin/messages)
@router.delete(
    "/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_message(message_id: int, user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    message = await get_message(db, message_id)
    check_author(message, user)

    await db.delete(message) # its likes go with it (cascade)
    await db.commit()


# PUT, like a message. PUT, not POST: liking twice is the same as liking once, so it's idempotent
@router.put(
    "/messages/{message_id}/like",
    response_model=ChatMessageResponse,
)
async def like_message(message_id: int, user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    message = await get_message(db, message_id)
    if not room_open(await db.get(models.Game, message.game_id), utcnow()):
        raise closed() # a closed room is read-only, likes included

    if not await db.get(models.MessageLike, (message_id, user.user_id)):
        db.add(models.MessageLike(message_id=message_id, user_id=user.user_id))
        await db.commit()

    return await message_response(db, message_id, user)


# DELETE, take your like back. also idempotent: unliking something you never liked is fine
@router.delete(
    "/messages/{message_id}/like",
    response_model=ChatMessageResponse,
)
async def unlike_message(message_id: int, user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    await get_message(db, message_id)
    await db.execute(
        sql_delete(models.MessageLike).where(
            models.MessageLike.message_id == message_id, models.MessageLike.user_id == user.user_id,
        ),
    )
    await db.commit()

    return await message_response(db, message_id, user)
