from collections.abc import AsyncGenerator

import httpx

from app.core.config import settings


async def stream_chat(question: str, messages: list[dict]) -> AsyncGenerator[str, None]:
    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        async with client.stream(
            "POST",
            f"{settings.llm_server_url}/api/rag/agent/stream",
            json={"question": question, "messages": messages},
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    yield line[len("data: "):]
