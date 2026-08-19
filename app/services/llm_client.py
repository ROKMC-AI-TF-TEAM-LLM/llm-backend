from collections.abc import AsyncGenerator
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


async def download_file(name: str) -> tuple[bytes, str] | None:
    """AI 서버가 생성한 문서 파일을 내려받는다. 실패 시 None (스트림을 막지 않기 위해 예외를 던지지 않음)."""
    url = f"{settings.llm_server_url}/files/{quote(name)}"
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            res = await client.get(url)
            res.raise_for_status()
            content_type = res.headers.get("content-type", "application/octet-stream")
            return res.content, content_type
    except Exception:
        logger.warning("생성 문서 다운로드 실패 url=%s", url)
        return None


async def stream_chat(
    question: str,
    messages: list[dict],
    domain: str | None = None,
    tool: str | None = None,
    project_id: str | None = None,
    project_instructions: str | None = None,
) -> AsyncGenerator[str, None]:
    payload: dict = {"question": question, "messages": messages}
    # 빈 값은 AI 서버 기본값("" = 자동)과 동일하므로 보내지 않는다
    if domain:
        payload["domain"] = domain
    if tool:
        payload["tool"] = tool
    # 값이 있으면 전사 문서 + 그 프로젝트 문서를 검색하고, 없으면 전사 문서만 검색된다.
    # AI 서버는 이 값을 검증 없이 신뢰하므로 호출자가 반드시 소유가 확인된 값만 넘겨야 한다
    if project_id:
        payload["project_id"] = project_id
    # 프로젝트에 설정된 지침. AI 서버는 저장하지 않으므로 매 요청에 실어 보낸다.
    # 길이 제한·정제는 AI 서버 책임이다 (중복 처리하면 상한이 두 곳이 된다)
    if project_instructions:
        payload["project_instructions"] = project_instructions

    timeout = httpx.Timeout(connect=settings.request_timeout, read=None, write=None, pool=None)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            f"{settings.llm_server_url}/query",
            json=payload,
        ) as response:
            buffer = ""
            async for chunk in response.aiter_text():
                logger.debug("[RAW HTTP CHUNK] %r", chunk)
                buffer += chunk

                while "\n\ndata: " in buffer:
                    sep = buffer.find("\n\ndata: ")
                    value = buffer[len("data: "):sep]
                    buffer = "data: " + buffer[sep + len("\n\ndata: "):]
                    yield value

            if buffer.startswith("data: "):
                value = buffer[len("data: "):].rstrip("\n")
                if value:
                    logger.debug("[PARSED EVENT last] %r", value)
                    yield value
