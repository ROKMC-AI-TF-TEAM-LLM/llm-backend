import uuid
from datetime import datetime

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    title: str
    instructions: str | None = None


class ProjectUpdate(BaseModel):
    title: str


class ProjectFavoriteUpdate(BaseModel):
    is_favorite: bool


class ProjectInstructionUpdate(BaseModel):
    # null 또는 빈 문자열로 보내면 지침 삭제
    instructions: str | None = None


class ProjectResponse(BaseModel):
    project_id: uuid.UUID
    title: str
    is_favorite: bool

    model_config = {"from_attributes": True}


class ProjectPageResponse(BaseModel):
    items: list[ProjectResponse]
    next_cursor: datetime | None
    has_next: bool


class ProjectDetailResponse(BaseModel):
    project_id: uuid.UUID
    title: str
    is_favorite: bool
    instructions: str | None = None

    model_config = {"from_attributes": True}
