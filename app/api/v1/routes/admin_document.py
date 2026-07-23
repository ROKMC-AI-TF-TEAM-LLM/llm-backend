from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.core.responses import R_401, R_403_ADMIN, R_422, R_502_LLM, R_404_DOCUMENT
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.document import DocumentUploadResponse,DocumentStatusResponse
from app.services import document_service
import uuid

router = APIRouter(prefix="/admin/documents", tags=["admin-documents"])


@router.post(
    "",
    response_model=ApiResponse[DocumentUploadResponse],
    status_code=202,
    summary="문서 업로드",
    description=(
        "관리자가 문서를 업로드하면 원본을 DB에 저장하고 MARS로 relay하여 색인을 요청한다. "
        "색인은 백그라운드로 진행되며 즉시 202를 반환한다."
    ),
    responses={**R_401, **R_403_ADMIN, **R_422, **R_502_LLM},
)
async def upload_document(
    file: UploadFile = File(..., description="업로드할 문서 (.md/.txt/.pdf)"),
    name: str = Form(..., description="파일명 (source_doc)"),
    domain: str = Form(..., description="도메인 (HR, TECH, ...)"),
    visibility: str = Form("ALL", description="공개 범위 (ALL | DEPT_ONLY)"),
    department: str | None = Form(None, description="visibility=DEPT_ONLY일 때 소유 부서"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    data = await file.read()
    doc = await document_service.upload_document(
        db=db,
        name=name,
        domain=domain,
        visibility=visibility,
        data=data,
        content_type=file.content_type or "application/octet-stream",
        department=department,
        user_id=admin.user_id,
    )
    return ApiResponse.ok(doc, status_code=202)


@router.get(
    "/{document_id}/status",
    response_model=ApiResponse[DocumentStatusResponse],
    responses={**R_401, **R_403_ADMIN, **R_404_DOCUMENT},  # 404 헬퍼 없으면 새로 만들거나 그냥 스펙만
)
async def get_status(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    doc = await document_service.get_document_status(db, document_id)
    return ApiResponse.ok(doc)