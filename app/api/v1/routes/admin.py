import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.user import AdminUserListResponse, UserResponse
from app.services import user_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=ApiResponse[AdminUserListResponse])
async def get_all_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    data = await user_service.get_all_users(db, page=page, size=size)
    return ApiResponse.ok(AdminUserListResponse(**data), status_code=200)


@router.get("/users/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    user = await user_service.get_user(db, user_id)
    return ApiResponse.ok(UserResponse.model_validate(user), status_code=200)


@router.patch("/users/{user_id}/approve", response_model=ApiResponse[UserResponse])
async def approve_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    user = await user_service.approve_user(db, user_id)
    return ApiResponse.ok(UserResponse.model_validate(user), status_code=200)


@router.patch("/users/{user_id}/reject", response_model=ApiResponse[UserResponse])
async def reject_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    user = await user_service.reject_user(db, user_id)
    return ApiResponse.ok(UserResponse.model_validate(user), status_code=200)


@router.delete("/users/{user_id}", response_model=ApiResponse[None])
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    await user_service.delete_user(db, user_id)
    return ApiResponse.ok(status_code=200)
