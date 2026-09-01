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

async def check_translation_server() -> bool:
    # LLM 서버와 달리 deep 파라미터가 없다. 준비 여부는 ready 필드가 단일 출처다.
    url = f"{settings.translate_server_url}/health"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url)
            res.raise_for_status()
            body = res.json()
            status, ready, detail = body.get("status"), body.get("ready"), body.get("detail")
    except httpx.HTTPStatusError as e:
        logger.warning("번역 서버 응답 오류 status=%d url=%s", e.response.status_code, url)
        return False
    except Exception:
        logger.warning("번역 서버에 연결할 수 없습니다 url=%s", url)
        return False

    # 기동 시 용어 인덱스 빌드에 10~20초가 걸리고 그동안 status=starting·ready=false다.
    # 번역 서버보다 백엔드가 먼저 뜨면 여기 걸리지만 잠시 뒤 스스로 해소된다.
    if not ready:
        logger.warning("번역 서버가 아직 준비되지 않았습니다 status=%s url=%s", status, url)
        return False
    if status != "ok":
        logger.warning("번역 서버 상태 이상 status=%s detail=%s url=%s", status, detail, url)
        return False
    return True
