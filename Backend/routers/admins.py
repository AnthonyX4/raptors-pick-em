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

# same picture cleanup as a user deleting their own account
from routers.users import delete_user_account

# Schemas
from schemas import (
    AdminUserResponse, CategoryKind, PaginatedAdminUsersResponse,
    PickCategoryCreate, PickCategoryResponse, PickCategoryUpdate,
)
from routers.pick_categories import category_key

# the dependency on the router itself protects every route below, a new route can't forget the admin check
router = APIRouter(dependencies=[Depends(get_current_admin)])

# GET, Access one page of users
@router.get(
    "/users",
    response_model=PaginatedAdminUsersResponse,
)
async def get_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.max_page_size)] = settings.items_per_page,
):

    query = select(models.User)
    count_query = select(func.count()).select_from(models.User) # must use the same filters as the page query

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

# GET, Access a single user
@router.get(
    "/users/{user_id}",
    response_model=AdminUserResponse,
)
async def get_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):

    existing_user = await db.get(models.User, user_id)

    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return existing_user

# DELETE, Delete a user's account (same as DELETE /api/users/{user_id})
@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):

    existing_user = await db.get(models.User, user_id)

    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # admin is granted only by make_admin.py, so it's removed the same way, one admin (or a stolen admin token)
    # can't wipe out the others, this also covers an admin deleting themselves here by accident
    if existing_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins can't be deleted, revoke admin with make_admin.py --revoke first",
        )

    await delete_user_account(existing_user, db)


# GET, every pick category, inactive ones included
@router.get(
    "/pick-categories",
    response_model=list[PickCategoryResponse],
)
async def get_pick_categories(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.PickCategory).order_by(models.PickCategory.sort_order, models.PickCategory.pick_category_id),
    )
    return result.scalars().all()

# POST, add a category, e.g. a blocks leader
@router.post(
    "/pick-categories",
    response_model=PickCategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pick_category(category: PickCategoryCreate, db: Annotated[AsyncSession, Depends(get_db)]):

    # a stat leader needs to know which stat it leads in, the other kinds have nothing to name
    if category.kind == CategoryKind.STAT_LEADER and category.stat is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A stat leader category needs a stat")
    if category.kind != CategoryKind.STAT_LEADER and category.stat is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"A {category.kind} category takes no stat")

    key = category_key(category.kind, category.stat)
    result = await db.execute(select(models.PickCategory.pick_category_id).where(models.PickCategory.key == key))
    if result.first():
        # one category per question: two "top scorer" categories would just double the points for one answer
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"A {key} category already exists")

    new_category = models.PickCategory(key=key, **category.model_dump())
    db.add(new_category)
    await db.commit()
    await db.refresh(new_category)

    return new_category

# PATCH, rename, reweight, reorder, or (de)activate a category
# reweighting is safe mid-season: scored picks store the points they earned, so past results don't change
@router.patch(
    "/pick-categories/{pick_category_id}",
    response_model=PickCategoryResponse,
)
async def update_pick_category(
    pick_category_id: int,
    update: PickCategoryUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):

    category = await db.get(models.PickCategory, pick_category_id)

    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pick category not found")

    for field, value in update.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(category, field, value)
    await db.commit()
    await db.refresh(category)

    return category
