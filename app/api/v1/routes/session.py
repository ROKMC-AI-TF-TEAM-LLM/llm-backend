import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.responses import (
    R_401,
    R_403_PROJECT,
    R_403_SESSION,
    R_404_PROJECT,
    R_404_SESSION,
    R_422,
)
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.session import (
    SessionCreate,
    SessionFavoriteUpdate,
    SessionPageResponse,
    SessionResponse,
    SessionUpdate,
)
from app.services import session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post(
    "",
    response_model=ApiResponse[SessionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="세션 생성",
    description=(
        "새로운 채팅 세션을 생성합니다.\n\n"
        "- `project_id`를 지정하면 해당 프로젝트 소속 대화가 됩니다 (생략 시 일반 대화)\n"
        "- 본인의 프로젝트만 지정할 수 있습니다"
    ),
    responses={**R_401, **R_403_PROJECT, **R_404_PROJECT, **R_422},
)
async def create_session(
    data: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await session_service.create_session(db, current_user.user_id, data)
    return ApiResponse.ok(SessionResponse.model_validate(session), status_code=201)


@router.get(
    "",
    response_model=ApiResponse[SessionPageResponse],
    summary="세션 목록 조회",
    description=(
        "내 채팅 세션 목록을 최근 수정순으로 조회합니다. cursor 기반 무한 스크롤을 지원합니다.\n\n"
        "- 첫 요청: cursor 없이 호출\n"
        "- 다음 페이지: 응답의 `next_cursor` 값을 cursor로 전달\n"
        "- `has_next`가 false이면 마지막 페이지\n"
        "- `is_favorite=true`로 즐겨찾기한 세션만 조회 가능\n"
        "- `project_id`는 프로젝트 소속 대화면 해당 프로젝트 ID, 일반 대화면 null"
    ),
    responses={**R_401, **R_422},
)
async def get_sessions(
    cursor: datetime | None = Query(None, description="이전 응답의 next_cursor 값"),
    size: int = Query(20, ge=1, le=100, description="한 번에 가져올 세션 수"),
    is_favorite: bool | None = Query(None, description="즐겨찾기 필터 (true: 즐겨찾기만, 생략: 전체)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sessions, has_next = await session_service.get_sessions(
        db, current_user.user_id, cursor=cursor, size=size, is_favorite=is_favorite
    )
    next_cursor = sessions[-1].updated_at if has_next and sessions else None
    return ApiResponse.ok(SessionPageResponse(
        items=[SessionResponse.model_validate(s) for s in sessions],
        next_cursor=next_cursor,
        has_next=has_next,
    ), status_code=200)


@router.get(
    "/search",
    response_model=ApiResponse[list[SessionResponse]],
    summary="세션 검색",
    description="제목 키워드로 채팅 세션을 검색합니다. (대소문자 구분 없음)",
    responses={**R_401, **R_422},
)
async def search_sessions(
    q: str = Query(..., min_length=1, description="검색 키워드"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sessions = await session_service.search_sessions(db, current_user.user_id, q)
    return ApiResponse.ok([SessionResponse.model_validate(s) for s in sessions], status_code=200)


@router.patch(
    "/{session_id}",
    response_model=ApiResponse[SessionResponse],
    summary="세션 제목 수정",
    description="채팅 세션의 제목을 수정합니다. 본인의 세션만 수정 가능합니다.",
    responses={**R_401, **R_403_SESSION, **R_404_SESSION, **R_422},
)
async def update_session(
    session_id: uuid.UUID,
    data: SessionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await session_service.update_session(db, session_id, current_user.user_id, data)
    return ApiResponse.ok(SessionResponse.model_validate(session), status_code=200)


@router.patch(
    "/{session_id}/favorite",
    response_model=ApiResponse[SessionResponse],
    summary="세션 즐겨찾기 설정",
    description=(
        "채팅 세션의 즐겨찾기 여부를 설정합니다. 본인의 세션만 설정 가능합니다.\n\n"
        "- `is_favorite: true` → 즐겨찾기 등록\n"
        "- `is_favorite: false` → 즐겨찾기 해제\n"
        "- 즐겨찾기 변경은 세션 목록 정렬 기준(`updated_at`)에 영향을 주지 않습니다."
    ),
    responses={**R_401, **R_403_SESSION, **R_404_SESSION, **R_422},
)
async def set_favorite(
    session_id: uuid.UUID,
    data: SessionFavoriteUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await session_service.set_favorite(db, session_id, current_user.user_id, data.is_favorite)
    return ApiResponse.ok(SessionResponse.model_validate(session), status_code=200)


@router.delete(
    "/{session_id}",
    response_model=ApiResponse[None],
    summary="세션 삭제",
    description="채팅 세션을 삭제합니다. 본인의 세션만 삭제 가능하며, 하위 메시지도 함께 삭제됩니다.",
    responses={**R_401, **R_403_SESSION, **R_404_SESSION},
)
async def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await session_service.delete_session(db, session_id, current_user.user_id)
    return ApiResponse.ok(status_code=200)
