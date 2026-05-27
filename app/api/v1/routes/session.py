import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.session import SessionCreate, SessionPageResponse, SessionResponse, SessionUpdate
from app.services import session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=ApiResponse[SessionResponse], status_code=status.HTTP_201_CREATED)
async def create_session(
    data: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await session_service.create_session(db, current_user.user_id, data)
    return ApiResponse.ok(SessionResponse.model_validate(session), status_code=201)


@router.get("", response_model=ApiResponse[SessionPageResponse])
async def get_sessions(
    cursor: datetime | None = Query(None),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sessions, has_next = await session_service.get_sessions(
        db, current_user.user_id, cursor=cursor, size=size
    )
    next_cursor = sessions[-1].updated_at if has_next and sessions else None
    return ApiResponse.ok(SessionPageResponse(
        items=[SessionResponse.model_validate(s) for s in sessions],
        next_cursor=next_cursor,
        has_next=has_next,
    ))


@router.get("/search", response_model=ApiResponse[list[SessionResponse]])
async def search_sessions(
    q: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sessions = await session_service.search_sessions(db, current_user.user_id, q)
    return ApiResponse.ok([SessionResponse.model_validate(s) for s in sessions], status_code=200)


@router.patch("/{session_id}", response_model=ApiResponse[SessionResponse])
async def update_session(
    session_id: uuid.UUID,
    data: SessionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await session_service.update_session(db, session_id, current_user.user_id, data)
    return ApiResponse.ok(SessionResponse.model_validate(session))


@router.delete("/{session_id}", response_model=ApiResponse[None])
async def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await session_service.delete_session(db, session_id, current_user.user_id)
    return ApiResponse.ok()
