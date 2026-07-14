import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.message import RoleEnum


class ChatRequest(BaseModel):
    question: str
    domain: str | None = None
    tool: str | None = None


class RegenerateRequest(BaseModel):
    domain: str | None = None
    tool: str | None = None


class SourceResponse(BaseModel):
    name: str
    page: str | None

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message_id: uuid.UUID
    role: RoleEnum
    content: str
    created_at: datetime
    sources: list[SourceResponse] = []

    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    session_id: uuid.UUID
    messages: list[MessageResponse]
