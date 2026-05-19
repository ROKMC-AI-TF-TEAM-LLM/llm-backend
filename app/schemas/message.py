import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.message import RoleEnum


class ChatRequest(BaseModel):
    question: str


class MessageResponse(BaseModel):
    message_id: uuid.UUID
    session_id: uuid.UUID
    role: RoleEnum
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
