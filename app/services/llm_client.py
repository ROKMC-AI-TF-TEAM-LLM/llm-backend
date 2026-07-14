from collections.abc import AsyncGenerator

import httpx

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


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
