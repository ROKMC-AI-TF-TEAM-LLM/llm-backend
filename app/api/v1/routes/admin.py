import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.core.responses import R_401, R_403_ADMIN, R_404_USER, R_422
from app.models.user import ApprovalStatus, User, UserRole
from app.schemas.common import ApiResponse
from app.schemas.user import AdminUserPageResponse, UserResponse
from app.services import user_service

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
