import httpx

from app.core.config import settings
from app.core.exceptions import LLMServerError
from app.core.logger import get_logger

logger = get_logger(__name__)


async def get_documents(offset: int, limit: int, domain: str | None = None) -> dict:
    url = f"{settings.llm_server_url}/documents"
    params = {"offset": offset, "limit": limit}
    if domain:
        params["domain"] = domain
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as e:
        logger.error("문서 목록 조회 실패 status=%d url=%s", e.response.status_code, url)
        raise LLMServerError(detail=f"LLM 서버 오류: HTTP {e.response.status_code}")
    except Exception:
        logger.error("LLM 서버 연결 오류 url=%s", url)
        raise LLMServerError(detail="LLM 서버에 연결할 수 없습니다.")

    logger.info(
        "문서 목록 조회 total=%s offset=%d limit=%d domain=%s",
        payload.get("total"), offset, limit, domain or "전체",
    )
    return payload
