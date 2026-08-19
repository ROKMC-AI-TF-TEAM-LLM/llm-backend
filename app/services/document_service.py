import httpx

from app.core.config import settings
from app.core.exceptions import LLMServerError, FileTooLargeError, ConflictError, DocumentNotFoundError, BadRequestError
from app.core.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,func
from sqlalchemy.orm import undefer, joinedload, load_only
from urllib.parse import quote
from app.models.document import Document
from app.models.user import User
from app.schemas.document import DocumentDeleteResponse
import uuid


logger = get_logger(__name__)


async def relay_document(
        name: str,
        domain: str,
        visibility: str,
        data: bytes,
        department: str | None = None,
        project_id: str | None = None,
    ) -> dict:
    url = f"{settings.llm_server_url}/documents"
    params: dict[str, str] = {"name": name, "domain": domain, "visibility": visibility}
    if department:
        params["department"] = department  # visibility=DEPT_ONLY일 때 조건부 필수
    if project_id:
        # 지정하면 그 프로젝트 채팅에서만 검색되는 문서로 적재된다. 없으면 전사 공용.
        # 형식(영숫자·_·-, 64자)이 틀리면 MARS가 400으로 거부한다 — 조용히 빈 값으로
        # 처리하면 프로젝트 전용 문서가 전사 공용으로 영구히 남기 때문이다
        params["project_id"] = project_id
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.post(
                url,
                params=params,
                content=data,
                headers={"Content-Type": "application/octet-stream"},  # multipart 아님
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 413:
            logger.error("문서 용량 초과 name=%s", name)
            raise FileTooLargeError(detail=f"업로드 파일 용량 50MB 초과 (파일이름: {name})")
        if status == 400:
            # 파라미터 오류(형식·도메인·빈 본문). 사용자가 고칠 수 있는 정보라 문구를 그대로 전달한다.
            # detail은 문자열이 아닐 수 있고(FastAPI 422는 리스트), 응답이 JSON이 아닐 수도 있다
            try:
                detail = e.response.json().get("detail")
            except Exception:
                detail = None
            if not isinstance(detail, str) or not detail:
                detail = "적재 요청이 거부되었습니다."
            logger.error("문서 적재 파라미터 오류 name=%s detail=%s", name, detail)
            raise BadRequestError(detail=detail)

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
            return None  # 서버 재시작으로 이력이 사라진 경우 — 호출자가 DB 값을 유지한다
        logger.error("작업 조회 실패 status=%d job_id=%s", status, job_id)
        raise LLMServerError(detail=f"LLM 서버 오류: HTTP {status}")
    except Exception:
        logger.error("LLM 서버 연결 오류 url=%s", url)
        raise LLMServerError(detail="LLM 서버에 연결할 수 없습니다.")


async def delete_document(name: str, project_id: str) -> dict:
    url = f"{settings.llm_server_url}/documents/{quote(name)}"
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.delete(url, params={"project_id":project_id})
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


async def delete_all_project_documents(project_id: str) -> dict:
    """프로젝트에 적재된 문서를 한 번에 삭제한다 (전사 공용 문서는 건드리지 않는다).

    동기 처리다 — 색인 재빌드 때문에 수 초~수십 초 걸릴 수 있다.
    적재된 문서가 없으면(404) 목표가 이미 달성된 것으로 보고 0건을 반환한다.
    """
    url = f"{settings.llm_server_url}/projects/{quote(project_id)}"
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.delete(url)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 404:
            # 해당 프로젝트에 적재된 문서 없음 → 멱등 처리
            logger.warning("프로젝트에 적재된 문서 없음 project_id=%s", project_id)
            return {"documents": [], "deleted_chunks": 0, "deleted_parents": 0}
        if status == 409:
            logger.error("다른 적재/삭제 작업 진행 중 project_id=%s", project_id)
            raise ConflictError(detail="현재 다른 적재/삭제 작업이 진행 중 입니다.")
        logger.error("프로젝트 문서 삭제 실패 status=%d project_id=%s", status, project_id)
        raise LLMServerError(detail=f"LLM 서버 오류: HTTP {status}")
    except Exception:
        logger.error("LLM 서버 연결 오류 url=%s", url)
        raise LLMServerError(detail="LLM 서버에 연결할 수 없습니다.")


async def get_documents(
    offset: int,
    limit: int,
    domain: str | None = None,
    project_id: str | None = None,
) -> dict:
    url = f"{settings.llm_server_url}/documents"
    params: dict = {"offset": offset, "limit": limit}
    if domain:
        params["domain"] = domain
    # ""(빈 문자열)은 "전사 공용만"이라는 의미가 있으므로 None과 구분해야 한다.
    # `if project_id:`로 쓰면 빈 문자열이 걸러져 프로젝트 문서까지 함께 반환된다
    if project_id is not None:
        params["project_id"] = project_id
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
        size=len(data),
        department=department,
        user_id=user_id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

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
    """MARS의 job 상태를 DB에 mirroring하고 최신 문서를 반환한다.

    관리자 문서와 프로젝트 참고 파일이 같은 정책을 쓴다 — mirroring 규칙이
    두 벌이 되면 정책이 갈린다.

    [임시방안] job이 404면 색인 실패로 확정한다. 유지하면 status가 running에
    고정돼 클라이언트가 영원히 폴링하고, 삭제·재시도 어느 쪽도 열리지 않기 때문이다.

    ⚠ MARS의 job 이력은 재시작뿐 아니라 100건 상한 prune으로도 사라지므로
    (`ingest_jobs.py` `_prune`), **색인에 성공한 문서가 404가 되는 경우가 있다.**
    즉 이 처리는 성공을 실패로 오판할 수 있다. 오판해도 재적재는 멱등이라 데이터가
    깨지지는 않지만, 근본 해법은 404 시 `GET /documents?project_id=`로 실제 적재
    여부를 확인하는 것이다 — my_docs/ingest_state_defects.md D6 참조.
    """
    doc = await db.get(Document, document_id)
    if doc is None:
        raise DocumentNotFoundError()

    if doc.job_id is None:
        return doc                  # relay 전이거나 이미 끝난 상태 → DB 그대로

    job = await get_job(doc.job_id)
    if job is None:
        # 이력이 사라진 job은 다시 진행될 수 없다. 종결 상태로 확정해 재시도/삭제를 연다
        logger.warning(
            "job 이력 유실 → 색인 실패로 확정 document_id=%s job_id=%s",
            document_id, doc.job_id,
        )
        doc.status = "error"
        doc.error = "색인 작업 이력이 유실되었습니다 (AI 서버 재시작 추정). 다시 시도해 주세요."
        await db.commit()
        await db.refresh(doc)
        return doc

    # MARS가 준 값을 번역 없이 그대로 저장한다 (새 상태가 추가돼도 깨지지 않도록)
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
    # [전사 문서 전용] 프로젝트 참고 파일은 사용자 개인 자료이므로 관리자 목록에서 제외한다.
    # 섞이면 개인 파일이 관리자 화면에 노출되고, 관리자 삭제 대상이 된다. I-09 참조.
    filters = [Document.project_id.is_(None)]
    if domain:
        filters.append(Document.domain == domain)
    if search:
        filters.append(Document.name.ilike(f"%{search}%"))

    count_query = select(func.count()).select_from(Document).where(*filters)
    total = await db.scalar(count_query)

    list_query = (
        select(Document)
        .options(joinedload(Document.user).load_only(User.name))
        .where(*filters)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.scalars(list_query)
    documents = list(result.all())

    has_more = offset + len(documents) < total

    return documents, total, has_more



async def get_document_file(db: AsyncSession, name: str) -> Document:
    """원본 문서를 문서명으로 조회한다 (바이너리 포함).

    name은 unique 제약이 없으므로, 같은 이름이 여러 건이면 가장 최근 등록본을 반환한다.

    [전사 문서 전용] project_id가 있는 프로젝트 참고 파일은 대상에서 제외한다.
    이 조회에는 소유자 조건이 없어(문서명만으로 찾는다) 프로젝트 파일이 섞이면
    다른 사용자가 파일명만으로 남의 개인 파일을 내려받을 수 있다. I-09 참조.
    """
    doc = await db.scalar(
        select(Document)
        .where(Document.name == name, Document.project_id.is_(None))
        .order_by(Document.created_at.desc())
        .limit(1)
        .options(undefer(Document.data))
    )
    if doc is None:
        raise DocumentNotFoundError()
    return doc


async def delete_document_admin(db: AsyncSession, document_id: uuid.UUID) -> DocumentDeleteResponse:
    # MARS는 문서명으로 삭제하므로 여기서 name을 꺼낸다
    # [전사 문서 전용] 프로젝트 참고 파일은 이 경로로 삭제할 수 없다 — 관리자 문서와
    # 삭제 규칙이 다르고(프로젝트 스코프), 소유자 동의 없이 사라지면 안 된다. I-09 참조.
    doc = await db.scalar(
        select(Document).where(
            Document.document_id == document_id,
            Document.project_id.is_(None),
        )
    )
    if doc is None:
        raise DocumentNotFoundError()

    try:
        result = await delete_document(doc.name, doc.project_id)
        deleted_chunks = result["deleted_chunks"]
    except DocumentNotFoundError:
        # MARS에 이미 없음(색인 실패했거나 이미 지워짐) → 목표(MARS에 청크 없음)는 이미 달성 → 멱등 처리
        deleted_chunks = 0
    # ConflictError(409)나 LLMServerError는 여기서 안 잡음 → 그대로 위로 던져짐
    # → DB는 안 지워짐(원본 유지, 재시도 가능) — ADR-17

    await db.delete(doc)
    await db.commit()

    return DocumentDeleteResponse(document_id=document_id, deleted_chunks=deleted_chunks)