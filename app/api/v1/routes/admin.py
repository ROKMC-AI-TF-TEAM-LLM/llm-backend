import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.user import UserResponse
from app.services import user_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.patch("/users/{user_id}/approve", response_model=ApiResponse[UserResponse])
async def approve_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    user = await user_service.approve_user(db, user_id)
    return ApiResponse.ok(UserResponse.model_validate(user))


@router.patch("/users/{user_id}/reject", response_model=ApiResponse[UserResponse])
async def reject_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    user = await user_service.reject_user(db, user_id)
    return ApiResponse.ok(UserResponse.model_validate(user))
