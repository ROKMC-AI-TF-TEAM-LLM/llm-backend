from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user
from app.core.responses import R_401, R_502_LLM
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
        "- `domain`을 지정하면 해당 도메인 문서만 조회 (미지정 시 전체 조회)"
    ),
    responses={**R_401, **R_502_LLM},
)
async def get_documents(
    offset: int = Query(0, ge=0, description="조회 시작 위치"),
    limit: int = Query(20, ge=1, le=100, description="한 번에 가져올 문서 수"),
    domain: str | None = Query(None, description="도메인 필터 (예: HR, FINANCE_LEGAL). 미지정 시 전체 조회"),
    _: User = Depends(get_current_user),
):
    data = await document_service.get_documents(offset=offset, limit=limit, domain=domain)
    return ApiResponse.ok(data, status_code=200)
