import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SessionAccessDeniedError, SessionNotFoundError
from app.core.logger import get_logger
from app.models.message import Message, RoleEnum
from app.models.session import Session
from app.services import llm_client

logger = get_logger(__name__)


def _to_llm_messages(messages: list[Message]) -> list[dict]:
    return [{"role": m.role.value, "content": m.content} for m in messages]


def _parse_event(raw: str) -> dict | None:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


async def _verify_session(db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID) -> Session:
    session = await db.scalar(select(Session).where(Session.session_id == session_id))
    if not session:
        logger.warning("세션 없음 session_id=%s", session_id)
        raise SessionNotFoundError()
    if session.user_id != user_id:
        logger.warning("세션 접근 권한 없음 session_id=%s user_id=%s", session_id, user_id)
        raise SessionAccessDeniedError()
    return session


async def _save_messages(
    db: AsyncSession,
    session: Session,
    session_id: uuid.UUID,
    question: str,
    answer: str,
) -> None:
    db.add(Message(session_id=session_id, role=RoleEnum.human, content=question))
    db.add(Message(session_id=session_id, role=RoleEnum.ai, content=answer))
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("메시지 저장 완료 — human + ai length=%d", len(answer))


async def get_messages(db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID) -> list[Message]:
    await _verify_session(db, session_id, user_id)
    result = await db.scalars(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
    )
    messages = list(result.all())
    logger.info("메시지 이력 조회 session_id=%s count=%d", session_id, len(messages))
    return messages


async def chat_stream(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    question: str,
) -> AsyncGenerator[str, None]:
    session = await _verify_session(db, session_id, user_id)
    logger.info("스트리밍 시작 session_id=%s", session_id)

    history = await db.scalars(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
    )
    llm_messages = _to_llm_messages(list(history.all()))
    logger.info("이전 대화 이력 %d건 전송", len(llm_messages))

    accumulated: list[str] = []

    async for raw in llm_client.stream_chat(question, llm_messages):
        event = _parse_event(raw)
        event_type = event.get("type") if event else None

        if event_type == "done":
            await _save_messages(db, session, session_id, question, "".join(accumulated))
            yield f"data: {raw}\n\n"
            return

        if event_type == "error":
            logger.error("LLM 오류 응답 session_id=%s error=%s", session_id, event.get("message"))
            yield f"data: {raw}\n\n"
            return

        if event_type == "sources":
            logger.debug("출처 이벤트 수신 session_id=%s", session_id)
            yield f"data: {raw}\n\n"
            continue

        accumulated.append(event["content"] if event and event.get("type") == "text" else "")
        yield f"data: {raw}\n\n"
