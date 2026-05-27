import uuid
from datetime import datetime

from pydantic import BaseModel


class SessionCreate(BaseModel):
    title: str = "새 대화"


class SessionUpdate(BaseModel):
    title: str


class SessionResponse(BaseModel):
    session_id: uuid.UUID
    title: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class SessionPageResponse(BaseModel):
    items: list[SessionResponse]
    next_cursor: datetime | None
    has_next: bool
