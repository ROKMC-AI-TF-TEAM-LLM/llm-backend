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


class AttachmentResponse(BaseModel):
    attachment_id: uuid.UUID
    name: str
    size: int

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message_id: uuid.UUID
    role: RoleEnum
    content: str
    created_at: datetime
    domain: str | None = None
    # AI 서버가 붙인 경고 코드. null이면 경고 없음.
    # 클라이언트는 code로 표시 방식을 고른다 (문구 파싱 금지)
    notice_code: str | None = None
    sources: list[SourceResponse] = []
    attachments: list[AttachmentResponse] = []

    model_config = {"from_attributes": True}


class MessagePageResponse(BaseModel):
    items: list[MessageResponse]
    next_cursor: datetime | None
    has_next: bool
