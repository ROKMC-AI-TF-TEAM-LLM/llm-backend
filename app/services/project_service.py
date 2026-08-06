import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProjectAccessDeniedError, ProjectNotFoundError
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectInstructionUpdate, ProjectUpdate

# [정렬 규칙] 프로젝트 목록은 updated_at desc(최근 수정순)로 정렬된다.
#   - 제목 변경  → updated_at 갱신    (목록 맨 위로 올라간다)
#   - 즐겨찾기   → 갱신하지 않음      (해제 시 원래 자리로 돌아가야 하므로)
#   - 지침 수정  → 갱신하지 않음      (수정으로 간주하지 않는다)
# 정렬에 영향을 주지 않아야 하는 UPDATE는 SET 절에 updated_at=Project.updated_at 을
# 반드시 명시할 것. ORM 속성 대입 후 commit 하면 모델의 onupdate가 무조건 발동한다.


async def create_project(db: AsyncSession, user_id: uuid.UUID, data: ProjectCreate) -> Project:
    project = Project(
        user_id=user_id,
        title=data.title,
        # 프론트가 지침 칸을 비워 보내면 ""로 오므로 NULL로 정규화한다
        instructions=data.instructions or None,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def get_projects(
    db: AsyncSession,
    user_id: uuid.UUID,
    cursor: datetime | None = None,
    size: int = 20,
    is_favorite: bool | None = None,
) -> tuple[list[Project], bool]:
    query = (
        select(Project)
        .where(Project.user_id == user_id)
        .order_by(Project.updated_at.desc())
        .limit(size + 1)
    )
    if cursor:
        query = query.where(Project.updated_at < cursor)
    if is_favorite is not None:
        query = query.where(Project.is_favorite == is_favorite)

    result = await db.scalars(query)
    projects = list(result.all())
    has_next = len(projects) > size
    return projects[:size], has_next


async def _get_project_owned(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> Project:
    project = await db.scalar(select(Project).where(Project.project_id == project_id))
    if not project:
        raise ProjectNotFoundError()
    if project.user_id != user_id:
        raise ProjectAccessDeniedError()
    return project


async def get_project(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> Project:
    return await _get_project_owned(db, project_id, user_id)


async def update_project(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID, data: ProjectUpdate
) -> Project:
    project = await _get_project_owned(db, project_id, user_id)
    project.title = data.title
    await db.commit()
    await db.refresh(project)
    return project


async def set_favorite(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID, is_favorite: bool
) -> Project:
    project = await _get_project_owned(db, project_id, user_id)
    # updated_at을 SET에 그대로 명시해 onupdate 갱신을 막는다
    # (즐겨찾기 변경이 최근 수정순 목록의 순서를 바꾸지 않도록)
    await db.execute(
        update(Project)
        .where(Project.project_id == project_id)
        .values(is_favorite=is_favorite, updated_at=Project.updated_at)
    )
    await db.commit()
    await db.refresh(project)
    return project


async def update_instructions(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID, data: ProjectInstructionUpdate
) -> Project:
    project = await _get_project_owned(db, project_id, user_id)
    # 지침 수정은 '수정'으로 보지 않는다 — updated_at을 SET에 그대로 명시해 onupdate 갱신을 막는다
    # 빈 문자열은 생성 시와 동일하게 NULL로 정규화한다 (지침 삭제)
    await db.execute(
        update(Project)
        .where(Project.project_id == project_id)
        .values(instructions=data.instructions or None, updated_at=Project.updated_at)
    )
    await db.commit()
    await db.refresh(project)
    return project
