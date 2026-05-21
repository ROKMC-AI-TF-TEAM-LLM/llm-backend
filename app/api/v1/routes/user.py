import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=ApiResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db)):
    user = await user_service.create_user(db, data)
    return ApiResponse.ok(UserResponse.model_validate(user), status_code=201)


@router.get("/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    user = await user_service.get_user(db, user_id)
    return ApiResponse.ok(UserResponse.model_validate(user))


@router.patch("/{user_id}", response_model=ApiResponse[UserResponse])
async def update_user(user_id: uuid.UUID, data: UserUpdate, db: AsyncSession = Depends(get_db)):
    user = await user_service.update_user(db, user_id, data)
    return ApiResponse.ok(UserResponse.model_validate(user))


@router.delete("/{user_id}", response_model=ApiResponse[None])
async def delete_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await user_service.delete_user(db, user_id)
    return ApiResponse.ok()
