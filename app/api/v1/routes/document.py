import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.responses import R_401, R_404_DOCUMENT
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.document import DocumentItem, DocumentListResponse
from app.services import document_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get(
    "",
    response_model=ApiResponse[DocumentListResponse],
    summary="문서 목록 조회",
    description=(
        "DB에 색인 완료(`done`)로 기록된 전사 공용 문서 목록을 반환합니다. "
        "등록일 내림차순(동일 시 문서 ID 내림차순)으로 정렬하며, offset 기반 무한 스크롤을 지원합니다.\n\n"
        "- 첫 요청: `offset=0`으로 시작\n"
        "- 다음 페이지: `offset += limit`으로 증가\n"
        "- 응답의 `has_more`가 false이면 마지막 페이지\n"
        "- `type`, `applied_at`은 DB에 대응하는 정보가 없어 null로 반환합니다\n"
        "- `domain`으로 도메인 필터링 가능 (예: `MANUAL`). 사용 가능 값은 `GET /capabilities` 참조\n"
        "- **전사 공용 문서만** 반환합니다. 프로젝트 참고 파일은 "
        "`GET /projects/{project_id}/documents`로 조회하세요"
    ),
    responses={**R_401},
)
async def get_documents(
    offset: int = Query(0, ge=0, description="조회 시작 위치"),
    limit: int = Query(20, ge=1, le=100, description="한 번에 가져올 문서 수"),
    domain: str | None = Query(None, description="도메인 필터 (예: HR, MANUAL)"),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    documents, total, has_more = await document_service.get_documents(
        db, offset=offset, limit=limit, domain=domain
    )
    data = DocumentListResponse(
        documents=[
            DocumentItem(
                document_id=doc.document_id,
                name=doc.name,
                domain=doc.domain,
                visibility=doc.visibility,
                owning_department=doc.department,
            )
            for doc in documents
        ],
        total=total,
        offset=offset,
        limit=limit,
        has_more=has_more,
    )
    return ApiResponse.ok(data, status_code=200)


@router.get(
    "/{document_id}/download",
    summary="원본 문서 다운로드",
    description=(
        "document_id로 원본 문서 파일을 다운로드합니다. 같은 이름의 문서가 여러 건이어도 "
        "정확히 해당 문서를 반환합니다.\n\n"
        "- **전사 공용 문서만** 받을 수 있습니다. 프로젝트 참고 파일과 삭제된 문서는 404를 반환합니다\n"
        "- 인증 헤더가 필요하므로 프론트는 fetch → blob 방식으로 다운로드해야 합니다"
    ),
    responses={**R_401, **R_404_DOCUMENT},
)
async def download_document(
    document_id: uuid.UUID,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await document_service.get_document_file(db, document_id)
    return Response(
        content=doc.data,
        media_type=doc.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(doc.name)}",
            "Content-Length": str(doc.size),
        },
    )
