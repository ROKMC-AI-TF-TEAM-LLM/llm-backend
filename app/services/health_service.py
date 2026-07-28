import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


async def check_db(db: AsyncSession) -> bool:
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.warning("DB 연결 실패")
        return False


async def check_llm_server() -> bool:
    url = f"{settings.llm_server_url}/health?deep=true"
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            res = await client.get(url)
            res.raise_for_status()
            status = res.json().get("status")
    except httpx.HTTPStatusError as e:
        logger.warning("LLM 서버 응답 오류 status=%d url=%s", e.response.status_code, url)
        return False
    except Exception:
        logger.warning("LLM 서버에 연결할 수 없습니다 url=%s", url)
        return False

    if status != "ok":
        logger.warning("LLM 서버 상태 이상 status=%s url=%s", status, url)
        return False
    return True
