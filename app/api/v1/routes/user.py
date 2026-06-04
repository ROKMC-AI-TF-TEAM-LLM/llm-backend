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

@router.get(
    "/me",
    response_model=ApiResponse[UserProfileResponse],
    summary="내 정보 조회",
    description="로그인한 사용자 본인의 프로필(이름, 이메일)을 조회합니다.",
    responses={**R_401},
)
async def get_me(current_user: User = Depends(get_current_user)):
    return ApiResponse.ok(UserProfileResponse.model_validate(current_user), status_code=200)
