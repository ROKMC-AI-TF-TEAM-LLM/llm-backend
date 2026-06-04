import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.responses import R_401, R_404_USER, R_409_EMAIL, R_422
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.user import UserCreate, UserProfileResponse, UserResponse, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "",
    response_model=ApiResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="사용자 생성 (TEST)",
    description="테스트용 사용자 생성 API입니다.",
    responses={**R_409_EMAIL, **R_422},
)
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db)):
    user = await user_service.create_user(db, data)
    return ApiResponse.ok(UserResponse.model_validate(user), status_code=201)


@router.get(
    "/me",
    response_model=ApiResponse[UserProfileResponse],
    summary="내 정보 조회",
    description="로그인한 사용자 본인의 프로필(이름, 이메일)을 조회합니다.",
    responses={**R_401},
)
async def get_me(current_user: User = Depends(get_current_user)):
    return ApiResponse.ok(UserProfileResponse.model_validate(current_user), status_code=200)


@router.get(
    "/{user_id}",
    response_model=ApiResponse[UserResponse],
    summary="사용자 조회 (TEST)",
    description="테스트용 특정 사용자 조회 API입니다.",
    responses={**R_404_USER, **R_422},
)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    user = await user_service.get_user(db, user_id)
    return ApiResponse.ok(UserResponse.model_validate(user), status_code=200)


@router.patch(
    "/{user_id}",
    response_model=ApiResponse[UserResponse],
    summary="사용자 수정 (TEST)",
    description="테스트용 사용자 정보 수정 API입니다.",
    responses={**R_404_USER, **R_422},
)
async def update_user(user_id: uuid.UUID, data: UserUpdate, db: AsyncSession = Depends(get_db)):
    user = await user_service.update_user(db, user_id, data)
    return ApiResponse.ok(UserResponse.model_validate(user), status_code=200)


@router.delete(
    "/{user_id}",
    response_model=ApiResponse[None],
    summary="사용자 삭제 (TEST)",
    description="테스트용 사용자 삭제 API입니다.",
    responses={**R_404_USER},
)
async def delete_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await user_service.delete_user(db, user_id)
    return ApiResponse.ok(status_code=200)
