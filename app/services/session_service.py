import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SessionAccessDeniedError, SessionNotFoundError
from app.models.session import Session
from app.schemas.session import SessionCreate, SessionUpdate
from app.services import project_service


async def create_session(db: AsyncSession, user_id: uuid.UUID, data: SessionCreate) -> Session:
    # 남의 프로젝트에 내 대화를 꽂아 넣지 못하도록 소유권을 먼저 확인한다
    if data.project_id is not None:
        await project_service.get_project(db, data.project_id, user_id)

    session = Session(user_id=user_id, title=data.title, project_id=data.project_id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_sessions(
    db: AsyncSession,
    user_id: uuid.UUID,
    cursor: datetime | None = None,
    size: int = 20,
    is_favorite: bool | None = None,
) -> tuple[list[Session], bool]:
    query = (
        select(Session)
        .where(Session.user_id == user_id)
        .order_by(Session.updated_at.desc())
        .limit(size + 1)
    )
    if cursor:
        query = query.where(Session.updated_at < cursor)
    if is_favorite is not None:
        query = query.where(Session.is_favorite == is_favorite)

    result = await db.scalars(query)
    sessions = list(result.all())
    has_next = len(sessions) > size
    return sessions[:size], has_next


async def get_project_sessions(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    cursor: datetime | None = None,
    size: int = 20,
) -> tuple[list[Session], bool]:
    # 프로젝트 소유권을 먼저 확인한다 (없으면 404, 남의 것이면 403)
    await project_service.get_project(db, project_id, user_id)

    query = (
        select(Session)
        .where(Session.project_id == project_id, Session.user_id == user_id)
        .order_by(Session.updated_at.desc())
        .limit(size + 1)
    )
    if cursor:
        query = query.where(Session.updated_at < cursor)

    result = await db.scalars(query)
    sessions = list(result.all())
    has_next = len(sessions) > size
    return sessions[:size], has_next


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


async def set_favorite(
    db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID, is_favorite: bool
) -> Session:
    session = await _get_session_owned(db, session_id, user_id)
    # updated_at을 SET에 그대로 명시해 onupdate 갱신을 막는다
    # (즐겨찾기 변경이 최근 수정순 목록의 순서를 바꾸지 않도록)
    await db.execute(
        update(Session)
        .where(Session.session_id == session_id)
        .values(is_favorite=is_favorite, updated_at=Session.updated_at)
    )
    await db.commit()
    await db.refresh(session)
    return session


async def delete_session(db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID) -> None:
    session = await _get_session_owned(db, session_id, user_id)
    await db.delete(session)
    await db.commit()
