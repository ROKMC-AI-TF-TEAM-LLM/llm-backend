from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.responses import R_401_CREDENTIALS, R_401_TOKEN, R_403_APPROVAL, R_409_EMAIL, R_422
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.schemas.common import ApiResponse
from app.schemas.user import UserCreate, UserResponse
from app.services import auth_service, user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=ApiResponse[None],
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
    description="이메일/비밀번호로 신규 계정을 생성합니다. 가입 후 관리자 승인이 필요합니다.",
    responses={**R_409_EMAIL, **R_422},
)
async def signup(data: UserCreate, db: AsyncSession = Depends(get_db)):
    await user_service.create_user(db, data)
    return ApiResponse.ok(status_code=201)


@router.post(
    "/login",
    response_model=ApiResponse[TokenResponse],
    summary="로그인",
    description="이메일/비밀번호로 로그인하여 JWT Access Token과 Refresh Token을 발급합니다.",
    responses={**R_401_CREDENTIALS, **R_403_APPROVAL, **R_422},
)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    access_token, refresh_token = await auth_service.login(db, data.email, data.password)
    return ApiResponse.ok(TokenResponse(access_token=access_token, refresh_token=refresh_token), status_code=200)


@router.post(
    "/refresh",
    response_model=ApiResponse[TokenResponse],
    summary="토큰 재발급",
    description="Refresh Token으로 새 Access Token과 Refresh Token을 재발급합니다.",
    responses={**R_401_TOKEN, **R_422},
)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    access_token, refresh_token = await auth_service.refresh(db, data.refresh_token)
    return ApiResponse.ok(TokenResponse(access_token=access_token, refresh_token=refresh_token), status_code=200)


@router.post(
    "/logout",
    response_model=ApiResponse[None],
    summary="로그아웃",
    description="서버에서 Refresh Token을 무효화합니다.",
    responses={**R_401_TOKEN, **R_422},
)
async def logout(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.logout(db, data.refresh_token)
    return ApiResponse.ok(status_code=200)
