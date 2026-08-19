import uuid
from datetime import datetime

from pydantic import BaseModel


class ProjectDocumentItem(BaseModel):
    document_id: uuid.UUID
    name: str
    content_type: str | None = None
    size: int
    # 색인 상태: pending(적재 요청 전) | queued | running | done | error
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectDocumentListResponse(BaseModel):
    documents: list[ProjectDocumentItem]
    total: int
    offset: int
    limit: int
    has_more: bool


class ProjectDocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    name: str
    content_type: str | None = None
    size: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
