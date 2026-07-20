import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.responses import R_401, R_404_FILE
from app.models.user import User
from app.services import file_service

router = APIRouter(prefix="/files", tags=["files"])


@router.get(
    "/{attachment_id}",
    summary="생성 문서 다운로드",
    description=(
        "AI가 생성해 대화에 첨부된 문서 파일(HWPX 등)을 다운로드합니다. 본인 세션의 파일만 접근 가능합니다.\n\n"
        "- `attachment_id`: 메시지 응답의 `attachments` 배열 또는 스트리밍 `files` 이벤트의 ID\n"
        "- 파일은 미들웨어 DB에 보관되므로 AI 서버에서 원본이 정리된 뒤에도 다운로드할 수 있습니다\n"
        "- 브라우저에서 `<a href>`로는 인증 헤더를 붙일 수 없으므로 fetch → blob 방식으로 다운로드해야 합니다"
    ),
    responses={**R_401, **R_404_FILE},
)
async def download_file(
    attachment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    attachment = await file_service.get_attachment(db, attachment_id, current_user.user_id)
    return Response(
        content=attachment.data,
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(attachment.name)}",
            "Content-Length": str(attachment.size),
        },
    )
