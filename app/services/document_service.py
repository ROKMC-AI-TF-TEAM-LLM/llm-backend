import httpx

from app.core.config import settings
from app.core.exceptions import LLMServerError, FileTooLargeError, ConflictError, DocumentNotFoundError, NotFoundError
from app.core.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,func
from sqlalchemy.orm import undefer
from urllib.parse import quote
from app.models.document import Document
from app.schemas.document import DocumentDeleteResponse
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
        # status는 모델 default "pending" 사용
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    #LLM 서버로 relay
    try:
        relay_response = await relay_document(name=name, domain=domain, visibility=visibility, data=data, department=department)
    except Exception as e:
        doc.status = "error"      # MARS에 못 보냄 → 로컬 실패 표시
        doc.error = str(e)
        await db.commit()
        raise

    doc.job_id = relay_response["job_id"]
    # MARS가 준 status를 그대로 저장 (없으면 방금 접수됐으니 queued)
    doc.status = relay_response.get("status", "queued")
    await db.commit()
    await db.refresh(doc)

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

    # 4. MARS가 준 값을 번역 없이 그대로 저장
    doc.status = job["status"]
    doc.chunks_indexed = job.get("chunks_indexed")
    doc.error = job.get("error")

    await db.commit()
    await db.refresh(doc)
    return doc


async def get_admin_documents(
    db: AsyncSession,
    offset: int,
    limit: int,
    domain: str | None = None,
    search: str | None = None,
) -> tuple[list[Document], int, bool]:
    # 1. 필터 조건을 먼저 만든다 (재사용할 거니까)
    filters = []
    if domain:
        filters.append(Document.domain == domain)
    if search:
        filters.append(Document.name.ilike(f"%{search}%"))

    # 2. total — 같은 필터로 개수만 세기
    count_query = select(func.count()).select_from(Document).where(*filters)
    total = await db.scalar(count_query)

    # 3. 실제 목록 — 같은 필터 + offset/limit
    list_query = (
        select(Document)
        .where(*filters)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.scalars(list_query)
    documents = list(result.all())

    # 계산
    has_more = offset + len(documents) < total

    return documents, total, has_more



async def get_document_file(db: AsyncSession, name: str) -> Document:
    """원본 문서를 문서명으로 조회한다 (바이너리 포함).

    name은 unique 제약이 없으므로, 같은 이름이 여러 건이면 가장 최근 등록본을 반환한다.
    """
    doc = await db.scalar(
        select(Document)
        .where(Document.name == name)
        .order_by(Document.created_at.desc())
        .limit(1)
        .options(undefer(Document.data))
    )
    if doc is None:
        raise DocumentNotFoundError()
    return doc


async def delete_document_admin(db: AsyncSession, document_id: uuid.UUID) -> DocumentDeleteResponse:
    # 1. id로 우리 DB에서 조회 (MARS는 name만 알아서 여기서 name을 꺼냄)
    doc = await db.get(Document, document_id)
    if doc is None:
        raise DocumentNotFoundError()

    # 2. MARS 먼저 삭제 (§7: MARS 먼저 → DB 나중)
    try:
        result = await delete_document(doc.name)
        deleted_chunks = result["deleted_chunks"]
    except NotFoundError:
        # MARS에 이미 없음(색인 실패했거나 이미 지워짐) → 목표(MARS에 청크 없음)는 이미 달성 → 멱등 처리
        deleted_chunks = 0
    # ConflictError(409)나 LLMServerError는 여기서 안 잡음 → 그대로 위로 던져짐
    # → DB는 안 지워짐(원본 유지, 재시도 가능) — 이것도 §7 원칙

    # 3. MARS 삭제 성공(또는 멱등 확인) 후에만 DB 원본 삭제
    await db.delete(doc)
    await db.commit()

    return DocumentDeleteResponse(document_id=document_id, deleted_chunks=deleted_chunks)