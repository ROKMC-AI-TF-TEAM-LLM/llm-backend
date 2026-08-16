import json
import re
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from urllib.parse import unquote

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    InvalidMessageRoleError,
    MessageNotFoundError,
    SessionAccessDeniedError,
    SessionNotFoundError,
)
from app.core.logger import get_logger
from app.models.attachment import Attachment
from app.models.message import Message, RoleEnum
from app.models.session import Session
from app.models.source import Source
from app.services import llm_client

logger = get_logger(__name__)

# 답변 텍스트 속 AI 서버 생성 문서 링크 (예: /files/MARS_%EB%8B%B5%EB%B3%80_...hwpx)
_FILE_LINK_RE = re.compile(r"/files/([^\s\"'<>()\[\]]+)")


async def _collect_attachments(
    answer: str, extra_names: list[str] | None = None
) -> tuple[str, list[Attachment], list[dict]]:
    """답변 속 /files/ 링크와 file 이벤트로 알려진 파일을 AI 서버에서 내려받는다.

    AI 서버 파일은 정리 주기에 따라 삭제되므로 즉시 받아 보관하고,
    텍스트 링크는 미들웨어 다운로드 URL로 치환해 반환한다.
    다운로드 실패 시 해당 파일만 건너뛰고 원본 링크를 유지한다.
    """
    attachments: list[Attachment] = []
    items: list[dict] = []

    # (치환할 링크 조각 | None, 파일명) 목록 — 텍스트 링크 우선, file 이벤트로만 알려진 파일은 치환 없이 저장
    targets: list[tuple[str | None, str]] = []
    seen: set[str] = set()
    for raw in dict.fromkeys(_FILE_LINK_RE.findall(answer)):
        name = unquote(raw)
        targets.append((raw, name))
        seen.add(name)
    for extra in extra_names or []:
        name = unquote(extra)
        if name not in seen:
            targets.append((None, name))
            seen.add(name)

    for raw, name in targets:
        result = await llm_client.download_file(name)
        if result is None:
            continue
        data, content_type = result
        if len(data) > settings.max_attachment_size_mb * 1024 * 1024:
            logger.warning("첨부 크기 초과로 저장 생략 name=%s size=%d", name, len(data))
            continue

        attachment = Attachment(
            attachment_id=uuid.uuid4(),
            name=name,
            content_type=content_type,
            size=len(data),
            data=data,
        )
        url = f"/api/v1/files/{attachment.attachment_id}"
        if raw:
            answer = answer.replace(f"/files/{raw}", url)
        attachments.append(attachment)
        items.append({
            "attachment_id": str(attachment.attachment_id),
            "name": name,
            "size": len(data),
            "url": url,
        })
        logger.info("생성 문서 저장 name=%s size=%d", name, len(data))

    return answer, attachments, items


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


async def _save_question(
    db: AsyncSession,
    session: Session,
    session_id: uuid.UUID,
    question: str,
    domain: str | None = None,
) -> None:
    db.add(Message(session_id=session_id, role=RoleEnum.human, content=question, domain=domain))
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("질문 저장 완료 session_id=%s", session_id)


async def _save_ai_message(
    db: AsyncSession,
    session: Session,
    session_id: uuid.UUID,
    answer: str,
    sources: list[dict],
    attachments: list[Attachment] | None = None,
    domain: str | None = None,
    notice_code: str | None = None,
) -> None:
    ai_message = Message(
        session_id=session_id,
        role=RoleEnum.ai,
        content=answer,
        domain=domain,
        notice_code=notice_code,
    )
    db.add(ai_message)
    await db.flush()

    for item in sources:
        db.add(Source(
            message_id=ai_message.message_id,
            name=item.get("name", ""),
            page=item.get("page"),
        ))

    for attachment in attachments or []:
        attachment.message_id = ai_message.message_id
        db.add(attachment)

    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info(
        "AI 메시지 저장 완료 length=%d, sources=%d, attachments=%d, notice=%s",
        len(answer), len(sources), len(attachments or []), notice_code or "-",
    )


async def get_messages(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    cursor: datetime | None = None,
    limit: int = 20,
) -> tuple[list[Message], bool]:
    await _verify_session(db, session_id, user_id)
    query = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(limit + 1)
        .options(selectinload(Message.sources), selectinload(Message.attachments))
    )
    if cursor:
        query = query.where(Message.created_at < cursor)
    result = await db.scalars(query)
    messages = list(result.all())
    has_next = len(messages) > limit
    messages = messages[:limit]
    messages.reverse()  # DESC로 가져온 걸 화면 표시용(오래된 것 먼저)으로 뒤집음
    logger.info("메시지 이력 조회 session_id=%s count=%d has_next=%s", session_id, len(messages), has_next)
    return messages, has_next


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
    domain: str | None = None,
    tool: str | None = None,
) -> AsyncGenerator[str, None]:
    try:
        session = await _verify_session(db, session_id, user_id)

        result = await db.scalars(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
        )
        all_msgs = list(result.all())

        ai_idx = next((i for i, m in enumerate(all_msgs) if m.message_id == message_id), None)
        if ai_idx is None:
            yield f"data: {json.dumps({'type': 'error', 'message': '메시지를 찾을 수 없습니다.'})}\n\n"
            return

        ai_message = all_msgs[ai_idx]
        if ai_message.role != RoleEnum.ai:
            yield f"data: {json.dumps({'type': 'error', 'message': 'AI 메시지만 재생성할 수 있습니다.'})}\n\n"
            return

        human_idx = next(
            (i for i in range(ai_idx - 1, -1, -1) if all_msgs[i].role == RoleEnum.human),
            None,
        )
        if human_idx is None:
            yield f"data: {json.dumps({'type': 'error', 'message': '원본 질문 메시지를 찾을 수 없습니다.'})}\n\n"
            return

        question = all_msgs[human_idx].content
        llm_messages = _to_llm_messages(all_msgs[:human_idx])

    except Exception as e:
        from app.core.exceptions import AppHTTPException
        detail = e.detail if isinstance(e, AppHTTPException) else "서버 오류가 발생했습니다."
        logger.exception("재생성 전처리 오류 session_id=%s message_id=%s", session_id, message_id)
        yield f"data: {json.dumps({'type': 'error', 'message': detail})}\n\n"
        return

    await db.delete(ai_message)
    await db.commit()
    logger.info("기존 AI 메시지 삭제 message_id=%s", message_id)

    accumulated: list[str] = []
    pending_sources: list[dict] = []
    pending_file_names: list[str] = []
    pending_notice_code: str | None = None

    # 프로젝트 소속 대화면 그 프로젝트의 참고 파일까지 검색 범위에 넣는다.
    # 값을 요청 body가 아닌 **세션 행에서 읽는 것이 핵심**이다 — _verify_session이
    # 세션 소유권을 이미 확인했으므로 이 값은 정의상 이 사용자의 프로젝트다.
    # AI 서버는 project_id를 검증 없이 신뢰하므로, 클라이언트가 값을 주입할 수 있으면
    # 남의 프로젝트 문서가 읽힌다. 주입 표면 자체를 두지 않는다
    project_id = str(session.project_id) if session.project_id else None

    async for raw in llm_client.stream_chat(
        question, llm_messages, domain=domain, tool=tool, project_id=project_id
    ):
        event = _parse_event(raw)
        event_type = event.get("type") if event else None

        if event_type == "done":
            answer = "".join(accumulated)
            if not answer:
                logger.warning("LLM 빈 응답 수신 session_id=%s", session_id)
                yield f"data: {json.dumps({'type': 'error', 'message': 'LLM이 빈 응답을 반환했습니다.'})}\n\n"
                return
            answer, attachments, file_items = await _collect_attachments(answer, pending_file_names)
            await _save_ai_message(
                db, session, session_id, answer, pending_sources, attachments, domain,
                notice_code=pending_notice_code,
            )
            if file_items:
                yield f"data: {json.dumps({'type': 'files', 'items': file_items}, ensure_ascii=False)}\n\n"
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

        if event_type == "notice":
            # 답변에 대한 경고(예: 문서 근거 없이 AI 지식으로 답한 경우).
            # code만 담는다 — 문구는 AI 서버가 code로 고르라고 명시한 계약이다.
            # 프론트에는 원본을 그대로 흘려 실시간 표시를 막지 않는다
            pending_notice_code = event.get("code")
            logger.info("경고 이벤트 수신 session_id=%s code=%s", session_id, pending_notice_code)
            yield f"data: {raw}\n\n"
            continue

        if event_type == "status":
            yield f"data: {raw}\n\n"
            continue

        if event_type == "file":
            # AI 서버의 생성 문서 알림 이벤트. done 시점에 저장 후 미들웨어 files
            # 이벤트로 통합 전달하므로 원본(AI 서버 경로)은 프론트에 넘기지 않는다
            if event.get("name"):
                pending_file_names.append(event["name"])
            continue

        if event_type == "text":
            accumulated.append(event.get("content", ""))
            yield f"data: {raw}\n\n"
            continue

        if event is None:
            # 구형 형식: 타입 없는 일반 문자열 토큰
            accumulated.append(raw)

        # 미지의 타입 이벤트는 답변 텍스트에 섞지 않고 그대로 통과시킨다
        yield f"data: {raw}\n\n"


async def chat_stream(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    question: str,
    domain: str | None = None,
    tool: str | None = None,
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

    await _save_question(db, session, session_id, question, domain)

    accumulated: list[str] = []
    pending_sources: list[dict] = []
    pending_file_names: list[str] = []
    pending_notice_code: str | None = None

    # 프로젝트 소속 대화면 그 프로젝트의 참고 파일까지 검색 범위에 넣는다.
    # 값을 요청 body가 아닌 **세션 행에서 읽는 것이 핵심**이다 — _verify_session이
    # 세션 소유권을 이미 확인했으므로 이 값은 정의상 이 사용자의 프로젝트다.
    # AI 서버는 project_id를 검증 없이 신뢰하므로, 클라이언트가 값을 주입할 수 있으면
    # 남의 프로젝트 문서가 읽힌다. 주입 표면 자체를 두지 않는다
    project_id = str(session.project_id) if session.project_id else None

    async for raw in llm_client.stream_chat(
        question, llm_messages, domain=domain, tool=tool, project_id=project_id
    ):
        event = _parse_event(raw)
        event_type = event.get("type") if event else None

        if event_type == "done":
            answer = "".join(accumulated)
            if not answer:
                logger.warning("LLM 빈 응답 수신 session_id=%s", session_id)
                yield f"data: {json.dumps({'type': 'error', 'message': 'LLM이 빈 응답을 반환했습니다.'})}\n\n"
                return
            answer, attachments, file_items = await _collect_attachments(answer, pending_file_names)
            await _save_ai_message(
                db, session, session_id, answer, pending_sources, attachments, domain,
                notice_code=pending_notice_code,
            )
            if file_items:
                yield f"data: {json.dumps({'type': 'files', 'items': file_items}, ensure_ascii=False)}\n\n"
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

        if event_type == "notice":
            # 답변에 대한 경고(예: 문서 근거 없이 AI 지식으로 답한 경우).
            # code만 담는다 — 문구는 AI 서버가 code로 고르라고 명시한 계약이다.
            # 프론트에는 원본을 그대로 흘려 실시간 표시를 막지 않는다
            pending_notice_code = event.get("code")
            logger.info("경고 이벤트 수신 session_id=%s code=%s", session_id, pending_notice_code)
            yield f"data: {raw}\n\n"
            continue

        if event_type == "status":
            yield f"data: {raw}\n\n"
            continue

        if event_type == "file":
            # AI 서버의 생성 문서 알림 이벤트. done 시점에 저장 후 미들웨어 files
            # 이벤트로 통합 전달하므로 원본(AI 서버 경로)은 프론트에 넘기지 않는다
            if event.get("name"):
                pending_file_names.append(event["name"])
            continue

        if event_type == "text":
            accumulated.append(event.get("content", ""))
            yield f"data: {raw}\n\n"
            continue

        if event is None:
            # 구형 형식: 타입 없는 일반 문자열 토큰
            accumulated.append(raw)

        # 미지의 타입 이벤트는 답변 텍스트에 섞지 않고 그대로 통과시킨다
        yield f"data: {raw}\n\n"
