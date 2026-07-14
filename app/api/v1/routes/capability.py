from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.core.responses import R_401, R_502_LLM
from app.models.user import User
from app.schemas.capability import CapabilityResponse
from app.schemas.common import ApiResponse
from app.services import capability_service

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


@router.get(
    "",
    response_model=ApiResponse[CapabilityResponse],
    summary="사용 가능한 domain·tool 목록 조회",
    description=(
        "채팅 스트리밍 요청의 `domain`·`tool` 필드에 넣을 수 있는 값 목록을 반환합니다. "
        "프론트엔드 도메인 탭/검색 모드 UI의 데이터 소스입니다.\n\n"
        "- `domains`: 검색 범위 한정 값 (code, label)\n"
        "- `tools`: 처리 경로 목록. `forcible: true`인 항목만 `tool` 필드로 강제 지정 가능"
    ),
    responses={**R_401, **R_502_LLM},
)
async def get_capabilities(_: User = Depends(get_current_user)):
    data = await capability_service.get_capabilities()
    return ApiResponse.ok(data, status_code=200)
