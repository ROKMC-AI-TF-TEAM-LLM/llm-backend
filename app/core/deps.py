import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AdminRequiredError, TokenInvalidError
from app.models.user import User, UserRole
from app.services import auth_service, user_service

bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = auth_service.decode_token(credentials.credentials, expected_type="access")
    try:
        return await user_service.get_user(db, uuid.UUID(user_id))
    except Exception:
        raise TokenInvalidError()


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != UserRole.admin:
        raise AdminRequiredError()
    return current_user
