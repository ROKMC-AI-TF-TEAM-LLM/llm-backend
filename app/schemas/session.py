import uuid
from datetime import datetime

from pydantic import BaseModel


class SessionCreate(BaseModel):
    title: str = "새 대화"


class SessionUpdate(BaseModel):
    title: str


class SessionFavoriteUpdate(BaseModel):
    is_favorite: bool


class SessionResponse(BaseModel):
    session_id: uuid.UUID
    title: str
    is_favorite: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


class SessionPageResponse(BaseModel):
    items: list[SessionResponse]
    next_cursor: datetime | None
    has_next: bool
