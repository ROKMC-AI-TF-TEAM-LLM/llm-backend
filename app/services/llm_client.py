import asyncio
from collections.abc import AsyncGenerator

import httpx

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

DONE_EVENT = '{"type": "done"}'


def _normalize(value: str) -> str:
    # LLM 서버는 스트림 종료를 OpenAI 스타일 "[DONE]"으로 보내지만,
    # 백엔드/프론트 계약은 {"type": "done"} JSON 이벤트다.
    return DONE_EVENT if value.strip() == "[DONE]" else value


async def stream_chat(question: str, messages: list[dict]) -> AsyncGenerator[str, None]:
    timeout = httpx.Timeout(connect=settings.request_timeout, read=None, write=None, pool=None)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{settings.llm_server_url}/query",
                json={"question": question, "messages": messages},
            ) as response:
                buffer = ""
                async for chunk in response.aiter_text():
                    logger.debug("[RAW HTTP CHUNK] %r", chunk)
                    buffer += chunk

                    while "\n\ndata: " in buffer:
                        sep = buffer.find("\n\ndata: ")
                        value = buffer[len("data: "):sep]
                        buffer = "data: " + buffer[sep + len("\n\ndata: "):]
                        yield _normalize(value)

                if buffer.startswith("data: "):
                    value = buffer[len("data: "):].rstrip("\n")
                    if value:
                        logger.debug("[PARSED EVENT last] %r", value)
                        yield _normalize(value)
    except (asyncio.CancelledError, GeneratorExit):
        # 클라이언트 연결 중단이 여기까지 전파되면 async with 해제로
        # LLM 서버와의 연결도 닫힌다. 감사 추적용 로그만 남기고 재전파.
        logger.info("LLM 서버 스트림 요청 중단 — 연결을 닫습니다.")
        raise
