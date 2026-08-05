import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProjectAccessDeniedError, ProjectNotFoundError
from app.models.project import Project
from app.schemas.project import ProjectCreate


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
