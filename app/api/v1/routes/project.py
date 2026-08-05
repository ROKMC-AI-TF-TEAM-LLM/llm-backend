import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.responses import R_401, R_403_PROJECT, R_404_PROJECT, R_422
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.project import (
    ProjectCreate,
    ProjectDetailResponse,
    ProjectPageResponse,
    ProjectResponse,
)
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "",
    response_model=ApiResponse[ProjectDetailResponse],
    status_code=status.HTTP_201_CREATED,
    summary="프로젝트 워크스페이스 생성",
    description="새로운 프로젝트 워크스페이스를 생성합니다.",
    responses={**R_401, **R_422},
)
async def create_project(
    data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await project_service.create_project(db, current_user.user_id, data)
    return ApiResponse.ok(ProjectDetailResponse.model_validate(project), status_code=201)


@router.get(
    "",
    response_model=ApiResponse[ProjectPageResponse],
    summary="프로젝트 목록 조회",
    description=(
        "내 프로젝트 목록을 최근 수정순으로 조회합니다. cursor 기반 무한 스크롤을 지원합니다.\n\n"
        "- 첫 요청: cursor 없이 호출\n"
        "- 다음 페이지: 응답의 `next_cursor` 값을 cursor로 전달\n"
        "- `has_next`가 false이면 마지막 페이지\n"
        "- `is_favorite=true`로 즐겨찾기한 프로젝트만 조회 가능"
    ),
    responses={**R_401, **R_422},
)
async def get_projects(
    cursor: datetime | None = Query(None, description="이전 응답의 next_cursor 값"),
    size: int = Query(20, ge=1, le=100, description="한 번에 가져올 프로젝트 수"),
    is_favorite: bool | None = Query(None, description="즐겨찾기 필터 (true: 즐겨찾기만, 생략: 전체)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    projects, has_next = await project_service.get_projects(
        db, current_user.user_id, cursor=cursor, size=size, is_favorite=is_favorite
    )
    next_cursor = projects[-1].updated_at if has_next and projects else None
    return ApiResponse.ok(ProjectPageResponse(
        items=[ProjectResponse.model_validate(p) for p in projects],
        next_cursor=next_cursor,
        has_next=has_next,
    ), status_code=200)


@router.get(
    "/{project_id}",
    response_model=ApiResponse[ProjectDetailResponse],
    summary="프로젝트 창 진입",
    description="프로젝트 상세 정보를 조회합니다. 본인의 프로젝트만 조회 가능합니다.",
    responses={**R_401, **R_403_PROJECT, **R_404_PROJECT, **R_422},
)
async def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await project_service.get_project(db, project_id, current_user.user_id)
    return ApiResponse.ok(ProjectDetailResponse.model_validate(project), status_code=200)
