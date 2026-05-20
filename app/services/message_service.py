import json
import uuid
from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logger import get_logger
from app.models.message import Message, RoleEnum
from app.models.session import Session
from app.services import llm_client

logger = get_logger(__name__)


def _to_llm_messages(messages: list[Message]) -> list[dict]:
    return [{"role": m.role.value, "content": m.content} for m in messages]


async def _verify_session(db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID) -> Session:
    session = await db.scalar(select(Session).where(Session.session_id == session_id))
    if not session:
        logger.warning("세션 없음 session_id=%s", session_id)
        raise NotFoundError("세션을 찾을 수 없습니다.")
    if session.user_id != user_id:
        logger.warning("세션 접근 권한 없음 session_id=%s user_id=%s", session_id, user_id)
        raise ForbiddenError("접근 권한이 없습니다.")
    return session


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
    await _verify_session(db, session_id, user_id)
    logger.info("스트리밍 시작 session_id=%s", session_id)

    history_result = await db.scalars(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
    )
    llm_messages = _to_llm_messages(list(history_result.all()))
    logger.info("이전 대화 이력 %d건 전송", len(llm_messages))

    db.add(Message(session_id=session_id, role=RoleEnum.human, content=question))
    await db.commit()
    logger.info("유저 메시지 저장 완료")

    accumulated: list[str] = []
    async for raw in llm_client.stream_chat(question, llm_messages):
        if raw == "[DONE]":
            content = "".join(accumulated)
            db.add(Message(session_id=session_id, role=RoleEnum.ai, content=content))
            await db.commit()
            logger.info("어시스턴트 응답 저장 완료 length=%d", len(content))
            yield "data: [DONE]\n\n"
            return

        if raw.startswith("[ERROR]"):
            logger.error("LLM 오류 응답 session_id=%s error=%s", session_id, raw)
            yield f"data: {raw}\n\n"
            return

        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and parsed.get("type") == "sources":
                logger.debug("출처 이벤트 수신 session_id=%s", session_id)
                yield f"data: {raw}\n\n"
                continue
        except (json.JSONDecodeError, ValueError):
            pass

        accumulated.append(raw)
        yield f"data: {raw}\n\n"
