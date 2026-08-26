from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator

from app.core.content_types import to_extension


class DocumentItem(BaseModel):
    name: str
    type: str | None = None
    domain: str | None = None
    visibility: str | None = None
    owning_department: str | None = None
    applied_at: datetime | None = None


class UploaderItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str


class AdminDocumentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    document_id: UUID
    name: str
    # type은 MARS가 내려주는 값이라 여기엔 없음 (content_type만 보유)
    # 표시용으로 확장자(.pdf 등)로 변환해 내려준다
    content_type: str | None = None
    domain: str | None = None
    visibility: str | None = None
    department: str | None = None
    status: str | None = None
    created_at: datetime | None = None
    size: int | None = None
    user: UploaderItem | None = None

    _to_ext = field_validator("content_type")(to_extension)


class DocumentListResponse(BaseModel):
    documents: list[DocumentItem]
    total: int
    offset: int
    limit: int
    has_more: bool


class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    document_id: UUID
    name: str
    domain: str
    visibility: str
    status: str
    created_at: datetime


class DocumentStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    document_id: UUID
    status: str
    chunks_indexed: int | None = None
    error: str | None = None


class AdminDocumentListResponse(BaseModel):
    documents: list[AdminDocumentItem]
    total: int
    offset: int
    limit: int
    has_more: bool

class DocumentDeleteResponse(BaseModel):
    document_id: UUID
    deleted_chunks: int