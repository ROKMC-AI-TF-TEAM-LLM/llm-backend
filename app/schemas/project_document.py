import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.core.content_types import to_extension


class ProjectDocumentItem(BaseModel):
    document_id: uuid.UUID
    name: str
    # 표시용으로 확장자(.pdf 등)로 변환해 내려준다
    content_type: str | None = None
    size: int
    # 색인 상태: pending(적재 요청 전) | queued | running | done | error
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}

    _to_ext = field_validator("content_type")(to_extension)


class ProjectDocumentListResponse(BaseModel):
    documents: list[ProjectDocumentItem]
    total: int
    offset: int
    limit: int
    has_more: bool


class ProjectDocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    name: str
    # 표시용으로 확장자(.pdf 등)로 변환해 내려준다
    content_type: str | None = None
    size: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}

    _to_ext = field_validator("content_type")(to_extension)
