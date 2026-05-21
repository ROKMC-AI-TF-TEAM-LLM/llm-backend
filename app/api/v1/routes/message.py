import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.message import ChatRequest, MessageResponse
from app.services import message_service

router = APIRouter(prefix="/sessions", tags=["messages"])


@router.get("/{session_id}/messages", response_model=ApiResponse[list[MessageResponse]])
async def get_messages(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    messages = await message_service.get_messages(db, session_id, current_user.user_id)
    return ApiResponse.ok([MessageResponse.model_validate(m) for m in messages])


@router.post("/{session_id}/messages/stream")
async def chat_stream(
    session_id: uuid.UUID,
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return StreamingResponse(
        message_service.chat_stream(db, session_id, current_user.user_id, body.question),
        media_type="text/event-stream",
    )
