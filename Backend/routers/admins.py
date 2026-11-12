from typing import Annotated

# Fastapi
from fastapi import Depends, status, HTTPException, APIRouter, Query
# Database
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
import models

from config import settings

# Dependencies
from auth import get_current_admin

# same hard/soft delete rules and picture cleanup as a user deleting their own account
from routers.users import delete_user_account

# Schemas
from schemas import AdminUserResponse, PaginatedAdminUsersResponse

# the dependency on the router itself protects every route below, a new route can't forget the admin check
router = APIRouter(dependencies=[Depends(get_current_admin)])

# GET, Access one page of users (soft-deleted users included unless filtered out)
@router.get(
    "/users",
    response_model=PaginatedAdminUsersResponse,
)
async def get_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    include_deleted: bool = True,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.max_page_size)] = settings.items_per_page,
):

    query = select(models.User)
    count_query = select(func.count()).select_from(models.User)
    if not include_deleted:
        query = query.where(models.User.deleted_at.is_(None))
        count_query = count_query.where(models.User.deleted_at.is_(None)) # total must use the same filter as the page

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    result = await db.execute(query.order_by(models.User.user_id).offset(skip).limit(limit))
    users = result.scalars().all()

    has_more = skip + len(users) < total

    return PaginatedAdminUsersResponse(
        users=[AdminUserResponse.model_validate(user) for user in users],
        total=total,
        skip=skip,
        limit=limit,
        has_more=has_more,
    )

# GET, Access a single user (soft-deleted users included)
@router.get(
    "/users/{user_id}",
    response_model=AdminUserResponse,
)
async def get_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):

    existing_user = await db.get(models.User, user_id)

    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return existing_user

# DELETE, Delete a user's account
# hard delete if they have no history, otherwise soft delete + anonymize (same as DELETE /api/users/{user_id})
@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):

    existing_user = await db.get(models.User, user_id)

    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if existing_user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already deleted")

    # admin is granted only by make_admin.py, so it's removed the same way, one admin (or a stolen admin token)
    # can't wipe out the others, this also covers an admin deleting themselves here by accident
    if existing_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins can't be deleted, revoke admin with make_admin.py --revoke first",
        )

    await delete_user_account(existing_user, db)
