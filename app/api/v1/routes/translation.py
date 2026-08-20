from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.core.responses import R_401, R_413_TRANSLATE, R_422, R_502_TRANSLATE
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.translation import TranslateRequest, TranslateResponse
from app.services import translation_service

router = APIRouter(prefix="/translate", tags=["translate"])


@router.post(
    "",
    response_model=ApiResponse[TranslateResponse],
    summary="군사 도메인 한↔영 번역",
    description=(
        "원문을 군사 용어집을 적용해 번역합니다. **한국어↔영어만** 지원합니다.\n\n"
        "- `style`: 생략하면 번역 서버 기본값(`press_release`)\n"
        "- `terms_applied`: 적용된 군사 용어와 원문 내 위치. 용어 하이라이트 UI용이며 지금은 표시하지 않아도 됩니다\n"
        "- `warnings`: 번역 품질 경고(`term_missing`, `wrong_language`, `length_anomaly` 등). 종류마다 형태가 다릅니다"
    ),
    responses={**R_401, **R_413_TRANSLATE, **R_422, **R_502_TRANSLATE},
)
async def translate(req: TranslateRequest, _: User = Depends(get_current_user)):
    data = await translation_service.translate(req)
    return ApiResponse.ok(data, status_code=200)
