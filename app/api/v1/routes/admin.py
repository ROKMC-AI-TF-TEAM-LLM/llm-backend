import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.core.responses import R_401, R_403_ADMIN, R_404_DOCUMENT, R_404_USER, R_422, R_502_LLM
from app.models.user import ApprovalStatus, User, UserRole
from app.schemas.common import ApiResponse
from app.schemas.document import (
    AdminDocumentItem,
    AdminDocumentListResponse,
    DocumentDeleteResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from app.schemas.user import AdminUserPageResponse, UserResponse
from app.services import document_service, user_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/users",
    response_model=ApiResponse[AdminUserPageResponse],
    summary="전체 회원 목록 조회",
    description=(
        "전체 회원 목록을 조회합니다. 역할/상태/검색어로 필터링 가능하며 cursor 기반 무한 스크롤을 지원합니다.\n\n"
        "- `role`: user | admin 필터\n"
        "- `status`: pending | approved | rejected 필터\n"
        "- `search`: 이름 또는 이메일 검색"
    ),
    responses={**R_401, **R_403_ADMIN, **R_422},
)
async def get_all_users(
    role: UserRole | None = Query(None, description="역할 필터 (user | admin)"),
    status: ApprovalStatus | None = Query(None, description="승인 상태 필터"),
    search: str | None = Query(None, max_length=100, description="이름 또는 이메일 검색"),
    cursor: datetime | None = Query(None, description="이전 응답의 next_cursor 값"),
    size: int = Query(20, ge=1, le=100, description="한 번에 가져올 수"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    users, has_next = await user_service.get_users_paged(
        db, role=role, status=status, search=search, cursor=cursor, size=size
    )
    next_cursor = users[-1].created_at if has_next else None
    return ApiResponse.ok(
        AdminUserPageResponse(items=users, next_cursor=next_cursor, has_next=has_next),
        status_code=200,
    )


@router.get(
    "/users/{user_id}",
    response_model=ApiResponse[UserResponse],
    summary="회원 상세 조회",
    description="특정 회원의 상세 정보를 조회합니다. 관리자 전용입니다.",
    responses={**R_401, **R_403_ADMIN, **R_404_USER},
)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    user = await user_service.get_user(db, user_id)
    return ApiResponse.ok(UserResponse.model_validate(user), status_code=200)


@router.patch(
    "/users/{user_id}/approve",
    response_model=ApiResponse[UserResponse],
    summary="회원 가입 승인",
    description="대기 중인 회원의 가입을 승인합니다. 승인 후 해당 사용자는 서비스를 이용할 수 있습니다.",
    responses={**R_401, **R_403_ADMIN, **R_404_USER},
)
async def approve_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    user = await user_service.approve_user(db, user_id)
    return ApiResponse.ok(UserResponse.model_validate(user), status_code=200)


@router.patch(
    "/users/{user_id}/reject",
    response_model=ApiResponse[UserResponse],
    summary="회원 가입 거절",
    description="대기 중인 회원의 가입을 거절합니다.",
    responses={**R_401, **R_403_ADMIN, **R_404_USER},
)
async def reject_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    user = await user_service.reject_user(db, user_id)
    return ApiResponse.ok(UserResponse.model_validate(user), status_code=200)


@router.delete(
    "/users/{user_id}",
    response_model=ApiResponse[None],
    summary="회원 삭제",
    description="회원을 삭제합니다. 관리자 전용입니다.",
    responses={**R_401, **R_403_ADMIN, **R_404_USER},
)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    await user_service.delete_user(db, user_id)
    return ApiResponse.ok(status_code=200)


@router.post(
    "/documents",
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
    "/documents/{document_id}/status",
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


@router.get(
    "/documents",
    response_model=ApiResponse[AdminDocumentListResponse],
    summary="관리자 문서 목록 조회",
    description=(
        "미들웨어 DB에 저장된 관리자 문서 목록을 조회한다 (적재 상태 병기). "
        "offset 기반 페이지네이션을 지원하며, domain 필터와 name 검색이 가능하다."
    ),
    responses={**R_401, **R_403_ADMIN},
)
async def list_admin_documents(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    domain: str | None = Query(None),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    documents, total, has_more = await document_service.get_admin_documents(
        db=db, offset=offset, limit=limit, domain=domain, search=search,
    )
    return ApiResponse.ok(
        AdminDocumentListResponse(
            documents=[AdminDocumentItem.model_validate(doc) for doc in documents],
            total=total,
            offset=offset,
            limit=limit,
            has_more=has_more,
        )
    )


@router.delete(
    "/documents/{document_id}",
    response_model=ApiResponse[DocumentDeleteResponse],
    summary="문서 삭제",
    description="LLM 서버 Vector DB에서 청크를 삭제한 뒤 미들웨어 DB의 원본도 함께 삭제한다.",
    responses={**R_401, **R_403_ADMIN, **R_404_DOCUMENT},
)
async def delete_document_route(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    result = await document_service.delete_document_admin(db, document_id)
    return ApiResponse.ok(result)