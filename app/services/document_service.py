import httpx

from app.core.config import settings
from app.core.exceptions import LLMServerError
from app.core.exceptions import FileTooLargeError
from app.core.logger import get_logger

logger = get_logger(__name__)


async def relay_document(
        name: str,
        domain: str,
        visibility: str,
        data: bytes,
        department: str | None = None
    ) -> dict:
    url = f"{settings.llm_server_url}/documents"
    params: dict[str, str] = {"name": name, "domain": domain, "visibility": visibility}
    if department:
        params["department"] = department #department는 조건부 필수라
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.post(
                url,
                params=params,
                content=data,
                headers={"Content-Type": "application/octet-stream"} #mulitpart 아님 
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 413:
            logger.error("문서 용량 초과 name=%s", name)
            raise FileTooLargeError(detail=f"업로드 파일 용량 50MB 초과 (파일이름: {name})") #전용 예외 처리
            
        logger.error("문서 relay 실패 status=%d name=%s", status, name)
        raise LLMServerError(detail=f"LLM서버 적재 요청 실패: HTTP {status}")
    except Exception:
        logger.error("LLM 서버 연결 오류 url=%s", url)
        raise LLMServerError(detail="LLM 서버에 연결할 수 없습니다.")
    

async def get_job(job_id: str) -> dict | None:
    url = f"{settings.llm_server_url}/documents/jobs/{job_id}"

    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 404:
            logger.warning("job 이 없음 (LLM 서버 재시작 추정) job_id=%s",job_id)
            return None #정보 없음을 None으로 알림.
        logger.error("작업 조회 실패 status=%d job_id=%s", status, job_id)
        raise LLMServerError(detail=f"LLM 서버 오류: HTTP {status}")
    except Exception:
        logger.error("LLM 서버 연결 오류 url=%s", url)
        raise LLMServerError(detail="LLM 서버에 연결할 수 없습니다.")
    


async def get_documents(offset: int, limit: int, domain: str | None = None) -> dict:
    url = f"{settings.llm_server_url}/documents"
    params: dict = {"offset": offset, "limit": limit}
    if domain:
        params["domain"] = domain
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error("문서 목록 조회 실패 status=%d url=%s", e.response.status_code, url)
        raise LLMServerError(detail=f"LLM 서버 오류: HTTP {e.response.status_code}")
    except Exception:
        logger.error("LLM 서버 연결 오류 url=%s", url)
        raise LLMServerError(detail="LLM 서버에 연결할 수 없습니다.")