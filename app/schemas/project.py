import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

# DB 컬럼이 VARCHAR(255)라 여기서 막지 않으면 초과분이 500으로 터진다
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]

# AI 서버가 1000자에서 조용히 잘라내므로(normalize.py _INSTRUCTIONS_MAX_CHARS), 같은 값으로
# 저장 시점에 422를 내어 "저장은 됐는데 앞부분만 적용되는" 상태를 막는다
Instructions = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class ProjectCreate(BaseModel):
    title: Title
    instructions: Instructions | None = None


class ProjectUpdate(BaseModel):
    title: Title


class ProjectFavoriteUpdate(BaseModel):
    is_favorite: bool


class ProjectInstructionUpdate(BaseModel):
    # null 또는 빈 문자열로 보내면 지침 삭제
    instructions: Instructions | None = None


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
