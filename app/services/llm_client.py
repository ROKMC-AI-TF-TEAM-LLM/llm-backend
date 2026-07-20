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
) -> AsyncGenerator[str, None]:
    payload: dict = {"question": question, "messages": messages}
    # 빈 값은 AI 서버 기본값("" = 자동)과 동일하므로 보내지 않는다
    if domain:
        payload["domain"] = domain
    if tool:
        payload["tool"] = tool

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
