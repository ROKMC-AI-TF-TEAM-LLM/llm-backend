import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

# 제목: DB 컬럼이 VARCHAR(255)다. 여기서 막지 않으면 초과분이 DB 오류(500)로 터진다.
# 공백만 남는 제목도 목록에서 빈 칸으로 보이므로 strip 후 최소 1자를 요구한다.
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]

# 지침: AI 서버가 1000자에서 **조용히 잘라낸다**(normalize.py `_INSTRUCTIONS_MAX_CHARS`).
# 여기서 같은 값으로 막아 사용자가 저장 시점에 422로 알게 한다 — 저장은 됐는데
# 앞 1000자만 적용되는 상태를 만들지 않기 위해서다.
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
