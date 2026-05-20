from collections.abc import AsyncGenerator

import httpx

from app.core.config import settings


async def stream_chat(question: str, messages: list[dict]) -> AsyncGenerator[str, None]:
    timeout = httpx.Timeout(connect=settings.request_timeout, read=None, write=None, pool=None)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            f"{settings.llm_server_url}/api/rag/agent/stream",
            json={"question": question, "messages": messages},
        ) as response:
            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk

                # 이벤트 경계: \n\ndata: (청크 내부 \n\n과 구별 가능)
                while "\n\ndata: " in buffer:
                    sep = buffer.find("\n\ndata: ")
                    value = buffer[len("data: "):sep]
                    buffer = "data: " + buffer[sep + len("\n\ndata: "):]
                    yield value

            # 마지막 이벤트 ([DONE] 또는 [ERROR])
            if buffer.startswith("data: "):
                value = buffer[len("data: "):].rstrip("\n")
                if value:
                    yield value
