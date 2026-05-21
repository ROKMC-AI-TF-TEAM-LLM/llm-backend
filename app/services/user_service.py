import uuid

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EmailAlreadyExistsError, UserNotFoundError
from app.models.user import ApprovalStatus, User
from app.schemas.user import UserCreate, UserUpdate


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    existing = await db.scalar(select(User).where(User.email == data.email))
    if existing:
        raise EmailAlreadyExistsError()

    user = User(name=data.name, email=data.email, password=_hash(data.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.scalar(select(User).where(User.user_id == user_id))
    if not user:
        raise UserNotFoundError()
    return user


async def update_user(db: AsyncSession, user_id: uuid.UUID, data: UserUpdate) -> User:
    user = await get_user(db, user_id)

    if data.name is not None:
        user.name = data.name
    if data.email is not None:
        user.email = data.email
    if data.password is not None:
        user.password = _hash(data.password)

    await db.commit()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    user = await get_user(db, user_id)
    await db.delete(user)
    await db.commit()


async def approve_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await get_user(db, user_id)
    user.status = ApprovalStatus.approved
    await db.commit()
    await db.refresh(user)
    return user


async def reject_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await get_user(db, user_id)
    user.status = ApprovalStatus.rejected
    await db.commit()
    await db.refresh(user)
    return user
