import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InvalidMessageRoleError,
    MessageNotFoundError,
    SessionAccessDeniedError,
    SessionNotFoundError,
)
from app.core.logger import get_logger
from app.models.message import Message, RoleEnum
from app.models.session import Session
from app.models.source import Source
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
    sources: list[dict],
) -> None:
    db.add(Message(session_id=session_id, role=RoleEnum.human, content=question))
    ai_message = Message(session_id=session_id, role=RoleEnum.ai, content=answer)
    db.add(ai_message)
    await db.flush()

    for item in sources:
        db.add(Source(
            message_id=ai_message.message_id,
            name=item.get("name", ""),
            page=item.get("page"),
        ))

    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("메시지 저장 완료 — human + ai length=%d, sources=%d", len(answer), len(sources))


async def _save_ai_message(
    db: AsyncSession,
    session: Session,
    session_id: uuid.UUID,
    answer: str,
    sources: list[dict],
) -> None:
    ai_message = Message(session_id=session_id, role=RoleEnum.ai, content=answer)
    db.add(ai_message)
    await db.flush()

    for item in sources:
        db.add(Source(
            message_id=ai_message.message_id,
            name=item.get("name", ""),
            page=item.get("page"),
        ))

    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("AI 메시지 재저장 완료 length=%d, sources=%d", len(answer), len(sources))


async def get_messages(db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID) -> list[Message]:
    await _verify_session(db, session_id, user_id)
    result = await db.scalars(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .options(selectinload(Message.sources))
    )
    messages = list(result.all())
    logger.info("메시지 이력 조회 session_id=%s count=%d", session_id, len(messages))
    return messages


async def delete_message(
    db: AsyncSession,
    session_id: uuid.UUID,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    await _verify_session(db, session_id, user_id)

    message = await db.scalar(
        select(Message).where(
            Message.message_id == message_id,
            Message.session_id == session_id,
        )
    )
    if not message:
        raise MessageNotFoundError()

    await db.delete(message)
    await db.commit()
    logger.info("메시지 삭제 완료 message_id=%s", message_id)


async def regenerate_stream(
    db: AsyncSession,
    session_id: uuid.UUID,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AsyncGenerator[str, None]:
    try:
        session = await _verify_session(db, session_id, user_id)
    except Exception as e:
        from app.core.exceptions import AppHTTPException
        detail = e.detail if isinstance(e, AppHTTPException) else "인증 오류가 발생했습니다."
        yield f"data: {json.dumps({'type': 'error', 'message': detail})}\n\n"
        return

    ai_message = await db.scalar(
        select(Message).where(
            Message.message_id == message_id,
            Message.session_id == session_id,
        )
    )
    if not ai_message:
        yield f"data: {json.dumps({'type': 'error', 'message': '메시지를 찾을 수 없습니다.'})}\n\n"
        return
    if ai_message.role != RoleEnum.ai:
        yield f"data: {json.dumps({'type': 'error', 'message': 'AI 메시지만 재생성할 수 있습니다.'})}\n\n"
        return

    human_message = await db.scalar(
        select(Message)
        .where(
            Message.session_id == session_id,
            Message.role == RoleEnum.human,
            Message.created_at < ai_message.created_at,
        )
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    if not human_message:
        yield f"data: {json.dumps({'type': 'error', 'message': '원본 질문 메시지를 찾을 수 없습니다.'})}\n\n"
        return

    question = human_message.content

    history_result = await db.scalars(
        select(Message)
        .where(
            Message.session_id == session_id,
            Message.created_at < human_message.created_at,
        )
        .order_by(Message.created_at.asc())
    )
    llm_messages = _to_llm_messages(list(history_result.all()))

    await db.delete(ai_message)
    await db.commit()
    logger.info("기존 AI 메시지 삭제 message_id=%s", message_id)

    accumulated: list[str] = []
    pending_sources: list[dict] = []

    async for raw in llm_client.stream_chat(question, llm_messages):
        event = _parse_event(raw)
        event_type = event.get("type") if event else None

        if event_type == "done":
            answer = "".join(accumulated)
            if not answer:
                logger.warning("LLM 빈 응답 수신 session_id=%s", session_id)
                yield f"data: {json.dumps({'type': 'error', 'message': 'LLM이 빈 응답을 반환했습니다.'})}\n\n"
                return
            await _save_ai_message(db, session, session_id, answer, pending_sources)
            yield f"data: {raw}\n\n"
            return

        if event_type == "error":
            logger.error("LLM 오류 응답 session_id=%s error=%s", session_id, event.get("message"))
            yield f"data: {raw}\n\n"
            return

        if event_type == "sources":
            pending_sources = event.get("items", [])
            logger.debug("출처 이벤트 수신 session_id=%s count=%d", session_id, len(pending_sources))
            yield f"data: {raw}\n\n"
            continue

        accumulated.append(event["content"] if event and event.get("type") == "text" else raw)
        yield f"data: {raw}\n\n"


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
    pending_sources: list[dict] = []

    async for raw in llm_client.stream_chat(question, llm_messages):
        event = _parse_event(raw)
        event_type = event.get("type") if event else None

        if event_type == "done":
            answer = "".join(accumulated)
            if not answer:
                logger.warning("LLM 빈 응답 수신 session_id=%s", session_id)
                yield f"data: {json.dumps({'type': 'error', 'message': 'LLM이 빈 응답을 반환했습니다.'})}\n\n"
                return
            await _save_messages(db, session, session_id, question, answer, pending_sources)
            yield f"data: {raw}\n\n"
            return

        if event_type == "error":
            logger.error("LLM 오류 응답 session_id=%s error=%s", session_id, event.get("message"))
            yield f"data: {raw}\n\n"
            return

        if event_type == "sources":
            pending_sources = event.get("items", [])
            logger.debug("출처 이벤트 수신 session_id=%s count=%d", session_id, len(pending_sources))
            yield f"data: {raw}\n\n"
            continue

        accumulated.append(event["content"] if event and event.get("type") == "text" else raw)
        yield f"data: {raw}\n\n"
