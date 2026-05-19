import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.models.user import User
from app.services.user_service import _verify


def _create_token(user_id: str, token_type: str, expire_delta: timedelta, role: str = "user") -> str:
    payload = {
        "sub": user_id,
        "type": token_type,
        "role": role,
        "exp": datetime.now(timezone.utc) + expire_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str, role: str) -> str:
    return _create_token(user_id, "access", timedelta(minutes=settings.access_token_expire_minutes), role)


def create_refresh_token(user_id: str) -> str:
    return _create_token(user_id, "refresh", timedelta(days=settings.refresh_token_expire_days))


def decode_token(token: str, expected_type: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise UnauthorizedError("유효하지 않은 토큰입니다.")

    if payload.get("type") != expected_type:
        raise UnauthorizedError("유효하지 않은 토큰입니다.")

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("유효하지 않은 토큰입니다.")

    return user_id


async def _get_user_by_refresh_token(db: AsyncSession, token: str) -> User:
    user_id = decode_token(token, expected_type="refresh")
    user = await db.scalar(select(User).where(User.user_id == uuid.UUID(user_id)))
    if not user or user.refresh_token != token:
        raise UnauthorizedError("유효하지 않은 토큰입니다.")
    return user


async def login(db: AsyncSession, email: str, password: str) -> tuple[str, str]:
    user = await db.scalar(select(User).where(User.email == email))
    if not user or not _verify(password, user.password):
        raise UnauthorizedError("이메일 또는 비밀번호가 올바르지 않습니다.")

    user_id = str(user.user_id)
    access_token = create_access_token(user_id, user.role.value)
    refresh_token = create_refresh_token(user_id)

    user.refresh_token = refresh_token
    await db.commit()

    return access_token, refresh_token


async def refresh(db: AsyncSession, token: str) -> tuple[str, str]:
    user = await _get_user_by_refresh_token(db, token)
    user_id = str(user.user_id)
    access_token = create_access_token(user_id, user.role.value)
    new_refresh_token = create_refresh_token(user_id)
    user.refresh_token = new_refresh_token
    await db.commit()
    return access_token, new_refresh_token


async def logout(db: AsyncSession, token: str) -> None:
    user = await _get_user_by_refresh_token(db, token)
    user.refresh_token = None
    await db.commit()
