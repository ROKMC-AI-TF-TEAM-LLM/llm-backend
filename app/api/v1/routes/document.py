from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.responses import R_401, R_404_DOCUMENT, R_502_LLM
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.document import DocumentListResponse
from app.services import document_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get(
    "",
    response_model=ApiResponse[DocumentListResponse],
    summary="문서 목록 조회",
    description=(
        "RAG 벡터스토어에 인덱싱된 문서 목록을 반환합니다. offset 기반 무한 스크롤을 지원합니다.\n\n"
        "- 첫 요청: `offset=0`으로 시작\n"
        "- 다음 페이지: `offset += limit`으로 증가\n"
        "- 응답의 `has_more`가 false이면 마지막 페이지\n"
        "- `domain`으로 도메인 필터링 가능 (예: `MANUAL`). 사용 가능 값은 `GET /capabilities` 참조"
    ),
    responses={**R_401, **R_502_LLM},
)
async def get_documents(
    offset: int = Query(0, ge=0, description="조회 시작 위치"),
    limit: int = Query(20, ge=1, le=100, description="한 번에 가져올 문서 수"),
    domain: str | None = Query(None, description="도메인 필터 (예: HR, MANUAL)"),
    _: User = Depends(get_current_user),
):
    data = await document_service.get_documents(offset=offset, limit=limit, domain=domain)
    return ApiResponse.ok(data, status_code=200)


@router.get(
    "/{name}/download",
    summary="원본 문서 다운로드",
    description=(
        "미들웨어 DB에 보관된 원본 문서 파일을 문서명(name)으로 조회해 다운로드합니다.\n\n"
        "- `name`: 문서명 그대로 전달 (한글·공백은 URL 인코딩, 예: `/documents/%ED%9C%B4%EA%B0%80%EA%B7%9C%EC%A0%95.pdf/download`)\n"
        "- 같은 이름의 문서가 여러 건이면 가장 최근 등록본을 반환합니다\n"
        "- 인증 헤더가 필요하므로 프론트는 fetch → blob 방식으로 다운로드해야 합니다"
    ),
    responses={**R_401, **R_404_DOCUMENT},
)
async def download_document(
    name: str,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await document_service.get_document_file(db, name)
    return Response(
        content=doc.data,
        media_type=doc.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(doc.name)}",
            "Content-Length": str(doc.size),
        },
    )


