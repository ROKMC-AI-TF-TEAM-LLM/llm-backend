import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.session import SessionCreate, SessionResponse, SessionUpdate
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


@router.get("", response_model=ApiResponse[list[SessionResponse]])
async def get_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sessions = await session_service.get_sessions(db, current_user.user_id)
    return ApiResponse.ok([SessionResponse.model_validate(s) for s in sessions])


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
