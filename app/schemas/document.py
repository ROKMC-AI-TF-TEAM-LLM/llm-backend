from datetime import datetime
from uuid import UUID
from app.models.document import IndexStatusEnum
from pydantic import BaseModel



class DocumentItem(BaseModel):
    name: str
    type: str | None = None
    domain: str | None = None
    visibility: str | None = None
    owning_department: str | None = None
    applied_at: datetime | None = None
    domain: str | None = None
    visibility: str | None = None
    owning_department: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentItem]
    total: int
    offset: int
    limit: int
    has_more: bool


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    name: str
    domain: str
    visibility: str
    status: str
    created_at: datetime


#class DocumentDeleteResponse(BaseModel):
