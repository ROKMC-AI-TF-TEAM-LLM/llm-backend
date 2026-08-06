import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.responses import R_400_MESSAGE_ROLE, R_401, R_403_SESSION, R_404_MESSAGE, R_404_SESSION, R_422
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.message import ChatRequest, MessagePageResponse, MessageResponse, RegenerateRequest
from app.services import message_service

router = APIRouter(prefix="/sessions", tags=["messages"])


@router.get(
    "/{session_id}/messages",
    response_model=ApiResponse[MessagePageResponse],
    summary="메시지 목록 조회",
    description=(
        "세션의 대화 기록을 시간순(오래된 것 먼저)으로 조회합니다. cursor 기반 무한 스크롤을 지원합니다.\n\n"
        "- 첫 요청: cursor 없이 호출 (최신 메시지부터)\n"
        "- 다음 페이지(과거 메시지): 응답의 `next_cursor` 값을 cursor로 전달\n"
        "- `has_next`가 false이면 더 이상 과거 메시지 없음\n"
        "AI 응답 메시지에는 출처(sources) 정보가 포함됩니다."
    ),
    responses={**R_401, **R_403_SESSION, **R_404_SESSION},
)
async def get_messages(
    session_id: uuid.UUID,
    cursor: datetime | None = Query(None, description="이전 응답의 next_cursor 값"),
    limit: int = Query(20, ge=1, le=100, description="한 번에 가져올 메시지 수"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    messages, has_next = await message_service.get_messages(
        db, session_id, current_user.user_id, cursor=cursor, limit=limit
    )
    next_cursor = messages[0].created_at if has_next and messages else None
    return ApiResponse.ok(MessagePageResponse(
        items=[MessageResponse.model_validate(m) for m in messages],
        next_cursor=next_cursor,
        has_next=has_next,
    ), status_code=200)


@router.post(
    "/{session_id}/messages/stream",
    summary="실시간 채팅 스트리밍",
    description=(
        "LLM에 질문을 전송하고 응답을 Server-Sent Events(SSE) 형식으로 스트리밍합니다.\n\n"
        "**요청 필드 (선택)**\n"
        "- `domain`: 검색 범위 한정 — `HR | TECH | FINANCE_LEGAL | MANUAL(교범) | DIRECTIVE(훈령)`. "
        "생략/빈 값/`ALL`이면 전체 검색. 사용 가능 값은 `GET /capabilities` 참조\n"
        "- `tool`: 처리 경로 강제 — `DOC_SEARCH | DISCHARGE_DAYS`. 생략 시 자동 분류. "
        "지정 시 자동 분류를 건너뛰고 해당 경로로 진행\n\n"
        "**이벤트 타입**\n"
        "- `{\"type\": \"status\", \"stage\": \"...\", \"message\": \"...\"}`: 진행 상태\n"
        "- `{\"type\": \"text\", \"content\": \"...\"}`: 답변 텍스트 (토큰 단위 스트리밍)\n"
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
        message_service.chat_stream(
            db, session_id, current_user.user_id, body.question,
            domain=body.domain, tool=body.tool,
        ),
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
        "- AI 메시지가 아닌 경우 400 오류 반환\n"
        "- body(선택)로 `domain`·`tool`을 지정할 수 있습니다. 원래 질문의 설정은 저장되지 않으므로 "
        "재생성 시 다시 지정해야 하며, 생략하면 자동 분류로 동작합니다"
    ),
    responses={**R_400_MESSAGE_ROLE, **R_401, **R_403_SESSION, **R_404_SESSION, **R_404_MESSAGE},
)
async def regenerate_stream(
    session_id: uuid.UUID,
    message_id: uuid.UUID,
    body: RegenerateRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return StreamingResponse(
        message_service.regenerate_stream(
            db, session_id, message_id, current_user.user_id,
            domain=body.domain if body else None,
            tool=body.tool if body else None,
        ),
        media_type="text/event-stream",
    )
