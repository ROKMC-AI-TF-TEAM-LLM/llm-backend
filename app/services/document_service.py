import httpx

from app.core.config import settings
from app.core.exceptions import LLMServerError
from app.core.logger import get_logger

logger = get_logger(__name__)


async def get_documents(offset: int, limit: int) -> dict:
    url = f"{settings.llm_server_url}/api/documents"
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.get(url, params={"offset": offset, "limit": limit})
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error("문서 목록 조회 실패 status=%d url=%s", e.response.status_code, url)
        raise LLMServerError(detail=f"LLM 서버 오류: HTTP {e.response.status_code}")
    except Exception:
        logger.error("LLM 서버 연결 오류 url=%s", url)
        raise LLMServerError(detail="LLM 서버에 연결할 수 없습니다.")
