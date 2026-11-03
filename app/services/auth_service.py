import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    ApprovalPendingError,
    ApprovalRejectedError,
    InvalidCredentialsError,
    SessionReplacedError,
    TokenInvalidError,
)
from app.core.logger import get_logger
from app.models.user import ApprovalStatus, User
from app.services.user_service import _verify

logger = get_logger(__name__)


def _create_token(user_id: str, sid: str, token_type: str, expire_delta: timedelta, role: str = "user") -> str:
    payload = {
        "sub": user_id,
        "sid": sid,
        "type": token_type,
        "role": role,
        "exp": datetime.now(timezone.utc) + expire_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str, sid: str, role: str) -> str:
    return _create_token(user_id, sid, "access", timedelta(minutes=settings.access_token_expire_minutes), role)


def create_refresh_token(user_id: str, sid: str) -> str:
    return _create_token(user_id, sid, "refresh", timedelta(days=settings.refresh_token_expire_days))


def decode_token(token: str, expected_type: str) -> tuple[str, str | None]:
    """토큰을 검증하고 (user_id, sid)를 돌려준다. sid 도입 전에 발급된 토큰은 sid가 None이다."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise TokenInvalidError()

    if payload.get("type") != expected_type:
        raise TokenInvalidError()

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise TokenInvalidError()

    return user_id, payload.get("sid")


def ensure_current_session(user: User, sid: str | None) -> None:
    """토큰이 이 사용자의 마지막 로그인에서 발급된 것인지 확인한다 (나중에 로그인한 기기가 이긴다).

    sid가 없는 옛 토큰이나 로그아웃으로 세션이 비워진 경우는 다른 기기 때문이 아니므로
    TOKEN_INVALID로 구분한다 — 프론트가 "다른 기기에서 로그인" 안내를 잘못 띄우지 않도록
    """
    if sid is None or user.current_sid is None:
        raise TokenInvalidError()
    if sid != user.current_sid:
        raise SessionReplacedError()


async def _get_user_by_refresh_token(db: AsyncSession, token: str) -> tuple[User, str]:
    user_id, sid = decode_token(token, expected_type="refresh")
    user = await db.scalar(select(User).where(User.user_id == uuid.UUID(user_id)))
    if not user:
        raise TokenInvalidError()
    ensure_current_session(user, sid)
    # 같은 세션 안에서 이미 교체된 옛 refresh token을 다시 쓴 경우
    if user.refresh_token != token:
        raise TokenInvalidError()
    return user, sid


async def login(db: AsyncSession, email: str, password: str) -> tuple[str, str]:
    user = await db.scalar(select(User).where(User.email == email))
    if not user or not _verify(password, user.password):
        raise InvalidCredentialsError()

    if user.status == ApprovalStatus.pending:
        raise ApprovalPendingError()
    if user.status == ApprovalStatus.rejected:
        raise ApprovalRejectedError()

    user_id = str(user.user_id)
    # 새 sid로 바꾸는 순간 다른 기기의 토큰은 다음 요청부터 SESSION_REPLACED로 거절된다
    sid = uuid.uuid4().hex
    access_token = create_access_token(user_id, sid, user.role.value)
    refresh_token = create_refresh_token(user_id, sid)

    if user.current_sid is not None:
        logger.info("기존 세션 교체 user_id=%s", user_id)
    user.current_sid = sid
    user.refresh_token = refresh_token
    await db.commit()

    return access_token, refresh_token


async def refresh(db: AsyncSession, token: str) -> tuple[str, str]:
    user, sid = await _get_user_by_refresh_token(db, token)
    user_id = str(user.user_id)
    # 재발급은 같은 로그인의 연장이므로 sid를 그대로 둔다
    access_token = create_access_token(user_id, sid, user.role.value)
    new_refresh_token = create_refresh_token(user_id, sid)
    user.refresh_token = new_refresh_token
    await db.commit()
    return access_token, new_refresh_token


async def logout(db: AsyncSession, token: str) -> None:
    try:
        user, _ = await _get_user_by_refresh_token(db, token)
    except SessionReplacedError:
        # 이미 다른 기기에 밀려난 쪽의 로그아웃. 지금 쓰는 기기의 세션을 끊지 않도록 DB는 건드리지 않는다
        return
    user.refresh_token = None
    user.current_sid = None
    await db.commit()
