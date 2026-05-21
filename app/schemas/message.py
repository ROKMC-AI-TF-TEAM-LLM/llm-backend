import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.message import RoleEnum


class ChatRequest(BaseModel):
    question: str


class MessageResponse(BaseModel):
    role: RoleEnum
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}

class MessageListResponse(BaseModel):
    session_id: uuid.UUID
    messages: list[MessageResponse]

