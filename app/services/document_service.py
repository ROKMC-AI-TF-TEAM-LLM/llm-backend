import httpx

from app.core.config import settings
from app.core.exceptions import LLMServerError, FileTooLargeError, ConflictError, DocumentNotFoundError
from app.core.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import quote
from app.models.document import Document, IndexStatusEnum
import uuid


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
    

async def delete_document(name: str) -> dict:
    url = f"{settings.llm_server_url}/documents/{quote(name)}"
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.delete(url)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        status= e.response.status_code
        if status == 404:
            logger.error("존재 하지 않는 문서 status=%d name=%s",status,name)
            raise DocumentNotFoundError(detail="존재하지 않는 문서입니다.")
        if status == 409:
            logger.error("다른 적재/삭제 작업 진행 중 status=%d",status)
            raise ConflictError(detail="현재 다른 적재/삭제 작업이 진행 중 입니다.")
        logger.error("문서 삭제 실패 status=%d url=%s", status, url)
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
    

async def upload_document(
        db: AsyncSession,
        name: str,
        domain: str,
        visibility: str,
        data : bytes,
        content_type: str,
        department: str | None,
        user_id: uuid.UUID | None,
) -> Document:
    doc = Document(
        name=name,
        domain=domain,
        visibility=visibility,
        data=data,
        content_type=content_type,
        size=len(data),          # ← 빠졌던 필수 필드
        department=department,
        user_id=user_id,
        status=IndexStatusEnum.PENDING,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    #LLM 서버로 relay 
    try:
        job = await relay_document(name=name, domain=domain, visibility=visibility, data=data, department=department)
    except Exception as e:
        doc.status = IndexStatusEnum.FAILED
        doc.error = str(e)
        await db.commit()
        raise 
        

    return doc


async def get_document_status(db: AsyncSession, document_id: uuid.UUID) -> Document:
    doc = await db.get(Document, document_id)      # 1. 조회 (없으면?)
    if doc is None:
        raise doc   # 기존 예외 재활용

    if doc.job_id is None:
        return doc                  # relay 전이거나 이미 끝난 상태 → DB 그대로

    job = await get_job(doc.job_id)  # 2. MARS에 물어봄
    if job is None:
        return doc                  # 3. MARS가 모름(404) → DB 마지막 상태 그대로 (폴백!)

    # 4. 번역해서 갱신
    mars_status = job["status"]
    if mars_status in ("queued", "running"):
        doc.status = IndexStatusEnum.INDEXING
    elif mars_status == "done":
        doc.status = IndexStatusEnum.INDEXED
        doc.chunks_indexed = job["chunks_indexed"]
    elif mars_status == "error":
        doc.status = IndexStatusEnum.FAILED
        doc.error = job["error"]

    await db.commit()
    await db.refresh(doc)
    return doc