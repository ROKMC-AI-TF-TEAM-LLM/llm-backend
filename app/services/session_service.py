import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SessionAccessDeniedError, SessionNotFoundError
from app.models.session import Session
from app.schemas.session import SessionCreate, SessionUpdate


async def create_session(db: AsyncSession, user_id: uuid.UUID, data: SessionCreate) -> Session:
    session = Session(user_id=user_id, title=data.title)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_sessions(db: AsyncSession, user_id: uuid.UUID) -> list[Session]:
    result = await db.scalars(
        select(Session)
        .where(Session.user_id == user_id)
        .order_by(Session.updated_at.desc())
    )
    return list(result.all())


async def search_sessions(db: AsyncSession, user_id: uuid.UUID, q: str) -> list[Session]:
    result = await db.scalars(
        select(Session)
        .where(Session.user_id == user_id, Session.title.ilike(f"%{q}%"))
        .order_by(Session.updated_at.desc())
    )
    return list(result.all())


async def _get_session_owned(db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID) -> Session:
    session = await db.scalar(select(Session).where(Session.session_id == session_id))
    if not session:
        raise SessionNotFoundError()
    if session.user_id != user_id:
        raise SessionAccessDeniedError()
    return session


async def update_session(db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID, data: SessionUpdate) -> Session:
    session = await _get_session_owned(db, session_id, user_id)
    session.title = data.title
    await db.commit()
    await db.refresh(session)
    return session


async def delete_session(db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID) -> None:
    session = await _get_session_owned(db, session_id, user_id)
    await db.delete(session)
    await db.commit()
