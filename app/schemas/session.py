import uuid
from datetime import datetime

from pydantic import BaseModel


class SessionCreate(BaseModel):
    title: str = "새 대화"
    # 지정하면 해당 프로젝트 소속 대화가 된다 (생략 시 일반 대화)
    project_id: uuid.UUID | None = None


class SessionUpdate(BaseModel):
    title: str


class SessionFavoriteUpdate(BaseModel):
    is_favorite: bool


class SessionResponse(BaseModel):
    session_id: uuid.UUID
    # 프로젝트에 속하지 않은 일반 대화는 null
    project_id: uuid.UUID | None
    title: str
    is_favorite: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


class SessionPageResponse(BaseModel):
    items: list[SessionResponse]
    next_cursor: datetime | None
    has_next: bool
