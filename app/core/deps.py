import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AdminRequiredError, TokenInvalidError, UnauthorizedError
from app.core.logger import user_id_var
from app.models.user import User, UserRole
from app.services import auth_service, user_service

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise UnauthorizedError()
    user_id = auth_service.decode_token(credentials.credentials, expected_type="access")
    try:
        user = await user_service.get_user(db, uuid.UUID(user_id))
    except Exception:
        raise TokenInvalidError()
    # 실제 사용자로 확인된 뒤에만 기록한다 — 이후 이 요청의 모든 로그 줄에 user=가 붙는다
    user_id_var.set(str(user.user_id))
    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != UserRole.admin:
        raise AdminRequiredError()
    return current_user
