import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.responses import (
    R_400_DOCUMENT,
    R_401,
    R_403_PROJECT,
    R_404_DOCUMENT,
    R_404_PROJECT,
    R_413_DOCUMENT,
    R_422,
    R_502_LLM,
)
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.project import (
    ProjectCreate,
    ProjectDetailResponse,
    ProjectFavoriteUpdate,
    ProjectInstructionUpdate,
    ProjectPageResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.schemas.document import DocumentStatusResponse
from app.schemas.project_document import (
    ProjectDocumentItem,
    ProjectDocumentListResponse,
    ProjectDocumentUploadResponse,
)
from app.schemas.session import SessionPageResponse, SessionResponse
from app.services import project_service, session_service

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


@router.patch(
    "/{project_id}",
    response_model=ApiResponse[ProjectDetailResponse],
    summary="프로젝트 제목 수정",
    description="프로젝트 제목을 수정합니다. 본인의 프로젝트만 수정 가능합니다.",
    responses={**R_401, **R_403_PROJECT, **R_404_PROJECT, **R_422},
)
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await project_service.update_project(db, project_id, current_user.user_id, data)
    return ApiResponse.ok(ProjectDetailResponse.model_validate(project), status_code=200)


@router.patch(
    "/{project_id}/favorite",
    response_model=ApiResponse[ProjectDetailResponse],
    summary="프로젝트 즐겨찾기 설정",
    description=(
        "프로젝트의 즐겨찾기 여부를 설정합니다. 본인의 프로젝트만 설정 가능합니다.\n\n"
        "- `is_favorite: true` → 즐겨찾기 등록\n"
        "- `is_favorite: false` → 즐겨찾기 해제\n"
        "- 즐겨찾기 변경은 목록 정렬 기준(`updated_at`)에 영향을 주지 않습니다."
    ),
    responses={**R_401, **R_403_PROJECT, **R_404_PROJECT, **R_422},
)
async def set_favorite(
    project_id: uuid.UUID,
    data: ProjectFavoriteUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await project_service.set_favorite(
        db, project_id, current_user.user_id, data.is_favorite
    )
    return ApiResponse.ok(ProjectDetailResponse.model_validate(project), status_code=200)


@router.patch(
    "/{project_id}/instruction",
    response_model=ApiResponse[ProjectDetailResponse],
    summary="프로젝트 지침 설정/수정",
    description=(
        "프로젝트 내 대화에 공통 적용할 지침을 설정합니다. 본인의 프로젝트만 설정 가능합니다.\n\n"
        "- `null` 또는 빈 문자열을 보내면 지침이 삭제됩니다."
    ),
    responses={**R_401, **R_403_PROJECT, **R_404_PROJECT, **R_422},
)
async def update_instructions(
    project_id: uuid.UUID,
    data: ProjectInstructionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await project_service.update_instructions(
        db, project_id, current_user.user_id, data
    )
    return ApiResponse.ok(ProjectDetailResponse.model_validate(project), status_code=200)


@router.delete(
    "/{project_id}",
    response_model=ApiResponse[None],
    summary="프로젝트 삭제",
    description=(
        "프로젝트를 삭제합니다. 본인의 프로젝트만 삭제 가능합니다.\n\n"
        "- 하위 **대화 세션·메시지·참고 파일이 함께 삭제**됩니다 (되돌릴 수 없습니다)\n"
        "- 색인된 참고 파일은 AI 서버의 청크를 먼저 정리한 뒤 삭제합니다"
    ),
    responses={**R_401, **R_403_PROJECT, **R_404_PROJECT, **R_422, **R_502_LLM},
)
async def delete_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await project_service.delete_project(db, project_id, current_user.user_id)
    return ApiResponse.ok(status_code=200)


@router.get(
    "/{project_id}/sessions",
    response_model=ApiResponse[SessionPageResponse],
    summary="프로젝트 하위 대화 세션 목록",
    description=(
        "프로젝트에 속한 대화 세션을 최근 수정순으로 조회합니다. cursor 기반 무한 스크롤을 지원합니다.\n\n"
        "- 첫 요청: cursor 없이 호출\n"
        "- 다음 페이지: 응답의 `next_cursor` 값을 cursor로 전달\n"
        "- `has_next`가 false이면 마지막 페이지\n"
        "- 본인의 프로젝트만 조회 가능합니다."
    ),
    responses={**R_401, **R_403_PROJECT, **R_404_PROJECT, **R_422},
)
async def get_project_sessions(
    project_id: uuid.UUID,
    cursor: datetime | None = Query(None, description="이전 응답의 next_cursor 값"),
    size: int = Query(20, ge=1, le=100, description="한 번에 가져올 세션 수"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sessions, has_next = await session_service.get_project_sessions(
        db, project_id, current_user.user_id, cursor=cursor, size=size
    )
    next_cursor = sessions[-1].updated_at if has_next and sessions else None
    return ApiResponse.ok(SessionPageResponse(
        items=[SessionResponse.model_validate(s) for s in sessions],
        next_cursor=next_cursor,
        has_next=has_next,
    ), status_code=200)


@router.post(
    "/{project_id}/documents",
    response_model=ApiResponse[ProjectDocumentUploadResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="프로젝트 참고 파일 업로드",
    description=(
        "프로젝트에 참고 파일을 업로드합니다. 본인의 프로젝트에만 업로드 가능합니다.\n\n"
        "- 지원 형식: `.md` / `.txt` / `.pdf` (최대 50MB). 형식·용량 위반은 400/413\n"
        "- 업로드한 파일은 **해당 프로젝트 대화에서만** 검색됩니다\n"
        "- 색인은 비동기로 진행되므로 즉시 202를 반환합니다. 진행 상태는 "
        "파일 목록의 `status`(`queued` → `running` → `done` | `error`)로 확인합니다"
    ),
    responses={
        **R_400_DOCUMENT,
        **R_401,
        **R_403_PROJECT,
        **R_404_PROJECT,
        **R_413_DOCUMENT,
        **R_422,
        **R_502_LLM,
    },
)
async def upload_project_document(
    project_id: uuid.UUID,
    file: UploadFile = File(..., description="업로드할 참고 파일 (.md/.txt/.pdf)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await file.read()
    doc = await project_service.upload_project_document(
        db,
        project_id,
        current_user.user_id,
        filename=file.filename or "",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )
    return ApiResponse.ok(
        ProjectDocumentUploadResponse.model_validate(doc), status_code=202
    )


@router.get(
    "/{project_id}/documents",
    response_model=ApiResponse[ProjectDocumentListResponse],
    summary="프로젝트 참고 파일 목록",
    description=(
        "프로젝트에 업로드된 참고 파일 목록을 최근 업로드순으로 조회합니다. "
        "본인의 프로젝트만 조회 가능합니다.\n\n"
        "- offset 기반 페이지네이션 (`has_more`가 false이면 마지막 페이지)\n"
        "- `status`: `pending`(적재 요청 전) | `queued`(대기) | `running`(색인 중) | "
        "`done`(완료) | `error`(실패)\n"
        "- **이 API의 `status`는 마지막으로 기록된 값**입니다. 진행 중인 파일의 최신 상태는 "
        "`GET /projects/{project_id}/documents/{document_id}/status`로 확인하세요 "
        "(목록은 AI 서버에 묻지 않으므로 폴링해도 값이 바뀌지 않습니다)"
    ),
    responses={**R_401, **R_403_PROJECT, **R_404_PROJECT, **R_422},
)
async def get_project_documents(
    project_id: uuid.UUID,
    offset: int = Query(0, ge=0, description="조회 시작 위치"),
    limit: int = Query(50, ge=1, le=100, description="한 번에 가져올 파일 수"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    documents, total, has_more = await project_service.get_project_documents(
        db, project_id, current_user.user_id, offset=offset, limit=limit
    )
    return ApiResponse.ok(ProjectDocumentListResponse(
        documents=[ProjectDocumentItem.model_validate(d) for d in documents],
        total=total,
        offset=offset,
        limit=limit,
        has_more=has_more,
    ), status_code=200)


@router.get(
    "/{project_id}/documents/{document_id}/status",
    response_model=ApiResponse[DocumentStatusResponse],
    summary="참고 파일 색인 상태 조회",
    description=(
        "참고 파일의 색인 진행 상태를 조회합니다. 업로드 후 이 API를 polling해 완료를 확인합니다.\n\n"
        "- `status`: `queued`(대기) → `running`(색인 중) → `done`(완료) | `error`(실패)\n"
        "- `done`이면 `chunks_indexed`에 적재된 청크 수가, `error`면 `error`에 사유가 담깁니다\n"
        "- **권장 주기 10~15초.** 색인은 문서당 수 분 걸리므로 더 짧게 부를 이유가 없습니다\n"
        "- `done`/`error`가 되면 polling을 중단하세요 (이후에는 AI 서버를 호출하지 않고 "
        "저장된 값을 그대로 반환합니다)"
    ),
    responses={**R_401, **R_403_PROJECT, **R_404_PROJECT, **R_404_DOCUMENT, **R_422, **R_502_LLM},
)
async def get_project_document_status(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await project_service.get_project_document_status(
        db, project_id, document_id, current_user.user_id
    )
    return ApiResponse.ok(DocumentStatusResponse.model_validate(doc), status_code=200)


@router.delete(
    "/{project_id}/documents/{document_id}",
    response_model=ApiResponse[None],
    summary="프로젝트 참고 파일 삭제",
    description=(
        "프로젝트 참고 파일을 삭제합니다. 본인의 프로젝트 파일만 삭제 가능합니다.\n\n"
        "- 색인된 파일은 AI 서버의 청크를 먼저 정리한 뒤 원본을 삭제합니다\n"
        "- 다른 프로젝트의 파일 ID를 지정하면 404를 반환합니다"
    ),
    responses={**R_401, **R_403_PROJECT, **R_404_PROJECT, **R_404_DOCUMENT, **R_422, **R_502_LLM},
)
async def delete_project_document(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await project_service.delete_project_document(
        db, project_id, document_id, current_user.user_id
    )
    return ApiResponse.ok(status_code=200)
