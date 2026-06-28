import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.responses import R_400_MESSAGE_ROLE, R_401, R_403_SESSION, R_404_MESSAGE, R_404_SESSION, R_422
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.message import ChatRequest, MessageListResponse
from app.services import message_service

router = APIRouter(prefix="/sessions", tags=["messages"])


@router.get(
    "/{session_id}/messages",
    response_model=ApiResponse[MessageListResponse],
    summary="메시지 목록 조회",
    description="세션의 전체 대화 기록을 시간순으로 조회합니다. AI 응답 메시지에는 출처(sources) 정보가 포함됩니다.",
    responses={**R_401, **R_403_SESSION, **R_404_SESSION},
)
async def get_messages(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    messages = await message_service.get_messages(db, session_id, current_user.user_id)
    return ApiResponse.ok(MessageListResponse(session_id=session_id, messages=messages), status_code=200)


@router.post(
    "/{session_id}/messages/stream",
    summary="실시간 채팅 스트리밍",
    description=(
        "LLM에 질문을 전송하고 응답을 Server-Sent Events(SSE) 형식으로 스트리밍합니다.\n\n"
        "**이벤트 타입**\n"
        "- 텍스트 토큰: 일반 문자열 (토큰 단위 스트리밍)\n"
        "- `{\"type\": \"sources\", \"items\": [...]}`: 참조 문서 출처\n"
        "- `{\"type\": \"done\"}`: 응답 완료\n"
        "- `{\"type\": \"error\", \"message\": \"...\"}`: 오류 발생"
    ),
    responses={**R_401, **R_403_SESSION, **R_404_SESSION, **R_422},
)
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


@router.delete(
    "/{session_id}/messages/{message_id}",
    response_model=ApiResponse[None],
    summary="메시지 삭제",
    description="메시지 ID로 특정 메시지를 삭제합니다. AI 메시지 삭제 시 출처(sources)도 함께 삭제됩니다.",
    responses={**R_401, **R_403_SESSION, **R_404_SESSION, **R_404_MESSAGE},
)
async def delete_message(
    session_id: uuid.UUID,
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await message_service.delete_message(db, session_id, message_id, current_user.user_id)
    return ApiResponse.ok(status_code=200)


@router.post(
    "/{session_id}/messages/{message_id}/regenerate",
    summary="AI 응답 재생성",
    description=(
        "기존 AI 응답을 삭제하고 동일한 질문으로 LLM에 재요청합니다. "
        "응답은 SSE 형식으로 스트리밍됩니다.\n\n"
        "- `message_id`: 재생성할 AI 메시지의 ID\n"
        "- AI 메시지가 아닌 경우 400 오류 반환"
    ),
    responses={**R_400_MESSAGE_ROLE, **R_401, **R_403_SESSION, **R_404_SESSION, **R_404_MESSAGE},
)
async def regenerate_stream(
    session_id: uuid.UUID,
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return StreamingResponse(
        message_service.regenerate_stream(db, session_id, message_id, current_user.user_id),
        media_type="text/event-stream",
    )
