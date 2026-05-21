from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.schemas.common import ApiResponse
from app.schemas.user import UserCreate, UserResponse
from app.services import auth_service, user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=ApiResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def signup(data: UserCreate, db: AsyncSession = Depends(get_db)):
    user = await user_service.create_user(db, data)
    return ApiResponse.ok(UserResponse.model_validate(user), status_code=201)


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    access_token, refresh_token = await auth_service.login(db, data.email, data.password)
    return ApiResponse.ok(TokenResponse(access_token=access_token, refresh_token=refresh_token))


@router.post("/refresh", response_model=ApiResponse[TokenResponse])
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    access_token, refresh_token = await auth_service.refresh(db, data.refresh_token)
    return ApiResponse.ok(TokenResponse(access_token=access_token, refresh_token=refresh_token))


@router.post("/logout", response_model=ApiResponse[None])
async def logout(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.logout(db, data.refresh_token)
    return ApiResponse.ok()
